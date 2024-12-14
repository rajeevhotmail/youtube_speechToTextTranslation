import openai
import time
import datetime
import speech_recognition as sr
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import os
import datetime
from datetime import timezone
from datetime import datetime, timezone
import speech_recognition as sr

print(sr.Microphone.list_microphone_names())


# Correctly use UTC
start_time = datetime.now(timezone.utc)  # Current time in UTC
current_time = datetime.now(timezone.utc)

print(f"Bot running since: {start_time.isoformat()}. Current time: {current_time.isoformat()}")


# Set your OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Google API Setup
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRET_FILE = "credential.json"

def get_credentials():
    """Authenticate and get credentials."""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)
    return credentials

credentials = get_credentials()
youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

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
def translate_to_english(transcription):
    """Translate Hindi text to English using OpenAI."""
    if not transcription:
        return None  # If transcription failed, skip translation

    prompt = f"""You are a professional translator. Translate the following Hindi text to English:
    Hindi: "{transcription}"
    English:"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",  # Replace with "gpt-3.5-turbo" if necessary
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        translation = response["choices"][0]["message"]["content"].strip()
        print(f"Translation: {translation}")
        return translation
    except Exception as e:
        print(f"Error translating text: {e}")
        return None

# Audio Transcription
def transcribe_audio():
    """Capture audio and transcribe it to text."""
    recognizer = sr.Recognizer()
    with sr.Microphone(device_index=1) as source:  # Use the correct microphone index
        print("Preparing to listen...")

        # Lower threshold and enable dynamic adjustment
        recognizer.energy_threshold = 50
        recognizer.dynamic_energy_threshold = True
        print(f"Initial energy threshold: {recognizer.energy_threshold}")

        print("Listening...")
        try:
            # Allow sufficient time for speech detection
            audio = recognizer.listen(source, timeout=60, phrase_time_limit=30)
            print("Audio captured, processing...")

            # Save captured audio for debugging
            with open("debug_audio.wav", "wb") as f:
                f.write(audio.get_wav_data())

            # Transcribe audio
            text = recognizer.recognize_google(audio, language="hi-IN")  # Assuming Hindi
            print(f"Anchor said: {text}")
            return text
        except sr.WaitTimeoutError:
            print("Error: listening timed out while waiting for phrase to start")
            return None
        except sr.UnknownValueError:
            print("Sorry, could not understand the audio.")
            return None
        except sr.RequestError as e:
            print(f"Error with speech recognition: {e}")
            return None



def split_into_chunks(text, max_words):
    """Split text into chunks of up to `max_words` words."""
    words = text.split()
    chunks = []

    # Create chunks of up to `max_words`
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)

    return chunks


def listen_and_comment(live_chat_id):
    """Continuously listen to the anchor and post translated comments in chunks."""
    api_call_count = 0
    API_LIMIT = 300  # Set a daily limit for API calls (adjust based on quota)
    start_time = datetime.now(timezone.utc)  # Track when the bot started

    while api_call_count < API_LIMIT:
        transcription = transcribe_audio()
        if transcription:
            # Translate transcription to English
            translation = translate_to_english(transcription)
            if translation:
                # Add a bot identifier message
                full_message = "I am bot. I am translating the audio to English text: " + translation

                # Split the message into chunks of up to 150 words
                chunks = split_into_chunks(full_message, max_words=150)

                # Post each chunk separately
                for chunk in chunks:
                    post_message(live_chat_id, chunk)
                    api_call_count += 1  # Increment API call count
                    if api_call_count >= API_LIMIT:
                        break  # Stop if API limit is reached

        # Log the bot's running time
        current_time = datetime.now(timezone.utc)
        print(f"Bot running since: {start_time.isoformat()}. Current time: {current_time.isoformat()}")
        time.sleep(10)  # Reduced sleep time


def listen_and_comment_witty(live_chat_id):
    
    api_call_count = 0
    API_LIMIT = 300  # Set a daily limit for API calls (adjust based on quota)
    start_time = datetime.datetime.now(datetime.timezone.utc)  # Track when the bot started

    while api_call_count < API_LIMIT:
        transcription = transcribe_audio()
        if transcription:
            # Generate and post witty comment
            witty_comment = generate_witty_comment(transcription)
            if witty_comment:
                post_message(live_chat_id, witty_comment)
                api_call_count += 1  # Increment API call count

        # Log the bot's running time
        current_time = datetime.datetime.now(datetime.timezone.utc)
        print(f"Bot running since: {start_time.isoformat()}. Current time: {current_time.isoformat()}")
        time.sleep(10)  # Reduced sleep time


# Replace all utcnow() instances with timezone-aware datetime
start_time = datetime.now(timezone.utc)
current_time = datetime.now(timezone.utc)
print(f"Bot running since: {start_time.isoformat()}. Current time: {current_time.isoformat()}")


# Generate Witty Comments
def generate_witty_comment(transcription):
    """Generate a witty comment based on the anchor's speech."""
    if not transcription:
        return None  # If transcription failed, skip generating a comment

    prompt = f"""You are a witty assistant. The anchor said: "{transcription}".
    Respond with a humorous or clever comment suitable for a live chat."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",  # Replace with "gpt-4" if desired
            messages=[
                {"role": "system", "content": "You are a witty assistant for live chat."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )
        comment = response["choices"][0]["message"]["content"].strip()
        print(f"Witty comment: {comment}")
        return comment
    except Exception as e:
        print(f"Error generating witty comment: {e}")
        return None

# Main Listening and Posting Loop
def listen_and_comment(live_chat_id):
    """Continuously listen to the anchor and post witty comments."""
    api_call_count = 0
    API_LIMIT = 300  # Set a daily limit for API calls (adjust based on quota)
    start_time = datetime.now(timezone.utc)  # Track when the bot started

    while api_call_count < API_LIMIT:
        transcription = transcribe_audio()
        if transcription:
            # Generate and post witty comment
            witty_comment = generate_witty_comment(transcription)
            if witty_comment:
                post_message(live_chat_id, witty_comment)
                api_call_count += 1  # Increment API call count

        # Log the bot's running time
        current_time = datetime.now(timezone.utc)
        print(f"Bot running since: {start_time.isoformat()}. Current time: {current_time.isoformat()}")
        time.sleep(10)  # Reduced sleep time

# Main Entry Point
if __name__ == "__main__":
    video_id = "2uY95PSUtGU"  # Replace with your video ID
    try:
        live_chat_id = get_live_chat_id(video_id)  # Fetch live chat ID
        print(f"Live Chat ID: {live_chat_id}")
        listen_and_comment(live_chat_id)  # Start listening and posting comments
    except Exception as e:
        print(f"Error: {e}")
