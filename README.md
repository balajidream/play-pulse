# Play Pulse

**One hit, then the copies.**

Play Pulse is an emerging-trend finder for indie mobile developers. A market scan needs no idea. Or type a loop (bus parking sort, tile blast). Each row is the biggest title by ratings count — size, not launch date — and the smaller copies of that loop, labeled **Early** or **Filled**.

Built for the **SerpApi India Hackathon 2026** — track **Commerce & Market Intelligence**.

## Who it’s for

An indie deciding what to prototype next — or validating a working title before shipping.

## How SerpApi is used (core, not cosmetic)

| Engine | Mode | Why |
| --- | --- | --- |
| `google_play` | Market scan | Broad queries (`puzzle game`, `casual game`, `arcade game`, `simulation game`), paged with `next_page_token`. |
| `google_play_games` | Market scan | One chart pull: `chart=topselling_free`, `games_category=GAME`. |
| `google_play_product` | Hits only | At most 5 lookups so a few hit icons can be refreshed. Copy icons use search `thumbnail`. |
| `google` | Coverage | One web search, separate from the shelf. |

**Icons:** `thumbnail` on Play search items, and `thumbnail` or `icon` on the product payload. Missing image → `/static/placeholder.svg`.

**Localization:** `hl=en`, `gl=in`.

**Paging:** `google_play` has no `start` offset. Each extra page sends `next_page_token` from `serpapi_pagination`. Cap is **3 pages** or **40 unique titles** per loop. If the first response has no token, the card says **first page only**.

**Call budget:** one chart plus those broad searches, paged only while the 6-search cap lasts. Product lookups stay **≤5**. Loops are classified from the titles. A shelf is kept only with at least 3 copies, then sorted fewest copies first, up to 20.

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

## What a scan shows

Each loop is one card: a large hit (icon, title, rating, ratings count) and smaller clone cards. **Early** means one much larger title and only a few copies, or a few similar titles with no giant. **Filled** means many copies. Icons come from SerpApi `thumbnail` (or `icon`) on `google_play` and `google_play_product`. If that URL is missing, the page uses `/static/placeholder.svg`.

Market scan discovers loops from the chart and broad searches above. It does not start from a fixed pair of loops. Titles that miss a known loop are clustered by shared title words (not game, puzzle, free, or 3d). The shelf name is those shared words. A typed loop check still searches that one phrase.

Idea check (title + pitch) is still at `POST /analyze`.

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
