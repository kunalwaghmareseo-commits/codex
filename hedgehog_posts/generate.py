"""Generate text-free hedgehog illustrations with the Gemini API."""

import base64
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / "reference" / "hedgehog_reference.jpg"
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash-image"


def build_prompt(config, quote, fmt):
    return (
        f"{config['style']}. Full-bleed illustration with no frame or border. "
        f"Main character: {config['character']}. Draw exactly the same hedgehog "
        f"character as in the reference image. "
        f"POSE: the hedgehog {quote['pose']}. "
        f"BACKGROUND: {quote['background']}. "
        f"COMPOSITION: {config['formats'][fmt]['composition']} "
        f"No text, no letters, no words, no numbers, no watermark, no signature."
    )


def generate(config, quote, fmt, out_path, attempts=4):
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_IMAGE_MODEL") or DEFAULT_MODEL
    parts = []
    if REFERENCE.exists():
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(REFERENCE.read_bytes()).decode()}})
    parts.append({"text": build_prompt(config, quote, fmt)})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": config["formats"][fmt]["aspect_ratio"]},
        },
    }

    for attempt in range(1, attempts + 1):
        resp = requests.post(API.format(model=model), json=body, timeout=180,
                             headers={"x-goog-api-key": api_key})
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
            time.sleep(15 * attempt)
            continue
        resp.raise_for_status()
        for candidate in resp.json().get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                data = part.get("inlineData") or part.get("inline_data")
                if data:
                    Path(out_path).write_bytes(base64.b64decode(data["data"]))
                    return out_path
        if attempt == attempts:
            raise RuntimeError(f"Gemini returned no image: {resp.text[:500]}")
        time.sleep(10)
