"""Daily hedgehog quote poster.

  python run_daily.py prepare            # pick today's quote, generate + compose images
  python run_daily.py publish [--now]    # wait for today's time slot, then post
  python run_daily.py preview --quote ID --art-3x4 a.png --art-9x16 b.png
                                         # compose locally from existing art, no API calls

State (which quote is next, what was posted) lives in state.json so the
GitHub Actions workflow can commit it back after each run.
"""

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from compose import LAYOUTS, SOURCE_FORMAT, plain_quote, render

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
POSTS_DIR = ROOT / "posts"
MAX_HASHTAGS = 5


def load_yaml(name):
    return yaml.safe_load((ROOT / name).read_text())


def load_quotes():
    quotes = load_yaml("quotes.yaml")["quotes"]
    for q in quotes:
        for platform in ("linkedin", "instagram"):
            tags = q[platform]["hashtags"]
            if len(tags) > MAX_HASHTAGS:
                raise ValueError(f"{q['id']}: {platform} has {len(tags)} hashtags (max {MAX_HASHTAGS})")
    return quotes


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"next_index": 0, "days": {}}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def today(config):
    return dt.datetime.now(ZoneInfo(config["schedule"]["timezone"])).date().isoformat()


def pick_slot(config, state, day):
    """A different posting time each day, never repeating yesterday's."""
    slots = list(config["schedule"]["slots"])
    previous = [state["days"][d]["slot"] for d in sorted(state["days"]) if d < day]
    if previous and len(slots) > 1 and previous[-1] in slots:
        slots.remove(previous[-1])
    return random.Random(day).choice(slots)


def caption(entry, footer):
    tags = " ".join(f"#{t}" for t in entry["hashtags"])
    return f"{entry['hook']}\n\n{entry['body']}\n\n🌿 {footer}\n\n{tags}"


def compose_all(config, quote, art, out_dir, seed):
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in LAYOUTS:
        path = out_dir / f"{name}.jpg"
        render(art[SOURCE_FORMAT[name]], quote["quote"], name,
               config["brand"]["footer"], seed).save(path, quality=92, optimize=True)
        files[name] = path.name
    return files


def cmd_prepare(args):
    from generate import generate

    config, quotes, state = load_yaml("config.yaml"), load_quotes(), load_state()
    day = today(config)
    if day in state["days"]:
        print(f"{day} already prepared: {state['days'][day]['quote_id']}")
        return

    quote = quotes[state["next_index"] % len(quotes)]
    # Raw art stays out of git; only the finished JPEGs are committed.
    art_dir = ROOT / ".art" / day
    art_dir.mkdir(parents=True, exist_ok=True)
    art = {}
    for fmt in config["formats"]:
        print(f"Generating {fmt} art for '{quote['id']}'...")
        art[fmt] = generate(config, quote, fmt, art_dir / f"{fmt}.png")

    files = compose_all(config, quote, art, POSTS_DIR / day, seed=day)
    footer = config["brand"]["footer"]
    state["days"][day] = {
        "quote_id": quote["id"],
        "slot": pick_slot(config, state, day),
        "files": files,
        "instagram_caption": caption(quote["instagram"], footer),
        "linkedin_text": f"{quote['linkedin']['hook']}\n\n{quote['linkedin']['body']}\n\n🌿 {footer}",
        "linkedin_hashtags": quote["linkedin"]["hashtags"],
        "alt_text": f"Cute watercolor hedgehog illustration with the quote: {plain_quote(quote['quote'])}",
        "posted": {},
    }
    state["next_index"] += 1
    save_state(state)
    print(f"Prepared '{quote['id']}' for {day}, posting at {state['days'][day]['slot']} IST")


def wait_for_slot(config, day, slot):
    tz = ZoneInfo(config["schedule"]["timezone"])
    hour, minute = map(int, slot.split(":"))
    target = dt.datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=tz)
    delay = (target - dt.datetime.now(tz)).total_seconds()
    if delay > 0:
        print(f"Waiting {delay / 60:.0f} min until {slot} IST...")
        time.sleep(delay)


def cmd_publish(args):
    from publish import Instagram, LinkedIn, linkedin_text

    config, state = load_yaml("config.yaml"), load_state()
    day = today(config)
    entry = state["days"].get(day)
    if not entry:
        sys.exit(f"Nothing prepared for {day}; run 'prepare' first.")

    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    image_url = lambda name: f"{base_url}/hedgehog_posts/posts/{day}/{entry['files'][name]}"
    image_path = lambda name: POSTS_DIR / day / entry["files"][name]

    jobs = {}
    if os.environ.get("IG_ACCESS_TOKEN"):
        jobs["instagram_feed"] = lambda: Instagram().post_image(
            image_url("instagram_feed_4x5"), entry["instagram_caption"])
        jobs["instagram_story"] = lambda: Instagram().post_story(image_url("instagram_story_9x16"))
    else:
        print("IG_ACCESS_TOKEN not set; skipping Instagram.")
    if os.environ.get("LINKEDIN_ACCESS_TOKEN"):
        jobs["linkedin"] = lambda: LinkedIn().post_image(
            image_path("linkedin_3x4"),
            linkedin_text(entry["linkedin_text"], entry["linkedin_hashtags"]),
            entry["alt_text"])
    else:
        print("LINKEDIN_ACCESS_TOKEN not set; skipping LinkedIn.")
    if any(j.startswith("instagram") for j in jobs) and not base_url:
        sys.exit("PUBLIC_BASE_URL is required for Instagram (it fetches images by URL).")

    pending = {k: v for k, v in jobs.items() if k not in entry["posted"]}
    if not pending:
        print("Everything for today is already posted.")
        return
    if not args.now:
        wait_for_slot(config, day, entry["slot"])

    failed = []
    for name, job in pending.items():
        try:
            entry["posted"][name] = job()
            print(f"Posted {name}: {entry['posted'][name]}")
        except Exception as exc:  # keep going so one network failing doesn't block the other
            detail = getattr(getattr(exc, "response", None), "text", "")
            print(f"FAILED {name}: {exc} {detail}", file=sys.stderr)
            failed.append(name)
        save_state(state)
    if failed:
        sys.exit(f"Failed: {', '.join(failed)}")


def cmd_preview(args):
    config = load_yaml("config.yaml")
    quote = next(q for q in load_quotes() if q["id"] == args.quote)
    art = {"portrait_3x4": args.art_3x4, "story_9x16": args.art_9x16 or args.art_3x4}
    out = Path(args.out)
    files = compose_all(config, quote, art, out, seed=quote["id"])
    footer = config["brand"]["footer"]
    (out / "instagram_caption.txt").write_text(caption(quote["instagram"], footer) + "\n")
    (out / "linkedin_post.txt").write_text(caption(quote["linkedin"], footer) + "\n")
    print(f"Wrote {', '.join(files.values())} and captions to {out}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare").set_defaults(func=cmd_prepare)
    p = sub.add_parser("publish")
    p.add_argument("--now", action="store_true", help="post immediately instead of waiting for the slot")
    p.set_defaults(func=cmd_publish)
    p = sub.add_parser("preview")
    p.add_argument("--quote", required=True)
    p.add_argument("--art-3x4", required=True)
    p.add_argument("--art-9x16")
    p.add_argument("--out", default="preview")
    p.set_defaults(func=cmd_preview)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
