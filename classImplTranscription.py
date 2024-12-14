import json
import time
import yt_dlp
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import threading
import openai
import os
import speech_recognition as sr
import requests
from datetime import datetime
import subprocess
from google.cloud import translate_v2 as translate
from googletrans import Translator

def split_message(message, limit=200):
    if len(message) <= limit:
        return [message]

    chunks = []
    sentences = message.split('. ')
    current_chunk = ''

    for sentence in sentences:
        test_sentence = sentence + '. ' if sentence != sentences[-1] else sentence

        if len(current_chunk) + len(test_sentence) <= limit:
            current_chunk += test_sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = test_sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
def chunk_message(message, max_length=180):
    """Split message into chunks that fit YouTube's limit"""
    chunks = []
    while message:
        if len(message) <= max_length:
            chunks.append(message)
            break
        # Find the last space within max_length
        split_point = message.rfind(' ', 0, max_length)
        if split_point == -1:
            split_point = max_length
        chunks.append(message[:split_point])
        message = message[split_point:].strip()
    return chunks

def post_unicode_message(live_chat_id, message, youtube_write):
    chunks = chunk_message(message)
    for chunk in chunks:
        formatted_message = f"🔄 {chr(8235)}{chunk}{chr(8234)}"
        print(f"Posting chunk: {formatted_message}")
        execute_post(live_chat_id, formatted_message, youtube_write)
        time.sleep(2)  # Respect YouTube API rate limits

def post_ascii_message(live_chat_id, message, youtube_write):
    chunks = chunk_message(message)
    for chunk in chunks:
        formatted_message = f"💬 {chunk}"
        print(f"Posting chunk: {formatted_message}")
        execute_post(live_chat_id, formatted_message, youtube_write)
        time.sleep(2)  # Respect YouTube API rate limits


def execute_post(live_chat_id, formatted_message, youtube_write):
    request = youtube_write.liveChatMessages().insert(
        part="snippet",
        body={
            "snippet": {
                "liveChatId": live_chat_id,
                "type": "textMessageEvent",
                "textMessageDetails": {
                    "messageText": formatted_message[:200]
                }
            }
        }
    )
    return request.execute()

def post_message(live_chat_id, message, youtube_write):
    message_chunks = split_message(message)

    for chunk in message_chunks:
        try:
            # Handle Urdu text with proper encoding and direction
            formatted_message = f"🔴 {chunk} "  # Adding an emoji prefix helps with RTL text
            print(formatted_message)

            request = youtube_write.liveChatMessages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": live_chat_id,
                        "type": "textMessageEvent",
                        "textMessageDetails": {
                            "messageText": formatted_message[:200]  # Ensure we stay within limit
                        }
                    }
                }
            )
            response = request.execute()
            if "id" in response:
                print(f"Message posted successfully!")
                time.sleep(3)  # Increased delay for better rate limiting
            else:
                print(f"Message not posted: {response}")
        except HttpError as e:
            print(f"API Error: {e.reason if hasattr(e, 'reason') else str(e)}")



