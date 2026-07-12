# Daily Drive Podcast

A fully automated, **$0/month** daily podcast for your commute. Every morning a
GitHub Actions pipeline researches your topics of interest (AI, anime, ...) via
Google News, summarizes new videos from your favorite YouTube channels, writes a
15–20 minute episode (NotebookLM two-host audio, or a free-LLM script read by
Edge TTS), and publishes it to a private RSS feed your podcast app downloads
automatically.

Releases: https://github.com/ROMANFern/driver-podcast/releases

```
GitHub Actions (daily, ~04:45 Asia/Colombo)
  1. collect_youtube  - channel RSS feeds -> new videos (24h) -> transcripts
  2. research         - Google News RSS per topic + free LLM -> summaries
  3. audio            - NotebookLM Audio Overview (two-host AI podcast), with
                        automatic fallback to free-LLM script + Edge TTS
  4. publish          - MP3 + RSS feed -> GitHub Pages
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
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys (free account; uses OpenRouter's free-model router) |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (free tier; automatic fallback LLM) |
| `SPOTIFY_OWNER_EMAIL` | Public contact email used once by Spotify to verify ownership of the RSS feed |
| `YOUTUBE_WEBSHARE_PROXY_USERNAME` | Optional: Webshare residential proxy username, recommended because GitHub Actions IPs are commonly blocked by YouTube |
| `YOUTUBE_WEBSHARE_PROXY_PASSWORD` | Optional: matching Webshare residential proxy password |

At least one of the two LLM keys is required; set both so the pipeline can fall
back to Gemini when OpenRouter's free models are unavailable or rate-limited.

YouTube transcripts are fetched with
[`youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api).
Direct requests usually work locally, but YouTube commonly blocks GitHub
Actions and other cloud-provider IPs. For reliable automated transcripts, add
the two optional Webshare **Residential** proxy secrets above. You can also set
the repository variable `YOUTUBE_PROXY_LOCATIONS` to a comma-separated list
such as `au,us`. Other proxy providers can be used locally with
`YOUTUBE_HTTP_PROXY` and `YOUTUBE_HTTPS_PROXY` environment variables.

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

### 3. Personalize
- `config/topics.yaml` — your topics and what counts as noteworthy.
- `config/channels.yaml` — YouTube channels (instructions for finding channel IDs are in the file).
- `config/settings.yaml` — voice, episode length, feed slug.

### 4. Subscribe
After the first successful run, your feed lives at:

```
<base_url>/feed-<feed_slug>.xml
```

Add that URL in AntennaPod / Pocket Casts / Apple Podcasts ("add by URL").
Enable auto-download so the episode is on your phone before you leave.

### Spotify

The generated feed includes Spotify-compatible artwork and podcast metadata.
Set the `SPOTIFY_OWNER_EMAIL` repository secret, run the workflow once, then
submit the feed URL to Spotify for Creators as an externally hosted show:

```
<base_url>/feed-<feed_slug>.xml
```

Spotify will verify ownership using the email in the feed and automatically
import future episodes. The show and feed become publicly discoverable after
submission.

## Running

- Automatic: daily at 23:15 UTC (04:45 Asia/Colombo). Edit the cron in
  `.github/workflows/daily.yml` to change.
- Manual: **Actions → Daily episode → Run workflow**.
- Local test: `pip install -r requirements.txt`, set the env vars, then
  `python -m src.pipeline` (use `--skip tts` to test cheaply).

## Notes & known issues
- **OpenRouter free-model availability varies:** `openrouter/free` automatically
  routes each request to an available free model, so response quality, speed,
  limits, and data policies can vary. The pipeline falls back to Gemini Flash
  automatically if OpenRouter fails; to switch primary
  models permanently, edit `llm.providers` in `config/settings.yaml`.
- **Gemini API free tier** (separate from the Google AI Pro consumer
  subscription, which does not include API credits) covers Flash models with a
  daily quota — more than enough for one episode per day.
- **YouTube transcripts from cloud IPs:** YouTube sometimes blocks transcript
  requests from datacenter IPs. The pipeline falls back to the video
  title/description from the RSS feed and continues. If it becomes chronic,
  consider a proxy for that step.
- **No Spotify integration:** Spotify blocked playlist-write API access for
  personal (development-mode) apps in May 2025, making automated playlist
  curation impossible for hobbyist apps. Use Spotify's own personalized
  playlists (Daylist, Daily Mix) for music after the episode.
- The feed URL is unlisted (random slug), not authenticated. Anyone with the
  exact URL could subscribe — rotate `feed_slug` if it leaks.
- Running cost: **$0/month** (Google News RSS, free LLMs, Edge TTS, GitHub free
  tier).
