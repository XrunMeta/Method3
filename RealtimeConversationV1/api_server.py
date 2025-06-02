from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from clonevoice_api import synthesize
from voice_to_gpt import generate_gpt_response, transcribe_audio, record_audio_vad, read_api_key, read_init_prompt
import os
import tempfile
import uuid

app = FastAPI()

openai_api_key = read_api_key()
system_prompt = read_init_prompt()

@app.post("/talk/")
async def talk(
    voice_sample: UploadFile = File(...),
    language: str = Form(...),
    speed: float = Form(1.0),
    model: str = Form("")
):
    # Save uploaded voice sample
    voice_sample_path = f"/tmp/{uuid.uuid4()}_{voice_sample.filename}"
    with open(voice_sample_path, "wb") as f:
        f.write(await voice_sample.read())

    # Record user input (or optionally accept pre-recorded file)
    user_audio_path = record_audio_vad()

    if not user_audio_path:
        return {"error": "No speech detected."}

    user_text = transcribe_audio(user_audio_path)
    gpt_reply = generate_gpt_response(system_prompt, user_text)

    synthesize(gpt_reply, language, speed, voice_sample_path, model)

    # Find latest output .wav
    output_dir = "output"
    wav_files = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".wav")],
                       key=os.path.getmtime)

    if not wav_files:
        return {"error": "No audio generated"}

    latest_wav = wav_files[-1]

    return FileResponse(latest_wav, media_type="audio/wav", filename="response.wav")
