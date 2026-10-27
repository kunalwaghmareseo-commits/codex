"""Build ready-to-post images and one text file of captions for manual posting.

    python build_posts.py              # uses the illustrations in art/
    python build_posts.py --generate   # also creates missing art with the
                                       # Gemini API (needs GEMINI_API_KEY)

Output goes to ../manual_posts/:
    NN_<quote-id>/linkedin_3x4.jpg          Quiamo LinkedIn page (1080x1440)
    NN_<quote-id>/instagram_feed_4x5.jpg    Dhwaja23 feed post (1080x1350)
    NN_<quote-id>/instagram_story_9x16.jpg  Dhwaja23 story / reel cover (1080x1920)
    ALL_POSTS.txt                           every LinkedIn post and Instagram caption
"""

import argparse
from pathlib import Path

import yaml
from PIL import Image

from compose import LAYOUTS, SOURCE_FORMAT, extend_sky, plain_quote, render

ROOT = Path(__file__).resolve().parent
ART = ROOT / "art"
OUT = ROOT.parent / "manual_posts"
MAX_HASHTAGS = 5


def caption(entry, footer):
    tags = " ".join(f"#{t}" for t in entry["hashtags"])
    return f"{entry['hook']}\n\n{entry['body']}\n\n🌿 {footer}\n\n{tags}"


def art_for(quote, fmt, config, generate):
    path = ART / f"{quote['id']}_{fmt}.jpg"
    if path.exists():
        return Image.open(path)
    if generate:
        from generate import generate as gemini
        png = ART / f"{quote['id']}_{fmt}.png"
        gemini(config, quote, fmt, png)
        Image.open(png).convert("RGB").save(path, quality=93)
        png.unlink()
        return Image.open(path)
    if fmt == "story_9x16":
        return extend_sky(art_for(quote, "portrait_3x4", config, generate))
    raise FileNotFoundError(f"No art for {quote['id']} ({fmt}). Run with --generate.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="create missing art with Gemini")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    quotes = yaml.safe_load((ROOT / "quotes.yaml").read_text())["quotes"]
    footer = config["brand"]["footer"]
    OUT.mkdir(exist_ok=True)

    text = ["HEDGEHOG QUOTE POSTS: Quiamo (LinkedIn) + Dhwaja23 (Instagram)",
            "Each post: LinkedIn image = linkedin_3x4.jpg | Instagram feed = instagram_feed_4x5.jpg"
            " | Instagram story = instagram_story_9x16.jpg", ""]
    for n, quote in enumerate(quotes, 1):
        for platform in ("linkedin", "instagram"):
            if len(quote[platform]["hashtags"]) > MAX_HASHTAGS:
                raise ValueError(f"{quote['id']}: more than {MAX_HASHTAGS} {platform} hashtags")
        folder = OUT / f"{n:02d}_{quote['id']}"
        folder.mkdir(exist_ok=True)
        art = {fmt: art_for(quote, fmt, config, args.generate) for fmt in config["formats"]}
        for name in LAYOUTS:
            render(art[SOURCE_FORMAT[name]], quote["quote"], name, footer, quote["id"]).save(
                folder / f"{name}.jpg", quality=92, optimize=True)

        text += [
            "=" * 72,
            f"POST {n:02d}  |  folder: {folder.name}",
            f"QUOTE ON IMAGE: {plain_quote(quote['quote'])}",
            "=" * 72, "",
            "---- LINKEDIN (Quiamo page) ---- image: linkedin_3x4.jpg", "",
            caption(quote["linkedin"], footer), "",
            "---- INSTAGRAM (Dhwaja23) ---- feed: instagram_feed_4x5.jpg, story: instagram_story_9x16.jpg", "",
            caption(quote["instagram"], footer), "", "",
        ]
        print(f"{folder.name}: done")

    (OUT / "ALL_POSTS.txt").write_text("\n".join(text))
    print(f"Wrote {OUT / 'ALL_POSTS.txt'}")


if __name__ == "__main__":
    main()
