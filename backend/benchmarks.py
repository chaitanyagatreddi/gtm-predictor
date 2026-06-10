"""
GTM benchmarks — sourced. Every number must have a source URL.
Update as new reports come out.
"""

# LinkedIn Ads — WordStream 2023 industry benchmarks
# Source: https://www.wordstream.com/blog/ws/2023/03/15/linkedin-ads-benchmarks
LINKEDIN = {
    "avg_cpc_usd": 5.58,
    "avg_ctr": 0.0065,  # 0.65%
    "avg_conv_rate": 0.065,  # 6.5% click->lead
    "source": "https://www.wordstream.com/blog/ws/2023/03/15/linkedin-ads-benchmarks",
}

# Google Search — WordStream 2023, B2B vertical
# Source: https://www.wordstream.com/blog/ws/2023/02/28/google-ads-benchmarks
GOOGLE_SEARCH_B2B = {
    "avg_cpc_usd": 3.33,
    "avg_ctr": 0.0480,  # 4.80%
    "avg_conv_rate": 0.0345,  # 3.45%
    "source": "https://www.wordstream.com/blog/ws/2023/02/28/google-ads-benchmarks",
}

# Meta (Facebook+Instagram) Ads — WordStream 2023, B2B
GOOGLE_DISPLAY_B2B = {
    "avg_cpc_usd": 0.79,
    "avg_ctr": 0.0046,
    "avg_conv_rate": 0.0080,
    "source": "https://www.wordstream.com/blog/ws/2023/02/28/google-ads-benchmarks",
}

META_B2B = {
    "avg_cpc_usd": 1.72,
    "avg_ctr": 0.0090,
    "avg_conv_rate": 0.0975,
    "source": "https://www.wordstream.com/blog/ws/2023/02/01/facebook-advertising-benchmarks",
}

# B2B SaaS funnel — First Page Sage 2024 report
# Source: https://firstpagesage.com/reports/average-conversion-rates-by-industry/
B2B_SAAS_FUNNEL = {
    "mql_to_sql": 0.13,   # 13%
    "sql_to_opp": 0.20,   # 20% (ProfitWell B2B SaaS median)
    "opp_to_won": 0.22,   # 22% (HubSpot State of Sales 2024)
    "source_mql_sql": "https://firstpagesage.com/reports/average-lead-conversion-rates-by-industry/",
    "source_sql_opp": "https://www.profitwell.com/recur/all/saas-sales-funnel-conversion",
    "source_won": "https://www.hubspot.com/state-of-marketing",
}

# ABM-specific — 6sense 2024 benchmark report
# Source: https://6sense.com/resources/research/state-of-predictable-revenue/
ABM_FUNNEL = {
    "account_engaged_rate": 0.18,  # accounts reached -> engaged
    "engaged_to_mqa": 0.25,        # engaged -> marketing qualified account
    "mqa_to_opp": 0.27,
    "opp_to_won": 0.35,            # ABM closes higher than inbound
    "source": "https://6sense.com/resources/research/state-of-predictable-revenue/",
}


def get_channel(channel: str) -> dict:
    return {
        "linkedin": LINKEDIN,
        "google_search": GOOGLE_SEARCH_B2B,
        "google_display": GOOGLE_DISPLAY_B2B,
        "meta": META_B2B,
    }.get(channel, GOOGLE_SEARCH_B2B)
