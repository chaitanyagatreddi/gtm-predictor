"""
Predictor — spend in, funnel out.
Adjusts conversion rate by CRO score and CTR by creative score.
"""
from benchmarks import get_channel, B2B_SAAS_FUNNEL, ABM_FUNNEL
from zenabm import real_benchmarks
from kaggle_benchmarks import benchmark as kaggle_benchmark
from writesonic_real import real_b2c_benchmarks
from abm_zenabm_real import abm_benchmark as zenabm_real_abm, reverse_funnel_for_goal

# channel -> Kaggle platform name
_PLATFORM_MAP = {
    "linkedin": None,  # not in Kaggle dataset
    "google_search": ("Google Ads", "Search"),
    "google_display": ("Google Ads", "Display"),
    "meta": ("Meta Ads", "Search"),
    "tiktok": ("TikTok Ads", "Video"),
}


async def predict_ppc(budget_usd: float, channel: str, cro_score: float = 0.5, creative_score: float = 0.5, acv_usd: float = 10000, region: str = "row", icp: str = "b2b_saas", use_real: bool = True) -> dict:
    """
    cro_score, creative_score: 0-1 (0.5 = avg, 1.0 = top decile, 0.0 = broken)
    Adjustment: ±50% around benchmark based on score.
    """
    public = get_channel(channel)
    f = B2B_SAAS_FUNNEL

    # 4-tier benchmark resolution:
    # ZenABM real (LinkedIn only) > Writesonic real (B2C SaaS) > Kaggle (region-aware) > public
    real = await real_benchmarks() if (use_real and channel == "linkedin") else None
    wsonic = real_b2c_benchmarks(channel) if (not real and icp == "b2c_saas") else None
    kg = None
    if not real and not wsonic and channel in _PLATFORM_MAP and _PLATFORM_MAP[channel]:
        plat, ctype = _PLATFORM_MAP[channel]
        kg = kaggle_benchmark(plat, ctype, region) or None

    src = real or wsonic or kg or public
    if real: data_source = "zenabm_real"
    elif wsonic: data_source = "writesonic_real_b2c"
    elif kg: data_source = "kaggle_" + region
    else: data_source = "public_benchmarks"

    # Score adjustment: 0.5 = 1x benchmark, 1.0 = 1.5x, 0.0 = 0.5x
    ctr_mult = 0.5 + creative_score
    conv_mult = 0.5 + cro_score

    cpc = src.get("avg_cpc_usd") or public["avg_cpc_usd"]
    ctr = (src.get("avg_ctr") or public["avg_ctr"]) * ctr_mult
    # Writesonic data: use real pageview->signup as click_to_lead if B2C; else channel default
    if wsonic:
        click_to_lead = wsonic["pageview_to_signup"] * conv_mult
    else:
        click_to_lead = public["avg_conv_rate"] * conv_mult
    source_label = src.get("source", public["source"])

    clicks = budget_usd / cpc
    impressions = clicks / ctr if ctr else 0
    leads = clicks * click_to_lead
    sqls = leads * f["mql_to_sql"]
    opps = sqls * f["sql_to_opp"]
    won = opps * f["opp_to_won"]
    revenue = won * acv_usd

    return {
        "mode": "ppc",
        "channel": channel,
        "budget_usd": budget_usd,
        "impressions": round(impressions),
        "clicks": round(clicks),
        "leads_mql": round(leads, 1),
        "sqls": round(sqls, 1),
        "opps": round(opps, 1),
        "closed_won": round(won, 2),
        "revenue_usd": round(revenue),
        "cac_usd": round(budget_usd / won, 2) if won > 0 else None,
        "cac_note": None if won >= 1 else f"Fractional deal ({round(won,2)}). Budget likely too small for 1 closed deal — scale ~{round(budget_usd/won if won>0 else 0)}+ for first deal.",
        "roi": round(revenue / budget_usd, 2) if budget_usd else 0,
        "assumptions": {
            "cpc": cpc, "ctr": round(ctr, 4), "click_to_lead": round(click_to_lead, 4),
            "mql_to_sql": f["mql_to_sql"], "sql_to_opp": f["sql_to_opp"], "opp_to_won": f["opp_to_won"],
            "acv_usd": acv_usd, "cro_score": cro_score, "creative_score": creative_score,
        },
        "sources": [source_label, f["source_mql_sql"], f["source_sql_opp"], f["source_won"]],
        "data_source": data_source,
        "region": region,
    }


