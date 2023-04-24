

# 介绍

一个 Python 项目，使用 OpenAI API 和群晖 Synology Chat 套件搭建了一个聊天机器人，同时整合了 ChatGPT-3.5 文本语言模型和 Edits 图片生成模型，并具备即时在本地运行 Python 代码和 Bash 命令的能力 —— *it is more than ChatGPT*.

它首先是一个 ChatGPT-3.5 的套壳；但同时，用户还可以：

1. 向它发送 Python 代码、Bash 命令，它会根据用户的输入生成回复，并执行其中的 Python 代码和 Bash 命令；

2. 向它发送图片描述等信息，它可以根据用户的图片描述生成图片；

3. 可调用一众搜索引擎（Google, Bing, Baidu, DuckDuckGo）搜索实时信息回答问题。

## 功能说明

1. `basicBot`和`talentBot`的区别及使用说明（Docker 版本使用`talentBot`）：
    
    1. `talentBot`同时基于 OpenAI 的 ChatGPT-3.5 文本语言模型和 Edits 的图片生成 AI 模型，并整合了即时在本地运行 Python 代码和 Bash 命令的能力。用户可以向机器人发送 Python 代码、Bash 命令、图片描述等信息，机器人会根据用户的输入生成回复，并执行其中的 Python 代码和 Bash 命令。机器人还可以根据用户的图片描述生成图片，并将图片发送给用户。具体使用说明：

        - 默认会调用 ChatGPT-3.5 进行答复 。
    
        - 以下关键词将引导机器人生成图片：`图片：`，`生成图片：`，或 `img:`；后面跟着的文本会被视为图片描述传给图片生成模型 Edits，生成图片。

        - 以下关键词引导机器人在本地运行 Python 代码：`python:` 或 `py:` ；后面跟着的文本会被视为 Python 代码，并被机器人在本地执行。

        - 以下关键词引导机器人在本地运行 Bash 命令：`bash:` 或 `b:` ；后面跟着的文本会被视为 Bash 命令，并被机器人在本地执行。
    
        - 具备使用搜索引擎（Google, Bing, Baidu, DuckDuckGo）搜索最新网络信息回答问题的能力，用关键词`bb`或`gg`开头即可实时搜索网络信息（`bb`或`gg`是一样的，默认都是会同时使用DuckDuckGo, Bing和Google逐一搜索一遍）。

    2. `basicBot`只具备上述`talentBot`的第一项功能，任何和`basicBot.py`的对话都传给 ChatGPT-3.5 生成答复，`basicBot`已经很久没更新了，未来可能只会删去，只保留`talentBot`。

    3. 目前 basicBot 和 talentBot 共用同一个 settings.py 文件，所以在同一个文件夹中两者只能同时运行其一，但其实只要再另建一个文件夹重新复制配置一遍所有文件，就能同时运行两个或者多个机器人。

2. 默认启用 stream 方法来传回 ChatGPT 的回复，即当 GPT 的回复有好几个小段落时，不需要等待所有段落都生成结束以后才把整个回复发送回群晖 Chat 的聊天窗口，而是会在每一个新的小段生成结束时就即刻发送回群晖 Chat。这样可以大大减少等待回复的时间。注意：如果要让 gpt 生成代码，并实时执行，记得在settings.py中关闭stream回传方法，即设置为`stream=False`。

3. 加入把非中文回复翻译成中文的功能，该功能会用到 DeepL 的 api: https://www.deepl.com/docs-api 。若要启用此功能，则需要在 DeepL官网上申请一个免费 api，替换`settings.py`中的`dl_key`，并设置`tranlsate_to_chinese=True`。

4. 要使用 Bing 和 Google 搜索最新网络信息以回答问题，你需要申请以下两个免费 api key：

    1. 按照这个官方网页的方法申请 Bing（必应搜索）的 API key: <https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview>，申请到的 key 填到`settings.py`最后的`your_key_for_Bing_search`处。

    2. 使用 google 需要在这个网上也注册申请一个key：<https://serpapi.com/>，申请到的 key 填到`settings.py`最后的`your_serpapi_key_for_google_search`处。




## 使用方法

### 1. 在<https://platform.openai.com/account/api-keys>申请 OpenAI API 密钥。

### 2. 群晖 Chat 客户端按照以下步骤添加聊天机器人：

（1） 用有管理员权限的账户登录 Synology Chat。

（2） 点击右上角你的头像，在菜单中选择「整合」(Integration)，点击「机器人」(Bots)。

（3） 点击「+ 创建」按钮，然后选择「创建新机器人」。

（4） 为你的机器人输入名称（例如：ChatGPT机器人）。点击「创建」。

（5） 在创建的机器人详情页面，找到「传出 Webhook」部分，将 Webhook URL 设置为你在代码中设置的 URL（即 `http://your_server_ip:PORT/webhook`， 其中 `your_server_ip` 应该是运行上述代码的机器的 IP 地址，`PORT`为你接下来在`settings.py`设置的端口号，默认 5008）。

（6） 在机器人详情页面的「传入 Webhook」部分，将生成一个 Webhook URL 和一个 Token，记录下这些值，按照下面第 3 步修改 `settings.py`中的`INCOMING_WEBHOOK_URL`和`OUTGOING_WEBHOOK_TOKEN`。

（7） 最后点击「确认」（OK）保存。

### 3. 使用Docker进行部署
#### 示例

```
docker run -d --name synobot \
-p 5008:5008 \
-e OPENAI_API_KEY="YOUR_OPENAI_API_KEY" \
-e INCOMING_WEBHOOK_URL="YOUR_INCOMING_WEBHOOK_URL" \
-e WEBHOOK_TOKEN="YOUR_WEBHOOK_TOKEN" \
xueheng/synogpt:latest
```

