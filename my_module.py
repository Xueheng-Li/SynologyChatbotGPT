import openai
import io
import sys
import re
from contextlib import redirect_stdout
import subprocess
import importlib
import tempfile
import os
import ast
import astor
import deepl

import logging
from duckduckgo_search import ddg
import json
import time
import requests
import hashlib
from datetime import datetime
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from llama_index import (
    GPTSimpleVectorIndex,
    SimpleDirectoryReader,
    Document,
    LLMPredictor,
    PromptHelper,
    QuestionAnswerPrompt,
    RefinePrompt,
    download_loader
)

from langdetect import detect
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
                command = f"source {venv_path}/bin/activate; python {temp_file_path}"
                execution_output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT,
                                                           executable="/bin/bash")
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
                        execution_output = subprocess.check_output(command, shell=True, text=True,
                                                                   stderr=subprocess.STDOUT, executable="/bin/bash")
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
        print_node = ast.Expr(
            value=ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[last_expr.value], keywords=[]))
        tree.body.remove(last_expr)
        tree.body.append(print_node)

    # Convert the modified AST back to code
    modified_code = astor.to_source(tree)
    return modified_code


def capture_bash_output(code):
    output = io.StringIO()
    try:
        execution_output = subprocess.check_output(code, shell=True, text=True, stderr=subprocess.STDOUT,
                                                   executable="/bin/bash")
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
        "user_ids": [int(user_id)],
        "text": str(response_text)
    }

    if image_filename:
        image_url = f"http://{your_server_ip}:{port}/image/{image_filename}"
        message_payload["file_url"] = image_url

    if image_url:
        message_payload["file_url"] = image_url

    payload = "payload=" + json.dumps(message_payload)

    try:
        response = requests.post(INCOMING_WEBHOOK_URL, data=payload)
        # response = requests.post(INCOMING_WEBHOOK_URL, json=message_payload)
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


def generate_gpt_response(chat_history, user_id=None, stream=False):
    print(f"messages_to_gpt: {chat_history}")
    message = chat_history[-1]["content"]

    # get gpt response
    if stream is False:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=chat_history,
            temperature=temperature,
        )
        response_role = response['choices'][0]['message']['role']
        response_text = response['choices'][0]['message']['content']
        chat_history.append({"role": response_role, "content": response_text})
        return response_text
    else:
        response = openai.ChatCompletion.create(
             model='gpt-3.5-turbo',
             messages=chat_history,
             temperature=temperature,
             stream=True)
        return response


# Set your OpenAI API key
openai.api_key = openai_api_key
os.environ['OPENAI_API_KEY'] = openai_api_key


def my_ddg(q, n=5):
    search_results = ddg(q, max_results=n)
    results_list = []
    for r in search_results:
        results_list.append(f'{r["title"]} ({r["href"]}). {r["body"]}')
    print(f"ddg: {len(results_list)}")
    return results_list


# bing

def my_bing(q, n=5, key=bing_key):
    # assert key
    search_url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": key}
    params = {'q': q,
              # 'mkt': 'zh-CN',
              "answerCount": n,
              "count": n}
    response = requests.get(search_url, headers=headers, params=params)
    response.raise_for_status()
    search_results = response.json()
    search_results = search_results["webPages"]["value"]
    results_list = []
    for r in search_results:
        results_list.append(f'{r["name"]} ({r["url"]}). {r["snippet"]}. 获取时间（Parsed time）: {r["dateLastCrawled"]}')
    print(f"bing: {len(results_list)}")
    return results_list


def my_google(q, n=5, engine="google", key=serpapi_key, serpapi_endpoint=serpapi_endpoint):
    params = {
        "api_key": key,
        "engine": engine,
        "q": q,
        "num": n,
        "rn": n,
        # "hl": "zh-CN",
    }
    response = requests.get(serpapi_endpoint, params=params)
    response_json = response.json()
    search_results = response_json.get("organic_results", [])
    results_list = []
    for r in search_results:
        # print(r)
        try:
            results_list.append(f"{r['title']} ({r['link']}). {r['snippet']}")
        except Exception as e:
            print(e)
            continue
    print(f"{engine}: {len(results_list)}")
    return results_list


def my_baidu(q, n=5, engine="baidu", key=serpapi_key, serpapi_endpoint=serpapi_endpoint):
    params = {
        "api_key": key,
        "engine": engine,
        "q": q,
        "num": n,
        "rn": n,
        # "ct":2,
    }
    response = requests.get(serpapi_endpoint, params=params)
    response_json = response.json()
    search_results = response_json.get("organic_results", [])
    results_list = []
    for r in search_results:
        # print(r)
        try:
            results_list.append(f"{r['title']} ({r['link']}). {r['snippet']}. 获取时间（Parsed time）: {r['date']}")
        except Exception as e:
            print(e)
            continue
    print(f"{engine}: {len(results_list)}")
    return results_list


