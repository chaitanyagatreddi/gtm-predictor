# GTM Predictor

Spend forecasting, landing page scoring, ad creative scoring, lifecycle math, and LTV/CAC — for B2B/B2C SaaS marketers. All outputs cite real sources.

Live: https://gtm-predictor-two.vercel.app

## What's inside

| Module | Input | Output |
|---|---|---|
| **PPC** | Budget, channel, region, ICP, ACV, CRO/Creative scores | Full funnel (impressions → won), CAC, ROI |
| **ABM** | Budget, target accounts, ad format, region, offer | Pipeline range, funnel, CAC, ROI (ZenABM 2026 real data n=211) |
| **ABM Goal (reverse)** | Target deals, ACV | Spend range needed (median → top performer) |
| **CRO** | URL or pasted content | Per-dimension 0–10 scorecard + detailed fixes |
| **Creative** | Channel, ad copy, image desc | Per-dimension 0–10 + before/after rewrites |
| **Outbound (cold email)** | Subject, body, goal, LP, open/click rate | Per-dimension 0–10 + rewrites (Polar email as gold standard) |
| **LTV/CAC** | Simple (CAC + LTV) OR full (ARPU + churn + GM + etc.) | Ratio, verdict, payback, formula derivation |

## Data sources used

Every response cites the source URL. No invented numbers.

- **ZenABM 2026 LinkedIn ABM Performance Report** — n=211 B2B companies, $5.5M spend, 161K ads, 29 countries. CTR/CPC/CPM by format, ROAS, pipeline per dollar.
- **Wall Street Prep + Porter Metrics** — LTV/CAC formula and verdict thresholds.
- **Writesonic Mixpanel** (internal, B2C AI SaaS) — pageview→signup 30.46%, trial→paid 10.86%, $28.64 ARPU.
- **Kaggle Global Ads Performance** (synthetic, n=1,800) — Google/Meta/TikTok medians by industry × region. Precomputed to JSON.
- **WordStream 2023** — public LinkedIn / Google Ads benchmarks (fallback tier).
- **6sense, HubSpot, NN/g, Baymard, Unbounce** — funnel rates, CRO rubric sources.
- **Reference landing pages** in `data/reference_pages/` — Ciphrix, Velt, Writesonic, Botsonic. Used as few-shot 9/10 gold standards in CRO scoring.

## Architecture

```
gtm-predictor/
├── index.html                 # frontend (Tide-inspired light theme)
├── main.py                    # Vercel entrypoint (FastAPI service)
├── backend/
│   ├── server.py              # FastAPI routes
│   ├── predictor.py           # PPC + ABM math
│   ├── cro.py                 # URL scrape + LLM scoring
│   ├── creative.py            # ad copy rubric
│   ├── lifecycle.py           # cold email scoring + LTV/CAC
│   ├── benchmarks.py          # public WordStream baselines
│   ├── kaggle_benchmarks.py   # precomputed Kaggle medians
│   ├── zenabm.py              # ZenABM REST client (LinkedIn live data)
│   ├── abm_zenabm_real.py     # ZenABM 2026 report constants
│   └── writesonic_real.py     # Mixpanel B2C SaaS constants
├── data/
│   ├── kaggle_medians.json    # precomputed Kaggle benchmarks
│   └── reference_pages/       # gold-standard landing pages (markdown)
├── vercel.json                # empty (Vercel auto-detects FastAPI service)
├── requirements.txt
└── .gitignore
```

## Run locally

```bash
cd backend
python3.11 -m pip install -r ../requirements.txt
cp .env.example .env          # add your keys
uvicorn server:app --reload --port 8765
# open http://localhost:8765
```

## Env vars

| Name | Purpose | Required |
|---|---|---|
| `OPENAI_API_KEY` | CRO / Creative / Outbound scoring | yes |
| `ZENABM_TOKEN` | LinkedIn live engagement data | yes (or empty falls through to public benchmarks) |
| `FIRECRAWL_API_KEY` | Better URL scraping for CRO | optional (built-in scraper as fallback) |
| `GAS_WEBHOOK_URL` | Google Apps Script URL to log gate signups to Sheets | optional |
| `ALLOWED_EMAILS` | Comma-separated allowlist (gate). Empty = open mode. | optional |

## Deploy

Vercel — auto-detects as a FastAPI service. From repo root:

```bash
vercel --prod
```

Set env vars: `vercel env add <NAME> production` (one at a time).

## Status

Built for internal use, live in production. Numbers update as new sourced benchmarks are added — see `data/reference_pages/` for the curated reference set.
