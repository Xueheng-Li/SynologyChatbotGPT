import openai
from flask import Flask, request
from flask import send_from_directory
from my_module import *
from settings import *
from search import *

# Set up OpenAI API key
openai.api_key = openai_api_key


# In-memory conversation history storage
conversation_history = {}



# This detect_channel function takes a message text as input and checks if it starts with specific keywords to determine which channel (python, bash, image, or gpt) the message belongs to, returning a dictionary containing the detected channel and the corresponding message content.
def separate_channel(message_text):

    keywords = {}
    keywords["python"] = ["python:", "py:", "python ", "py ", "Python:", "Python "]
    keywords["bash"] = ["bash:", "b:", "bash ", "Bash:"]
    keywords["image"] = ["图片:", "图片：", "图片 ", "img:",  "Img:", "生成图片：", "生成图片:"]
    keywords["gpt"] = ["生成程序：","程序生成：","generator:", "Generator:", "ai:", "AI:", "gpt:", "Gpt:", "Ai:"]
    keywords["google"] = ["google:", "Google:", "谷歌:", "谷歌：", "搜索:", "搜索：", "search:", "Search:", "Search：", "search：",
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
def process_synology_chat_message(event):

    print(f"event: {event}")
    
    if not event:
        return "Empty request body", 400
        
    else:
        
        if event.get('token') != OUTGOING_WEBHOOK_TOKEN:
            return "Invalid token"
    
        user_id = event.get('user_id')
        message = event.get('text')
        username = event.get('username')

        # check and execute python code 
        code_results = separate_channel(message)
        if code_results["python"]:
            print("python code found")
            send_back_message(user_id, f"Python input: \n```{code_results['python']}``` ")
            code_output = capture_python_output(code_results["python"])
            send_back_message(user_id, f"Output: \n```{code_output}```")
            
        elif code_results["bash"]:
            print("bash code found")
            send_back_message(user_id, f"Bash input: \n```{code_results['bash']}``` ")
            code_output = capture_bash_output(code_results["bash"])
            send_back_message(user_id, f"Output: \n```{code_output}```")

        elif code_results["image"]:
            print("image description found")
            text_description = code_results["image"]
            send_back_message(user_id, f"收到👌🏻我会按你要求生成图片：{text_description}")
            img_filename = generate_img_from_openai(text_description, user_id=user_id)
            print(f"img_filename = {img_filename}")
            send_back_message(user_id, text_description, image_filename=img_filename)

        elif code_results["google"]:
            print(f"Google search request found: {code_results['google']}")
            answer = my_web_search(question=code_results["google"], num_keywords=3, max_doc=3, num_results=8)
            print(f"answer = {answer}")
            send_back_message(user_id, answer)
            conversation_history[user_id]["messages"].append(
                {"role": "Google", "content": answer}
            )
        else:
            print("Collect messages to send to gpt")
            # generate an instant pre-response to signal the bot is at work
            send_back_message(user_id, "...")
            # print(f"python_or_bash_code(message): {python_or_bash_code(message)}")
            # get gpt response and excute any Python code
            response_text = generate_gpt_response(user_id, username, message)
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
            
        # else:
        #     send_back_message(user_id, "请问我有滴咩可以帮到你？")
    
        return "Message processed"




def generate_gpt_response(user_id, username, message, max_conversation_length=max_conversation_length, refresh_keywords=None, max_time_gap=max_time_gap):
    # max_conversation_length sets the maximum length for each conversation
    # refresh_keywords store the keywords to start a new conversation


    # Check for refresh_prompt input to start a new conversation
    if refresh_keywords is None:
        refresh_keywords = ["new", "refresh", "00", "restart", "刷新", "新话题", "退下", "结束", "over"]
    if len(message)>0 and message.strip().lower() in refresh_keywords:
        if user_id in conversation_history:
            del conversation_history[user_id]
        return "----------------------------"

    current_timestamp = int(time.time())
    # Check if the conversation has been idle for 30 minutes (1800 seconds)
    if (user_id in conversation_history and
            current_timestamp - conversation_history[user_id]["last_timestamp"] >= max_time_gap*60):
        del conversation_history[user_id]

    # Maintain conversation history
    if user_id not in conversation_history:
        conversation_history[user_id] = {"username": username, "messages": [], "last_timestamp": current_timestamp}
    else:
        conversation_history[user_id]["last_timestamp"] = current_timestamp
        # Truncate conversation history if it exceeds the maximum length
        if len(conversation_history[user_id]["messages"]) > max_conversation_length:
            conversation_history[user_id]["messages"] = conversation_history[user_id]["messages"][-max_conversation_length:]

    conversation_history[user_id]["messages"].append({"role": "user", "content": message})

    system_prompt = chatbot_character

    # construct a list of messages to be sent to the GPT-3 model for generating a response
    messages_to_gpt = [{"role": "system", "content": system_prompt}]
    for entry in conversation_history[user_id]["messages"]:
        role = entry['role']
        content = entry['content']
        messages_to_gpt.append({"role": role, "content": content})
    print(f"messages: {messages_to_gpt}")
    
    # get gpt response
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages_to_gpt,
        temperature=temperature,
    )

    response_role = response['choices'][0]['message']['role']
    if response['choices'][0]['finish_reason'] == "stop":
        response_text = response['choices'][0]['message']['content']
        conversation_history[user_id]["messages"].append(
            {"role": response_role, "content": response_text}
        )
    else:
        conversation_history[user_id]["messages"].append(
            {"role": response_role, "content": f"error: stop reason - {response['choices'][0]['finish_reason']}"}
        )

    return response_text

    

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
    output = process_synology_chat_message(event)  # Pass the event dictionary instead of the raw request body
    return output



if __name__ == "__main__":
    app.run(host=your_server_ip, port=PORT)
