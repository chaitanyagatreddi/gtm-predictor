"""
Kaggle benchmarks — precomputed from Global Ads Performance dataset (1,800 campaigns).
Source: https://www.kaggle.com/datasets/nudratabbas/global-ads-performance-google-meta-tiktok
License: CC0 Public Domain.
NOTE: dataset is synthetically generated — structurally correct, not real-world numbers.

We precompute medians to JSON so production has zero pandas dependency.
Regenerate JSON by running the pandas snippet in deploy.sh / docs.
"""
import os, json
from functools import lru_cache

JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kaggle_medians.json")


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(JSON_PATH) as f:
        return json.load(f)


@lru_cache(maxsize=64)
def benchmark(platform: str = "Google Ads", campaign_type: str = "Search", region: str = "row") -> dict:
    data = _load()
    entry = data.get(region, {}).get(platform, {}).get(campaign_type)
    if not entry:
        return {}
    return {
        **entry,
        "region": region,
        "platform": platform,
        "campaign_type": campaign_type,
        "source": "Kaggle: Global Ads Performance (nudratabbas, CC0, synthetic — precomputed medians)",
    }


def all_benchmarks(region: str = "row") -> dict:
    out = {}
    data = _load()
    for plat, types in data.get(region, {}).items():
        for ct in types:
            out[f"{plat}__{ct}"] = benchmark(plat, ct, region)
    return out
