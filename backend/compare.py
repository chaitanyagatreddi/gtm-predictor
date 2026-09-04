"""
Competitor compare — scrape your page + a competitor's, score both on the CRO
rubric, then diff them into a "what they do better / steal this" report.

Reuses scrape_url + score_content + the OpenAI client from cro.py.
"""
import asyncio, json
from cro import scrape_url, score_content, oai


COMPARE_PROMPT = """You are a CRO expert comparing two landing pages.

You are given CRO scores for both pages plus excerpts of their actual copy.
Identify where the competitor beats the user's page, and exactly what to copy.

CRITICAL — never fabricate:
- their_actual_copy must be text that appears VERBATIM in the competitor excerpt
  provided. If you cannot find it, use "[not found in scraped content]".
- Do NOT invent names, job titles, company names, or metrics.
- Do NOT describe elements you cannot see in the provided content.

Rank the steal_list by IMPACT (biggest conversion gain first).

Return JSON only:
{
  "headline_verdict": str,
  "dimension_table": [
    {"dimension": str, "my_score": int, "their_score": int,
     "verdict": "ahead|behind|tied", "gap": int}
  ],
  "they_do_better": [
    {"dimension": str, "what_they_do": str, "their_actual_copy": str,
     "why_it_works": str, "source": str}
  ],
  "you_do_better": [
    {"dimension": str, "what_you_do": str}
  ],
  "steal_list": [
    {"rank": int, "action": str, "specific_change": str,
     "effort": "low|med|high", "expected_lift": str}
  ]
}"""


async def _scrape_one(url: str) -> dict:
    """Scrape a single URL, never raise — return an error marker instead."""
    try:
        page = await scrape_url(url)
        return {
            "url": url,
            "ok": True,
            "title": page.get("metadata", {}).get("title", ""),
            "content": (page.get("markdown") or "")[:20000],
            "scraper": page.get("scraper", "firecrawl"),
        }
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)}


async def compare_pages(my_url: str, competitor_url: str) -> dict:
    """Scrape + score both pages, then diff them."""
    mine, theirs = await asyncio.gather(
        _scrape_one(my_url), _scrape_one(competitor_url)
    )

    if not mine["ok"]:
        raise RuntimeError(f"Could not scrape your page: {mine['error']}")
    if not theirs["ok"]:
        return {
            "partial": True,
            "my_url": my_url,
            "competitor_url": competitor_url,
            "error": f"Could not scrape competitor: {theirs['error']}",
            "my_score": score_content(my_url, mine["title"], mine["content"]),
        }

    # Score both against the existing rubric
    my_score = score_content(my_url, mine["title"], mine["content"])
    their_score = score_content(competitor_url, theirs["title"], theirs["content"])

    # Diff pass — smaller excerpts to stay inside context
    payload = {
        "my_page": {"url": my_url, "scores": my_score, "excerpt": mine["content"][:6000]},
        "their_page": {"url": competitor_url, "scores": their_score, "excerpt": theirs["content"][:6000]},
    }

    resp = oai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": COMPARE_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )

    diff = json.loads(resp.choices[0].message.content)
    diff.update({
        "partial": False,
        "my_url": my_url,
        "competitor_url": competitor_url,
        "my_overall": my_score.get("overall_score_10"),
        "their_overall": their_score.get("overall_score_10"),
        "my_score": my_score,
        "their_score": their_score,
        "scrapers": {"mine": mine["scraper"], "theirs": theirs["scraper"]},
    })
    return diff
