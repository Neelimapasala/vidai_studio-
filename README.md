# VidAI Studio

**Create complete AI videos from a single prompt.**

Open the site, describe a video, pick a duration/aspect ratio/style, hit
**Generate Video** — VidAI Studio writes the script, plans the scenes,
generates visuals and voice-over, burns in captions, and renders a real
downloadable MP4 with FFmpeg. No account, no login, no payment.

This build has been run end-to-end in development (script → scenes → images →
voice‑over → captions → FFmpeg render → playable MP4) and works out of the
box in **demo mode**, with zero API keys required — see [How the fallbacks
work](#how-the-fallbacks-work).

---

## 1. Features

- **One-prompt generation** — idea in, finished MP4 out, on a single page
- **Groq-powered script + scene planning**, validated with Pydantic, with
  automatic JSON-repair retry if the model returns malformed output
- **Provider-abstracted media pipeline** — image, video and TTS providers are
  interfaces (`app/providers/`), so swapping in a paid API later doesn't
  touch the rest of the app
- **Works with zero API keys** — offline image generator (styled gradient
  cards) + offline TTS (`pyttsx3`/`espeak-ng`) + FFmpeg keep the app fully
  functional in demo mode
- **Ken Burns image-to-video fallback** — since real video-generation APIs
  are paid, scenes are rendered as animated zoom/pan clips over AI-styled
  images, so you always get a real MP4, not a placeholder
- Burned-in captions (SRT), optional synthesized ambient background music
- Async job queue with live progress polling (no frozen UI)
- Per-scene regeneration (redo one scene's image + voice without
  re-rendering everything from scratch)
- Fully responsive dark UI with a distinctive "film studio" visual identity

## 2. Architecture

```
React (Vite + Tailwind)
        │
        ▼
FastAPI backend  ───▶  Groq API (script + scene JSON)
        │        ───▶  Image provider (fallback: PIL gradient cards)
        │        ───▶  TTS provider (fallback: pyttsx3 / espeak-ng, offline)
        │        ───▶  FFmpeg (Ken Burns render, concat, subtitles, mix)
        ▼
   storage/*.mp4  ───▶  served back to the browser, downloadable
```

API keys never touch the frontend — every external call goes through the
FastAPI backend.

### Project structure

```
vidai-studio/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app, CORS, static mount
│   │   ├── jobs.py                 async pipeline orchestration
│   │   ├── api/
│   │   │   ├── routes_video.py     all /api/video/* endpoints
│   │   │   └── routes_health.py    /api/health
│   │   ├── services/
│   │   │   ├── groq_service.py     Groq calls + JSON validation/repair
│   │   │   ├── scene_service.py    demo-mode fallback script + reconciling durations
│   │   │   ├── image_service.py    scene image generation (fallback provider)
│   │   │   ├── tts_service.py      narration synthesis (offline fallback)
│   │   │   ├── caption_service.py  SRT generation
│   │   │   └── video_renderer.py   FFmpeg: Ken Burns, concat, subtitles, music
│   │   ├── providers/              swappable interfaces for image/video/TTS
│   │   ├── models/                 Pydantic schemas (Scene, VideoScript, Job…)
│   │   └── utils/                  file/storage helpers, Groq prompt templates
│   ├── storage/                    generated images/audio/videos/subtitles
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── components/             Header, PromptInput, VideoSettings,
    │   │                           AudioControls, CaptionControls,
    │   │                           GenerationProgress, VideoPreview,
    │   │                           SceneTimeline, SceneCard
    │   ├── pages/Studio.jsx        page state machine + polling
    │   ├── services/api.js         typed fetch wrapper for the backend
    │   └── App.jsx / main.jsx / index.css
    ├── package.json
    └── .env.example
```

## 3. Installation

### Requirements

- Python 3.10+
- Node.js 18+
- **FFmpeg** installed and on your `PATH`

Install FFmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y ffmpeg espeak-ng

# Windows
# Download a build from https://www.gyan.dev/ffmpeg/builds/ and add its
# bin/ folder to your PATH
```

`espeak-ng` (Linux) powers the offline voice-over fallback. On macOS/Windows
the bundled system voices are used automatically by `pyttsx3` — no extra
install needed there.

### Backend setup

```bash
cd backend
python -m venv venv

# activate it
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env            # then edit .env, see below

uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`).

### Frontend setup

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_URL, defaults to localhost:8000
npm run dev
```

Open `http://localhost:5173`.

### Environment variables

**backend/.env**

| Variable | Required? | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Optional | Enables real AI script/scene generation. Get one free at [console.groq.com](https://console.groq.com). Without it, the app uses a built-in sample-script generator (demo mode) instead of crashing. |
| `GROQ_MODEL` | Optional | Defaults to `llama-3.3-70b-versatile`. |
| `IMAGE_API_KEY` | Optional | Reserved for a real image-generation provider. Not required — an offline stylized-gradient generator is used by default. |
| `VIDEO_API_KEY` | Optional | Reserved for a real video-generation provider. Not required — the Ken Burns image pipeline is used by default. |
| `TTS_API_KEY` | Optional | Reserved for a paid TTS provider. Not required — offline `pyttsx3`/`espeak-ng` is used by default. |
| `MUSIC_API_KEY` | Optional | Reserved for a licensed music library. Not required — a small synthesized ambient pad is used when "Background music" is enabled. |
| `USE_DEMO_MODE` | Recommended `true` | When `true`, any missing/failing provider falls back gracefully instead of erroring. Set to `false` only once you have a working `GROQ_API_KEY` and want hard failures instead of fallbacks. |
| `FRONTEND_URL` | Yes | Comma-separated CORS origins, e.g. `http://localhost:5173`. |

**frontend/.env**

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Base URL of the FastAPI backend, e.g. `http://localhost:8000`. |

### Getting a Groq API key

1. Go to [console.groq.com/keys](https://console.groq.com/keys)
2. Sign in and create a new API key
3. Paste it into `backend/.env` as `GROQ_API_KEY=gsk_...`
4. Restart the backend

## 4. Running locally

Two terminals:

```bash
# terminal 1
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Visit `http://localhost:5173`, type an idea, and click **Generate Video**.

## 5. How the fallbacks work

Every external dependency has a working fallback, so the whole pipeline runs
with **no API keys and no internet access at generation time**:

| Stage | Real provider | Fallback (default) |
|---|---|---|
| Script + scenes | Groq (`llama-3.3-70b-versatile`), strict JSON mode + Pydantic validation + one repair retry | Deterministic built-in sample script, sized to the requested duration |
| Scene visuals | Pluggable `BaseImageProvider` (wire in Stability/Replicate/etc via `IMAGE_API_KEY`) | Stylized gradient "concept card" rendered with Pillow, palette chosen per visual style |
| Motion | Pluggable `BaseVideoProvider` (real video-gen APIs are paid, not implemented) | Ken Burns zoom/pan over the generated image, via FFmpeg `zoompan` |
| Voice-over | Pluggable `BaseTTSProvider` (wire in ElevenLabs/Azure/etc via `TTS_API_KEY`) | Offline `pyttsx3` + `espeak-ng`, no internet or key required |
| Captions | — | SRT generated from scene narration/timing, burned in via FFmpeg `subtitles` filter |
| Background music | Pluggable, licensed library via `MUSIC_API_KEY` | Small synthesized ambient triad pad (FFmpeg `sine`+`amix`), looped and mixed at low volume |

If Groq is configured and available, it's always used; if it fails (bad key,
rate limit, malformed JSON even after a repair attempt) and `USE_DEMO_MODE=true`,
the app quietly falls back rather than showing the user a stack trace.

## 6. API reference

All endpoints are prefixed `/api/video` unless noted.

| Method | Path | Purpose |
|---|---|---|
| POST | `/create` | Start a full generation job. Body: `VideoCreateRequest`. Returns `{job_id}`. |
| GET | `/status/{job_id}` | Poll job progress/stage/status. |
| GET | `/{video_id}` | Fetch the full video record (scenes, paths, metadata). |
| GET | `/{video_id}/download` | Download the rendered MP4. |
| POST | `/script` | Preview the AI script/scene plan without rendering media. |
| POST | `/scenes` | Same as `/script`, returns just the scene list. |
| POST | `/scene/{scene_number}/regenerate` | Regenerate one scene's image + voice + clip, then re-render the final MP4. Body: `{video_id, visual_prompt?, narration?}`. |
| POST | `/voice` | One-off narration synthesis utility. |
| POST | `/captions` | Return the SRT text for a video's current scenes. |
| POST | `/render` | Re-render the final MP4 from current (possibly edited) scene clips. |
| GET | `/api/health` | Liveness + whether Groq/FFmpeg are available. |

## 7. Troubleshooting

### Fixed in this build (2026-08-11)

- **`imageio-ffmpeg` was missing from `requirements.txt`.** `app/utils/ffmpeg.py`
  tries to auto-locate a bundled FFmpeg binary via `imageio_ffmpeg`, but since
  the package was never declared as a dependency, a fresh
  `pip install -r requirements.txt` silently fell back to whatever `ffmpeg`
  was (or wasn't) on your system `PATH`. If FFmpeg wasn't separately
  installed and added to `PATH`, **every render call failed and no video was
  ever produced** — this is the most likely cause if "Generate Video" did
  nothing or errored out. Now fixed: `imageio-ffmpeg` is in
  `requirements.txt`, so a working FFmpeg binary is available automatically,
  no manual install required.
- `GET /api/health` now actually **executes** `ffmpeg -version` /
  `ffprobe -version` instead of just checking they exist on `PATH`, so it
  reliably tells you whether rendering will work.
- CORS now also accepts any `http://localhost:<port>` or
  `http://127.0.0.1:<port>` origin in addition to `FRONTEND_URL`, so a Vite
  dev server on an unexpected port (e.g. 5174 because 5173 was busy) doesn't
  get silently blocked — which looks exactly like "nothing happens when I
  click Generate" in the browser.

### First step: check `/api/health`

With the backend running, open `http://localhost:8000/api/health` (or run
`curl http://localhost:8000/api/health`). It should return:

```json
{
  "status": "ok",
  "groq_configured": false,
  "ffmpeg_available": true,
  "ffprobe_available": true
}
```

If `ffmpeg_available` is `false`, video generation cannot work — reinstall
dependencies with `pip install -r requirements.txt` (make sure
`imageio-ffmpeg` installs successfully; it downloads a small platform binary
on first use, so you need internet access once).

### Common issues

**"Video generation is temporarily unavailable" / job status is "failed"**
Check `ffmpeg_available` at `/api/health` (see above). Also check the
backend terminal output — every failure is logged with the underlying
FFmpeg/TTS error before being turned into a friendly message.

**Clicking "Generate Video" does nothing / spinner never starts**
Open the browser dev tools → Network tab. If the `POST /api/video/create`
request fails outright (not even a red 4xx/5xx, just fails), it's almost
always CORS or the backend not running:
- Confirm the backend is actually running at the URL in `frontend/.env`'s
  `VITE_API_URL` (default `http://localhost:8000`).
- Confirm `backend/.env` exists (copy it from `.env.example` if you skipped
  that step — the backend still runs without it, but it's easy to lose
  track of which values are active).

**Groq errors / falls back to demo script even with a key set**
Check `GET /api/health` → `groq_configured`. Make sure `GROQ_API_KEY` is in
`backend/.env` (not `.env.example`) and the backend was restarted after
adding it.

**No sound in the generated video**
On Linux, install `espeak-ng` (`sudo apt-get install espeak-ng`). If TTS
still fails, the app automatically substitutes silent audio matched to the
narration length so rendering never breaks — check backend logs for the
specific TTS error.

**CORS errors in the browser console**
Make sure `FRONTEND_URL` in `backend/.env` matches the URL you're loading
the frontend from exactly (including port) — or rely on the built-in
localhost/127.0.0.1 allowance described above.

**Video generation is slow**
The Ken Burns FFmpeg pass and offline TTS are CPU-bound; longer durations
(60–90s) and more scenes take proportionally longer. This is expected for a
local/demo deployment.

## 8. Limitations

- Video "generation" is really an AI-styled image + Ken Burns motion
  pipeline, not true text-to-video — wire in a real `BaseVideoProvider`
  implementation for actual generated motion clips
- The default image provider is a stylized typographic gradient card, not a
  diffusion-model image — wire in `IMAGE_API_KEY` + a real provider for
  photorealistic scenes
- In-memory job/video storage (`app/jobs.py`) — restarting the backend
  clears all video history; add a database if you need persistence across
  restarts
- Single-server deployment only; no queue/worker separation, so very long
  render queues will serialize behind FastAPI's background tasks

## 9. What to test next

1. Add a real `GROQ_API_KEY` and compare script quality against demo mode
2. Try all three aspect ratios and confirm the player + download match
3. Regenerate a single scene and confirm only that scene's clip changes
4. Toggle background music and captions off/on
5. Try a 90-second video to see multi-scene pacing and render time
6. Wire in a real image or TTS provider by implementing the corresponding
   `Base*Provider` interface in `backend/app/providers/`
