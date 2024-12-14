import openai
import time
import datetime
import speech_recognition as sr
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import os
from datetime import timezone, datetime

# Print available microphones
print("Available microphones:")
print(sr.Microphone.list_microphone_names())

# Set up Google API
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRET_FILE = "credential.json"

def get_credentials():
    """Authenticate and get credentials."""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)
    return credentials

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

def transcribe_audio():
    """Capture audio and transcribe it to text."""
    recognizer = sr.Recognizer()
    with sr.Microphone(device_index=1) as source:  # Change index as needed
        print("Calibrating microphone for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=3)
        print(f"Calibrated energy threshold: {recognizer.energy_threshold}")

        print("Listening...")
        try:
            # Set smaller timeout values for debugging
            audio = recognizer.listen(source, timeout=30, phrase_time_limit=10)
            print("Audio captured, processing...")

            # Save audio for debugging
            with open("debug_audio.wav", "wb") as f:
                f.write(audio.get_wav_data())

            text = recognizer.recognize_google(audio, language="hi-IN")
            print(f"Transcribed text: {text}")
            return text
        except sr.WaitTimeoutError:
            print("Error: Listening timed out (no phrase detected).")
            return None
        except sr.UnknownValueError:
            print("Error: Could not understand the audio.")
            return None
        except sr.RequestError as e:
            print(f"Error with speech recognition: {e}")
            return None

def listen_and_comment(live_chat_id):
    """Continuously listen to the anchor and post comments."""
    start_time = datetime.now(timezone.utc)
    try:
        while True:
            transcription = transcribe_audio()
            if transcription:
                message = f"Transcribed text: {transcription}"
                post_message(live_chat_id, message)
            current_time = datetime.now(timezone.utc)
            print(f"Bot running since: {start_time.isoformat()}. Current time: {current_time.isoformat()}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Bot stopped manually.")

if __name__ == "__main__":
    # Authenticate and set up YouTube API
    credentials = get_credentials()
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    # Fetch Live Chat ID
    video_id = "Y9iO1pOIZ0I"
    try:
        live_chat_id = get_live_chat_id(video_id)
        print(f"Live Chat ID: {live_chat_id}")
        listen_and_comment(live_chat_id)
    except Exception as e:
        print(f"Error: {e}")
