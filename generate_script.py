
import os
import json
import sys
import subprocess
import urllib.request
import urllib.error

API_KEY = os.environ.get("SKRIPTA_KEY")

if not API_KEY:
    raise RuntimeError("SKRIPTA_KEY nije pronađen.")

MODEL = "gemini-3.5-flash-lite"
VOICE = "en_US-lessac-medium"

prompt = """
You are the official scriptwriter for MIND FORGE.

Create one original English YouTube Shorts narration.

Topic: A fascinating fact about human psychology.

Requirements:
- 45 to 60 seconds when spoken.
- Powerful opening hook.
- Simple natural English.
- Interesting and informative.
- No invented statistics.
- Memorable ending.

Return only the spoken narration.
"""

url = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent?key={API_KEY}"
)

data = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "temperature": 0.8,
        "maxOutputTokens": 700
    }
}

request = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    script = result["candidates"][0]["content"]["parts"][0]["text"]

    with open("script.txt", "w", encoding="utf-8") as file:
        file.write(script)

    print("1. SCRIPT GENERATED!")

    print("2. DOWNLOADING PIPER VOICE...")
    subprocess.run(
        [sys.executable, "-m", "piper.download_voices", VOICE],
        check=True
    )

    print("3. GENERATING AUDIO...")
    subprocess.run(
        [
            sys.executable, "-m", "piper",
            "-m", VOICE,
            "-f", "voice.wav",
            "--", script
        ],
        check=True
    )

    print("4. MIND FORGE AUDIO GENERATED!")
    
except urllib.error.HTTPError as error:
    print("GEMINI HTTP ERROR:", error.code)
    print(error.read().decode("utf-8", errors="replace"))
    raise

except Exception as error:
    print("ERROR:", repr(error))
    raise
