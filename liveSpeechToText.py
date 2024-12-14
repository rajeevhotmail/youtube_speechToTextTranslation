import json
import time
import re
from datetime import datetime, timezone
import yt_dlp
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import threading
import openai
import os
import queue
import speech_recognition as sr
import requests
from google.cloud import translate_v2 as translate
import subprocess




openai.api_key = os.getenv('OPENAI_API_KEY')

message_queue = queue.Queue()
video_id = "pmh4XOy8KMk"
stop_event = threading.Event()
auth_event = threading.Event()

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRET_FILE = "credentials_rajeev.india@gmail.com"


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


def get_live_chat_id(youtube):
    """Get live chat ID from a video ID."""
    try:
        print(f"[INFO] Fetching live chat ID for video ID: {video_id}")
        response = youtube.videos().list(
            part="liveStreamingDetails",
            id=video_id
        ).execute()
        print(f"[DEBUG] API response: {json.dumps(response, indent=4)}")  # Debugging API response

        if "items" in response and response["items"]:
            live_chat_id = response["items"][0].get("liveStreamingDetails", {}).get("activeLiveChatId")
            if live_chat_id:
                print(f"[SUCCESS] Live Chat ID found: {live_chat_id}")
                return live_chat_id
            else:
                raise Exception("No active live chat found for this video.")
        else:
            raise Exception("Video not found or does not have live chat.")
    except HttpError as e:
        print(f"[ERROR] HTTP error while fetching live chat ID: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error while fetching live chat ID: {e}")
        raise


