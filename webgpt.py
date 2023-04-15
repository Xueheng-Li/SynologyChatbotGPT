#!/usr/bin/env python3
import json
import uuid
import tls_client
import dotenv
import os
from datetime import date
from settings import *
dotenv.load_dotenv()


class WebGPT:

    def __init__(self, model="text-davinci-002-render-sha"):
        self.session = tls_client.Session(
            client_identifier="chrome110",
            random_tls_extension_order=True
        )
        self.session.headers["Authorization"] = "Bearer " + ACCESS_TOKEN
        self.session.headers["Host"] = "chat.openai.com"
        self.session.headers["origin"] = "https://chat.openai.com/chat"
        self.session.headers["referer"] = "https://chat.openai.com/chat"
        self.session.headers["content-type"] = "application/json"
        self.session.headers["sec-ch-ua"] = '" Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"'
        self.session.headers["sec-ch-ua-mobile"] = "?0"
        self.session.headers["sec-fetch-dest"] = "empty"
        self.session.headers["sec-fetch-mode"] = "cors"
        self.session.headers["sec-fetch-site"] = "same-site"
        self.session.headers[
            "user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
        self.session.cookies["_puid"] = PUID
        self.parent_id = str(uuid.uuid4())
        self.refresh_puid()
        self.model = model
        self.conversation = {}
        self.chat_history = []

    def refresh_puid(self):
        res = self.session.get(
            "https://chat.openai.com/backend-api/models",
            headers={
                "key1": "value1",
            },
        )
        self.session.cookies["_puid"] = res.cookies["_puid"]

    def start_session(self,
                      system_prompt=f"{system_prompt} Current date: {str(date.today())}"
                      ):
        res = self.session.post(
            "https://chat.openai.com/backend-api/conversation",
            json={
                "id": str(uuid.uuid4()),
                "action": "next",
                "messages": [
                    {
                        "author": {
                            "role": "user"
                        },
                        "role": "system",
                        "content": {
                            "content_type": "text",
                            "parts": [system_prompt]
                        }
                    }
                ],
                "parent_message_id": self.parent_id,
                "model": self.model,
                "timezone_offset_min": -60
            },
        )
        text = os.linesep.join([s for s in res.text.splitlines() if s])
        base = text.splitlines()[len(text.splitlines()) - 2]
        base = json.loads(base[base.find("data: ") + 6:])
        self.conversation = base
        self.chat_history.append({"role": "system", "content": system_prompt})
        return base

    def resume_session(self, chat_id):
        res = self.session.get(
            "https://chat.openai.com/backend-api/conversation/" + chat_id,
        )

        parent_id = res.json()["current_node"]
        self.conversation = {"conversation_id": chat_id, "message": {"id": parent_id}}
        return {"conversation_id": chat_id, "message": {"id": parent_id}}

    def send_message(self, message, old_question=None):
        if old_question is None:
            old_question = self.conversation
        res = self.session.post(
            "https://chat.openai.com/backend-api/conversation",
            json={"id": str(uuid.uuid4()), "action": "next", "messages": [
                {"author": {"role": "user"}, "role": "user",
                 "content": {"content_type": "text", "parts": [f"{message}\n"]}}],
                  "conversation_id": old_question['conversation_id'],
                  "parent_message_id": old_question['message']['id'], "model": self.model,
                  "timezone_offset_min": -60},
        )
        response = res.text
        text = os.linesep.join([s for s in response.splitlines() if s])
        base = text.splitlines()[len(text.splitlines()) - 2]
        base = json.loads(base[base.find("data: ") + 6:])
        response_text = base['message']['content']['parts'][0]
        self.conversation_id = base["conversation_id"]
        self.chat_history.append({"role": "assistant", "content": response_text})
        return response_text


if __name__ == "__main__":
    gpt4 = WebGPT(model="gpt-4")  # or "text-davinci-002-render-sha" (default)(AKA GPT-3.5)
    session = gpt4.start_session()
    while True:
        response = gpt4.send_message(input(">>> "), session)
        print(gpt4.chat_history)
