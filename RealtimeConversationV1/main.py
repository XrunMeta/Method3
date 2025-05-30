import os
import time
import threading
import tempfile
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio
from clonevoice_api import synthesize, normalize_language, upload_voice_file
from voice_to_gpt import read_api_key, read_init_prompt, generate_gpt_response, transcribe_audio, record_audio_vad
import openai

# === Setup ===
openai.api_key = read_api_key()
system_prompt = read_init_prompt()
playing_audio = None
play_lock = threading.Lock()

# === Playback with interruption ===
def play_audio(file_path):
    global playing_audio
    try:
        sound = AudioSegment.from_wav(file_path)
        with play_lock:
            if playing_audio:
                playing_audio.stop()
            playing_audio = _play_with_simpleaudio(sound)
        playing_audio.wait_done()
    except Exception as e:
        print(f"Error playing audio: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# === Full conversation loop ===
def conversation_loop(language, speed, voice_sample_path, model=""):
    print("🎤 Voice conversation started. Press Ctrl+C to stop.")
    try:
        while True:
            print("\n--- Waiting for user voice input ---")
            audio_path = record_audio_vad()
            if not audio_path:
                print("⏭️ No speech detected. Try again.")
                continue

            print("🔠 Transcribing...")
            user_text = transcribe_audio(audio_path)
            print("📝 You said:", user_text)

            print("🤖 Getting GPT response...")
            gpt_reply = generate_gpt_response(system_prompt, user_text)
            print("💬 GPT:", gpt_reply)

            print("🧬 Synthesizing voice...")
            synthesize(gpt_reply, language, speed, voice_sample_path, model)

            output_dir = "output"
            wav_files = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".wav")],
                               key=os.path.getmtime)
            if not wav_files:
                print("❌ No audio file generated.")
                continue

            wav_to_play = wav_files[-1]
            print(f"🔊 Playing: {wav_to_play}")

            threading.Thread(target=play_audio, args=(wav_to_play,), daemon=True).start()
            time.sleep(0.5)  # Slight delay to allow new playback before listening again
    except KeyboardInterrupt:
        print("\n🛑 Conversation ended by user.")

# === Run ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice GPT Conversation with Cloned TTS")
    parser.add_argument("--language", type=str, required=True, help="Language (e.g., 'english')")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (e.g., 1.0)")
    parser.add_argument("--voice", type=str, required=True, help="Voice sample file path")
    parser.add_argument("--model", type=str, default="", help="Optional voice model")
    args = parser.parse_args()

    conversation_loop(args.language, args.speed, args.voice, args.model)
