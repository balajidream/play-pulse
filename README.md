# Play Pulse

**See what’s trending on Google Play, where there’s still room, and what an indie should build next.**

Play Pulse is a local tool for indie mobile game developers (especially in India). It uses live SerpApi Play data to answer three questions in a short brief:

1. **What’s trending** on Google Play game charts right now
2. **What still has room** — genres or title patterns that are visible but not saturated
3. **What’s worth building next** — a plain-language recommendation tied to those numbers

A second mode keeps **check my idea** — a competitive shelf brief (title + pitch → Play search + saturation read).

Built for the **SerpApi India Hackathon 2026** — track **Commerce & Market Intelligence**.

## Who it’s for

An indie deciding what to prototype next — or validating a working title before shipping.

## How SerpApi is used (core, not cosmetic)

| Engine | Mode | Why |
| --- | --- | --- |
| `google_play_games` | Trend scan | Top charts (`chart=topselling_free`, `chart=movers_shakers`, `games_category=GAME`) — verified against [Google Play Games API](https://serpapi.com/google-play-games). |
| `google_play` | Trend (optional) + idea check | Query search (`q`) for idea probes / casual shelf probe. |
| `google_play_product` | Both | Enrich top unique apps: title, developer, rating, ratings count, description, genre (`store=apps`). |
| `google` | Both | One web search for recent coverage (“what people are writing”), separate from the shelf. |

**Localization:** `hl=en`, `gl=in`.

**Call budget:** about **≤10 credits** per run (trend: ~2 charts + ≤5 product + 1 Google; idea: ≤3 Play searches + ≤5 product + 1 Google).

There is **no LLM API**. Analysis is deterministic Python.

## Setup

```bash
cd shelf-check
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set SERPAPI_API_KEY=... from https://serpapi.com/users/sign_up
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

| Action | Needs key? |
| --- | --- |
| **Scan live Play trends** (home primary) | Yes — clear setup error if missing |
| **SAMPLE trend preview** | No — banner says SAMPLE, not live |
| **Build idea brief** | Yes |
| **SAMPLE idea preview** | No |

## What the trend scan shows

- **Trending now** — unique apps from topselling free + movers & shakers, genre mix, example titles
- **Still has room** — genres/title patterns that appear on charts but are not dominant / not packed with heavy-review incumbents
- **Worth building next** — one short recommendation grounded in those counts
- Optional **web coverage** hits from Google organic results

## Example idea-check input

| Field | Example |
| --- | --- |
| Working title | Rush Bay |
| One-line pitch | unblock colorful buses, match passengers, clear island parking bays |
| Extra keywords | bus parking sort puzzle |

## Tests

```bash
source .venv/bin/activate
pytest -q
```

Tests mock HTTP — no network and no real API key required.

## Project layout

```
app/           FastAPI, Serp client, trend + idea analyzers, query planner
templates/     Home, trends, idea brief (no JS build step)
static/        CSS
tests/         Mocked unit + route tests
SUBMISSION.md  Draft answers for the hackathon form
```

## License

MIT — see [LICENSE](LICENSE).
