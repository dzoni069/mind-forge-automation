#!/usr/bin/env python3
"""Create one researched, hook-led MIND FORGE AI Short and its video bundle."""

from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from PIL import Image, ImageDraw, ImageFilter, ImageFont


API_KEY = os.environ.get("SKRIPTA_KEY", "").strip()
SEARCH_MODEL = "gemini-3.5-flash-lite"
VOICE_MODEL = "gemini-3.8-flash-lite-tts"
VOICE_NAME = "Achird"
WIDTH, HEIGHT = 720, 1280
SCENE_COUNT = 8
OUT = Path("output")
SCENE_DIR = OUT / "scenes"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PALETTES = [
    ((7, 12, 31), (27, 45, 105), (0, 214, 255)),
    ((15, 8, 38), (77, 24, 106), (255, 71, 180)),
    ((4, 24, 38), (15, 91, 105), (47, 237, 190)),
    ((24, 13, 35), (111, 47, 58), (255, 177, 66)),
    ((10, 17, 43), (38, 47, 122), (138, 126, 255)),
    ((12, 25, 35), (30, 82, 91), (255, 112, 92)),
    ((21, 11, 43), (67, 38, 124), (255, 204, 85)),
    ((5, 24, 32), (13, 79, 87), (87, 232, 255)),
]


def http_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"Gemini API returned HTTP {error.code}: {details[:1200]}") from error
        except urllib.error.URLError as error:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"Could not reach the Gemini API: {error.reason}") from error
    raise RuntimeError("The Gemini API did not respond after three attempts.")


