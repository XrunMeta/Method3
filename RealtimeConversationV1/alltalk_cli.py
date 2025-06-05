import argparse
import requests

def generate_tts_form_api(
    text_input, character_voice, narrator_voice, narrator_enabled, output_file,
    timestamp=True, language="en", autoplay=True, autoplay_volume=0.8
):
    url = "http://127.0.0.1:7851/api/tts-generate"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "text_input": text_input,
        "text_filtering": "none", #none, standard, html
        "character_voice_gen": character_voice,
        "narrator_enabled": str(narrator_enabled).lower(),
        "narrator_voice_gen": narrator_voice or character_voice,
        "text_not_inside": "character",
        "language": language,
        "output_file_name": output_file,
        "output_file_timestamp": str(timestamp).lower(),
        "autoplay": str(autoplay).lower(),
        "autoplay_volume": str(autoplay_volume)
    }

    # 👇 Debug: print full link-style payload
    query_string = "&".join(f"{k}={str(v)}" for k, v in payload.items())
    debug_url = f"{url}?{query_string}"
    print(f"\nAllTalk API POST payload:\n{debug_url}\n")


    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        print("[✔] TTS generation succeeded.")
        #print(response.text)
        result = response.json()
        print(result)
        return result.get("output_file_path")
    except requests.RequestException as e:
        print(f"[✘] TTS generation failed: {e}")
        print(f"[DEBUG] Response ({getattr(e.response, 'status_code', '?')}): {getattr(e.response, 'text', '?')}")
        return ""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AllTalk CLI (Form-Encoded POST)")
    parser.add_argument("--text", required=True, help="Input text for TTS")
    parser.add_argument("--character_voice", required=True, help="Voice file name for character (e.g., female_01.wav)")
    parser.add_argument("--narrator_voice", default="male_01.wav", help="Voice file for narrator")
    parser.add_argument("--narrator", action="store_true", help="Enable narrator voice")
    parser.add_argument("--output", default="output", help="Base name for output file (timestamp added automatically)")
    args = parser.parse_args()

    generate_tts_form_api(
        text_input=args.text,
        character_voice=args.character_voice,
        narrator_voice=args.narrator_voice,
        narrator_enabled=args.narrator,
        output_file=args.output
    )
