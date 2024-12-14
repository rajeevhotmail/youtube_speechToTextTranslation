import json
import time
import re
from datetime import datetime, timezone
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import threading
import openai
import os
import queue

# Set your OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Global declarations
message_queue = queue.Queue()
target_users = {}
video_id = "tytdMqRHucE"  # Example video ID
stop_event = threading.Event()
auth_event = threading.Event()

def load_target_users(filename="target_users_poem.json"):
    """Loads the target users and their messages from a JSON file."""
    try:
        with open(filename, "r") as f:
            loaded_users = json.load(f)
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
    """Reloads the target users periodically."""
    while not stop_event.is_set():
        global target_users
        target_users = load_target_users()
        time.sleep(60)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRET_FILE = "credential.json"

def get_credentials(account_email):
    """Authenticate and get credentials for a specific account."""
    try:
        print(f"[INFO] Authenticating account: {account_email}")
        client_secret_file = f"credentials_{account_email}.json"
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
        credentials = flow.run_local_server(port=0)
        print(f"[SUCCESS] Authentication successful for account: {account_email}")
        return credentials
    except Exception as e:
        print(f"[ERROR] Authentication failed for account {account_email}: {e}")
        raise

def generate_witty_onliner_informative(username, message):
    """Generate a 1-line witty remark for a live chat user based on their name and message."""

    prompt = f"Answer a query from a live chat user in their language within 150 words. The user's name is {username}, and their message is: '{message}'. If you can't answer, reply with 'I can't answer'. Keep the response precise and to the point."


    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that tries to answer questions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Error generating Urdu one-liner: {e}")
        return "Error in generating Urdu one-liner."

def generate_witty_onliner(username, message):
    """Generate a 1-line witty remark for a live chat user based on their name and message."""
    #prompt = f"Write a single witty and grim remark for a live chat user in hindi. The user's name is {username}, and their message is: '{message}'. The response should be sharp, engaging, and creative."
    #prompt = f"Write a single witty, sarcastic  grim remark for a live chat troll user in hindi or roman hindi script. The user's name is {username}, and their message is: '{message}'. The response should be sharp, sarcastic, and creative. The user is a troll"
    #prompt = f"Write a single witty, polite and complimentary message praising the user on the content of the message. the message should be in marathi or roman marathi script. The user's name is {username}, and their message is: '{message}'. The response should be polite, giving the user a compliment upon the user's message"
    prompt = f"Write a single sarcastic remark for a live chat troll user in the script and languge of the user. The user's name is {username}, and their message is: '{message}'. Respond only if you think it is necessary. You are responding for username 'Rajeev Sharma'"


    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that writes sarcastic remarks against live chat troll users."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Error generating Urdu one-liner: {e}")
        return "Error in generating Urdu one-liner."

def get_live_chat_id(youtube):
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

def fetch_live_chat_messages(youtube, live_chat_id, next_page_token=None):
    """Fetch live chat messages."""
    response = youtube.liveChatMessages().list(
        liveChatId=live_chat_id,
        part="snippet,authorDetails",
        pageToken=next_page_token
    ).execute()
    return response.get("items", []), response.get("nextPageToken")

def detect_and_warn_abuse(live_chat_id, message, message_time, youtube_write):
    """Detect and warn abusive messages."""
    global target_users

    raw_author_name = message["authorDetails"]["displayName"]
    normalized_author_name = normalize_username(raw_author_name)
    user_message = message["snippet"]["textMessageDetails"]["messageText"] if "textMessageDetails" in message["snippet"] else ""
    print(f"Received message from {normalized_author_name} ({raw_author_name}): {user_message}")


    if normalized_author_name in target_users:
        poem_hindi = generate_witty_onliner(raw_author_name, user_message)
        #poem_hindi = f"🤖({message_time.strftime('%Y-%m-%d %H:%M:%S')}) {poem_hindi}"
        poem_hindi = f"🤖 I am AI bot. {poem_hindi}"
        post_message(live_chat_id, poem_hindi, youtube_write)
    else:
        print(f"{normalized_author_name} not found in target users.")

def post_message(live_chat_id, message, youtube_write):
    """Post a message to live chat."""
    try:
        request = youtube_write.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": message},
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

def reader():
    """Reader thread to fetch live chat messages and filter by target users."""
    try:
        print("[INFO] Reader attempting to authenticate...")
        credentials = get_credentials("aphidspider@gmail.com")
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
        live_chat_id = get_live_chat_id(youtube)
        print(f"[SUCCESS] Reader authenticated. Live Chat ID: {live_chat_id}")

        auth_event.set()  # Signal that the reader is authenticated

        next_page_token = None
        while not stop_event.is_set():
            try:
                # Fetch live chat messages
                messages, next_page_token = fetch_live_chat_messages(youtube, live_chat_id, next_page_token)
                for message in messages:
                    # Filter messages by target users
                    raw_author_name = message["authorDetails"]["displayName"]
                    normalized_author_name = normalize_username(raw_author_name)
                    user_message = message["snippet"]["textMessageDetails"]["messageText"] if "textMessageDetails" in message["snippet"] else ""
                    print(f"Received message from {normalized_author_name} ({raw_author_name}): {user_message}")

                    if normalized_author_name in target_users:
                        #print(f"[INFO] Queuing message from target user: {raw_author_name}")
                        message_queue.put(message)
                    else:
                        #print(f"[DEBUG] Skipping message from: {raw_author_name}")
                        print("")

                time.sleep(15)  # Adjust poll interval as needed
            except Exception as e:
                print(f"[ERROR] Error in reader: {e}")
                stop_event.set()
    except Exception as e:
        print(f"[ERROR] Unexpected error in reader: {e}")
        stop_event.set()


def writer():
    """Writer thread to process the last two messages."""
    try:
        print("[INFO] Writer waiting for reader authentication...")
        auth_event.wait(timeout=30)  # Wait for up to 30 seconds
        if not auth_event.is_set():
            print("[ERROR] Reader failed to authenticate. Writer exiting.")
            return

        print("[INFO] Writer attempting to authenticate...")
        credentials = get_credentials("rajeev.india@gmail.com")
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
        live_chat_id = get_live_chat_id(youtube)
        print(f"[SUCCESS] Writer authenticated. Live Chat ID: {live_chat_id}")

        while not stop_event.is_set():
            try:
                # Transfer all messages to a temporary list
                temp_messages = []
                while not message_queue.empty():
                    try:
                        temp_messages.append(message_queue.get_nowait())
                    except queue.Empty:
                        break

                if not temp_messages:
                   # print("[INFO] No messages to process. Writer relaxing.")
                    time.sleep(5)  # Relax for a short duration
                    continue

                # Get the last two messages
                messages_to_process = temp_messages[-2:]

                # Process the last two messages
                for message in messages_to_process:
                    if "snippet" in message:
                        message_time = datetime.fromisoformat(message["snippet"]["publishedAt"].replace("Z", "+00:00"))
                        detect_and_warn_abuse(live_chat_id, message, message_time, youtube)

            except Exception as e:
                print(f"[ERROR] Error in writer: {e}")
                stop_event.set()

    except Exception as e:
        print(f"[ERROR] Unexpected error in writer: {e}")
        stop_event.set()


def main():
    """Main function to start threads."""
    global stop_event

    threads = [
        threading.Thread(target=reload_target_users_thread, daemon=True),
        threading.Thread(target=reader),
        threading.Thread(target=writer),
    ]

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Stopping threads...")
        stop_event.set()

    for t in threads[1:]:  # Skip daemon threads
        t.join()

    print("Program terminated gracefully.")


if __name__ == "__main__":
    main()
