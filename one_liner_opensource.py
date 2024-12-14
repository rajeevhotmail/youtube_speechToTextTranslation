import json
import time
import re
from datetime import datetime, timezone
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import threading
import os
import random
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# Initialize the tokenizer and model
tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")


# Create a text generation pipeline
generator = pipeline(task="text-generation", model=model, tokenizer=tokenizer)

# Global variable to hold target users
target_users = {}

def load_target_users(filename="target_users_poem.json"):
    """Loads the target users and their messages from a JSON file."""
    try:
        with open(filename, "r") as f:
            loaded_users = json.load(f)
            # Normalize usernames using regex
            normalized_users = {normalize_username(k): v for k, v in loaded_users.items()}
            print("Target users reloaded:", normalized_users)
            return normalized_users
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in '{filename}'.")
        return {}

def normalize_username(username):
    """Normalize usernames by removing non-alphanumeric characters and converting to lowercase."""
    return re.sub(r'\W+', '', username.strip().lower())

def reload_target_users_thread():
    """Reloads the target users in a separate thread."""
    global target_users
    target_users = load_target_users()

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRET_FILE = "credential.json"

abusive_words = ["abuse1", "abuse2", "offensiveWord"]

def get_credentials():
    """Authenticate and get credentials."""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)
    return credentials

credentials = get_credentials()
youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

def generate_witty_onliner_urdu(username, message):
    """Generate a 1-line witty remark for a live chat user based on their name and message."""
    prompt = f"Write a single witty and complimentary remark for a live chat user in Urdu or Roman Urdu. The user's name is {username}, and their message is: '{message}'. The response should be polite, complimentary, engaging, and creative."

    try:
        response = generator(prompt, max_length=100, num_return_sequences=1)
        witty_remark = response[0]["generated_text"].strip()
        return witty_remark
    except Exception as e:
        print(f"Error generating witty remark: {e}")
        return f"{username}, your message is a breath of fresh air!"

def generate_witty_onliner_hindi(username, message):
    """Generate a 1-line witty remark for a live chat user based on their name and message."""
    prompt = f"Write a single witty and grim remark for a live chat user in Hindi. The user's name is {username}, and their message is: '{message}'. The response should be sharp, engaging, and creative."

    try:
        response = generator(prompt, max_length=100, num_return_sequences=1)
        witty_remark = response[0]["generated_text"].strip()
        return witty_remark
    except Exception as e:
        print(f"Error generating witty remark: {e}")
        return f"{username}, your words are like music to my ears!"

def generate_witty_line(username, message):
    """Generate a 1-line witty remark for a live chat user based on their name and message."""
    prompt = f"Write a single witty and grim remark for a live chat user. The user's name is {username}, and their message is: '{message}'. The response should be sharp, engaging, and creative. The input can be in Hindi or Roman Hindi or English."

    try:
        response = generator(prompt, max_length=100, num_return_sequences=1)
        witty_remark = response[0]["generated_text"].strip()
        return witty_remark
    except Exception as e:
        print(f"Error generating witty remark: {e}")
        return f"{username}, your {message} was so bold it scared punctuation away!"

def get_live_chat_id(video_id):
    """Get live chat ID from a video ID."""
    try:
        response = youtube.videos().list(
            part="liveStreamingDetails",
            id=video_id
        ).execute()

        if "items" in response and response["items"]:
            live_chat_id = response["items"][0].get("liveStreamingDetails", {}).get("activeLiveChatId")
            if live_chat_id:
                return live_chat_id
            else:
                raise Exception("No active live chat found for this video.")
        else:
            raise Exception("Video not found or does not have live chat.")
    except HttpError as e:
        print(f"Error while fetching live chat ID: {e}")
        raise

def fetch_live_chat_messages(live_chat_id, next_page_token=None):
    """Fetch live chat messages."""
    response = youtube.liveChatMessages().list(
        liveChatId=live_chat_id,
        part="snippet,authorDetails",
        pageToken=next_page_token
    ).execute()
    return response.get("items", []), response.get("nextPageToken")


def detect_and_warn_abuse(live_chat_id, messages, start_time):
    """Check for abuse in the chat messages and send poems for target users."""
    global target_users
    for message in messages:
        # Check if the snippet part is available before accessing it
        if "snippet" in message:
            message_time = datetime.fromisoformat(message["snippet"]["publishedAt"].replace("Z", "+00:00"))
            if message_time < start_time:
                continue

        raw_author_name = message["authorDetails"]["displayName"]
        normalized_author_name = normalize_username(raw_author_name)

        # Extract the user's message
        user_message = message["snippet"]["textMessageDetails"]["messageText"] if "textMessageDetails" in message["snippet"] else ""
        print(f"Received message from {normalized_author_name} {raw_author_name}: {user_message}")  # Debug statement

        # Check for target users
        if normalized_author_name in target_users:

            print(f"Detected target user {normalized_author_name}. Generating poem...")
            poem = generate_witty_line(raw_author_name, user_message)
            poem = ":robot: " + poem

            # poem = poem + " (a sinister sneer ensues ) he he he he he"
            post_message(live_chat_id, poem)


            """
            poem_hindi = generate_witty_onliner_hindi(raw_author_name, user_message)
            poem_hindi = ":robot: " + poem_hindi

            poem_hindi = poem_hindi + " (एक भयावह हंसी शुरू होती है) हे हे हे हे हे"
            post_message(live_chat_id, poem_hindi)
            """
        else:
            print(f"{normalized_author_name} not found in target users")  # Debug statement

        # Check for abusive messages
        if "snippet" in message and "textMessageDetails" in message["snippet"]:
            if any(word in user_message.lower() for word in abusive_words):
                warning_message = f"@{raw_author_name}, this is a bot. Please maintain respect in the chat!"
                print(f"Detected abusive message from {raw_author_name}: {user_message}")
                post_message(live_chat_id, warning_message)
                print(f"Warning sent to {raw_author_name} for abusive language")

def post_message(live_chat_id, message):
    """Post a message to live chat."""

    try:
        request = youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": message
                    },
                }
            },
        )
        response = request.execute()

        if "id" in response:
            print(f"Message posted successfully: {message}")
        else:
            print(f"Error: Message not posted: {response}")

    except HttpError as e:
        print(f"Failed to post message '{message}': {e}")

def main():
    global target_users
    video_id = "c7AriYOczdU"
    try:
        live_chat_id = get_live_chat_id(video_id)
        print("Live Chat ID:", live_chat_id)

        next_page_token = None
        program_start_time = datetime.now(timezone.utc)
        print(f"Program started at: {program_start_time.isoformat()} UTC")

        target_users = load_target_users()
        count = 0
        while True:
            # Check and reload target users periodically

            if count > 3:
                threading.Thread(target=reload_target_users_thread).start()
                count = 0


            messages, next_page_token = fetch_live_chat_messages(live_chat_id, next_page_token)

            time.sleep(15)  # Adjusted to 15 seconds
            count += 1
            detect_and_warn_abuse(live_chat_id, messages, program_start_time)

    except HttpError as e:
        if e.resp.status == 403 and "quotaExceeded" in str(e):
            print("Error:", e)
            print("Quota exceeded. Retrying in 100 seconds...")
            time.sleep(100)
        else:
            raise

if __name__ == "__main__":
    main()
