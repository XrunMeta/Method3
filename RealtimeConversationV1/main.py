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
from voice_to_gpt import read_api_key, read_init_prompt, generate_gpt_response, transcribe_audio, record_audio_vad, generate_speechrecognition_tts
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
import time  # Ensure this is imported at the top

<<<<<<< HEAD
def conversation_loop(language, speed, voice_sample_path, model="", tts_mode="cv"):
=======
def conversation_loop(language, speed, voice_sample_path, model="", tts_mode="cv", transcriber="gpt-whisper1"):

>>>>>>> 6-search-faster-transcribe-method
    print("🎤 Voice conversation started. Press Ctrl+C to stop.")
    try:
        while True:
            print("\n--- Waiting for user voice input ---")
            audio_path = record_audio_vad()
            if not audio_path:
                print("⏭️ No speech detected. Try again.")
                continue

            latency_start = time.time()  # ⏱️ Start timing after speech ends
<<<<<<< HEAD

            # Transcription
            t0 = time.time()
            print("🔠 Transcribing...")
            user_text = transcribe_audio(audio_path)
            print("📝 You said:", user_text)
            t1 = time.time()
            print(f"⏱️ Transcription latency: {t1 - t0:.2f} sec")

=======

            # Transcription
            t0 = time.time()
            print("🔠 Transcribing...")
            user_text = transcribe_audio(audio_path, transcriber)
            print("📝 You said:", user_text)
            t1 = time.time()
            print(f"⏱️ Transcription latency: {t1 - t0:.2f} sec")

>>>>>>> 6-search-faster-transcribe-method
            # GPT Response
            t0 = time.time()
            print("🤖 Getting GPT response...")
            gpt_reply = generate_gpt_response(system_prompt, user_text)
            print("💬 GPT:", gpt_reply)
            t1 = time.time()
            print(f"⏱️ GPT generation latency: {t1 - t0:.2f} sec")

            # TTS
            if tts_mode == "no":
                print(f"⏱️ Total latency (no TTS): {time.time() - latency_start:.2f} sec")
                continue

            t0 = time.time()
            if tts_mode == "cv":
                print("🧬 Synthesizing voice using CloneVoice...")
                synthesize(gpt_reply, language, speed, voice_sample_path, model)
                output_dir = "output"
                wav_files = sorted(
                    [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".wav")],
                    key=os.path.getmtime
                )
                if not wav_files:
                    print("❌ No audio file generated.")
                    continue
                wav_to_play = wav_files[-1]

            elif tts_mode == "sr":
                print("🗣️ Synthesizing with SpeechRecognition TTS...")
                wav_to_play = generate_speechrecognition_tts(gpt_reply)
                if not wav_to_play or not os.path.exists(wav_to_play):
                    print("❌ Failed to generate TTS.")
                    continue
            else:
                print(f"⚠️ Unknown TTS mode: {tts_mode}")
                continue
            t1 = time.time()
            print(f"⏱️ TTS synthesis latency: {t1 - t0:.2f} sec")

            print(f"⏱️ Total latency from end of speech to ready-to-play: {time.time() - latency_start:.2f} sec")

            print(f"🔊 Playing: {wav_to_play}")
            threading.Thread(target=play_audio, args=(wav_to_play,), daemon=True).start()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n🛑 Conversation ended by user.")

# === Run ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice GPT Conversation with TTS")
    parser.add_argument("--language", type=str, required=True, help="Language (e.g., 'english')")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (e.g., 1.0)")
    parser.add_argument("--voice", type=str, help="Voice sample file path (required if --tts=cv)")
    parser.add_argument("--model", type=str, default="", help="Optional voice model")
    parser.add_argument("--tts", type=str, choices=["no", "cv", "sr"], default="cv",
                        help="TTS mode: 'no' (text only), 'cv' (CloneVoice), 'sr' (SpeechRecognition/pyttsx3)")
<<<<<<< HEAD
=======
    parser.add_argument("--transcriber", type=str, choices=["gpt-4o", "gpt-4o-mini", "gpt-whisper1", "faster-whisper"], default="gpt-whisper1",
                    help="Transcription engine to use.")

>>>>>>> 6-search-faster-transcribe-method

    args = parser.parse_args()

    # Manual validation
    if args.tts == "cv" and not args.voice:
        parser.error("--voice is required when --tts=cv")

<<<<<<< HEAD
    conversation_loop(args.language, args.speed, args.voice, args.model, args.tts)
=======
    conversation_loop(args.language, args.speed, args.voice, args.model, args.tts, args.transcriber)
>>>>>>> 6-search-faster-transcribe-method
