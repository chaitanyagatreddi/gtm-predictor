"""
Real B2C AI SaaS benchmarks — Writesonic Mixpanel data (Aug 2023 onwards).
Source: Writesonic internal analytics (Chaitanya). Live numbers, not synthetic.

Returns benchmarks for B2C AI SaaS predictions when ICP matches.
"""

# Source: Writesonic Mixpanel — Pageview → Signup → Subscription funnel (since Aug 2023)
WRITESONIC_FUNNEL = {
    "pageview_to_signup": 0.3046,     # 10.29M -> 3.14M
    "signup_to_subscription": 0.0028,  # 3.14M -> 8,889 (overall, organic + paid mixed)
    "signup_speed_under_1min": 0.59,   # 59% sign up within 1 min of landing
    "signup_to_sub_speed_under_1hr": 0.2973,  # 29.73% subscribe within 1hr of signup
    "source": "Writesonic Mixpanel (internal, verified screenshots Jun 2024)",
}

# Paid funnel (paid ads only — much higher quality than organic mix)
WRITESONIC_PAID = {
    "signups_from_paid": 42900,
    "new_paid_users": 4662,
    "trial_to_paid_rate": 0.1086,    # 10.86% — strong vs industry 2-5%
    "total_billed_usd": 133500,
    "arpu_per_paid_user_usd": 28.64,
    "mrr_mix_monthly": 0.33,
    "mrr_mix_annual": 0.10,
    "source": "Writesonic Paid Ads Dashboard (internal, Jun 2024)",
}

# Landing page conversion by destination
WRITESONIC_PAGES = {
    "/chat": {"traffic_share": 0.31, "signup_rate": 0.16},
    "writesonic.com (home)": {"traffic_share": 0.09, "signup_rate": 0.3483},
    "source": "Writesonic page-level analytics (internal, Jun 2024)",
}

# Monthly signup->sub trend (declining indicates market saturation / paid quality drop)
WRITESONIC_MONTHLY = {
    "2023-08": {"signups": 369055, "subs": 3485, "rate": 0.0094},
    "2023-09": {"signups": 563330, "subs": 2609, "rate": 0.0046},
    "2023-10": {"signups": 521749, "subs": 2121, "rate": 0.0041},
    "2023-11": {"signups": 494913, "subs": 1805, "rate": 0.0036},
    "2023-12": {"signups": 327170, "subs": 1661, "rate": 0.0051},
    "avg": {"signups": 337886, "subs": 1763, "rate": 0.0052},
    "source": "Writesonic month-over-month Mixpanel (internal)",
}

# Botsonic (B2B AI SaaS arm) — much smaller scale, useful for B2B AI baseline
BOTSONIC_FUNNEL = {
    "starting_mrr_usd": 571,
    "ending_mrr_30d_usd": 4500,
    "mrr_growth_30d_pct": 7.88,  # 4500/571 - 1
    "arr_starting_usd": 4508,
    "arr_ending_30d_usd": 55000,
    "source": "Botsonic Mixpanel (internal, Jun 2024)",
}


def real_b2c_benchmarks(channel: str = "any") -> dict:
    """
    Returns Writesonic-derived B2C AI SaaS benchmarks.
    Use when ICP is B2C AI SaaS / prosumer.
    """
    return {
        "avg_cpc_usd": None,  # not directly in Mixpanel data, fall through to channel default
        "pageview_to_signup": WRITESONIC_FUNNEL["pageview_to_signup"],
        "trial_to_paid_rate": WRITESONIC_PAID["trial_to_paid_rate"],
        "arpu_per_paid_user_usd": WRITESONIC_PAID["arpu_per_paid_user_usd"],
        "signup_to_subscription_overall": WRITESONIC_FUNNEL["signup_to_subscription"],
        "source": WRITESONIC_PAID["source"],
        "tier": "real_b2c_writesonic",
    }


def real_b2b_ai_benchmarks() -> dict:
    """Botsonic-derived B2B AI SaaS — small sample, treat as directional only."""
    return {
        "mrr_growth_potential_30d": BOTSONIC_FUNNEL["mrr_growth_30d_pct"],
        "source": BOTSONIC_FUNNEL["source"],
        "tier": "real_b2b_botsonic",
        "note": "Small sample (30 days early MRR). Use directional only.",
    }