def replace_today(prompt):
    today = datetime.today().strftime("%Y-%m-%d")
    return prompt.replace("{current_date}", today)


def get_documents(file_src):
    documents = []
    index_name = ""
    logging.debug("Loading documents...")
    logging.debug(f"file_src: {file_src}")
    for file in file_src:
        logging.debug(f"file: {file}")
        index_name += file
        if os.path.splitext(file)[1] == ".pdf":
            logging.debug("Loading PDF...")
            CJKPDFReader = download_loader("CJKPDFReader")
            loader = CJKPDFReader()
            documents += loader.load_data(file=file)
        elif os.path.splitext(file)[1] == ".docx":
            logging.debug("Loading DOCX...")
            DocxReader = download_loader("DocxReader")
            loader = DocxReader()
            documents += loader.load_data(file=file)
        elif os.path.splitext(file)[1] == ".epub":
            logging.debug("Loading EPUB...")
            EpubReader = download_loader("EpubReader")
            loader = EpubReader()
            documents += loader.load_data(file=file)
        else:
            logging.debug("Loading text file...")
            with open(file, "r", encoding="utf-8") as f:
                text = add_space(f.read())
                documents += [Document(text)]
    index_name = sha1sum(index_name)
    return documents, index_name


def add_space(text):
    punctuations = {"，": "， ", "。": "。 ", "？": "？ ", "！": "！ ", "：": "： ", "；": "； "}
    for cn_punc, en_punc in punctuations.items():
        text = text.replace(cn_punc, en_punc)
    return text


def sha1sum(filename):
    sha1 = hashlib.sha1()
    sha1.update(filename.encode("utf-8"))
    return sha1.hexdigest()


def get_gpt_response(new_message, chat_history=None, system_prompt=chatbot_character):
    print(f"new message: {new_message}")
    if system_prompt is None:
        system_prompt = replace_today("You are a helpful assistant. Current date: {current_date}.")
    if chat_history:
        chat_history.append({"role": "user", "content": new_message})
    else:
        chat_history = [{"role": "user", "content": new_message}]
    print(f"chat history: {chat_history}")
    messages_to_gpt = [{"role": "system", "content": system_prompt}]
    messages_to_gpt.extend(chat_history)
    print(f"messages: {messages_to_gpt}")

    # get gpt response
    send_text = " ".join(
        [m["content"] for m in messages_to_gpt]
    )
    print(f"Token used for messages_to_gpt: {len(send_text)}")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages_to_gpt,
        temperature=0.3,
    )

    if response['choices'][0]['finish_reason'] == "stop":
        response_text = response['choices'][0]['message']['content']
        chat_history.append(
            {"role": "bot", "content": response_text}
        )
        print(f"Token used for completion: {len(response_text)}")
    else:
        chat_history.append(
            {"role": "bot", "content": f"error: stop reason - {response['choices'][0]['finish_reason']}"}
        )
    print(f"response: {response_text}")
    return response_text, chat_history


def llama_process(question, keywords, reindex=False, file_source=[], index=None, user_id=None):
    if os.path.exists("./index") is False:
        os.mkdir("./index")
    if os.path.exists("./searchResults") is False:
        os.mkdir("./searchResults")

    llm_predictor = LLMPredictor(
        llm=ChatOpenAI(
            temperature=0.5,
            # messages=[{"role": "system", "content": chatbot_character}],
            # max_tokens=4096,
            # max_input_size=4096,
            # model_name="gpt-3.5-turbo-0301",
            model_name="gpt-3.5-turbo"
        )
    )

    # prompt_helper = PromptHelper(
    #     max_input_size=4096,
    #     max_chunk_overlap=20,
    #     num_output=1,
    #     embedding_limit=None,
    #     chunk_size_limit=600,
    #     separator=" ",
    # )

    context_dir = "searchResults"
    if len(file_source) == 0:
        files = [f"{context_dir}/{f}" for f in os.listdir(context_dir) if keywords in f]
    else:
        files = file_source

    if len(files) == 0:
        print(f"No files found in {context_dir} with keywords {keywords}")
        return None
    else:
        print(f"Found files in {context_dir}: {files}")
        documents, index_name = get_documents(file_src=files)
        print(f"Loaded documents: {len(documents)}")
        if os.path.exists(f"./index/{index_name}.json") and reindex is False:
            logging.info("找到了缓存的索引文件，加载中……")
            index = GPTSimpleVectorIndex.load_from_disk(f"./index/{index_name}.json")
        else:
            current_time = time.time()
            print("Indexing...")
            if user_id:
                send_back_message(user_id, "indexing...")
            if index is None:
                index = GPTSimpleVectorIndex(
                    documents,
                    # prompt_helper=prompt_helper
                )
            else:
                for doc in documents:
                    index.insert(doc)
            print(f"Indexing finished. Time used: {time.time() - current_time} seconds.")
            index.save_to_disk(f"./index/{index_name}.json")
            print(f"Index saved to 'index/{index_name}.json'.")

    # Querying the index
    print("Querying...")
    if user_id:
        send_back_message(user_id, "querying...")
    qa_prompt = QuestionAnswerPrompt(replace_today(PROMPT_TEMPLATE))
    response = index.query(
        question,
        llm_predictor=llm_predictor,
        similarity_top_k=1,
        text_qa_template=qa_prompt,
        # response_mode="compact" # or "tree_summarize"
        mode="embedding"  # or "default"
    )
    print(f"type of index.query response: {type(response)}")
    response_text = response.response
    print(f"type of response.response: {type(response_text)}")
    print("Query finished.")
    print(f"Response from llama: {response_text}")
    return response_text, index


