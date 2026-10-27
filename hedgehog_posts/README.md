# Hedgehog quote posts: Quiamo (LinkedIn) + Dhwaja23 (Instagram)

These are made for posting by hand. The finished files are in `../manual_posts/`:

| File | Use it for | Size |
|---|---|---|
| `NN_<quote>/linkedin_3x4.jpg` | Quiamo LinkedIn page post | 1080×1440 |
| `NN_<quote>/instagram_feed_4x5.jpg` | Dhwaja23 feed post | 1080×1350 |
| `NN_<quote>/instagram_story_9x16.jpg` | Dhwaja23 story or reel cover | 1080×1920 |
| `ALL_POSTS.txt` | Every LinkedIn post and Instagram caption, with a hook and at most 5 hashtags | |

Instagram feed posts can't be taller than 4:5, so use the 9:16 image for Stories.

## How they're made

- `quotes.yaml` holds each quote, kept separate from the hedgehog's **pose** and **background**, plus the LinkedIn and Instagram copy. Phrases in `[brackets]` get a coloured brush highlight.
- `config.yaml` holds the shared character and art style, so the same hedgehog is described in every prompt.
- `art/` holds the text-free illustrations, generated with Gemini.
- `compose.py` letters the quote and adds the **Quiamo.com** footer. The program does the lettering rather than the image model, so the spelling is always right.

## Rebuild or add quotes

```
pip install -r requirements.txt
python build_posts.py                # rebuild everything from art/
python build_posts.py --generate     # make art for new quotes with the Gemini API
```

`--generate` needs a `GEMINI_API_KEY` from https://aistudio.google.com/apikey. If a quote has 3:4 art but no 9:16 art, the story version is made by extending the sky above the 3:4 art.
