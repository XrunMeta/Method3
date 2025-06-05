import os
import time
import threading
import tempfile
import sounddevice as sd
import soundfile as sf
import numpy as np
import shutil
from scipy.io.wavfile import write
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio
from clonevoice_api import synthesize, normalize_language, upload_voice_file
from alltalk_cli import generate_tts_form_api
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

    ''' # Clean generated after playback
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    '''
def play_audio_sd(file_path):
    try:
        abs_path = os.path.abspath(file_path)
        print(f"[🔈] Playing via sounddevice: {abs_path}")
        data, samplerate = sf.read(abs_path, dtype='float32')
        sd.play(data, samplerate)
        sd.wait()
    except Exception as e:
        print(f"❌ Error during sounddevice playback: {e}")

# === Full conversation loop ===
def conversation_loop(language, speed, voice_sample_path, model="", tts_mode="cv", transcriber="gpt-whisper1",
                      narrator_enabled=False, narrator_voice="male_01.wav"):

    print("🎤 Voice conversation started. Press Ctrl+C to stop.")
    try:
        while True:
            print("\n--- Waiting for user voice input ---")
            audio_path = record_audio_vad()
            if not audio_path:
                print("⏭️ No speech detected. Try again.")
                continue

            latency_start = time.time()  # ⏱️ Start timing after speech ends

            # Transcription
            t0 = time.time()
            print("🔠 Transcribing...")
            user_text = transcribe_audio(audio_path, transcriber)
            print("📝 You said:", user_text)
            t1 = time.time()
            print(f"⏱️ Transcription latency: {t1 - t0:.2f} sec")

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
                print("🧜‍♂️ Synthesizing voice using CloneVoice...")
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

            elif tts_mode == "at":
                print("🗣️ Synthesizing with AllTalk TTS...")
                base_name = f"output_{int(time.time())}"
                """
                generate_tts_form_api(
                    text_input=gpt_reply,
                    character_voice=voice_sample_path,
                    narrator_voice="",                 # Don't pass narrator voice if disabled
                    narrator_enabled=False,
                    output_file=base_name,
                    timestamp=False,
                    autoplay=False
                )
                wav_to_play = f"{base_name}.wav"
                """
                wav_original = generate_tts_form_api(
                    text_input=gpt_reply,
                    character_voice=voice_sample_path,
                    narrator_voice=voice_sample_path,
                    narrator_enabled=False,
                    language=language,
                    output_file=base_name,
                    timestamp=True,
                    autoplay=False
                )

                if not wav_original or not os.path.exists(wav_original):
                    print("❌ Failed to generate TTS with AllTalk.")
                    continue

                # Move file from AllTalk output to our app's output directory
                safe_output_dir = "output"
                os.makedirs(safe_output_dir, exist_ok=True)
                wav_to_play = os.path.join(safe_output_dir, os.path.basename(wav_original))

                try:
                    shutil.move(wav_original, wav_to_play)
                    print(f"📂 Moved audio to {wav_to_play}")
                except Exception as e:
                    print(f"⚠️ Failed to move file: {e}")
                    wav_to_play = wav_original  # fallback just in case
                


            else:
                print(f"⚠️ Unknown TTS mode: {tts_mode}")
                continue
            t1 = time.time()
            print(f"⏱️ TTS synthesis latency: {t1 - t0:.2f} sec")

            print(f"⏱️ Total latency from end of speech to ready-to-play: {time.time() - latency_start:.2f} sec")

            print(f"🔊 Playing: {wav_to_play}")
            if tts_mode == "at":
                # Use sounddevice for AllTalk playback
                threading.Thread(target=play_audio_sd, args=(wav_to_play,), daemon=True).start()
            else:
                # Use pydub for other TTS modes
                threading.Thread(target=play_audio, args=(wav_to_play,), daemon=True).start()
            #play_audio(wav_to_play)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n🛌 Conversation ended by user.")

# === Run ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice GPT Conversation with TTS")
    parser.add_argument("--language", type=str, required=True, help="Language (e.g., 'english')")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (e.g., 1.0)")
    parser.add_argument("--voice", type=str, help="Voice sample file path (used for CloneVoice and AllTalk)")
    parser.add_argument("--model", type=str, default="", help="Optional voice model")
    parser.add_argument("--tts", type=str, choices=["no", "cv", "sr", "at"], default="cv",
                        help="TTS mode: 'no' (text only), 'cv' (CloneVoice), 'sr' (SpeechRecognition/pyttsx3), 'at' (AllTalk)")
    parser.add_argument("--transcriber", type=str, choices=["gpt-4o", "gpt-4o-mini", "gpt-whisper1", "faster-whisper"], default="gpt-whisper1",
                        help="Transcription engine to use.")

    args = parser.parse_args()

    if args.tts in ["cv", "at"] and not args.voice:
        parser.error("--voice is required when --tts=cv or --tts=at")

    conversation_loop(
        language=args.language,
        speed=args.speed,
        voice_sample_path=args.voice,
        model=args.model,
        tts_mode=args.tts,
        transcriber=args.transcriber,
        narrator_enabled=False,
        narrator_voice=args.voice
    )
