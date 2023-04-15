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
# from webgpt import *

from urllib.parse import quote

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

    headers = {
        "Content-Type": "application/json"
    }

    if image_filename:
        image_url = f"http://{your_server_ip}:{port}/image/{image_filename}"
        message_payload["file_url"] = image_url

    if image_url:
        message_payload["file_url"] = image_url

    payload = "payload=" + quote(json.dumps(message_payload))

    try:
        response = requests.post(INCOMING_WEBHOOK_URL, data=payload)
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


def generate_gpt_response(chat_history, stream=False, temperature=0.5):
    print(f"messages_to_gpt: {chat_history}")
    # get gpt response
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=chat_history,
        temperature=temperature,
        stream=stream,
    )
    if stream is False:
        return response['choices'][0]['message']['content']
    else:
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


def llama_process(keywords, index=None, reindex=False, file_source=[],  user_id=None):
    if os.path.exists("./index") is False:
        os.mkdir("./index")

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
        keywords,
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
else:
    translator = None


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


# This detect_channel function takes a message text as input and checks if it starts with specific keywords to determine which channel (python, bash, image, or gpt) the message belongs to, returning a dictionary containing the detected channel and the corresponding message content.
def separate_channel(message_text):
    keywords = {}
    keywords["python"] = ["python:", "py:", "python ", "py ", "Python:", "Python "]
    keywords["bash"] = ["bash:", "b:", "bash ", "Bash:"]
    keywords["image"] = ["图片:", "图片：", "图片 ", "img:", "Img:", "生成图片：", "生成图片:"]
    keywords["gpt"] = ["生成程序：", "程序生成：", "generator:", "Generator:", "ai:", "AI:", "gpt:", "Gpt:", "Ai:"]
    keywords["google"] = ["google:", "Google:", "谷歌:", "谷歌：", "搜索:", "搜索：", "search:", "Search:", "Search：",
                          "search：", "bb", "ss",
                          "gl", "gg"]

    results = {}
    for channel in ["python", "bash", "image", "gpt", "google"]:
        results[channel] = None
        for keyword in keywords[channel]:
            if message_text.startswith(keyword):
                results[channel] = message_text[len(keyword):].strip()
                break
    print(f"results = {results}")

    return results




