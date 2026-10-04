# Play Pulse

**One hit, then the copies.**

Play Pulse is an emerging-trend finder for indie mobile developers. A market scan needs no idea. Or type a loop (bus parking sort, tile blast). Each row is the biggest title by ratings count — size, not launch date — and the smaller copies of that loop, labeled **Early** or **Filled**.

Built for the **SerpApi India Hackathon 2026** — track **Commerce & Market Intelligence**.

## Who it’s for

An indie deciding what to prototype next — or validating a working title before shipping.

## How SerpApi is used (core, not cosmetic)

| Engine | Mode | Why |
| --- | --- | --- |
| `google_play` | Market scan and loop check | `q` finds games in one loop so the hit and the copies are on the same shelf. |
| `google_play_product` | Both | Ratings count, developer, description, and `product_info.thumbnail` (`store=apps`). |
| `google` | Both | One web search for coverage, separate from the shelf. |
| `google_play_games` | Not used for this scan | Charts are in the client, but a chart does not show clones of one loop. |

**Icons:** `thumbnail` on Play search items, and `thumbnail` or `icon` on the product payload. Missing image → `/static/placeholder.svg`.

**Localization:** `hl=en`, `gl=in`.

**Paging:** `google_play` has no `start` offset. Each extra page sends `next_page_token` from `serpapi_pagination`. Cap is **3 pages** or **40 unique titles** per loop. If the first response has no token, the card says **first page only**.

**Call budget:** page searches are the bulk (up to 3 per loop, 2 loops on a market scan). Product lookups stay **≤5** (the hit and a few copies). Plus one Google search.

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

Market scan: two Play searches (`bus jam parking puzzle`, `block blast puzzle`), up to 5 product lookups, one Google search. A single loop uses the same engines with at most two queries. No launch dates are invented.

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