#### 所有Docker环境参数说明

| 变量名 | 描述                               | 默认值                                                                                   | 必填 |
| --- |----------------------------------|---------------------------------------------------------------------------------------| --- |
| `OPENAI_API_KEY` | 你的 OpenAI API 密钥                 | 无                                                                                     | 是 |
| `INCOMING_WEBHOOK_URL` | Synology Chat 机器人的传入 Webhook URL | 无                                                                                     | 是 |
| `WEBHOOK_TOKEN` | Synology Chat 机器人的传出 Webhook 令牌  | 无                                                                                     | 是 |
| `SERVER_IP` | 运行脚本的服务器 IP 地址                   | 127.0.0.1                                                                             | 否 |                                                                             | 否 |
| `system_prompt` | 聊天机器人的角色                         | '你是全能君，一名智能助手。你的使命是尽可能地用详尽的、温暖的、友善的话语帮助我和我的家人，在各种方面提供帮助和支持。无论我需要什么帮助或建议，你都会尽力提供详尽信息。' | 否 |
| `max_conversation_length` | 对话历史记录次数长度                        | 10                                                                                    | 否 |
| `max_time_gap` | 启动新对话的最大空闲时间间隔                   | 15                                                                                    | 否 |
| `temperature` | OpenAI API 的一个参数，控制生成文本的随机性。     | 0.5                                                                                   | 否 |
| `stream` | 使用stream方法传回 GPT 答复              | True                                                                                  | 否 |
| `image_size` | 使用 ai 生成图像时的图像大小                 | 'medium'                                                                              | 否 |
| `translate_to_chinese` | 是否将非中文文本翻译为中文（必须和下面的Deepl_api_key配合使用）  | False                                                                                 | 否 |
| `Deepl_api_key` | DeepL API 密钥                     | None                                                                                  | 否 |
| `bing_key` | Bing API 密钥                      | None                                                                | 否 |
| `serpapi_key` | SerpApi 密钥，以启用 google 搜索         | None                                                                | 否 |


### 4. 不使用 Docker 进行部署：


（1） 用你的 OpenAI API 密钥替换`settings.py`中的`openai.api_key`：
    

```python
openai_api_key = "your_api_key_here"
```
    
（2） 更改`settings.py`中的其他设置：

```
# Replace with your Synology Chat bot details
INCOMING_WEBHOOK_URL = "your_INCOMING_WEBHOOK_URL"
OUTGOING_WEBHOOK_TOKEN = "your_OUTGOING_WEBHOOK_TOKEN"

# Your se   rver IP address；你运行本聊天机器人的服务器 ip，如果你就在同一台群晖上跑这个程序，那就是群晖的内网 ip；如果是另一台机子上运行，就是另一台机子的 ip
your_server_ip = 'your_server_ip'

# Port
PORT = 5008

# System prompt sets up the character of the chatbot; change it if you want
system_prompt = '''你是全能君，一名智能助手。你的使命是尽可能地用详尽的、温暖的、友善的话语帮助我和我的家人，在各种方面提供帮助和支持。无论我需要什么帮助或建议，你都会尽力提供详尽信息。'''


# Set maximum conversation exchanges or idle time gap to start a new conversatoin
max_conversation_length = 20 
max_time_gap = 15 # minutes

# 默认启用 stream 方法；如果要让 gpt 生成代码，需要关闭 stream 功能
stream=True

# get your free bing search api key here: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
bing_key = "your_key_for_Bing_search" 

# get your free serpapi_key for using Google here: https://serpapi.com/
serpapi_key = "your_serpapi_key_for_google_search"


# 若要使用翻译功能，此处改为 True，并且需要申请一个DeepL的 api key：https://www.deepl.com/docs-api
translate_to_chinese = False # True or False; 
                         # if True, the bot will send chinese translation for any non-chinese gpt response
                         # 如果设置为 True，必须提供下面的 dl_key，否则会报错
dl_key = None # the translation uses the DeepL api; hence an deepl api key is required; 
              # then change this varaible to something like: dl_key = "xxx-xxx-xxx-xxx-xxxx:fx"

```         
    
（3）  安装所需的库：

在bash shell中运行：

```bash
pip install -r requirements.txt 
```

（4）  运行 Python 文件：

在bash shell中运行`basicBot`：

```
python basicBot.py
```

使用`talentBot`时先在`talentBot.py`所在文件夹新创建一个名为`static`的文件夹，然后运行：

```
python talentBot.py
```
    

（5） 在 Synology Chat 中与机器人进行对话。如果运行的是`basicBot.py`，那么任何你的输入，机器人都将使用OpenAI的 gpt-3.5-turbo 模型生成回复。关于`talentBot.py`的使用请参考前述更新说明。


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Xueheng-Li/SynologyChatbotGPT&type=Date)](https://star-history.com/#Xueheng-Li/SynologyChatbotGPT&Date)

注意事项
----

*   请确保你的 OpenAI API 密钥和 Synology Chat 机器人详细信息已正确填写。
    
*   确保你的服务器可以访问互联网，以便与 OpenAI API 进行通信。
    
*   本示例代码为了简化展示而直接在全局范围内设置了密钥和 URL。在实际生产环境中，你可能需要使用环境变量或配置文件来存储这些敏感信息。
    
*   请注意，向 OpenAI API 发送请求可能会产生费用。根据你的 API 使用情况，费用可能有所不同。请参阅 OpenAI 的[定价页面](https://openai.com/pricing)了解详细信息。
    
*   本代码的对话历史存储在内存中。在实际生产环境中，你可能需要使用持久存储（例如数据库）来存储对话历史。
    
*   本示例代码中未实现对输入和输出的过滤和检查。在实际应用中，请确保对输入进行验证和过滤，以防止潜在的安全问题。
    