class StreamProcessor:
    def __init__(self, segment_duration=30, live_chat_id=None, youtube=None):
        self.segment_duration = segment_duration
        self.stop_event = threading.Event()
        self.last_processed_time = 0
        self.live_chat_id = live_chat_id
        self.youtube = youtube
        self.translator = Translator()

    def translate_text(self, text, target_language='en'):
        """Translates text to target language using googletrans."""
        result = self.translator.translate(text, dest=target_language)
        return result.text

    def download_segment(self, stream_url, output_file):
        command = [
            "ffmpeg",
            "-i", stream_url,
            "-t", str(self.segment_duration),
            "-c", "copy",
            "-y",
            output_file
        ]
        subprocess.run(command, check=True, capture_output=True)

    def convert_to_wav(self, input_file, output_file):
        command = [
            "ffmpeg",
            "-i", input_file,
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            output_file
        ]
        subprocess.run(command, check=True, capture_output=True)

    def transcribe_audio(self, audio_file):
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
        try:
            # Changed language to Hindi
            text = recognizer.recognize_google(audio, language="hi-IN")
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"Transcription error: {e}")
            return ""


    def process_stream(self, stream_url):
        while not self.stop_event.is_set():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_segment = f"segment_{timestamp}.ts"
            wav_segment = f"segment_{timestamp}.wav"

            try:
                self.download_segment(stream_url, raw_segment)
                self.convert_to_wav(raw_segment, wav_segment)
                hindi_transcription = self.transcribe_audio(wav_segment)
                if hindi_transcription:
                    # Translate directly to Arabic
                    arabic_translation = self.translate_text(hindi_transcription, 'ar')
                    message = f"Hindi: {hindi_transcription}\nArabic: {arabic_translation}\n"
                    print(f"Transcription and Translation: {message}")
                    if self.live_chat_id and self.youtube:
                        #post_message(self.live_chat_id, message, self.youtube)
                        post_unicode_message(self.live_chat_id, message, self.youtube)
                    with open("transcriptions.txt", "a", encoding="utf-8") as f:
                        f.write(f"[{timestamp}] {message}\n")

            except Exception as e:
                print(f"Error processing segment: {e}")
            finally:
                if os.path.exists(raw_segment):
                    os.remove(raw_segment)
                if os.path.exists(wav_segment):
                    os.remove(wav_segment)
                self.last_processed_time += self.segment_duration

class YouTubeLiveTranscriber:
    def __init__(self, video_id, client_secret_file):
        self.video_id = video_id
        self.client_secret_file = client_secret_file
        self.stop_event = threading.Event()
        self.SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

    def get_credentials(self):
        flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, self.SCOPES)
        credentials = flow.run_local_server(port=0)
        return credentials

    def get_live_chat_id(self, youtube):
        response = youtube.videos().list(
            part="liveStreamingDetails",
            id=self.video_id
        ).execute()

        if "items" in response and response["items"]:
            return response["items"][0].get("liveStreamingDetails", {}).get("activeLiveChatId")
        return None

    def get_stream_url_with_ytdlp(self):
        ydl_opts = {"quiet": True, "format": "best"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={self.video_id}", download=False)
            return info.get("url")

    def get_live_stream_info(self, youtube):
        try:
            request = youtube.videos().list(
                part="liveStreamingDetails",
                id=self.video_id
            )
            response = request.execute()

            if "items" in response and response["items"]:
                streaming_details = response["items"][0].get("liveStreamingDetails")
                if streaming_details:
                    return streaming_details.get("hlsManifestUrl")
            return None
        except HttpError as e:
            print(f"Error getting live stream info: {e}")
            return None

    def process_live_stream(self, youtube):
        stream_url = self.get_live_stream_info(youtube)
        if not stream_url:
            stream_url = self.get_stream_url_with_ytdlp()

        if stream_url:
            live_chat_id = self.get_live_chat_id(youtube)
            processor = StreamProcessor(segment_duration=30, live_chat_id=live_chat_id, youtube=youtube)
            processor.process_stream(stream_url)
        else:
            print("Could not retrieve live stream URL")

    def start(self):
        try:
            credentials = self.get_credentials()
            youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

            live_chat_id = self.get_live_chat_id(youtube)
            if not live_chat_id:
                print("Live Chat ID could not be fetched")
                return

            self.process_live_stream(youtube)

        except Exception as e:
            print(f"Error in transcriber: {e}")
            self.stop_event.set()

def main():
    VIDEO_ID = "GohajeZuFfY"  # Replace with your YouTube video ID
    CLIENT_SECRET_FILE = "credentials_rajeev.india@gmail.com.json"  # Replace with your OAuth client secret file

    transcriber = YouTubeLiveTranscriber(VIDEO_ID, CLIENT_SECRET_FILE)

    try:
        transcriber.start()
    except KeyboardInterrupt:
        print("Stopping transcription...")
        transcriber.stop_event.set()

if __name__ == "__main__":
    main()