class ChatBot:

    def __init__(self, user_id,
                 refresh_keywords=None,
                 max_conversation_length=10,
                 max_time_gap=15,
                 index=None,
                 system_prompt=system_prompt,
                 stream=False,
                 temperature=0.5,
                 translate=translate_to_chinese,
                 model="gpt4",
                 ):
        self.user_id = user_id
        self.chat_history = [{"role": "system", "content": system_prompt}]
        self.last_timestamp = int(time.time())
        if index == None:
            self.index = GPTSimpleVectorIndex([])
        else:
            self.index = index
        if refresh_keywords is None:
            self.refresh_keywords = ["new", "refresh", "00", "restart", "刷新", "新话题", "退下", "结束", "over"]
        else:
            self.refresh_keywords = refresh_keywords
        self.max_conversation_length = max_conversation_length
        self.max_time_gap = max_time_gap
        self.stream = stream
        self.message = ""
        self.temperature = temperature
        self.translate = translate
        self.system_prompt = system_prompt
        self.model = model
        self.gpt4 = None
        if self.model == "gpt4" or self.model == "gpt-4":
            self.gpt4 = WebGPT(model="gpt-4")
            try:
                self.gpt4.start_session(system_prompt=self.system_prompt)
                self.stream = False
            except Exception as e:
                print(f"Error: {e}")
                self.gpt4 = None
                self.model = "gpt3"
                self.stream = True


    def process(self, message,
                num_search_results=10,
                ):

        # update the latest user message
        self.message = message

        # Check for refresh_prompt input to start a new conversation
        if self.message.strip().lower() in self.refresh_keywords:
            send_back_message(self.user_id, "好的，开启一下新话题。")
            self.chat_history = self.chat_history[0:1]
            self.index = GPTSimpleVectorIndex([])
            self.last_timestamp = int(time.time())
            if self.model == "gpt4":
                self.gpt4.start_session(system_prompt=self.system_prompt)
            return "----------------------------"

        # Check if the conversation has been idle for 30 minutes (1800 seconds)
        if int(time.time()) - self.last_timestamp >= max_time_gap * 60:
            self.chat_history = self.chat_history[0:1]
            self.index = GPTSimpleVectorIndex([])

        # Truncate conversation history if it exceeds the maximum length
        if len(self.chat_history) > max_conversation_length:
            self.chat_history = self.chat_history[-max_conversation_length:]

        self.chat_history.append({"role": "user", "content": self.message})

        # check and execute python code
        code_results = separate_channel(self.message)
        if code_results["python"]:
            print("python code found")
            send_back_message(self.user_id, f"Python input: \n```{code_results['python']}``` ")
            code_output = capture_python_output(code_results["python"])
            send_back_message(self.user_id, f"Output: \n```{code_output}```")
            self.chat_history.append({
                "role": "assistant",
                "content": f"Python input: \n```{code_results['python']}``` " + f"Output: \n```{code_output}```"
            })

        elif code_results["bash"]:
            print("bash code found")
            send_back_message(self.user_id, f"Bash input: \n```{code_results['bash']}``` ")
            code_output = capture_bash_output(code_results["bash"])
            send_back_message(self.user_id, f"Output: \n```{code_output}```")
            self.chat_history.append({
                "role": "assistant",
                "content": f"Bash input: \n```{code_results['bash']}``` " + f"Output: \n```{code_output}```"
            })

        elif code_results["image"]:
            print("image description found")
            text_description = code_results["image"]
            send_back_message(self.user_id, f"收到👌🏻我会按你要求生成图片：{text_description}")
            img_filename = generate_img_from_openai(text_description, user_id=self.user_id)
            print(f"img_filename = {img_filename}")
            send_back_message(self.user_id, text_description, image_filename=img_filename)
            self.chat_history.append({
                "role": "assistant",
                "content": f"收到👌🏻我会按你要求生成图片：{text_description}. [An image link here]"
            })

        elif code_results["google"]:
            question = code_results["google"]
            print(f"Search request found: {question}")
            self.search(
                keywords=question,
                num_results=num_search_results,
                engines=["ddg", "bing", "google"])

        else:
            send_back_message(self.user_id, "...")
            if self.gpt4 is not None:
                print(f"Sending message to gpt4: {self.message}")
                gpt_response = self.gpt4.send_message(self.message)
                print(f"Got response from gpt4: {gpt_response}")
            else:
                gpt_response = generate_gpt_response(
                    chat_history=self.chat_history,
                    stream=self.stream,
                    temperature=self.temperature,
                )

            print("Got gpt response")
            if self.stream:
                text = []
                whole_text = []
                for r in gpt_response:
                    # print(r.choices[0]["delta"])
                    if "content" in r.choices[0]["delta"]:
                        word = r.choices[0]["delta"]["content"]
                        text.append(word)
                        whole_text.append(word)
                        # Check if the current output ends with \n
                        if re.search(r'[\n]', word[-1]):
                            sentence = ''.join(text).strip().replace("\n", "")
                            send_stream(self.user_id, sentence)
                            text = []
                text = ''.join(text)
                if len(text) > 0:
                    send(self.user_id, text, stream=self.stream)
                response_text = ''.join(whole_text)
            else:
                response_text = gpt_response
                if re.findall(r"```python(.*?)```", response_text, re.DOTALL):
                    print(f"Original response: {response_text}\n")
                    response_text = modify_response_to_include_code_output(response_text)
                    print(f"With code output: {response_text}")
                send(self.user_id, response_text, stream=False)

            self.chat_history.append({"role": "assistant", "content": response_text})

            if is_chinese(response_text) is False and self.translate:
                print("Translating...")
                try:
                    response_text = translate_to_CN(response_text)
                    print(f"Translated gpt_response = {response_text}")
                    send(self.user_id, f"翻译:\n\n{response_text}", stream=self.stream)
                except Exception as e:
                    print(f"Error in translation: {e}")

        # update timestamp
        self.last_timestamp = int(time.time())

        return "Message processed", 200


    def search(self,
               keywords=None,
               num_results=10,
               engines=["ddg", "bing", "google", "baidu"]):

        if keywords is None:
            keywords = self.message
        print(f"Search keywords: {keywords}")
        print("Searching...")
        send_back_message(self.user_id, f"...")

        results_list = []
        if "ddg" in engines:
            try:
                ddg_results = my_ddg(keywords, n=num_results)
                results_list.append(ddg_results)
                send_back_message(self.user_id, f"ddg: {len(ddg_results)}")
            except Exception as e:
                print(f"Error: {e}; ddg_results = {ddg_results}")
        if "bing" in engines:
            try:
                bing_results = my_bing(self.message, n=num_results)
                results_list.append(bing_results)
                send_back_message(self.user_id, f"bing: {len(bing_results)}")
            except Exception as e:
                print(f"Error: {e}; bing_results = {bing_results}")
        if "google" in engines:
            try:
                google_results = my_google(keywords, n=num_results)
                results_list.append(google_results)
                send_back_message(self.user_id, f"google: {len(google_results)}")
            except Exception as e:
                print(f"Error: {e}; google_results = {google_results}")
        if "baidu" in engines:
            try:
                baidu_results = my_baidu(keywords, n=num_results)
                results_list.append(baidu_results)
                send_back_message(self.user_id, f"baidu: {baidu_results}")
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

        prompt_input = replace_today(PROMPT_TEMPLATE).replace("{context_str}", results_text).replace("{query_str}", keywords)

        if len(prompt_input) <= 4000:

            gpt_response = generate_gpt_response(
                chat_history=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt_input}
                ],
                stream=self.stream,
                temperature=self.temperature,
            )
            print("Got gpt response")
            if self.stream:
                text = []
                whole_text = []
                for r in gpt_response:
                    # print(r.choices[0]["delta"])
                    if "content" in r.choices[0]["delta"]:
                        word = r.choices[0]["delta"]["content"]
                        text.append(word)
                        whole_text.append(word)
                        # Check if the current output ends with \n
                        if re.search(r'[\n]', word[-1]):
                            sentence = ''.join(text).strip().replace("\n", "")
                            send_stream(self.user_id, sentence)
                            text = []
                text = ''.join(text)
                if len(text) > 0:
                    send(self.user_id, text, stream=self.stream)
                answer = ''.join(whole_text)
            else:
                answer = gpt_response
                print(f"Original response: {answer}\n")
                if re.findall(r"```python(.*?)```", answer, re.DOTALL):
                    answer = modify_response_to_include_code_output(answer)
                    print(f"With code output: {answer}")
                send(self.user_id, answer, stream=self.stream)

        else:

            results_text += "# Conversation history:\n\n"
            for item in self.chat_history:
                results_text += f"{item['role']}: {item['content']}\n"

            print(f"Search finished.")

            context_dir = "searchResults"
            if os.path.exists(context_dir) is False:
                os.mkdir(context_dir)
            print(f"Saving search results...")
            search_results_name = sha1sum(results_text)
            with open(f'{context_dir}/{search_results_name}.txt', 'w') as f:
                f.write(results_text)
            print(f"Saved to search results to {context_dir}/{search_results_name}.txt")
            context_files = [f"{context_dir}/{search_results_name}.txt"]

            try:
                answer, self.index = llama_process(keywords,
                                                   file_source=context_files,
                                                   index=self.index,
                                                   user_id=self.user_id)
                with open('output.txt', 'w') as f:
                    f.write(str(answer).strip())
                # return answer
            except Exception as e:
                print(f"Error: Could not summarize content. - {e}")
                # return "Error: No answer provided."

            if answer is None:
                answer = "Error: No answer provided."
            print(f"original answer = {answer}")
            send(self.user_id, answer, stream=self.stream)


        self.chat_history.append({
            "role": "assistant",
            "content": answer
        })

        print(self.chat_history)

        if is_chinese(answer) is False and self.translate:
            print("Translating...")
            try:
                answer_cn = translate_to_CN(answer)
                print(f"Translated gpt_response = {answer_cn}")
                send(self.user_id, f"翻译:\n{answer_cn}", stream=self.stream)
            except Exception as e:
                print(f"Error in translation: {e}")





