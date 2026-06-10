"""
ABM benchmarks — ZenABM 2026 LinkedIn ABM Performance Report.
Source: https://zenabm.com/blog/linkedin-abm-performance-benchmarks-report-2026
       https://zenabm.com/blog/linkedin-ads-benchmarks
Sample: 211 B2B companies, 161,256 LinkedIn ads, $5.5M spend, 29 countries, CRM-connected.

Real sourced data — cite ZenABM in every response that uses these numbers.
"""

SOURCE = "ZenABM 2026 LinkedIn ABM Performance Benchmarks Report (n=211 companies, 161K ads, $5.5M spend, 29 countries)"
SOURCE_URLS = [
    "https://zenabm.com/blog/linkedin-abm-performance-benchmarks-report-2026",
    "https://zenabm.com/blog/linkedin-ads-benchmarks",
]

# CTR by ad format (median)
CTR_BY_FORMAT = {
    "thought_leader": 0.0268,
    "event": 0.0055,
    "document": 0.0043,
    "single_image": 0.0042,
    "carousel": 0.0032,
    "video": 0.0024,
    "text": 0.0002,
}

# CPC by format (median USD)
CPC_BY_FORMAT = {
    "thought_leader": 2.29,
    "single_image": 13.23,
    "carousel": 13.30,
    "video": 15.61,
}

# CPM by format (median USD)
CPM_BY_FORMAT = {
    "text": 2.00,
    "video": 38.94,
    "carousel": 45.28,
    "thought_leader": 49.37,
    "single_image": 59.15,
}

# CPM by country (median USD)
CPM_BY_COUNTRY = {
    "USA": 62.67,
    "UK": 56.62,
    "Netherlands": 50.08,
}

# Conversion rates by offer type
CONV_RATE_BY_OFFER = {
    "demo_high_commitment": (0.02, 0.05),    # 2-5%
    "content_low_friction": (0.10, 0.15),    # 10-15%
    "lead_gen_form": (0.10, 0.15),           # ~10% median, top 15%+
}

# CPL by region (USD)
CPL_BY_REGION = {
    "north_america": (200, 250),
    "europe": (120, 150),
    "apac": (80, 120),
    "latam": (60, 90),
}

# Pipeline + ROAS
PIPELINE_PER_DOLLAR = {
    "median": 5.21,
    "top_performer": 15.20,
}
ROAS = {
    "median": 1.62,
    "top_performer": 2.79,
}

# Lead Gen Form vs Landing Page
LEAD_GEN_FORM_CPL_REDUCTION = 0.25  # 20-30% lower CPL


def region_to_key(region: str) -> str:
    """Map our region input to ZenABM region key."""
    r = (region or "").lower()
    if r in ("india", "apac", "sea"): return "apac"
    if r in ("us", "usa", "na", "north_america", "north america"): return "north_america"
    if r in ("eu", "europe", "uk", "ireland"): return "europe"
    if r in ("latam", "brazil", "mexico"): return "latam"
    return "north_america"  # default


def abm_benchmark(ad_format: str = "single_image", region: str = "north_america", offer: str = "demo_high_commitment") -> dict:
    """
    Returns ABM benchmark for a given format + region + offer type.
    All numbers cited from ZenABM 2026 report.
    """
    rkey = region_to_key(region)
    cpl_lo, cpl_hi = CPL_BY_REGION.get(rkey, CPL_BY_REGION["north_america"])
    conv_lo, conv_hi = CONV_RATE_BY_OFFER.get(offer, CONV_RATE_BY_OFFER["demo_high_commitment"])

    return {
        "ad_format": ad_format,
        "region": rkey,
        "offer": offer,
        "ctr_median": CTR_BY_FORMAT.get(ad_format, CTR_BY_FORMAT["single_image"]),
        "cpc_median_usd": CPC_BY_FORMAT.get(ad_format, CPC_BY_FORMAT["single_image"]),
        "cpm_median_usd": CPM_BY_FORMAT.get(ad_format, CPM_BY_FORMAT["single_image"]),
        "conv_rate_median": (conv_lo + conv_hi) / 2,
        "conv_rate_range": [conv_lo, conv_hi],
        "cpl_median_usd": (cpl_lo + cpl_hi) / 2,
        "cpl_range_usd": [cpl_lo, cpl_hi],
        "pipeline_per_dollar_median": PIPELINE_PER_DOLLAR["median"],
        "pipeline_per_dollar_top": PIPELINE_PER_DOLLAR["top_performer"],
        "roas_median": ROAS["median"],
        "roas_top": ROAS["top_performer"],
        "lead_gen_form_cpl_reduction": LEAD_GEN_FORM_CPL_REDUCTION,
        "source": SOURCE,
        "source_urls": SOURCE_URLS,
        "tier": "real_abm_zenabm",
    }


def reverse_funnel_for_goal(target_deals: int, ad_format: str = "thought_leader",
                             region: str = "north_america", offer: str = "demo_high_commitment",
                             acv_usd: float = 10000) -> dict:
    """
    Given a deal goal, reverse-engineer the funnel + spend needed.
    Uses ZenABM median benchmarks.

    Math:
    - Deals = ACV × close rate (assume 22% B2B SaaS opp→won from HubSpot 2024)
    - Opps = Deals / 0.22
    - MQLs = Opps / 0.20  (industry SQL→Opp)
    - Demos/Leads = MQLs / 0.13 (industry MQL→SQL... wait that's the wrong direction)

    Simpler model using ZenABM data:
    - Pipeline needed = target_deals × ACV × 4 (typical 4x pipeline coverage)
    - Spend needed = Pipeline / pipeline_per_dollar_median ($5.21)
    """
    pipeline_coverage = 4.0  # standard B2B coverage
    pipeline_needed_usd = target_deals * acv_usd * pipeline_coverage
    spend_median_usd = pipeline_needed_usd / PIPELINE_PER_DOLLAR["median"]
    spend_top_perf_usd = pipeline_needed_usd / PIPELINE_PER_DOLLAR["top_performer"]

    bench = abm_benchmark(ad_format, region, offer)
    clicks_needed = spend_median_usd / bench["cpc_median_usd"]
    impressions_needed = clicks_needed / bench["ctr_median"]
    leads_needed = clicks_needed * bench["conv_rate_median"]

    return {
        "target_deals": target_deals,
        "acv_usd": acv_usd,
        "pipeline_needed_usd": round(pipeline_needed_usd),
        "spend_median_usd": round(spend_median_usd),
        "spend_top_performer_usd": round(spend_top_perf_usd),
        "spend_range_usd": [round(spend_top_perf_usd), round(spend_median_usd)],
        "clicks_needed": round(clicks_needed),
        "impressions_needed": round(impressions_needed),
        "leads_estimated": round(leads_needed),
        "assumptions": {
            "pipeline_coverage_x": pipeline_coverage,
            "pipeline_per_dollar_median": PIPELINE_PER_DOLLAR["median"],
            "pipeline_per_dollar_top": PIPELINE_PER_DOLLAR["top_performer"],
            "ad_format": ad_format,
            "region": region,
            "offer": offer,
        },
        "benchmark_used": bench,
        "source": SOURCE,
        "source_urls": SOURCE_URLS,
    }
