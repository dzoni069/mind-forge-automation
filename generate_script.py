
import os
import json
import urllib.request
import urllib.error

API_KEY = os.environ["SKRPITA_API"]
MODEL = "gemini-2.5-flash"

prompt = """
You are the creative scriptwriter for MIND FORGE.

Brand slogan: KNOW MORE. THINK BIGGER.

Create one original YouTube Shorts script in English.
Topic: A surprising psychological fact about human behavior.

Requirements:
- 45 to 60 seconds when spoken.
- Start with a powerful hook.
- Use simple, natural English.
- Keep viewers curious.
- Include useful, interesting information.
- End with a memorable sentence.
- No fake facts or unsupported statistics.

Return only the spoken narration, without headings,
camera directions or explanations.
"""

url = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent?key={API_KEY}"
)

data = {
    "contents": [
        {"parts": [{"text": prompt}]}
    ],
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

with urllib.request.urlopen(request, timeout=60) as response:
    result = json.loads(response.read().decode("utf-8"))

script = result["candidates"][0]["content"]["parts"][0]["text"]

with open("script.txt", "w", encoding="utf-8") as file:
    file.write(script)

print("MIND FORGE SCRIPT GENERATED!")
print(script)
