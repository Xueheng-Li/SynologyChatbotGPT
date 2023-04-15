#coding:utf-8
from flask import Flask, request
from flask import send_from_directory
from my_module import *
from settings import *

# Set up OpenAI API key
openai.api_key = openai_api_key

# Initializes a Flask web application with the name app
app = Flask(__name__)

# # Update the Flask app configuration with the Celery broker URL
# app.config.update(
#     CELERY_BROKER_URL=CELERY_BROKER_URL,
# )

# In-memory storage of chatbot data
bots = {}


@app.route('/image/<filename>')
def serve_image(filename):
    return send_from_directory('static', filename)


@app.route("/webhook", methods=["POST"])
def webhook():

    # Parse URL-encoded form data
    form_data = request.form

    # Convert the form data to a dictionary
    event = {key: form_data.get(key) for key in form_data}
    print(f"event = {event}")

    # from celery_tasks import process_message  # Import the Celery task
    # process_message.delay(event, num_search_results=5)

    # Call the process method of the ChatBot instance
    user_id = event.get('user_id')
    message = event["text"]
    if user_id not in bots:
        bots[user_id] = ChatBot(user_id,
                                max_conversation_length=max_conversation_length,
                                max_time_gap=max_time_gap,
                                index=None,
                                system_prompt=system_prompt,
                                stream=stream,
                                temperature=temperature,
                                translate=translate_to_chinese,
                                model="gpt-3.5"
                                )
    output = bots[user_id].process(message, num_search_results=5)
    return output
    # return "Message processing started", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
