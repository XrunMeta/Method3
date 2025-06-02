import os
import time
import glob
import openai
import numpy as np
import tempfile
import sounddevice as sd
from scipy.io.wavfile import write
from silero_vad import load_silero_vad, get_speech_timestamps, read_audio
import openai
from openai import OpenAI
import requests
import shutil
import hashlib
import pyttsx3

# === Paths ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(SCRIPT_DIR, "key.txt")
INIT_PROMPT_FILE = os.path.join(SCRIPT_DIR, "InitPrompt.txt")
RESULT_DIR = os.path.join(SCRIPT_DIR, "result")
FILENAME_PREFIX = "generated"

# === Settings ===
SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_TIMEOUT = 0.5  # seconds
USE_VAD = True #voice activity detection
VAD_MODEL = load_silero_vad()

# === API Setup ===
def read_api_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    else:
        raise FileNotFoundError(f"API key file '{KEY_FILE}' not found.")

# === Init Prompt ===
def read_init_prompt():
    if os.path.exists(INIT_PROMPT_FILE):
        with open(INIT_PROMPT_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# === Folder Setup ===
def clean_result_folder():
    if not os.path.exists(RESULT_DIR):
        os.makedirs(RESULT_DIR)
    else:
        for file in glob.glob(os.path.join(RESULT_DIR, f"{FILENAME_PREFIX}*.txt")):
            os.remove(file)

def get_next_filename():
    existing = glob.glob(os.path.join(RESULT_DIR, f"{FILENAME_PREFIX}*.txt"))
    suffix = len(existing) + 1
    return os.path.join(RESULT_DIR, f"{FILENAME_PREFIX}{suffix}.txt")

# === VAD-based Recording ===
def record_audio_vad():
    print("🔴 Recording... Speak now!")

    chunk_duration = 0.03
    chunk_samples = int(SAMPLE_RATE * chunk_duration)
    silence_timeout = SILENCE_TIMEOUT
    max_silence_chunks = int(silence_timeout / chunk_duration)

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    stream.start()

    recorded = []
    audio_buffer = []
    silence_counter = 0
    speech_detected = False

    try:
        while True:
            chunk, _ = stream.read(chunk_samples)
            chunk_float = chunk.astype(np.float32).flatten() / 32768.0
            recorded.append(chunk.copy())
            audio_buffer.extend(chunk_float)

            # Trim buffer
            max_buffer_size = int(SAMPLE_RATE * 1.5)
            if len(audio_buffer) > max_buffer_size:
                audio_buffer = audio_buffer[-max_buffer_size:]

            timestamps = get_speech_timestamps(np.array(audio_buffer), VAD_MODEL, sampling_rate=SAMPLE_RATE)
            if timestamps:
                silence_counter = 0
                if not speech_detected:
                    print("🔊 Speech detected...")
                speech_detected = True
            else:
                if speech_detected:
                    silence_counter += 1

            if speech_detected and silence_counter > max_silence_chunks:
                print("🛑 Silence detected. Stopping...")
                break
    finally:
        stream.stop()

    if not speech_detected:
        print("🔇 No speech detected.")
        return None

    audio = np.concatenate(recorded)
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    write(tmp_wav.name, SAMPLE_RATE, audio)
    return tmp_wav.name

# === Transcription ===
def transcribe_audio(file_path):
    with open(file_path, "rb") as f:
        transcription = openai.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=f,
            response_format="text"
        )
    return transcription

# === GPT Call with System/User Prompt ===
def generate_gpt_response(system_prompt, user_prompt):
    client = OpenAI(api_key=openai.api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini", # gpt-4o-mini gpt-4o
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def generate_gpt_response_audio(system_prompt, user_prompt, output_path=None, voice_model="YourModelName", clone_server="http://127.0.0.1:9988"):
    client = OpenAI(api_key=openai.api_key)

    # === 1. Generate GPT text response ===
    chat_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    gpt_reply = chat_response.choices[0].message.content.strip()
    print("💬 GPT text response:", gpt_reply)

    # === 2. Generate TTS audio with GPT's voice ===
    speech_response = client.audio.speech.create(
        model="tts-1",
        voice="onyx",  # Use any of the available voices: alloy, echo, fable, onyx, nova, shimmer
        input=gpt_reply,
        response_format="mp3"
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
        tmp_mp3.write(speech_response.content)
        tmp_mp3_path = tmp_mp3.name

    # === 3. Convert to WAV for STS input ===
    tmp_wav_path = tmp_mp3_path.replace(".mp3", ".wav")
    os.system(f'ffmpeg -hide_banner -loglevel error -y -i "{tmp_mp3_path}" "{tmp_wav_path}"')

    # === 4. Upload WAV to CloneVoice server ===
    upload_resp = requests.post(
        f"{clone_server}/upload",
        files={"audio": open(tmp_wav_path, "rb")},
        data={"save_dir": "ttslist"}
    )
    upload_result = upload_resp.json()
    if upload_result.get("code") != 0:
        raise Exception(f"Upload failed: {upload_result}")

    uploaded_name = upload_result["data"]

    # === 5. Trigger STS cloning ===
    sts_payload = {
        "voice": voice_model,
        "name": uploaded_name
    }
    sts_resp = requests.post(f"{clone_server}/sts", data=sts_payload)
    sts_result = sts_resp.json()
    if sts_result.get("code") != 0:
        raise Exception(f"Voice cloning failed: {sts_result}")

    cloned_path = sts_result["filename"]
    print("🧬 Cloned voice file:", cloned_path)

    # === 6. Copy to desired output path ===
    if output_path is None:
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    shutil.copyfile(cloned_path, output_path)

    return output_path

def generate_speechrecognition_tts(text):
    try:
        engine = pyttsx3.init()
        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        engine.save_to_file(text, tmp_wav.name)
        engine.runAndWait()
        return tmp_wav.name
    except Exception as e:
        print(f"pyttsx3 TTS failed: {e}")
        return None


# === Main Loop ===
def main():
    openai.api_key = read_api_key()
    clean_result_folder()
    system_prompt = read_init_prompt()

    while True:
        if USE_VAD:
            audio_path = record_audio_vad()
            if not audio_path:
                print("⏭️ No speech detected. Listening again...\n")
                continue
        else:
            print("Fallback fixed-duration not implemented in this version.")
            break

        user_input = transcribe_audio(audio_path)
        print("📝 You said:", user_input)

        output = generate_gpt_response(system_prompt, user_input)
        print("🤖 GPT says:", output)

        output_file = get_next_filename()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)

        print("\n--- Listening again ---\n")
        time.sleep(1)

if __name__ == "__main__":
    main()
