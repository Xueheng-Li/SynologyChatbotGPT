import os

def get_from_env(key:str,default_value:str)->str:
    if key in os.environ and isinstance(os.environ[key],str) and len(os.environ[key]) > 0:
        return os.environ[key]
    else :
        return default_value

# Replace with your OpenAI API key
openai_api_key = get_from_env("openai_api_key", "your_openai_api_key")

# example "https://oa.api2d.net/v1" or "NULL"
openai_api_proxy = "NULL" 

# Replace with your Synology Chat bot details
INCOMING_WEBHOOK_URL = get_from_env("INCOMING_WEBHOOK_URL", "your_INCOMING_WEBHOOK_URL")
OUTGOING_WEBHOOK_TOKEN = get_from_env("OUTGOING_WEBHOOK_TOKEN", "your_OUTGOING_WEBHOOK_TOKEN")


# Your server IP address where you run this bot (more explicitly, the ip of the server where you put this script)
your_server_ip = 'your_server_ip'


# Port
PORT = 5008


# This system prompt sets up the character of the chatbot; change it if you want
system_prompt = '''你是全能君，一名智能助手。你的使命是尽可能地用详尽的、温暖的、友善的话语帮助我和我的家人，在各种方面提供帮助和支持。无论我需要什么帮助或建议，你都会尽力提供详尽信息。'''


# Set maximum conversation exchanges or idle time gap to start a new conversatoin
max_conversation_length = 20
max_time_gap = 15 # minutes


# Set temperature -- a parameter in the OpenAI API that controls the randomness of the generated text. It is a floating-point value that ranges from 0 to 1. A higher value (e.g., 0.8) will result in more random and creative outputs, while a lower value (e.g., 0.2) will produce more focused and deterministic outputs. In this case, the temperature is set to 0.5, which provides a balance between creativity and determinism in the generated text.
temperature = 0.5


# Translate non-chinese text to chinese
translate_to_chinese = False # True or False;
                             # if True, the bot will send chinese translation for any non-chinese gpt response; default is False
                             # 如果设置为 True，必须提供下面的 dl_key，否则会报错
dl_key = None # the translation uses the DeepL api; hence an deepl api key is required;
              # apply one here: https://www.deepl.com/docs-api;
              # then change this varaible to something like: dl_key = "xxx-xxx-xxx-xxx-xxxx:fx"


# Using streaming chatgpt response, which will break gpt response into small paragraphs (using `\n` as separator) and send them one by one
stream = True # True or False



# Image size when using ai to generate image
image_size = get_from_env("image_size", "medium") # "small", "medium" or "large"


# Set the virtual Python environment path if you want the bot to run Python code -- ignore it if you don't know what it is.
# This variable is used to store the path to the virtual Python environment for the project. This virtual environment is where the project's dependencies are installed and managed, ensuring that they don't interfere with other projects or the system's global Python installation. By specifying the path to the virtual environment, the project can reference and activate the environment when needed, ensuring that the correct dependencies are used during execution.
venv_path = get_from_env("venv_path", "./venv")


PROMPT_TEMPLATE = """Web search context information is provided below.
---------------------
{context_str}
---------------------
Current date: {current_date}.
Using the provided web search context information, write a comprehensive reply to the given query.
Now, use the provided information to answer the following question: {query_str}
"""

bing_key = get_from_env("bing_key", "your_key_for_Bing_search") # get your free bing search api key here: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
serpapi_key = get_from_env("serpapi_key", "your_serpapi_key_for_google_search") # get your free key here: https://serpapi.com/
serpapi_endpoint = get_from_env("serpapi_endpoint", "https://serpapi.com/search")

print("****************************\nsettings is loaded:")
print(f'openai_api_key={openai_api_key}')
print(f'INCOMING_WEBHOOK_URL={INCOMING_WEBHOOK_URL}')
print(f'OUTGOING_WEBHOOK_TOKEN={OUTGOING_WEBHOOK_TOKEN}')
print(f'image_size={image_size}')
print(f'venv_path={venv_path}')
print(f'bing_key={bing_key}')
print(f'serpapi_key={serpapi_key}')
print(f'serpapi_endpoint={serpapi_endpoint}')
print("****************************\n")