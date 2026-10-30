
import os
import json
import urllib.request
import urllib.error

API_KEY = os.environ.get("SKRIPTA_KEY")

if not API_KEY:
    raise RuntimeError("SKRIPTA_KEY nije pronađen u GitHub Secrets.")

MODEL = "gemini-3.5-flash-lite"
prompt = """
You are the official scriptwriter for MIND FORGE.

Brand slogan: KNOW MORE. THINK BIGGER.

Create one original English YouTube Shorts narration.

Topic: A surprising psychological fact about human behavior.

Requirements:
- 45 to 60 seconds when spoken.
- Start with a powerful hook.
- Use simple, natural English.
- Keep viewers curious.
- Provide interesting and useful information.
- Do not invent facts or statistics.
- End with a memorable sentence.

Return only the spoken narration.
No headings or explanations.
"""

url = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent?key={API_KEY}"
)

data = {
    "contents": [
        {
            "parts": [
                {"text": prompt}
            ]
        }
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

try:
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini nije vratio scenario: " + json.dumps(result)
        )

    script = candidates[0]["content"]["parts"][0]["text"]

    with open("script.txt", "w", encoding="utf-8") as file:
        file.write(script)

    print("MIND FORGE SCRIPT GENERATED!")
    print(script)

except urllib.error.HTTPError as error:
    print("HTTP ERROR:", error.code)
    print(error.read().decode("utf-8", errors="replace"))
    raise

except Exception as error:
    print("ERROR:", repr(error))
    raise
