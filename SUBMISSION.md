# SerpApi India Hackathon 2026 — submission draft

Paste these into the official form. **Do not** put phone numbers, home address, or API keys in the GitHub repo.

**Deadline:** 10 Oct 2026, 23:59 IST  
**Entrant:** Balaji Masilamani (solo)  
**Project name:** Play Pulse

---

## Project description (what / who / why)

**Play Pulse** helps indie mobile game developers in India decide what to build next using live Google Play data. The primary flow is a **trend scan**: SerpApi game charts show what is trending, which genres/title patterns still have room, and a short numbers-backed recommendation for what is worth prototyping. A second mode lets you **check a working title + pitch** against Play search and product enrichment (competitive shelf brief). Output is a scannable brief — not a chatbot. Built for judges to click through in under three minutes.

## Track

**Commerce & Market Intelligence**

## SerpApi usage (engines and why)

- **`google_play_games`** — trend core: `chart=topselling_free` and `chart=movers_shakers` with `games_category=GAME` (official Games Store API).
- **`google_play`** — idea-check queries (`q`) and an optional casual puzzle probe on the trend path.
- **`google_play_product`** — enrich top unique apps (`product_id`, `store=apps`) with ratings, description, genre, developer.
- **`google`** — one organic web search for recent writing about mobile games / the idea’s genre, shown separately from the store shelf.

SerpApi is the data backbone. Call volume is capped (~10 credits per run) for free-tier demos.

## Public GitHub repository

_(Add the public repo URL after you push. This workspace copy lives at `/workspace/shelf-check` and was not auto-published.)_

## Demo video notes (under 3 minutes)

1. Blur the API key; show the app starting locally.  
2. Home → **Scan live Play trends** → scroll the three answers (trending / room / build next), genre table, chart apps.  
3. Jump to **check my idea** with Rush Bay example → brief findings.  
4. Optionally open **SAMPLE trend** and point at the SAMPLE banner.

Unlisted YouTube or shareable Drive link that opens in incognito without sign-in.

## Did this project exist before the Hackathon?

**No.** Built during the SerpApi India Hackathon 2026 window for this submission.

## AI tools used

Development was assisted by an AI coding assistant in Cursor. Product analysis uses no LLM API — only SerpApi + deterministic Python.

## How did you hear about the event?

Found while researching online game and app contests.

## Lead participant (form only — keep PII out of the repo)

| Field | Value |
| --- | --- |
| Name | Balaji Masilamani |
| Email | _(your email)_ |
| Mobile | _(your mobile — form only)_ |
| Occupation | _(your occupation)_ |
| Years of professional experience | _(number; 0 if none)_ |

## Team

Solo — no additional members.

## Checklist before Submit

- [ ] Public GitHub repo with README setup instructions  
- [ ] Demo video link opens in incognito  
- [ ] Track: Commerce & Market Intelligence  
- [ ] SerpApi engines explained in the form  
- [ ] Prior project: No  
- [ ] AI tools field filled  
- [ ] Rules + Terms accepted  
- [ ] Submitted before 10 Oct 2026 23:59 IST  
