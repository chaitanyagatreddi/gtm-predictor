"""
CRO scorer — scrape URL, run rubric, return score 0-1 + fix list.
Uses Firecrawl (if key set) OR built-in fallback scraper, then OpenAI gpt-4o-mini for scoring.
Loads user-authored reference pages as few-shot gold standards.
"""
import os, json, glob, re, html as html_lib, httpx
from openai import OpenAI

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "reference_pages")


def load_references() -> str:
    """Concat all reference pages into a single few-shot block."""
    chunks = []
    for path in sorted(glob.glob(os.path.join(REF_DIR, "*.md"))):
        with open(path) as f:
            chunks.append(f"--- {os.path.basename(path)} ---\n{f.read()[:2500]}")
    return "\n\n".join(chunks) if chunks else ""

_client = None
def oai():
    global _client
    if _client is None: _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def _html_to_text(raw_html: str) -> tuple[str, str]:
    """Stdlib-only HTML → (title, markdown-ish text). No external deps."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    title = html_lib.unescape(title_match.group(1).strip()) if title_match else ""
    # strip script + style blocks
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", raw_html, flags=re.IGNORECASE | re.DOTALL)
    # headings to markdown
    body = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", body, flags=re.IGNORECASE | re.DOTALL)
    # list items
    body = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", body, flags=re.IGNORECASE | re.DOTALL)
    # line breaks for blocks
    body = re.sub(r"</(p|div|br|section|article|header|footer)>", "\n", body, flags=re.IGNORECASE)
    # strip remaining tags
    body = re.sub(r"<[^>]+>", "", body)
    body = html_lib.unescape(body)
    # collapse whitespace
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return title, body


# Anti-bot protection answers a plain fetch with one of these. Without a
# ZenRows or Firecrawl key configured there is no tier that can get past it,
# so the user gets an explanation rather than a raw HTTP status.
BLOCKED_STATUSES = {401, 403, 429, 503}
BLOCKED_MSG = ("This site uses a bot challenge that our scraper cannot pass. "
               "Premium scraping is coming soon \u2014 for now, paste the page "
               "content into the CRO tab.")


async def scrape_url(url: str) -> dict:
    """Try Firecrawl (if key set) → fall back to built-in scraper."""
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url

    firecrawl_key = os.getenv("FIRECRAWL_API_KEY") or ""
    if firecrawl_key.strip():
        try:
            async with httpx.AsyncClient() as c:
                r = await c.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    json={"url": url, "formats": ["markdown", "html"]},
                    headers={"Authorization": f"Bearer {firecrawl_key.strip()}"},
                    timeout=30,
                )
            if r.status_code == 200:
                return r.json().get("data", {})
        except Exception:
            pass  # fall through to native

    # ZenRows — handles Cloudflare, CAPTCHA, JS-rendered pages
    zenrows_key = os.getenv("ZENROWS_API_KEY") or ""
    if zenrows_key.strip():
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    "https://api.zenrows.com/v1/",
                    params={"url": url, "apikey": zenrows_key.strip(), "js_render": "true"},
                    timeout=60,
                )
            if r.status_code == 200 and r.text.strip():
                title, text = _html_to_text(r.text)
                return {"markdown": text, "metadata": {"title": title}, "scraper": "zenrows"}
        except Exception:
            pass  # fall through to builtin

    # Built-in fallback — fetch + parse, no external service needed
    async with httpx.AsyncClient(follow_redirects=True) as c:
        r = await c.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        })
    if r.status_code in BLOCKED_STATUSES:
        raise RuntimeError(BLOCKED_MSG)
    if r.status_code >= 400:
        raise RuntimeError(f"Page fetch failed: HTTP {r.status_code}")
    title, text = _html_to_text(r.text)
    return {"markdown": text, "metadata": {"title": title}, "scraper": "builtin_fallback"}


CRO_RUBRIC_PROMPT = """You are a CRO expert. Score this landing page against best practices.

Rubric (each /10):
1. Headline clarity — does it state value in <8 words?
2. Subhead — does it explain who/what/why?
3. CTA — visible above fold, action verb, contrasting color?
4. Social proof — logos, testimonials, numbers, case studies?
5. Form friction — fewest fields needed? (HubSpot 3-field optimum)
6. Page focus — single primary action or scattered?
7. Trust signals — security badges, reviews, guarantees?
8. Mobile-readable — short paragraphs, scannable?

Sources to cite:
- Baymard Institute (form research)
- NN/g (clarity heuristics)
- Unbounce Conversion Benchmark Report 2024
- HubSpot State of Marketing 2024

CRITICAL — never fabricate:
- Do NOT invent names, job titles, company names, or metrics in after_suggestion.
- If a rewrite needs attribution or a number, use a bracketed placeholder:
  "[customer name, title, company]" or "[X]%".
- Only quote people or companies that appear verbatim in the page content provided.
- before_quote must be text actually present on the page, or "[missing]".

For EVERY dimension, return a DETAILED fix — not a 1-liner.

`fix` must include:
- before_quote: the exact current copy/element on the page (or "[missing]" if absent)
- after_suggestion: the rewritten copy or specific element to add — actual words, not abstract advice
- why: 1-sentence reason this works better (with cited principle)
- effort: "low" (<1 day) | "med" (1-3 days) | "high" (rewrite/redesign)
- expected_lift: rough conversion lift estimate (e.g., "+10-15% form conversion")

Return JSON only:
{
  "overall_score_10": float,
  "dimensions": [
    {
      "name": "headline",
      "score_10": int,
      "what_works": str,
      "gap_to_10": str,
      "fix": {
        "before_quote": str,
        "after_suggestion": str,
        "why": str,
        "effort": "low|med|high",
        "expected_lift": str
      },
      "impact": "high|med|low",
      "source": str
    },
    ... (8 dimensions)
  ],
  "priority_fixes": [
    {"rank": 1, "fix_summary": str, "expected_lift": str, "first_step": str},
    {"rank": 2, ...},
    {"rank": 3, ...}
  ]
}"""


def score_content(url: str, title: str, content: str) -> dict:
    """Score pre-scraped content (skips Firecrawl)."""
    return _score_with_llm(url, title, content[:20000])


def _score_with_llm(url: str, title: str, content: str) -> dict:

    refs = load_references()
    ref_block = f"\n\nGOLD-STANDARD reference pages (treat these as 9-10/10 baselines for hook, clarity, social proof, pricing transparency):\n{refs}" if refs else ""

    resp = oai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CRO_RUBRIC_PROMPT + ref_block},
            {"role": "user", "content": f"URL: {url}\nTitle: {title}\n\nPage content:\n{content}\n\nScore vs rubric and reference pages."},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )
    data = json.loads(resp.choices[0].message.content)
    data["url"] = url
    return data


async def score_url(url: str) -> dict:
    page = await scrape_url(url)
    content = (page.get("markdown") or "")[:20000]
    title = page.get("metadata", {}).get("title", "")
    result = _score_with_llm(url, title, content)
    result["scraper_used"] = page.get("scraper", "firecrawl")
    return result