def get_candidate_text(response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    candidates = response.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no story. Run the workflow again in a few minutes.")
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not text.strip():
        raise RuntimeError("Gemini returned an empty story.")
    return text.strip(), candidate


def parse_story(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    try:
        story = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("The story response was not valid JSON. Run the workflow again.")
        try:
            story = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as error:
            raise RuntimeError("The story response was not valid JSON. Run the workflow again.") from error

    for field in ("topic", "title", "hook", "narration"):
        if not isinstance(story.get(field), str) or not story[field].strip():
            raise RuntimeError(f"The story response is missing: {field}")

    word_count = len(story["narration"].split())
    if not 90 <= word_count <= 165:
        raise RuntimeError(
            f"The narration has {word_count} words. It needs 90–165 words for a short video; run again."
        )
    return story


def fetch_news_candidates() -> list[dict[str, Any]]:
    query = 'AI OR "artificial intelligence" when:7d'
    params = urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    url = f"https://news.google.com/rss/search?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "MIND-FORGE/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            root = ET.fromstring(response.read())
    except (urllib.error.URLError, ET.ParseError) as error:
        raise RuntimeError(f"Could not load recent AI headlines: {error}") from error

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link or title.lower() in seen:
            continue
        seen.add(title.lower())
        source = item.find("source")
        source_name = (source.text or "News source").strip() if source is not None else "News source"
        raw_summary = item.findtext("description") or ""
        summary = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", raw_summary))).strip()
        candidates.append(
            {
                "id": len(candidates) + 1,
                "title": title,
                "source": source_name,
                "published": (item.findtext("pubDate") or "").strip(),
                "summary": summary[:420],
                "url": link,
            }
        )
        if len(candidates) >= 18:
            break

    if len(candidates) < 4:
        raise RuntimeError("The news feed returned too few recent AI stories. Try again later.")
    return candidates


def choose_story(api_key: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    now = datetime.now(timezone.utc)
    hour = now.hour
    if 6 <= hour < 11:
        slot = "visual surprises, strange AI creations, and consumer tools"
    elif 11 <= hour < 16:
        slot = "family, school, online safety, scams, and everyday life"
    else:
        slot = "work, money, creativity, and how AI changes ordinary jobs"

    news = fetch_news_candidates()
    news_json = json.dumps(news, ensure_ascii=False, indent=2)
    prompt = f"""You are the story editor for MIND FORGE, a short-video channel about AI.
Today's UTC date is {now.strftime('%Y-%m-%d')}. The JSON list below contains recent AI headlines and snippets from Google News RSS. Today's content angle is: {slot}.

Choose the supplied story with the strongest broad short-video potential. Judge potential by: an instantly understandable hook, surprise or curiosity, a real human consequence, relevance to teenagers and adults including older viewers, and visuals that can be shown in a phone-sized video. Prefer stories that people would share with family or friends. A trend is not automatically a good story. If the same development appears in several headlines, that is a useful signal of wider coverage.

Use only facts supported by the supplied headlines and snippets. Do not add details that are not in the feed. Do not claim a story is viral or widely shared; this feed does not provide social-media view counts. Do not invent statistics, quotes, dates, product abilities, or consequences. Avoid partisan campaigning, graphic harm, and fearbait. Explain technical ideas in plain English. If a detail is uncertain, leave it out.

Create one original English narration for a 45–60 second vertical video. Aim for 110–140 spoken words. Structure: a punchy first-sentence hook; quick context; one surprising but verified detail; why it matters to ordinary people; a useful takeaway; a natural question that invites real comments. Avoid generic openings like “You won't believe this.” Do not repeat the headline word for word.

Return only one valid JSON object with these fields:
{{
  "topic": "the story in one sentence",
  "title": "short video title, maximum 8 words",
  "hook": "the first spoken sentence",
  "narration": "spoken narration only, 110–140 words",
  "scenes": [
    {{"label": "2–5 word on-screen phrase", "visual": "a simple visual idea such as a phone, family, robot, shield, video, or workplace"}}
  ],
  "viral_angle": "why a broad audience may watch or share this, without claiming guaranteed virality",
  "source_ids": [1, 2]
}}
Choose source_ids only from the supplied list. Provide exactly 8 scene entries. Use English throughout. The narration must contain only words meant to be spoken; do not include source notes or stage directions.

Recent story candidates:
{news_json}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{SEARCH_MODEL}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 2600},
    }
    response = http_json(url, api_key, payload)
    text, _candidate = get_candidate_text(response)
    story = parse_story(text)
    source_ids = story.get("source_ids", [])
    selected_ids: set[int] = set()
    if isinstance(source_ids, list):
        for value in source_ids:
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                continue
    selected = [item for item in news if item["id"] in selected_ids]
    if not selected:
        topic_words = set(re.findall(r"[a-z]{4,}", story["topic"].lower()))
        ranked = sorted(
            news,
            key=lambda item: len(
                topic_words
                & set(re.findall(r"[a-z]{4,}", f"{item['title']} {item['summary']}".lower()))
            ),
            reverse=True,
        )
        selected = ranked[:2]
    sources = [
        {"title": f"{item['source']}: {item['title']}", "url": item["url"]}
        for item in selected[:4]
    ]
    story["sources"] = sources
    story["news_candidates"] = news
    story["created_utc"] = now.isoformat(timespec="seconds")
    return story, sources


def make_voice(api_key: str, narration: str, destination: Path) -> None:
    payload = {
        "model": VOICE_MODEL,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": narration,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": (
                                    "Natural, warm, modern conversational narration, like a friendly voice assistant "
                                    "speaking clearly to one person. Sound curious and lively on the opening hook, "
                                    "then calm, confident, and human. Use natural short pauses and an easy-to-follow "
                                    "pace. Adult voice, neutral English accent. Not a commercial, not a movie trailer."
                                ),
                            }
                        ],
                    }
                ],
            }
        ],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": VOICE_NAME}]},
    }
    response = http_json("https://generativelanguage.googleapis.com/v1beta/interactions", api_key, payload)
    audio_data = None
    for step in response.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            if content.get("type") == "audio" and content.get("data"):
                audio_data = content["data"]
    if not audio_data:
        raise RuntimeError("Gemini TTS returned no audio data.")
    destination.write_bytes(base64.b64decode(audio_data))


def wrap_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3]


def icon_kind(scene: dict[str, str], topic: str) -> str:
    words = f"{scene.get('label', '')} {scene.get('visual', '')} {topic}".lower()
    if any(word in words for word in ("phone", "voice", "call", "scam", "deepfake", "fake video", "camera", "social")):
        return "phone"
    if any(word in words for word in ("family", "child", "kid", "school", "parent", "teen", "friend")):
        return "family"
    if any(word in words for word in ("job", "work", "office", "career", "money", "worker", "salary")):
        return "briefcase"
    if any(word in words for word in ("safe", "safety", "protect", "private", "risk", "secure")):
        return "shield"
    if any(word in words for word in ("robot", "agent", "assistant", "chatbot", "bot")):
        return "robot"
    if any(word in words for word in ("video", "image", "photo", "creator", "camera", "filter")):
        return "video"
    return "chip"


def draw_icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, accent: tuple[int, int, int]) -> None:
    white = (242, 247, 255)
    dark = (10, 16, 38)
    a = accent
    if kind == "phone":
        draw.rounded_rectangle((cx - 120, cy - 205, cx + 120, cy + 205), radius=38, fill=dark, outline=a, width=10)
        draw.rounded_rectangle((cx - 93, cy - 160, cx + 93, cy + 140), radius=20, fill=(20, 34, 70), outline=(90, 119, 180), width=3)
        draw.ellipse((cx - 37, cy - 105, cx + 37, cy - 31), fill=a)
        draw.arc((cx - 58, cy - 33, cx + 58, cy + 79), 190, 350, fill=white, width=9)
        heights = [34, 58, 86, 48, 70, 38, 64]
        for j, height in enumerate(heights):
            x = cx - 70 + j * 23
            draw.rounded_rectangle((x, cy + 96 - height // 2, x + 10, cy + 96 + height // 2), radius=5, fill=a)
        draw.rounded_rectangle((cx - 34, cy + 169, cx + 34, cy + 177), radius=4, fill=white)
    elif kind == "family":
        for dx, scale, color in [(-94, 0.76, a), (0, 1.0, white), (94, 0.76, (129, 202, 255))]:
            head = int(48 * scale)
            draw.ellipse((cx + dx - head, cy - 150 - head, cx + dx + head, cy - 150 + head), fill=color)
            draw.rounded_rectangle((cx + dx - int(62 * scale), cy - 87, cx + dx + int(62 * scale), cy + 115), radius=45, fill=color)
        draw.rounded_rectangle((cx - 185, cy + 116, cx + 185, cy + 195), radius=32, fill=(17, 28, 61), outline=a, width=6)
        draw.rectangle((cx - 4, cy + 129, cx + 4, cy + 190), fill=(100, 122, 170))
    elif kind == "briefcase":
        draw.rounded_rectangle((cx - 185, cy - 72, cx + 185, cy + 160), radius=34, fill=dark, outline=a, width=10)
        draw.rounded_rectangle((cx - 83, cy - 140, cx + 83, cy - 66), radius=22, fill=dark, outline=white, width=8)
        draw.rectangle((cx - 185, cy + 7, cx + 185, cy + 35), fill=a)
        draw.rounded_rectangle((cx - 28, cy - 2, cx + 28, cy + 55), radius=10, fill=white)
        draw.ellipse((cx + 102, cy - 196, cx + 196, cy - 102), fill=(12, 24, 48), outline=(255, 191, 77), width=8)
        draw.text((cx + 117, cy - 188), "$", font=ImageFont.truetype(FONT_BOLD_PATH, 58), fill=(255, 191, 77))
    elif kind == "shield":
        points = [(cx, cy - 218), (cx + 177, cy - 151), (cx + 147, cy + 62), (cx, cy + 218), (cx - 147, cy + 62), (cx - 177, cy - 151)]
        draw.polygon(points, fill=(14, 28, 58), outline=a)
        draw.line(points + [points[0]], fill=a, width=10, joint="curve")
        draw.line((cx - 82, cy + 2, cx - 20, cy + 68, cx + 96, cy - 75), fill=white, width=20, joint="curve")
    elif kind == "video":
        draw.rounded_rectangle((cx - 215, cy - 150, cx + 215, cy + 150), radius=38, fill=dark, outline=a, width=10)
        draw.ellipse((cx - 83, cy - 86, cx + 83, cy + 80), fill=(40, 76, 125), outline=white, width=6)
        draw.polygon([(cx - 25, cy - 48), (cx - 25, cy + 45), (cx + 55, cy - 1)], fill=a)
        for i in range(4):
            draw.rounded_rectangle((cx - 170 + i * 89, cy + 108, cx - 121 + i * 89, cy + 119), radius=5, fill=white)
    elif kind == "robot":
        draw.line((cx, cy - 215, cx, cy - 168), fill=a, width=12)
        draw.ellipse((cx - 18, cy - 238, cx + 18, cy - 202), fill=white)
        draw.rounded_rectangle((cx - 194, cy - 170, cx + 194, cy + 137), radius=65, fill=dark, outline=a, width=10)
        draw.rounded_rectangle((cx - 130, cy - 84, cx + 130, cy + 35), radius=46, fill=(26, 43, 81), outline=(89, 121, 184), width=4)
        draw.ellipse((cx - 85, cy - 44, cx - 38, cy + 3), fill=white)
        draw.ellipse((cx + 38, cy - 44, cx + 85, cy + 3), fill=white)
        draw.arc((cx - 48, cy - 8, cx + 48, cy + 75), 15, 165, fill=a, width=9)
        draw.rounded_rectangle((cx - 91, cy + 169, cx + 91, cy + 196), radius=12, fill=white)
    else:
        draw.rounded_rectangle((cx - 178, cy - 178, cx + 178, cy + 178), radius=42, fill=dark, outline=a, width=10)
        for offset in (-112, 0, 112):
            draw.line((cx + offset, cy - 225, cx + offset, cy - 180), fill=white, width=8)
            draw.line((cx + offset, cy + 180, cx + offset, cy + 225), fill=white, width=8)
            draw.line((cx - 225, cy + offset, cx - 180, cy + offset), fill=white, width=8)
            draw.line((cx + 180, cy + offset, cx + 225, cy + offset), fill=white, width=8)
        draw.text((cx - 94, cy - 78), "AI", font=ImageFont.truetype(FONT_BOLD_PATH, 150), fill=white, stroke_width=2, stroke_fill=a)
        for dx, dy in [(-250, -210), (240, -180), (-248, 180), (248, 197)]:
            draw.ellipse((cx + dx - 13, cy + dy - 13, cx + dx + 13, cy + dy + 13), fill=a)


def draw_scene(path: Path, scene: dict[str, str], index: int, topic: str) -> None:
    base, secondary, accent = PALETTES[(index - 1) % len(PALETTES)]
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)
        color = tuple(int(base[i] * (1 - ratio) + secondary[i] * ratio) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=color)

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((250, 170, 850, 770), fill=(*accent, 62))
    glow_draw.ellipse((-220, 640, 330, 1190), fill=(*secondary, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    grid = ImageDraw.Draw(overlay)
    for x in range(24, WIDTH, 64):
        grid.line((x, 0, x, HEIGHT), fill=(208, 228, 255, 12), width=1)
    for y in range(24, HEIGHT, 64):
        grid.line((0, y, WIDTH, y), fill=(208, 228, 255, 12), width=1)
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    draw.text((52, 55), "MIND FORGE  /  AI, MADE HUMAN", font=ImageFont.truetype(FONT_BOLD_PATH, 22), fill=(238, 245, 255, 235))
    pill = f"SCENE {index:02d} / {SCENE_COUNT:02d}"
    pill_font = ImageFont.truetype(FONT_BOLD_PATH, 18)
    draw.rounded_rectangle((52, 112, 232, 153), radius=20, fill=(5, 10, 28, 175), outline=(*accent, 225), width=2)
    draw.text((68, 121), pill, font=pill_font, fill=(245, 248, 255, 255))

    # A large translucent frame, plus a simple topic-aware vector illustration.
    draw.rounded_rectangle((42, 184, 678, 1036), radius=44, fill=(7, 12, 31, 88), outline=(*accent, 100), width=2)
    draw.ellipse((267, 252, 453, 438), outline=(*accent, 145), width=3)
    kind = icon_kind(scene, topic)
    draw_icon(draw, kind, 360, 490, accent)

    label = str(scene.get("label", "AI IN REAL LIFE")).strip().upper()
    title_font = ImageFont.truetype(FONT_BOLD_PATH, 52)
    lines = wrap_words(draw, label, title_font, 590)
    if len(lines) > 2:
        title_font = ImageFont.truetype(FONT_BOLD_PATH, 44)
        lines = wrap_words(draw, label, title_font, 590)
    y = 765 if len(lines) <= 2 else 735
    for line in lines:
        box = draw.textbbox((0, 0), line, font=title_font, stroke_width=1)
        x = (WIDTH - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=title_font, fill=(250, 252, 255, 255), stroke_width=1, stroke_fill=(2, 8, 22, 180))
        y += 64

    visual = str(scene.get("visual", "A clear visual metaphor for the story")).strip()
    visual = re.sub(r"\s+", " ", visual)
    if len(visual) > 56:
        visual = visual[:53].rsplit(" ", 1)[0] + "..."
    note_font = ImageFont.truetype(FONT_PATH, 22)
    box = draw.textbbox((0, 0), visual, font=note_font)
    note_x = max(42, (WIDTH - (box[2] - box[0])) // 2)
    draw.text((note_x, min(y + 12, 944)), visual, font=note_font, fill=(214, 226, 248, 235))

    # A small animated-looking accent shape; FFmpeg adds a slow camera push to each card.
    draw.rounded_rectangle((72, 1000, 208, 1008), radius=4, fill=(*accent, 235))
    image.convert("RGB").save(path, quality=95)


def fallback_scenes(narration: str) -> list[dict[str, str]]:
    words = narration.split()
    scenes: list[dict[str, str]] = []
    for index in range(SCENE_COUNT):
        start = round(index * len(words) / SCENE_COUNT)
        end = round((index + 1) * len(words) / SCENE_COUNT)
        part = words[start:end]
        label = " ".join(part[:5]).strip(" ,.!?;:") or "AI IN REAL LIFE"
        scenes.append({"label": label, "visual": "A bold illustration that matches this moment"})
    return scenes


def scene_list(story: dict[str, Any]) -> list[dict[str, str]]:
    supplied = story.get("scenes", [])
    scenes: list[dict[str, str]] = []
    if isinstance(supplied, list):
        for item in supplied[:SCENE_COUNT]:
            if isinstance(item, dict):
                scenes.append(
                    {
                        "label": str(item.get("label", "AI IN REAL LIFE"))[:64],
                        "visual": str(item.get("visual", "A bold illustration about AI"))[:110],
                    }
                )
    fallback = fallback_scenes(story["narration"])
    while len(scenes) < SCENE_COUNT:
        scenes.append(fallback[len(scenes)])
    return scenes[:SCENE_COUNT]


def caption_groups(text: str, max_words: int = 5, max_chars: int = 34) -> list[str]:
    words = text.split()
    groups: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            groups.append(" ".join(current))
            current = []
        current.append(word)
        if re.search(r"[.!?][\"')\]]?$", word):
            groups.append(" ".join(current))
            current = []
    if current:
        groups.append(" ".join(current))
    return groups


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def write_captions(text: str, duration: float, path: Path) -> None:
    groups = caption_groups(text)
    if not groups:
        raise RuntimeError("The narration did not produce any caption lines.")
    weights = [max(1, len(group)) for group in groups]
    total = sum(weights)
    elapsed = 0
    entries: list[str] = []
    for index, (group, weight) in enumerate(zip(groups, weights), start=1):
        start = duration * elapsed / total
        elapsed += weight
        end = duration if index == len(groups) else duration * elapsed / total
        entries.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{group}\n")
    path.write_text("\n".join(entries), encoding="utf-8")


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def render_video(story: dict[str, Any], voice_path: Path) -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil_which(tool):
            raise RuntimeError(f"{tool} is missing on the GitHub runner.")
    for font_path in (FONT_PATH, FONT_BOLD_PATH):
        if not Path(font_path).is_file():
            raise RuntimeError("The DejaVu fonts are missing. Check the workflow's apt install step.")

    duration = float(
        run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path),
            ]
        )
    )
    if not 25 <= duration <= 90:
        raise RuntimeError(f"Voice length is {duration:.1f}s; expected a short video between 25 and 90 seconds.")

    scenes = scene_list(story)
    image_paths: list[Path] = []
    for index, scene in enumerate(scenes, start=1):
        path = SCENE_DIR / f"scene_{index:02d}.png"
        draw_scene(path, scene, index, story["topic"])
        image_paths.append(path)

    captions_path = OUT / "captions.srt"
    write_captions(story["narration"], duration, captions_path)

    per_scene_duration = duration / len(image_paths)
    command: list[str] = ["ffmpeg", "-hide_banner", "-y"]
    for path in image_paths:
        command.extend(["-loop", "1", "-framerate", "30", "-t", f"{per_scene_duration:.4f}", "-i", str(path)])
    audio_input = len(image_paths)
    command.extend(["-i", str(voice_path)])

    filters: list[str] = []
    for index in range(len(image_paths)):
        filters.append(
            f"[{index}:v]scale=1080:1920,fps=30,"
            "zoompan=z='min(zoom+0.00045,1.04)':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            "d=1:s=1080x1920:fps=30,"
            f"trim=duration={per_scene_duration:.4f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{index}]"
        )

    joined = "".join(f"[v{index}]" for index in range(len(image_paths)))
    subtitle_filter = (
        f"subtitles=filename='{captions_path.resolve()}':fontsdir='/usr/share/fonts/truetype/dejavu':"
        "force_style='FontName=DejaVu Sans,FontSize=46,Bold=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginL=90,MarginR=90,MarginV=320,BorderStyle=3,BackColour=&HBB07111F'"
    )
    filters.append(f"{joined}concat=n={len(image_paths)}:v=1:a=0,{subtitle_filter},format=yuv420p[vout]")
    command.extend(
        [
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", f"{audio_input}:a:0",
            "-t", f"{duration:.3f}", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(OUT / "mind-forge-viral-video.mp4"),
        ]
    )
    print(f"Rendering 8 changing visual scenes into a 9:16 video ({duration:.1f}s)...")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        tail = (error.stderr or "").strip()[-1800:]
        raise RuntimeError(f"FFmpeg could not render the video. {tail}") from error


def shutil_which(name: str) -> str | None:
    # Kept in the standard library so the workflow needs only Pillow.
    import shutil

    return shutil.which(name)


def main() -> None:
    if not API_KEY:
        raise RuntimeError("GitHub secret SKRIPTA_KEY is missing.")
    OUT.mkdir(parents=True, exist_ok=True)
    SCENE_DIR.mkdir(parents=True, exist_ok=True)

    print("Finding a recent AI story with broad short-video appeal...")
    story, sources = choose_story(API_KEY)
    (OUT / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "script.txt").write_text(story["narration"].strip() + "\n", encoding="utf-8")
    source_lines = [f"{source['title']} — {source['url']}" for source in sources]
    (OUT / "sources.txt").write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    print(f"Selected: {story['topic']}")

    voice_path = OUT / "voice.wav"
    print(f"Creating a natural conversational voice ({VOICE_NAME})...")
    make_voice(API_KEY, story["narration"], voice_path)
    render_video(story, voice_path)
    print("Finished. The video, script, voice, captions, scenes and sources are in output/.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"MIND FORGE VIDEO ERROR: {error}", file=sys.stderr)
        raise
