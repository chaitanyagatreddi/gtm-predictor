from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

from predictor import predict_ppc, predict_abm
from cro import score_url, score_content
from compare import compare_pages
from analytics_import import parse_export, detect_source, match_to_page
from creative import score_creative
from lifecycle import score_sequence, ltv_cac

app = FastAPI(title="GTM Predictor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PPCReq(BaseModel):
    budget_usd: float
    channel: str = "linkedin"  # linkedin | google_search | google_display | meta | tiktok
    cro_score: float = 0.5
    creative_score: float = 0.5
    acv_usd: float = 10000
    region: str = "row"  # india | row
    icp: str = "b2b_saas"  # b2b_saas | b2c_saas (b2c_saas uses Writesonic real data)


class ABMReq(BaseModel):
    budget_usd: float
    target_accounts: int
    cro_score: float = 0.5
    creative_score: float = 0.5
    acv_usd: float = 50000
    ad_format: str = "thought_leader"  # thought_leader | single_image | carousel | video | text | document | event
    region: str = "north_america"      # north_america | europe | apac | latam
    offer: str = "demo_high_commitment"  # demo_high_commitment | content_low_friction | lead_gen_form


class ABMGoalReq(BaseModel):
    target_deals: int
    acv_usd: float = 50000
    ad_format: str = "thought_leader"
    region: str = "north_america"
    offer: str = "demo_high_commitment"


class CROReq(BaseModel):
    url: str


class CreativeReq(BaseModel):
    channel: str
    copy: str
    image_desc: str = ""


@app.get("/health")
def health(): return {"ok": True}


@app.post("/predict/ppc")
async def ppc(r: PPCReq): return await predict_ppc(r.budget_usd, r.channel, r.cro_score, r.creative_score, r.acv_usd, r.region, r.icp)


@app.post("/predict/abm")
def abm(r: ABMReq): return predict_abm(r.budget_usd, r.target_accounts, r.cro_score, r.creative_score, r.acv_usd, r.ad_format, r.region, r.offer)


@app.post("/predict/abm/goal")
def abm_goal(r: ABMGoalReq):
    """Reverse-engineer: 'I want X deals' → spend + funnel needed (ZenABM 2026 real data)."""
    from abm_zenabm_real import reverse_funnel_for_goal
    return reverse_funnel_for_goal(r.target_deals, r.ad_format, r.region, r.offer, r.acv_usd)


@app.post("/cro")
async def cro(r: CROReq):
    try: return await score_url(r.url)
    except Exception as e: raise HTTPException(500, str(e))


class CRORawReq(BaseModel):
    url: str
    title: str = ""
    content: str


@app.post("/cro/raw")
def cro_raw(r: CRORawReq):
    try: return score_content(r.url, r.title, r.content)
    except Exception as e: raise HTTPException(500, str(e))


MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB — serverless payload ceiling


class AnalyticsImportReq(BaseModel):
    content: str          # raw CSV text
    source: str = "ga4"
    match_url: str = ""   # optional: pull the row for one page


@app.post("/analytics/import")
def analytics_import(r: AnalyticsImportReq):
    if len(r.content.encode("utf-8")) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large. Filter the date range and export again (5MB max).")
    try:
        src = r.source or detect_source(r.content) or "ga4"
        data = parse_export(r.content, src)
        data["detected_source"] = detect_source(r.content)
        if r.match_url:
            data["matched_page"] = match_to_page(data["rows"], r.match_url)
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


class CompareReq(BaseModel):
    url: str
    competitor: str


@app.post("/compare")
async def compare(r: CompareReq):
    try: return await compare_pages(r.url, r.competitor)
    except Exception as e: raise HTTPException(500, str(e))


@app.post("/creative")
def creative(r: CreativeReq):
    try: return score_creative(r.channel, r.copy, r.image_desc)
    except Exception as e: raise HTTPException(500, str(e))


class LifecycleReq(BaseModel):
    sequence: str  # free-text or structured (with subject/goal/body/lp/etc)
    subject: str = ""
    goal: str = ""
    landing_page: str = ""
    open_rate_pct: float = 0
    click_rate_pct: float = 0
    trigger: str = ""


@app.post("/lifecycle/score")
def lifecycle_score(r: LifecycleReq):
    try:
        # Build structured input for the LLM
        structured = f"""SUBJECT: {r.subject or '(not given)'}
GOAL: {r.goal or '(not given)'}
LANDING PAGE: {r.landing_page or '(not given)'}
ASSUMED OPEN RATE: {r.open_rate_pct}%
ASSUMED CLICK RATE: {r.click_rate_pct}%
RE-ENGAGEMENT TRIGGER: {r.trigger or '(none)'}

BODY:
{r.sequence}"""
        return score_sequence(structured)
    except Exception as e: raise HTTPException(500, str(e))


class LTVCACReq(BaseModel):
    cac_usd: float
    monthly_arpu_usd: float
    monthly_churn_rate: float = 0.05
    gross_margin: float = 0.80
    activation_rate: float = 0.40
    trial_to_paid_rate: float = 0.15
    expansion_rate: float = 0.10
    referral_rate: float = 0.05


@app.post("/lifecycle/ltv-cac")
def lifecycle_ltv_cac(r: LTVCACReq):
    return ltv_cac(r.cac_usd, r.monthly_arpu_usd, r.monthly_churn_rate, r.gross_margin,
                   r.activation_rate, r.trial_to_paid_rate, r.expansion_rate, r.referral_rate)


class LTVCACSimpleReq(BaseModel):
    cac_usd: float
    ltv_usd: float


class GateReq(BaseModel):
    email: str
    name: str = ""
    role: str = ""
    title: str = ""


def _norm_email(e: str) -> str:
    """Normalize for matching. Gmail/Googlemail: strip dots in local part + drop +tag.
    Other domains: just lowercase + trim."""
    e = (e or "").strip().lower()
    if "@" not in e:
        return e
    local, domain = e.split("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


@app.post("/gate")
def gate(r: GateReq):
    """Gate. Proxies to GAS_WEBHOOK_URL (server-to-server, avoids multi-account browser bug).
    Always returns ok=true unless ALLOWED_EMAILS env restricts."""
    import json as _json
    import httpx as _httpx
    email = (r.email or "").strip().lower()
    norm = _norm_email(email)
    log_status = "skipped"
    gas_url = os.getenv("GAS_WEBHOOK_URL", "").strip()

    # Optional allowlist (keep prior behavior if env set)
    allowed_raw = os.getenv("ALLOWED_EMAILS", "").strip().lower()
    if allowed_raw:
        allowed = {_norm_email(e) for e in allowed_raw.split(",") if e.strip()}
        if norm not in allowed:
            return {"ok": False, "email": email, "normalized": norm, "mode": "allowlist"}

    # Log to Google Sheet via Apps Script (server-to-server)
    if gas_url and "@" in email:
        try:
            with _httpx.Client(timeout=10) as c:
                resp = c.post(
                    gas_url,
                    content=_json.dumps({
                        "email": email,
                        "name": (r.name or "").strip(),
                        "role": (r.role or "").strip(),
                        "title": (r.title or "").strip(),
                    }),
                    headers={"Content-Type": "text/plain"},
                    follow_redirects=True,
                )
                log_status = f"sent (HTTP {resp.status_code})"
        except Exception as e:
            log_status = f"error: {str(e)[:100]}"

    return {"ok": True, "mode": "open", "email": email, "log": log_status}


@app.post("/lifecycle/ltv-cac-simple")
def lifecycle_ltv_cac_simple(r: LTVCACSimpleReq):
    """Porter Metrics style: 2 inputs (CAC, LTV) → ratio + interpretation."""
    ratio = r.ltv_usd / r.cac_usd if r.cac_usd else 0
    if ratio >= 5:
        verdict = "under_investing"
        interpretation = f"Your LTV:CAC Ratio is {ratio:.2f}:1. A ratio above 5:1 suggests you're under-investing in customer acquisition — you could likely spend more aggressively on growth without sacrificing profitability."
    elif ratio >= 3:
        verdict = "healthy"
        interpretation = f"Your LTV:CAC Ratio is {ratio:.2f}:1. A healthy ratio is typically 3:1 or higher, indicating that the revenue generated by a customer is three times the cost of acquiring them. You're in the sustainable zone."
    elif ratio >= 1:
        verdict = "borderline"
        interpretation = f"Your LTV:CAC Ratio is {ratio:.2f}:1. You're breaking even or making small profit per customer, but below the 3:1 target. Consider strategies to reduce CAC or increase LTV to improve your ratio."
    else:
        verdict = "burning_cash"
        interpretation = f"Your LTV:CAC Ratio is {ratio:.2f}:1. Below 1:1 means you're losing money on every customer — burning cash. Pause growth spend, fix retention or pricing, then resume."
    return {
        "mode": "simple",
        "cac_usd": r.cac_usd,
        "ltv_usd": r.ltv_usd,
        "ltv_cac_ratio": round(ratio, 2),
        "ratio_display": f"{ratio:.2f}:1",
        "verdict": verdict,
        "interpretation": interpretation,
        "sources": [
            "Porter Metrics: https://portermetrics.com/en/free-tools/calculators/free-cacltv-ratio/",
            "Wall Street Prep: https://www.wallstreetprep.com/knowledge/ltv-cac-ratio/",
        ],
    }


# Serve frontend — works for local dev (../frontend) and Vercel (project root)
def _find_index_html():
    for p in [
        os.path.join(os.path.dirname(__file__), "..", "index.html"),       # Vercel root
        os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"),  # local dev
    ]:
        if os.path.isfile(p):
            return p
    return None

_INDEX_HTML = _find_index_html()

@app.get("/")
def index():
    if _INDEX_HTML:
        return FileResponse(_INDEX_HTML)
    return {"status": "ok", "note": "index.html not found, API only"}
