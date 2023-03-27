import openai
import requests
from bs4 import BeautifulSoup
from googlesearch import search
import asyncio
import time, datetime
import logging

import os
from settings import *
import hashlib

from langchain.chat_models import ChatOpenAI
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


# Set your OpenAI API key
openai.api_key = openai_api_key
os.environ['OPENAI_API_KEY'] = openai_api_key



WEBSEARCH_PTOMPT_TEMPLATE = """\
Web search results:

{web_results}
Current date: {current_date}

Instructions: Using the provided web search results, write a comprehensive reply to the given query. Make sure to cite results using [[number](URL)] notation after the reference. If the provided search results refer to multiple subjects with the same name, write separate answers for each subject.
Query: {query}
Reply in 中文"""


PROMPT_TEMPLATE = """\
Context information is below.
---------------------
{context_str}
---------------------
Current date: {current_date}.
Using the provided context information, write a comprehensive reply to the given query.
Add a referece list after your answer, and make sure to cite results using [number] notation for each reference.
If the provided context information refer to multiple subjects with the same name, write separate answers for each subject.
Use prior knowledge only if the given context didn't provide enough information.
Answer the question: {query_str}
Reply in 中文
"""


def replace_today(prompt):
    today = datetime.datetime.today().strftime("%Y-%m-%d")
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



def get_gpt_response(new_message, chat_history=None, system_prompt=None):
    print(f"new message: {new_message}")
    if system_prompt is None:
        system_prompt = "You are a helpful assistant."
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
    print(f"Token used for messages_to_gpt: {len( send_text)}")
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


def llama_process(question, keywords, reindex=True, context_dir="searchResults", search_result_html=None):

    if os.path.exists("./index") is False:
        os.mkdir("./index")
    if os.path.exists("./searchResults") is False:
        os.mkdir("./searchResults")

    # Load the index from your saved index.json file
    index_file = f"index/{keywords}.json"

    llm_predictor = LLMPredictor(
        llm=ChatOpenAI(
            temperature=0.3,
            model_name="gpt-3.5-turbo-0301"
        )
    )

    prompt_helper = PromptHelper(
        max_input_size=4000,
        max_chunk_overlap=20,
        num_output = 1,
        embedding_limit=None,
        chunk_size_limit=600,
        separator=" ",
    )

    files = [f"{context_dir}/{f}" for f in os.listdir(context_dir) if keywords in f]

    if len(files) == 0:
        print(f"No files found in {context_dir} with keywords {keywords}")
        return None
    else:
        documents, index_name = get_documents(file_src=files)
        if os.path.exists(f"./index/{index_name}.json") and reindex is False:
            logging.info("找到了缓存的索引文件，加载中……")
            return GPTSimpleVectorIndex.load_from_disk(f"./index/{index_name}.json")
        else:
            current_time = time.time()
            print("Indexing...")
            index = GPTSimpleVectorIndex(
                documents,
                llm_predictor=llm_predictor,
                prompt_helper=prompt_helper
            )
            print(f"Indexing finished. Time used: {time.time() - current_time} seconds.")
            index.save_to_disk(f"./index/{index_name}.json")
            print(f"Index saved to 'index/{index_name}.json'.")



    # Querying the index


    print("Querying...")
    qa_prompt = QuestionAnswerPrompt(replace_today(PROMPT_TEMPLATE))
    # rf_prompt = RefinePrompt(REFINE_TEMPLATE)
    response = index.query(
        question,
        # llm_predictor=llm_predictor,
        similarity_top_k=1,
        text_qa_template=qa_prompt,
        # refine_template=rf_prompt,
        # response_mode="compact"
    )
    print("Query finished.")
    print(f"Response from llama: {response}")
    return response


def my_web_search(question=None, num_keywords=3, max_doc=3, num_results=8):
    if question is None:
        question = input("Enter your question: ")
        if len(question) == 0:
            question = "罗列总结一下2022年都有什么科技大事。"
    print(f"Question: {question}")
    prompt = f'''Generate no more than {num_keywords} keywords for Google search to answer: {question}
    If the question is in Chinese, generate the keywords in Chinese. If the question is in English, generate the keywords in English.
    Just type the keywords separated by spaces. Don't include any other text or punctuation.'''
    keywords, chat_history = get_gpt_response(prompt)
    print("Searching Google...")
    google_results = search(keywords, num=num_results, start=1, stop=num_results)
    print(f"Search finished.")
    # urls = [url for url in google_results]
    web_results = []
    idx = 0
    for url in google_results:
        print(f"Getting: {url}")
        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.content, 'html.parser')
            print(f"{response.status_code} - {soup.title.string}")
            if response.status_code == 200:
                web_results.append(f'[{idx+1}]"{soup.title.string}"\nURL: {url}')
                with open(f'searchResults/{keywords}-{idx}.html', 'w') as f:
                    f.write(soup.prettify())
                print(f"Saved to searchResults/{keywords}-{idx}.html")
                idx += 1
                if idx >= max_doc:
                    break
        except:
            continue

    # summary = summarize_text(question, text)
    answer = llama_process(question, keywords)
    if not answer:
        print("Could not summarize content. Exiting.")
        return
    else:
        print(f"\nBest Answer:\n{answer}")
        with open('output.txt', 'w') as f:
            f.write(str(answer).strip())
        return answer


if __name__ == "__main__":
    my_web_search(num_keywords=3, max_doc_len=3)
