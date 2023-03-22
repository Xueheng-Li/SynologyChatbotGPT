
# Replace with your OpenAI API key
openai_api_key = "your_openai_api_key"


# Replace with your Synology Chat bot details
INCOMING_WEBHOOK_URL = "your_INCOMING_WEBHOOK_URL"
OUTGOING_WEBHOOK_TOKEN = "your_OUTGOING_WEBHOOK_TOKEN"


# Your server IP address where you run this bot (more explicitly, the ip of the server where you put this script)
your_server_ip = 'your_server_ip'


# Port
PORT = 5008


# This system prompt sets up the character of the chatbot; change it if you want
chatbot_character = '''You are a AI assistant, a friend of mine, trying to help me and my family as much as possible and in whatever ways you can. 
    If the user talks to you in English, you respond in English. If the user talks to you in Chinese, you respond in Chinese. 
    Be talkative, personable, friendly, positive, and speak always with love.'''


# Set maximum conversation exchanges or idle time gap to start a new conversatoin
max_conversation_length = 20 
max_time_gap = 15 # minutes


# Set temperature -- a parameter in the OpenAI API that controls the randomness of the generated text. It is a floating-point value that ranges from 0 to 1. A higher value (e.g., 0.8) will result in more random and creative outputs, while a lower value (e.g., 0.2) will produce more focused and deterministic outputs. In this case, the temperature is set to 0.5, which provides a balance between creativity and determinism in the generated text.
temperature = 0.5


# Image size when using ai to generate image
image_size = "medium" # "small", "medium" or "large"


# Set the virtual Python environment path if you want the bot to run Python code -- ignore it if you don't know what it is.
# This variable is used to store the path to the virtual Python environment for the project. This virtual environment is where the project's dependencies are installed and managed, ensuring that they don't interfere with other projects or the system's global Python installation. By specifying the path to the virtual environment, the project can reference and activate the environment when needed, ensuring that the correct dependencies are used during execution.
venv_path = "./venv"
