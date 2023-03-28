from flask import Flask, request
from flask import send_from_directory
from my_module import *
from settings import *
# from search import *


# Set up OpenAI API key
openai.api_key = openai_api_key

# In-memory conversation history storage
conversation_history = {}

index = GPTSimpleVectorIndex([])


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


# Processes incoming messages from Chat, generates a response using GPT-3, executes any Python code found in the response,
# and sends the modified response back to the user.
def process_synology_chat_message(event, refresh_keywords=None,
                                  max_conversation_length=max_conversation_length,
                                  max_time_gap=max_time_gap,
                                  index=index, max_web_page=0,
                                  num_search_results=5):

    print(f"event: {event}")

    if not event:
        return "Empty request body", 400

    else:

        if event.get('token') != OUTGOING_WEBHOOK_TOKEN:
            return "Invalid token"

        user_id = event.get('user_id')
        message = event.get('text')
        username = event.get('username')

        # Maintain conversation history
        if user_id not in conversation_history:
            conversation_history[user_id] = {"username": username,
                                             "messages": [{"role": "system", "content": chatbot_character}],
                                             "last_timestamp": int(time.time())}
        conversation_history[user_id]["messages"].append({"role": "user", "content": message})
        # Truncate conversation history if it exceeds the maximum length
        if len(conversation_history[user_id]["messages"]) > max_conversation_length:
            conversation_history[user_id]["messages"] = conversation_history[user_id]["messages"][
                                                            -max_conversation_length:]


        # Check for refresh_prompt input to start a new conversation
        if refresh_keywords is None:
            refresh_keywords = ["new", "refresh", "00", "restart", "刷新", "新话题", "退下", "结束", "over"]
        if len(message) > 0 and message.strip().lower() in refresh_keywords:
            send_back_message(user_id, "好的，开启一下新话题。")
            conversation_history[user_id]["messages"] = conversation_history[user_id]["messages"][0:1]
            index = GPTSimpleVectorIndex([])
            return "----------------------------"

        # Check if the conversation has been idle for 30 minutes (1800 seconds)
        if int(time.time()) - conversation_history[user_id]["last_timestamp"] >= max_time_gap * 60:
            conversation_history[user_id]["messages"] = conversation_history[user_id]["messages"][0:1]
            index = GPTSimpleVectorIndex([])

        # update timestamp
        conversation_history[user_id]["last_timestamp"] = int(time.time())

        # check and execute python code
        code_results = separate_channel(message)
        if code_results["python"]:
            print("python code found")
            send_back_message(user_id, f"Python input: \n```{code_results['python']}``` ")
            code_output = capture_python_output(code_results["python"])
            send_back_message(user_id, f"Output: \n```{code_output}```")
            conversation_history[user_id]["messages"].append({
                "role": "assistant",
                "content": f"Python input: \n```{code_results['python']}``` " + f"Output: \n```{code_output}```"
            })

        elif code_results["bash"]:
            print("bash code found")
            send_back_message(user_id, f"Bash input: \n```{code_results['bash']}``` ")
            code_output = capture_bash_output(code_results["bash"])
            send_back_message(user_id, f"Output: \n```{code_output}```")
            conversation_history[user_id]["messages"].append({
                "role": "assistant",
                "content": f"Bash input: \n```{code_results['bash']}``` " + f"Output: \n```{code_output}```"
            })

        elif code_results["image"]:
            print("image description found")
            text_description = code_results["image"]
            send_back_message(user_id, f"收到👌🏻我会按你要求生成图片：{text_description}")
            img_filename = generate_img_from_openai(text_description, user_id=user_id)
            print(f"img_filename = {img_filename}")
            send_back_message(user_id, text_description, image_filename=img_filename)
            conversation_history[user_id]["messages"].append({
                "role": "assistant",
                "content": f"收到👌🏻我会按你要求生成图片：{text_description}. [An image link here]"
            })

        elif code_results["google"]:
            search_keywords = code_results["google"]
            # send_back_message(user_id, "Binging...")
            print(f"Google search request found: {search_keywords}")
            answer, index = my_web_search(question=search_keywords, index=index,
                                          predict_keywords=False, max_keywords=5,
                                          max_web_page=max_web_page, num_results=num_search_results,
                                          user_id=user_id,
                                          chat_history=conversation_history[user_id]["messages"],
                                          engines=["ddg", "bing", "google"])
            # answer = str(answer).strip()
            print(f"answer = {answer}")
            send_back_message(user_id, response_text=answer)
            conversation_history[user_id]["messages"].append({
                "role": "assistant",
                "content": answer
            })
            print(conversation_history[user_id]["messages"])
        else:
            send_back_message(user_id, "...")
            conversation_history[user_id]["messages"] = generate_gpt_response(
                chat_history=conversation_history[user_id]["messages"],
                index=None)
            response_text = conversation_history[user_id]["messages"][-1]["content"]
            print(f"Original response: {response_text}\n")

            if re.findall(r"```python(.*?)```", response_text, re.DOTALL):
                response_text = modify_response_to_include_code_output(response_text)
                print(f"With code output: {response_text}")

            unsplash_text_links = re.findall(r"!\[(.*?)\]\((.*?)\)", response_text)
            # unsplash_titles = re.findall(r"!\[(.*?)\]https://source.unsplash.com/", response_text)
            print(f"unsplash_links = {unsplash_text_links}")
            if unsplash_text_links:
                # response_text = re.sub(r"!\[.*?\]\(https://source.unsplash.com/\S+\)", "", response_text)
                send_back_message(user_id, response_text)
                for text, link in unsplash_text_links:
                    send_back_message(user_id, f"直接下载:{text}", image_url=link)
                    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{current_time}.png"
                    # send_back_message(user_id, "下载图片...")
                    download_image(link, "static/" + filename)
                    send_back_message(user_id, text, image_filename=filename)
            else:
                send_back_message(user_id, response_text)

        return "Message processed", 200





# Initializes a Flask web application with the name app
app = Flask(__name__)


@app.route('/image/<filename>')
def serve_image(filename):
    return send_from_directory('static', filename)


@app.route("/webhook", methods=["POST"])
def webhook():
    # Parse URL-encoded form data
    form_data = request.form

    # Convert the form data to a dictionary
    event = {key: form_data.get(key) for key in form_data}
    output = process_synology_chat_message(event,
                                           max_web_page=0,
                                           num_search_results=15)
    return output


if __name__ == "__main__":
    app.run(host=your_server_ip, port=PORT)
