import json, time
import requests
import openai
from flask import Flask, request
import io
import sys
import re
from contextlib import redirect_stdout
import subprocess
import importlib
import tempfile
import os
from flask import send_from_directory
from datetime import datetime
import ast
import astor
from settings import *


# Capture and Execute Python Code in GPT-3 Response
def capture_python_output(code, venv_path=venv_path):

    # The selected code modifies the input Python code to print the last expression in the code.
    code = modify_code_to_print_last_expression(code)
    
    output = io.StringIO()
    # Create a temporary file to store the code
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".py", delete=False) as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name
    with redirect_stdout(output):
        while True:
            try:
                # Activate virtual environment in the subprocess and execute the temporary file
                command = f"source {venv_path}/bin/activate; python3.8 {temp_file_path}"
                execution_output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT, executable="/bin/bash")
                print(execution_output, file=output)
                break
            except subprocess.CalledProcessError as cpe:
                error_output = cpe.output
                print(f"error_output = cpe.output: {error_output}")
                if "ModuleNotFoundError" in error_output:
                    missing_package = error_output.split()[-1]
                    print(f"missing_package = error_output.split()[-1]: {missing_package}")
                    try:
                        command = f"source {venv_path}/bin/activate; pip install {missing_package}"
                        execution_output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT, executable="/bin/bash")
                        break
                        # subprocess.check_call([f"{venv_path}/bin/pip", "install", missing_package])
                    except Exception as e:
                        result = f"Error1: {e}"
                        print(result, file=output)
                        break
                else:
                    result = f"Error2: {error_output}"
                    print(result, file=output)
                    break
            except Exception as e:
                result = f"Error3: {e}"
                print(result, file=output)
                break
    # Remove the temporary file
    os.remove(temp_file_path)
    execution_output = output.getvalue().strip()
    print(f"execution_output = {output.getvalue()}")
    # execution_output = output.getvalue()
    return execution_output


# Function takes Python code string as input, modifies it by wrapping the last non-empty expression with a print statement, and returns the modified code as a string.
def modify_code_to_print_last_expression(code):
    # Parse the code into an AST
    tree = ast.parse(code)

    # Find the last non-empty expression in the code
    last_expr = None
    for node in reversed(tree.body):
        if isinstance(node, ast.Expr):
            last_expr = node
            break

    # If a non-empty expression is found, wrap it with a print statement
    if last_expr:
        print_node = ast.Expr(value=ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[last_expr.value], keywords=[]))
        tree.body.remove(last_expr)
        tree.body.append(print_node)

    # Convert the modified AST back to code
    modified_code = astor.to_source(tree)
    return modified_code



def capture_bash_output(code):
    output = io.StringIO()
    try:
        execution_output = subprocess.check_output(code, shell=True, text=True, stderr=subprocess.STDOUT, executable="/bin/bash")
        print(execution_output, file=output)
    except subprocess.CalledProcessError as cpe:
        error_output = cpe.output
        print(f"Error 1: {error_output}")
    except Exception as e:
        result = f"Error 2: {e}"
        print(result, file=output)
    return output.getvalue().strip()


def download_image(url, save_path="static/img.png"):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(save_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)



# Sending Messages to Synology Chat
def send_back_message(user_id, response_text, image_filename=None, image_url=None, 
                      your_server_ip=your_server_ip, port=PORT, INCOMING_WEBHOOK_URL=INCOMING_WEBHOOK_URL):
                          
    message_payload = {
        'text': response_text,
        "user_ids": [int(user_id)]
    }

    if image_filename:
        image_url = f"http://{your_server_ip}:{port}/image/{image_filename}"
        message_payload["file_url"] = image_url

    if image_url:
        message_payload["file_url"] = image_url
    
    payload = 'payload=' + json.dumps(message_payload)

    try:
        response = requests.post(INCOMING_WEBHOOK_URL, payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to Synology Chat: {e}")
        return "Error sending message to Synology Chat", 500



# Take the orginal GPT-3 response text as input, extracts and executes any Python code blocks within it, 
# and replaces the code blocks with their respective outputs in the final response text:
def modify_response_to_include_code_output(response_text):
    python_blocks = re.findall(r"```python(.*?)```", response_text, re.DOTALL)
    print(f"python_blocks = {python_blocks}")
    if python_blocks:
        modified_response = re.sub(r"```python.*?```", "{{PYTHON_OUTPUT}}", response_text, flags=re.DOTALL)
        # modified_response = re.sub(r"```.*?```", "{{PYTHON_OUTPUT}}", modified_response, flags=re.DOTALL)
        output_list = []
        for python_code in python_blocks:
            python_code = python_code.strip()
            execution_output = capture_python_output(python_code)
            output_list.append(f"```\n{python_code}\n```\n运行结果：\n```\n{execution_output}\n```")
        response_with_output = modified_response.replace("{{PYTHON_OUTPUT}}", "{}").format(*output_list)
        return response_with_output
    else:
        return response_text

        

# A function generating an image using OpenAI's API based on the given text description and size, and returns the filename of the downloaded image.
def generate_img_from_openai(text_description, size=image_size, user_id=None):

    if size in ["small", "medium", "large"]:
        size = {"small": "256x256", "medium": "512x512", "large": "1024x1024"}[size]
    else:
        size = "256x256"
    
    print(f"text_description = {text_description}")
    
    try:
        response = openai.Image.create(
            prompt=text_description,
            n=1,
            size=size
            )
        image_url = response['data'][0]['url']
        print(f"image_url = {image_url}")
    except openai.error.OpenAIError as e:
        print(f"Error: {e.http_status}")
        print(f"Error: {e.error}")
        image_url = None
        
    if image_url:
        if user_id:
            send_back_message(user_id, "生成图片完成，正在下载…")
        try:
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{current_time}.png"
            download_image(image_url, "static/" + filename)
            print("Image downloaded successfully!")
            return filename
        except Exception as e:
            print(f"Error: {e}")
            return None
    else:
        return None