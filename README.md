# Daily Drive Podcast

A fully automated, **$0/month** daily podcast for your commute. Every morning a
GitHub Actions pipeline researches your topics of interest (AI, anime, ...) via
Google News, summarizes new videos from your favorite YouTube channels, writes a
15–20 minute script with a free LLM (OpenRouter's owl-alpha, with Gemini Flash
free tier as automatic fallback), turns it into audio with Edge TTS, refreshes a
Spotify playlist for the rest of the drive, and publishes the episode to a
private RSS feed your podcast app downloads automatically.

```
GitHub Actions (daily, ~04:45 Asia/Colombo)
  1. collect_youtube  - channel RSS feeds -> new videos (24h) -> transcripts
  2. research         - Google News RSS per topic + free LLM -> summaries
  3+4. audio          - NotebookLM Audio Overview (two-host AI podcast), with
                        automatic fallback to free-LLM script + Edge TTS
  5. spotify_refresh  - rebuild "Daily Drive Mix" playlist
  6. publish          - MP3 + RSS feed -> GitHub Pages
```

## One-time setup

### 1. GitHub repo
1. Push this repo to GitHub (private is fine).
2. **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main`, folder `/docs`.
3. Put the resulting Pages URL into `config/settings.yaml` → `podcast.base_url`
   (e.g. `https://<username>.github.io/driver-podcast`).
4. **Settings → Actions → General → Workflow permissions** → *Read and write permissions*
   (the workflow commits the feed + episode back to the repo).

### 2. API keys (repo → Settings → Secrets and variables → Actions)

| Secret | Where to get it |
|---|---|
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys (free account; owl-alpha costs $0) |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (free tier; automatic fallback LLM) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | https://developer.spotify.com/dashboard → your app's credentials (any localhost redirect URI works; set `SPOTIFY_REDIRECT_URI` if it differs from the default in `scripts/spotify_auth.py`) |
| `SPOTIFY_REFRESH_TOKEN` | run `python scripts/spotify_auth.py` locally once (see below) |

At least one of the two LLM keys is required; set both so the pipeline survives
owl-alpha's eventual retirement.

### 2b. NotebookLM audio (optional but recommended — two-host AI podcast)

The default audio engine is NotebookLM Audio Overviews via the unofficial
[notebooklm-py](https://github.com/teng-lin/notebooklm-py) client, using your
Google account (AI Pro gives higher Audio Overview quotas). One-time setup:

```powershell
pip install "notebooklm-py[browser]"
playwright install chromium
notebooklm login          # opens a browser; sign in to Google
```

Then copy the contents of `~/.notebooklm/profiles/default/storage_state.json`
into a `NOTEBOOKLM_AUTH_JSON` GitHub secret.

Caveats: this drives the consumer NotebookLM web app (no official consumer
API — gray area, could break if Google changes things), and Google sessions
expire after a while. When that happens the pipeline automatically falls back
to the single-voice script + Edge TTS path, and the Actions log tells you to
re-run `notebooklm login` and refresh the secret. To skip NotebookLM entirely,
set `audio.engine: "edge"` in `config/settings.yaml`.

### 3. Spotify refresh token (run locally once)

```powershell
$env:SPOTIFY_CLIENT_ID = "..."; $env:SPOTIFY_CLIENT_SECRET = "..."
pip install spotipy
python scripts/spotify_auth.py
```

A browser opens; log in and authorize. The script prints the refresh token —
paste it into the `SPOTIFY_REFRESH_TOKEN` secret.

### 4. Personalize
- `config/topics.yaml` — your topics and what counts as noteworthy.
- `config/channels.yaml` — YouTube channels (instructions for finding channel IDs are in the file).
- `config/settings.yaml` — voice, episode length, playlist size, feed slug.

### 5. Subscribe
After the first successful run, your feed lives at:

```
<base_url>/feed-<feed_slug>.xml
```

Add that URL in AntennaPod / Pocket Casts / Apple Podcasts ("add by URL").
Enable auto-download so the episode is on your phone before you leave.

## Running

- Automatic: daily at 23:15 UTC (04:45 Asia/Colombo). Edit the cron in
  `.github/workflows/daily.yml` to change.
- Manual: **Actions → Daily episode → Run workflow**.
- Local test: `pip install -r requirements.txt`, set the env vars, then
  `python -m src.pipeline` (use `--skip tts,spotify` to test cheaply).

## Notes & known issues
- **owl-alpha is a stealth preview model:** free in exchange for usage data
  (prompts/completions may be logged for training), slow (~12 tok/s — fine for
  a cron job), and it will disappear without notice when the preview ends. The
  pipeline then falls back to Gemini Flash automatically; to switch primary
  models permanently, edit `llm.providers` in `config/settings.yaml`.
- **Gemini API free tier** (separate from the Google AI Pro consumer
  subscription, which does not include API credits) covers Flash models with a
  daily quota — more than enough for one episode per day.
- **YouTube transcripts from cloud IPs:** YouTube sometimes blocks transcript
  requests from datacenter IPs. The pipeline falls back to the video
  title/description from the RSS feed and continues. If it becomes chronic,
  consider a proxy for that step.
- **Spotify recommendations endpoint** is deprecated for new apps, so the
  playlist is curated from your top tracks, saved tracks, and new releases from
  artists you follow.
- The feed URL is unlisted (random slug), not authenticated. Anyone with the
  exact URL could subscribe — rotate `feed_slug` if it leaks.
- Running cost: **$0/month** (Google News RSS, free LLMs, Edge TTS, GitHub free
  tier).
