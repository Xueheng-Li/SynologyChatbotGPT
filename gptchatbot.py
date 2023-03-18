import json, time, csv, os
import requests
import openai
from flask import Flask, request, jsonify

# Replace with your OpenAI API key
openai.api_key = "your_api_key_here"

# Replace with your Synology Chat bot details
INCOMING_WEBHOOK_URL = "your_incoming_webhook_url_here"
OUTGOING_WEBHOOK_TOKEN = "your_outgoing_webhook_token_here"

# This system prompt sets up the character of the chatbot; change it if you want
chatbot_character = '''You are a AI assistant, a friend of mine, trying to help me and my family as much as possible and in whatever ways you can. 
    If the user talks to you in English, you respond in English. If the user talks to you in Chinese, you respond in Chinese. 
    Be talkative, personable, friendly, positive, and speak always with love.'''

max_conversation_length=20 # if a conversation has more than 20 exchanges, then refresh the conversation history and start a new one. 
max_time_gap=15 # if a conversation is idle for more than 15 minunites, then refresh the conversation history and start a new one. 

# In-memory conversation history storage
conversation_history = {}


def send_back_message(user_id, response_text):


    payload = 'payload=' + json.dumps({
        'text': response_text,
        "user_ids": [int(user_id)]
    })

    # Add a try-except block to handle potential exceptions during the POST request
    try:
        response = requests.post(INCOMING_WEBHOOK_URL, payload)
        # response = requests.post(INCOMING_WEBHOOK_URL, json=payload)
        response.raise_for_status()  # Raise an exception if the response contains an HTTP error
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to Synology Chat: {e}")
        return "Error sending message to Synology Chat", 500


def process_synology_chat_message(event):

    if event.get('token') != OUTGOING_WEBHOOK_TOKEN:
        return "Invalid token"

    user_id = event.get('user_id')
    text = event.get('text')
    username = event.get('username')

    # generate an instant pre-response
    # time.sleep(0.1)
    send_back_message(user_id, "...")

    # generate and send back the proper response
    response_text = generate_gpt_response(user_id, username, text)
    print(response_text)
    send_back_message(user_id, response_text)

    return "Message processed"


def generate_gpt_response(user_id, username, message, max_conversation_length=max_conversation_length, refresh_keywords=None, max_time_gap=max_time_gap):
    # max_conversation_length sets the maximum length for each conversation
    # refresh_keywords store the keywords to start a new conversation


    # Check for refresh_prompt input to start a new conversation
    if refresh_keywords is None:
        refresh_keywords = ["new", "refresh", "00", "restart", "刷新", "新话题", "退下", "结束", "over"]
    if message.strip().lower() in refresh_keywords:
        if user_id in conversation_history:
            del conversation_history[user_id]
        return "--------------"

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

    messages = [{"role": "system", "content": system_prompt}]

    for entry in conversation_history[user_id]["messages"]:
        role = entry['role']
        content = entry['content']
        messages.append({"role": role, "content": content})

    print(f"messages: {messages}")

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.5,
    )

    response_role = response['choices'][0]['message']['role']
    if response['choices'][0]['finish_reason'] == "stop":
        response_text = response['choices'][0]['message']['content']
        conversation_history[user_id]["messages"].append({"role": response_role, "content": response_text})
    else:
        conversation_history[user_id]["messages"].append({"role": response_role, "content": f"error: stop reason - {response['choices'][0]['finish_reason']}"})

    return response_text


def handle_request(event):
    print(f"event: {event}")
    if not event:
        return "Empty request body", 400
    return process_synology_chat_message(event)


app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    # Parse URL-encoded form data
    form_data = request.form

    # Convert the form data to a dictionary
    event = {key: form_data.get(key) for key in form_data}

    return handle_request(event)  # Pass the event dictionary instead of the raw request body


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