def get_fresh_stream_url(video_id):
    ydl_opts = {"quiet": True, "format": "best"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        return info.get("url")





def download_hls_stream(hls_url, output_file):
    # Check if partial file exists
    if os.path.exists(output_file):
        print("Resuming download...")
        # Append to existing file
        command = f"ffmpeg -i {hls_url} -c copy -continue_at {os.path.getsize(output_file)} {output_file}"
    else:
        print("Starting new download...")
        # Start a new download
        command = f"ffmpeg -i {hls_url} -c copy {output_file}"

    # Run the command
    subprocess.run(command, shell=True)





def convert_to_pcm_wav(input_file, output_file):
    """Convert an audio file to PCM WAV format."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_file, "-acodec", "pcm_s16le", "-ar", "16000", output_file],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("[INFO] Audio converted to PCM WAV successfully.")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Conversion failed: {e.stderr.decode()}")
        return None



def download_with_retries(url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[WARNING] Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    print("[ERROR] Failed to download audio after retries.")
    return None



def get_stream_url_with_ytdlp(video_url):
    """Gets the stream URL using yt-dlp."""
    try:
        ydl_opts = {"quiet": True, "format": "best"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url")
            if stream_url:
                print(f"[INFO] Stream URL fetched with yt-dlp: {stream_url}")
                return stream_url
            else:
                print("[ERROR] No stream URL found with yt-dlp.")
                return None
    except Exception as e:
        print(f"[ERROR] yt-dlp failed to retrieve stream URL: {e}")
        return None


def get_live_stream_info(youtube):
    """Gets the live stream URL from the video ID."""
    try:
        request = youtube.videos().list(
            part="liveStreamingDetails",
            id=video_id
        )
        response = request.execute()

        print(f"[DEBUG] API response for live stream info: {json.dumps(response, indent=4)}")

        if "items" in response and response["items"]:
            streaming_details = response["items"][0].get("liveStreamingDetails")
            if streaming_details:
                stream_url = streaming_details.get("hlsManifestUrl")
                if stream_url:
                    print(f"[INFO] Found stream URL: {stream_url}")
                    return stream_url
                else:
                    print("[WARNING] Stream URL (hlsManifestUrl) not found in liveStreamingDetails.")
                    return None
            else:
                print("[ERROR] liveStreamingDetails is empty or missing.")
                return None
        else:
            print("[ERROR] Video not found or does not have live stream details.")
            return None
    except HttpError as e:
        print(f"[ERROR] HTTP error while fetching live stream URL: {e}")
        return None



def transcribe_with_whisper(audio_data):
    """Transcribes audio data to text using Whisper API."""
    try:
        audio_file= open(audio_data, "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript['text']
    except Exception as e:
        print(f"Error transcribing audio with Whisper: {e}")
        return ""


def transcribe_with_sr(audio_data):
    """Transcribes audio data to text using speech_recognition."""
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_data) as source:
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio, language="hi-IN")
        return text
    except sr.UnknownValueError:
        print("Could not understand audio")
        return ""
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return ""



def transcribe_audio(audio_data):
    """Transcribes audio data to text using Whisper API."""
    try:
        audio_file= open(audio_data, "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript['text']
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return ""


def download_audio(audio_url):
    """Downloads audio from a URL."""
    try:
        response = requests.get(audio_url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open("temp_audio.wav", "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return "temp_audio.wav"
    except requests.exceptions.RequestException as e:
        print(f"Error downloading audio: {e}")
        return None

def translate_to_hindi(text):
    """Translates Marathi text to Hindi."""
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language="en")
    return result['translatedText']

def download_hls(hls_url, output_file, stop_event):
    """
    Downloads an HLS stream using ffmpeg in a separate thread,
    allowing the process to be non-blocking.
    """
    command = [
        "ffmpeg",
        "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "-headers", f"Referer: https://www.youtube.com/watch?v={video_id}",
        "-i", hls_url,
        "-c", "copy",
        output_file
    ]

    def run_ffmpeg():
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True  # To capture output as a string
            )
            while not stop_event.is_set():
                if process.poll() is not None:
                    print("[INFO] ffmpeg process completed successfully.")
                    break
                time.sleep(1)
            if stop_event.is_set() and process.poll() is None:
                print("[INFO] Stopping ffmpeg process.")
                process.terminate()
                process.wait()

            # Capture and log ffmpeg output
            stdout, stderr = process.communicate()
            print("[DEBUG] ffmpeg stdout:\n", stdout)
            print("[DEBUG] ffmpeg stderr:\n", stderr)

        except Exception as e:
            print(f"[ERROR] Error during download: {e}")
        finally:
            if os.path.exists(output_file):
                print("[INFO] Ensuring ffmpeg process has released the file.")
                time.sleep(1)  # Ensure the file is released before accessing it
            else:
                print("[WARNING] Downloaded file not found or empty.")


    # Spawn the thread for ffmpeg
    download_thread = threading.Thread(target=run_ffmpeg)
    download_thread.start()
    return download_thread


def validate_url(url):
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code == 200:
            print("[INFO] URL is valid and accessible.")
            return True
        else:
            print(f"[WARNING] URL validation failed with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] URL validation error: {e}")
        return False


def process_live_stream(youtube):
    """Continuously processes the live stream audio."""
    stream_url = get_live_stream_info(youtube)
    if not stream_url:
        print("[INFO] Falling back to yt-dlp to fetch stream URL.")
        stream_url = get_stream_url_with_ytdlp(f"https://www.youtube.com/watch?v={video_id}")

    if stream_url:
        print(f"[INFO] Live stream URL found: {stream_url}")
        while not stop_event.is_set():
            try:
                # File paths
                downloaded_file = "temp_audio_segment_converted.wav"
                pcm_file = "fixed_audio.wav"

                # Remove previous files
                if os.path.exists(downloaded_file):
                    os.remove(downloaded_file)
                if os.path.exists(pcm_file):
                    os.remove(pcm_file)

                # Download and convert HLS stream
                print("[DEBUG] Starting segment download...")
                download_thread = download_hls(stream_url, downloaded_file, stop_event)

                # Wait for the download thread to complete
                download_thread.join(timeout=30)

                # Convert to PCM WAV format
                if os.path.exists(downloaded_file):
                    converted_file = convert_to_pcm_wav(downloaded_file, pcm_file)
                    if converted_file:
                        # Transcribe PCM WAV
                        transcribed_text = transcribe_with_sr(converted_file)
                        print(f"[INFO] Transcribed text: {transcribed_text}")
                    else:
                        print("[WARNING] Conversion to PCM WAV failed. Skipping this segment.")
                else:
                    print("[WARNING] Downloaded file not found or empty.")

            except Exception as e:
                print(f"[ERROR] Error processing live stream: {e}")
    else:
        print("[ERROR] Could not retrieve live stream URL.")


def reader():
    """Reader thread to handle live stream processing."""
    try:
        print("[INFO] Reader attempting to authenticate...")
        credentials = get_credentials("rajeev.india@gmail.com")
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

        live_chat_id = get_live_chat_id(youtube)  # Fetch Live Chat ID
        if not live_chat_id:
            print("[ERROR] Live Chat ID could not be fetched. Exiting Reader.")
            stop_event.set()
            return

        print(f"[SUCCESS] Reader authenticated. Live Chat ID: {live_chat_id}")
        auth_event.set()  # Signal that the reader is authenticated

        process_live_stream(youtube)  # Start processing the live stream
    except Exception as e:
        print(f"[ERROR] Error in reader: {e}")
        stop_event.set()

def main():
    """Main function to start threads."""
    global stop_event

    threads = [

        threading.Thread(target=reader)

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
