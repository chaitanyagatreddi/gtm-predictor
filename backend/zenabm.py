"""
ZenABM REST client — pulls real account performance to override generic benchmarks.
Source: https://app.zenabm.com/api/v1 (verified live 2026-06-08).
"""
import os, httpx
from typing import Optional

BASE = "https://app.zenabm.com/api/v1"
TOKEN = os.getenv("ZENABM_TOKEN")


def _headers():
    if not TOKEN:
        raise RuntimeError("ZENABM_TOKEN not set in env")
    return {"Authorization": f"Bearer {TOKEN}"}


async def get_linkedin_metrics(period: str = "last30Days") -> dict:
    """Real LinkedIn CTR/CPC/conv from user's account."""
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/linkedin-metrics", params={"period": period}, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("data", {})


async def get_ad_spend(period: str = "last30Days") -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/ad-spend", params={"period": period}, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("data", {})


async def list_deals(period: str = "last90Days") -> list:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/deals", params={"period": period, "pageSize": 100}, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("data", [])


async def real_benchmarks() -> Optional[dict]:
    """
    Derive CPC/CTR/click-to-lead from actual ZenABM data.
    Returns None if account has no data (predictor falls back to public benchmarks).
    """
    try:
        m = await get_linkedin_metrics("last90Days")
        cur = m.get("current") or m.get("linkedInMetrics", {}).get("current") or {}
        imp = cur.get("impressions", 0)
        clicks = cur.get("clicks", 0)
        cost = cur.get("costInUsd", 0)
        if not imp or not clicks or not cost:
            return None
        deals = await list_deals("last90Days")
        won = sum(1 for d in deals if (d.get("stage") or "").lower() in ("won", "closed_won"))
        # crude click->won until we get MQL field
        return {
            "avg_cpc_usd": round(cost / clicks, 2),
            "avg_ctr": round(clicks / imp, 4),
            "click_to_won": round(won / clicks, 4) if clicks else 0,
            "source": "ZenABM /api/v1 — your account, last 90 days",
        }
    except Exception:
        return None
