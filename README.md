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
| **Compare** | Your landing page URL + a competitor's | Both scored on the CRO rubric, plus a head-to-head diff |
| **Analytics import** | GA4 "Pages and screens" CSV export | Parsed page table, optionally matched to a scored URL |
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
│   ├── compare.py             # two-page competitor comparison
│   ├── analytics_import.py    # GA4 CSV export parser
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
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt uvicorn
npx vercel env pull .env.local --environment=production
./run-local.sh                # http://localhost:8765
```

Vercel will not export secret values, so `.env.local` carries `[SENSITIVE]`
placeholders for `OPENAI_API_KEY`, `ZENABM_TOKEN` and `GTMP`. `run-local.sh`
drops those placeholders and sources the real values from
`~/.claude/secrets.zsh`.

Use 3.12 rather than the system Python: production runs a newer runtime, so
an older local interpreter can accept code that fails once deployed.

## Staging

Work on the `staging` branch. Pushing it builds a Vercel preview with the
production environment on the real serverless runtime, which catches cold
starts, the 60s function ceiling and missing env vars that a local server
cannot. Merge to `main` only once the preview looks right; `main` deploys
straight to production.

## Env vars

| Name | Purpose | Required |
|---|---|---|
| `OPENAI_API_KEY` | CRO / Creative / Outbound scoring | yes |
| `ZENABM_TOKEN` | LinkedIn live engagement data | yes (or empty falls through to public benchmarks) |
| `FIRECRAWL_API_KEY` | Better URL scraping for CRO | optional (built-in scraper as fallback) |
| `ZENROWS_API_KEY` | Scraping tier for Cloudflare / JS-rendered pages | optional |
| `GAS_WEBHOOK_URL` | Google Apps Script URL to log gate signups to Sheets | optional |
| `ALLOWED_EMAILS` | Comma-separated allowlist (gate). Empty = open mode. | optional |

## Deploy

Vercel — auto-detects as a FastAPI service. From repo root:

```bash
vercel --prod
```

Set env vars: `vercel env add <NAME> production` (one at a time).

## Notes on inputs

- URLs may be entered without a protocol; `https://` is added automatically.
- GA4 exports keyed on **page title** cannot be matched to a URL. Re-export
  using **Page path and screen class** if you need page matching.

## Status

Built for internal use, live in production. Numbers update as new sourced benchmarks are added — see `data/reference_pages/` for the curated reference set.
