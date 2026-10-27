# Daily hedgehog quotes: Dhwaja23 (Instagram) + Quiamo (LinkedIn)

Every morning a GitHub Action:

1. Takes the next quote from `quotes.yaml`.
2. Asks Gemini for two text-free illustrations of the hedgehog (3:4 and 9:16), built from the quote's **pose** and **background** plus the shared character and style in `config.yaml`. `reference/hedgehog_reference.jpg` is sent along so the character stays consistent.
3. Letters the quote on top with coloured brush highlights for the `[bracketed]` phrases and adds a **Quiamo.com** footer (`compose.py`). The program does the lettering rather than Gemini so the spelling is always right.
4. Waits for the day's random time slot between **08:10 and 08:45 IST**, never the same as the day before.
5. Posts:

| Where | Format | Size |
|---|---|---|
| LinkedIn, Quiamo page | 3:4 image + LinkedIn post (hook, body, ≤5 hashtags) | 1080×1440 |
| Instagram, Dhwaja23 feed | 4:5 image + Instagram caption (hook, body, ≤5 hashtags) | 1080×1350 |
| Instagram, Dhwaja23 story | 9:16 image | 1080×1920 |

Instagram's API rejects feed photos taller than 4:5, so the 9:16 version goes to Stories.

`samples/` has example output and captions.

## One-time setup (repo → Settings → Secrets and variables → Actions)

| Secret | What it is |
|---|---|
| `GEMINI_API_KEY` | From https://aistudio.google.com/apikey. Image generation is billed on the Gemini API (roughly US$0.04 per image, 2 images a day). |
| `IG_USER_ID` | Dhwaja23's Instagram business account id: `17841467124393420` |
| `IG_ACCESS_TOKEN` | Long-lived Instagram Graph API token with `instagram_content_publish` permission. If it is an "Instagram Login" token rather than a Facebook Page token, also set the variable `IG_GRAPH_HOST` = `graph.instagram.com`. |
| `LINKEDIN_ACCESS_TOKEN` | Token from a LinkedIn developer app with `w_organization_social`, made by an admin of the Quiamo page. These tokens expire after 60 days, so refresh them. |
| `LINKEDIN_ORG_ID` | The number in the Quiamo admin URL: `linkedin.com/company/<ID>/admin` |

Optional variables: `GEMINI_IMAGE_MODEL` (default `gemini-2.5-flash-image`), `LINKEDIN_API_VERSION` (default `202509`, YYYYMM).

If a token is missing, that network is skipped and the rest still posts.

## Everyday use

- **Add or edit quotes:** edit `quotes.yaml`. Each entry has `quote`, `pose`, `background`, and separate `linkedin` / `instagram` hook, body and hashtags.
- **Post right now:** Actions → *Daily hedgehog quote* → *Run workflow* → tick *post_now*.
- **Preview locally without API calls:**
  `python run_daily.py preview --quote own-garden --art-3x4 art.png --art-9x16 art_tall.png --out preview`
- **Re-runs are safe.** `state.json` records what was posted each day, so a re-run only retries the networks that failed.
