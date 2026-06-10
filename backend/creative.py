"""
Creative scorer — score ad creative (URL to image OR text copy) against channel best practices.
"""
import os, json
from openai import OpenAI

_client = None
def oai():
    global _client
    if _client is None: _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


RUBRICS = {
    "linkedin": """LinkedIn Ad creative rubric (Source: LinkedIn Marketing Solutions Best Practices 2024):
- Hook in first 2 lines (LinkedIn collapses after)
- Specific number or claim
- Tagged audience (job title, industry)
- Single CTA
- Image: shows people or product, not stock
- Copy length: 150 chars optimal for see-more rate""",
    "google": """Google Ads creative rubric (Source: Google Ads Help 2024):
- Headline 1 contains primary keyword
- Headline 2 contains differentiator
- Headline 3 contains CTA
- Description: benefit + proof + CTA
- Sitelinks/callouts present""",
    "meta": """Meta Ads creative rubric (Source: Meta Advantage+ Creative Best Practices 2024):
- Hook in first 3 seconds (video) or first line (static)
- Bold visual contrast
- Single product/message
- Native feel (not banner-y)
- CTA matches landing page promise""",
}


def score_creative(channel: str, copy: str, image_desc: str = "") -> dict:
    rubric = RUBRICS.get(channel, RUBRICS["linkedin"])
    prompt = f"""You are a paid media creative reviewer.
{rubric}

Score each rubric item /10. For EVERY item, return a DETAILED fix — not a 1-liner.

`fix` must include:
- before_quote: exact current copy element (or "[missing]" if absent)
- after_suggestion: rewritten copy / specific element to add — actual words
- why: 1-sentence reason this works better (with cited principle)
- effort: "low" (<1 day) | "med" (1-3 days) | "high"
- expected_lift: rough CTR/CVR lift estimate (e.g., "+10-15% CTR")

Return JSON only:
{{
  "channel": "{channel}",
  "overall_score_10": float,
  "dimensions": [
    {{
      "name": str,
      "score_10": int,
      "what_works": str,
      "gap_to_10": str,
      "fix": {{"before_quote": str, "after_suggestion": str, "why": str, "effort": "low|med|high", "expected_lift": str}},
      "impact": "high|med|low",
      "source": str
    }}
  ],
  "priority_fixes": [
    {{"rank": 1, "fix_summary": str, "expected_lift": str, "first_step": str}},
    {{"rank": 2, ...}},
    {{"rank": 3, ...}}
  ]
}}"""

    user = f"Channel: {channel}\n\nAd copy:\n{copy}\n\nImage description:\n{image_desc or 'N/A'}"
    resp = oai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4000,
    )
    return json.loads(resp.choices[0].message.content)