def predict_abm(budget_usd: float, target_accounts: int, cro_score: float = 0.5, creative_score: float = 0.5, acv_usd: float = 50000, ad_format: str = "thought_leader", region: str = "north_america", offer: str = "demo_high_commitment") -> dict:
    """
    ABM: account-level funnel using ZenABM 2026 real benchmark data (n=211 companies).
    Tier 1: ZenABM real data | Tier 2 (fallback): generic 6sense ABM_FUNNEL.
    """
    bench = zenabm_real_abm(ad_format, region, offer)
    f = ABM_FUNNEL

    cpm = bench["cpm_median_usd"]
    cpc = bench["cpc_median_usd"]
    impressions = (budget_usd / cpm) * 1000

    engage_mult = 0.5 + creative_score
    convert_mult = 0.5 + cro_score

    # Format-driven funnel: clicks → leads → engaged accounts → MQA → opps → won
    # ZenABM data shows TLA delivers 6x clicks per $ vs single_image, so format directly drives volume.
    clicks = budget_usd / cpc
    leads = clicks * bench["conv_rate_median"] * convert_mult

    # Assume ~2 leads per engaged account (multi-stakeholder buying committee).
    # Cap at target_accounts so you can't engage more accounts than you targeted.
    accounts_engaged_from_leads = leads / 2.0
    accounts_reached = min(target_accounts, impressions / 150)
    engaged = min(target_accounts, accounts_engaged_from_leads * engage_mult)

    mqa = engaged * f["engaged_to_mqa"] * convert_mult
    opps = mqa * f["mqa_to_opp"]
    won = opps * f["opp_to_won"]
    revenue = won * acv_usd

    # ZenABM pipeline efficiency varies by format (TLA = top performer territory)
    # Apply format multiplier to pipeline-per-dollar
    format_efficiency = {
        "thought_leader": 1.5,    # closest to top performer ($15.20/$)
        "single_image": 1.0,      # baseline median
        "carousel": 0.9,
        "video": 0.85,
        "document": 0.95,
        "event": 0.9,
        "text": 0.5,              # cheap but low intent
    }.get(ad_format, 1.0)
    pipeline_estimated = budget_usd * bench["pipeline_per_dollar_median"] * format_efficiency
    pipeline_top_perf = budget_usd * bench["pipeline_per_dollar_top"] * format_efficiency

    return {
        "mode": "abm",
        "budget_usd": budget_usd,
        "target_accounts": target_accounts,
        "accounts_reached": round(accounts_reached),
        "accounts_engaged": round(engaged),
        "mqa": round(mqa, 1),
        "opps": round(opps, 1),
        "closed_won": round(won, 2),
        "revenue_usd": round(revenue),
        "cac_usd": round(budget_usd / won, 2) if won > 0 else None,
        "roi": round(revenue / budget_usd, 2) if budget_usd else 0,
        "pipeline_estimated_usd": round(pipeline_estimated),
        "pipeline_top_performer_usd": round(pipeline_top_perf),
        "pipeline_range_usd": [round(pipeline_estimated), round(pipeline_top_perf)],
        "assumptions": {
            "cpm_zenabm": cpm,
            "cpc_zenabm": cpc,
            "ctr_zenabm": bench["ctr_median"],
            "conv_rate_zenabm": bench["conv_rate_median"],
            "pipeline_per_dollar_median": bench["pipeline_per_dollar_median"],
            "pipeline_per_dollar_top": bench["pipeline_per_dollar_top"],
            "engaged_rate": f["account_engaged_rate"], "engaged_to_mqa": f["engaged_to_mqa"],
            "mqa_to_opp": f["mqa_to_opp"], "opp_to_won": f["opp_to_won"],
            "acv_usd": acv_usd, "cro_score": cro_score, "creative_score": creative_score,
            "ad_format": ad_format, "region": region, "offer": offer,
        },
        "data_source": "zenabm_real_abm",
        "sources": bench["source_urls"] + [f["source"]],
        "source_label": bench["source"],
    }