def my_web_search(question=None, predict_keywords=False, max_keywords=5, max_web_page=0, num_results=8,
                  index=None, user_id=None, chat_history=None, engines=["ddg", "bing", "google", "baidu"]):
    print(f"Question: {question}")
    if predict_keywords:
        prompt = []
        prompt = f'''Return the {max_keywords} most relevant keywords for doing a Google search to answer the query: {question}
        If the question is in Chinese, return Chinese keywords; otherwise, return English keywords.
        Only return the keywords separated by spaces. Don't include any other text or punctuation. Keywords:'''
        keywords, chat_history = get_gpt_response(prompt, chat_history=chat_history)
    else:
        keywords = question

    print("Web searching...")
    results_list = []
    if "ddg" in engines:
        try:
            ddg_results = my_ddg(keywords, n=num_results)
            results_list.append(ddg_results)
            if user_id:
                send_back_message(user_id, f"ddg: {len(ddg_results)}")
        except Exception as e:
            print(f"Error: {e}")
    if "bing" in engines:
        try:
            bing_results = my_bing(keywords, n=num_results)
            results_list.append(bing_results)
            if user_id:
                send_back_message(user_id, f"bing: {len(bing_results)}")
        except Exception as e:
            print(f"Error: {e}")
    if "google" in engines:
        try:
            google_results = my_google(keywords, n=num_results)
            results_list.append(google_results)
            if user_id:
                send_back_message(user_id, f"google: {len(google_results)}")
        except Exception as e:
            print(f"Error: {e}")
    if "baidu" in engines:
        try:
            baidu_results = my_baidu(keywords, n=num_results)
            results_list.append(baidu_results)
            if user_id:
                send_back_message(user_id, f"baidu: {baidu_results}")
        except Exception as e:
            print(f"Error: {e}")
    results_text = "# Web search results:\n\n"
    i = 1
    for results in results_list:
        try:
            for r in results:
                results_text += f"{i}. {r}\n\n"
                i += 1
        except Exception as e:
            print(f"Error: {e}")
            continue
    if chat_history:
        results_text += "# Conversation history:\n\n"
        for item in chat_history:
            results_text += f"{item['role']}: {item['content']}\n"

    print(f"Search finished.")

    # web_results = []
    # idx = 0
    context_dir = "searchResults"
    print(f"Saving Bing search results...")
    # bing_results_name = sha1sum(f"bing-{keywords}-{datetime.today().strftime('%Y-%m-%d')}")
    bing_results_name = sha1sum(results_text)
    with open(f'{context_dir}/{bing_results_name}.txt', 'w') as f:
        f.write(results_text)
    print(f"Saved to Bing search results to {context_dir}/{bing_results_name}.txt")
    context_files = [f"{context_dir}/{bing_results_name}.txt"]

    if index is None:
        index = GPTSimpleVectorIndex([])

    try:
        answer, index = llama_process(question, keywords, file_source=context_files, index=index, user_id=user_id)
        with open('output.txt', 'w') as f:
            f.write(str(answer).strip())
        return answer, index
    except Exception as e:
        print(f"Error: Could not summarize content. - {e}")
        return "Error: No answer provided.", index


# detect main language of a text
def is_chinese(text):
    try:
        lang = detect(text)
        if lang.startswith('zh'):
            print("The text is primarily in Chinese.")
            return True
        else:
            return False
    except Exception as e:
        print(f"Error: {e}")
        return None


# prepare deepL translator
if dl_key is not None:
    translator = deepl.Translator(dl_key)


def translate_to_CN(text):
    if dl_key is not None:
        return translator.translate_text(text, target_lang="ZH").text
    else:
        return text



def translate_to_EN(text):
    if dl_key is not None:
        return translator.translate_text(text, target_lang="EN-US").text
    else:
        return text


def detect_and_translate(text):
    if is_chinese(text) is False:
        try:
            return translate_to_CN(text)
        except Exception as e:
            print(f"Error: {e}")
            return text
    else:
        return text


def send_stream(user_id, text, cut="\n"):
    sentences = text.split(cut)
    for s in sentences:
        if len(s) > 0:
            send_back_message(user_id, s)



def send(user_id, text, stream=False, cut="\n"):
    if stream:
        send_stream(user_id, text, cut=cut)
    else:
        send_back_message(user_id, text)
