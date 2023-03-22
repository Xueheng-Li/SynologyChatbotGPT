

# 介绍

一个 Python script，使用 OpenAI API 和群晖 Synology Chat 套件搭建了一个基于 ChatGPT-3.5 的聊天机器人。

重要说明：
1、对于版本 v0.1，你只需下载和更改 gptbot.py 中的参数（`openai_api_key`，`INCOMING_WEBHOOK_URL`，`OUTGOING_WEBHOOK_TOKEN`等）即可。
2、对于 v0.2 及以上的版本，所有 .py 结尾的文件都需要拉取下载到本地，然后所有需要你修改的参数（`openai_api_key`，`INCOMING_WEBHOOK_URL`，`OUTGOING_WEBHOOK_TOKEN`等）都保存在`settings.py`中，你只需要修改这个文档中的相关参数即可。

使用说明
----

1.  在 Synology Chat 中请按照以下步骤添加聊天机器人：

    - 用有管理员权限的账户登录 Synology Chat。

    - 点击右上角你的头像，在菜单中选择「整合」(Integration)，点击「机器人」(Bots)。

    - 点击「+ 创建」按钮，然后选择「创建新机器人」。

    - 为您的机器人输入名称（例如：ChatGPT机器人）。点击「创建」。

    - 在创建的机器人详情页面，找到「传出 Webhook」部分，将 Webhook URL 设置为您在代码中设置的 URL（即 `http://your_server_ip:5005/webhook`， 其中 `your_server_ip` 应该是运行上述代码的机器的 IP 地址）。

    - 在机器人详情页面的「传入 Webhook」部分，将生成一个 Webhook URL 和一个 Token。请将这两个值复制并替换`gptchatbot.py`中相关变量：

    ```python
    INCOMING_WEBHOOK_URL = "your_incoming_webhook_url_here"
    OUTGOING_WEBHOOK_TOKEN = "your_outgoing_webhook_token_here"

    ```
    - 最后点击「确认」（OK）保存。

2. 在`https://platform.openai.com/account/api-keys`申请 OpenAI API 密钥，用你的 OpenAI API 密钥替换`gptchatbot.py`中的`openai.api_key`：
    

    ```python
    openai.api_key = "your_api_key_here"
    ```
    
3.  安装所需的库：

    在bash shell中运行：

    ```bash
    pip install openai requests flask
    ```
    或
    ```bash
    pip install -r requirements.txt 
    ```

4.  运行 Python 文件：

    在bash shell中运行：

    ```bash
    python gptchatbot.py
    ```

5. 在 Synology Chat 中与机器人进行对话。根据您的输入，机器人将使用OpenAI的 gpt-3.5-turbo 模型生成回复。



注意事项
----

*   请确保您的 OpenAI API 密钥和 Synology Chat 机器人详细信息已正确填写。
    
*   确保您的服务器可以访问互联网，以便与 OpenAI API 进行通信。
    
*   本示例代码为了简化展示而直接在全局范围内设置了密钥和 URL。在实际生产环境中，您可能需要使用环境变量或配置文件来存储这些敏感信息。
    
*   请注意，向 OpenAI API 发送请求可能会产生费用。根据您的 API 使用情况，费用可能有所不同。请参阅 OpenAI 的[定价页面](https://openai.com/pricing)了解详细信息。
    
*   在生产环境中部署聊天机器人时，请确保遵循最佳安全实践，例如使用 HTTPS、验证令牌等。
    
*   本代码的对话历史存储在内存中。在实际生产环境中，您可能需要使用持久存储（例如数据库）来存储对话历史。
    
*   本示例代码中未实现对输入和输出的过滤和检查。在实际应用中，请确保对输入进行验证和过滤，以防止潜在的安全问题。
    

