import speech_recognition as sr

recognizer = sr.Recognizer()
microphone_list = sr.Microphone.list_microphone_names()

for index, name in enumerate(microphone_list):
    print(f"Index: {index}, Device: {name}")

try:
    with sr.Microphone(device_index=1) as source:  # Replace 24 with your correct index
        print("Using device:", microphone_list[1])
        audio = recognizer.listen(source)
        # Further processing of audio
        print("Audio captured successfully.")
except Exception as e:
    print(f"An error occurred: {e}")
