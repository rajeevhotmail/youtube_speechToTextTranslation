import asyncio
import subprocess
import os
import speech_recognition as sr
import requests


# Number of rotating files to use
NUM_FILES = 4
file_paths = [f"segment_{i}.wav" for i in range(NUM_FILES)]


async def download_segment(hls_url, output_file, segment_duration=5):
    """
    Download a segment of the live stream using ffmpeg.
    """
    command = [
        "ffmpeg",
        "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-i", hls_url,
        "-t", str(segment_duration),  # Duration of each segment
        "-acodec", "pcm_s16le",  # PCM WAV format
        "-ar", "16000",  # 16 kHz sample rate
        output_file
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        print(f"[ERROR] Download failed: {stderr.decode().strip()}")
    else:
        print(f"[INFO] Downloaded segment to {output_file}")


async def transcribe_segment(output_file):
    """
    Transcribe the audio segment using Google SpeechRecognition.
    """
    recognizer = sr.Recognizer()
    if os.path.exists(output_file):
        try:
            with sr.AudioFile(output_file) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="hi-IN")
            print(f"[LIVE TRANSCRIPTION] {text}")
        except sr.UnknownValueError:
            print("[WARNING] Could not understand audio.")
        except sr.RequestError as e:
            print(f"[ERROR] Google SpeechRecognition API error: {e}")
    else:
        print(f"[WARNING] File {output_file} does not exist for transcription.")


async def live_transcription(hls_url):
    """
    Coordinate downloading and transcribing audio in real-time.
    """
    index = 0
    while True:
        current_file = file_paths[index % NUM_FILES]
        index += 1

        # Download and transcribe concurrently
        await asyncio.gather(
            download_segment(hls_url, current_file),
            transcribe_segment(current_file)
        )


if __name__ == "__main__":
    # Replace with your HLS live stream URL
    response = requests.get("https://api.streamingplatform.com/get_stream_url?video_id=pmh4XOy8KMk")
    data = response.json()
    hls_url = data.get("hls_url")
    print(f"HLS URL: {hls_url}")

    try:
        asyncio.run(live_transcription(hls_url))
    except KeyboardInterrupt:
        print("\n[INFO] Live transcription stopped by user.")
