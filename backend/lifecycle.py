"""
Lifecycle scorer — evaluates email sequences and computes LTV/CAC.

Two modes:
1. score_sequence(emails) — rubric scoring against retention best practice
2. ltv_cac(...) — unit economics from acquisition cost + retention rates
"""
import os, json, glob
from openai import OpenAI

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "reference_pages")
_client = None
def oai():
    global _client
    if _client is None: _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def load_lifecycle_ref() -> str:
    """Cold outbound reference — Polar Analytics rewrite."""
    path = os.path.join(REF_DIR, "polar_cold_email.md")
    if not os.path.exists(path):
        path = os.path.join(REF_DIR, "writesonic_lifecycle.md")
    if not os.path.exists(path): return ""
    with open(path) as f: return f.read()[:4000]


LIFECYCLE_RUBRIC = """You are a B2B cold outbound email expert.

Score the COLD OUTBOUND email /10 on each of 10 dimensions:

1. Subject line — short, curiosity/pain-led, no spam triggers, <60 chars?
2. Hook (first line) — recognizable shared pain, not "I'm reaching out"?
3. ICP qualifier — does it call out who this is for (e.g. "Shopify Plus", "Series B SaaS")?
4. Specific proof — named customer + 2-3 quantified results (%, $, x)?
5. Goal-fit — does the body match the stated goal (book demo / reply / click / download)?
6. CTA clarity — single ask, easy to say yes to, low commitment?
7. Personalization signal — at least 1 element written FOR this prospect (demo app, custom note)?
8. P.S. or pattern break — surprise element that reverses sales dynamic ("we're picky")?
9. Brevity — under 150 words for body, no corporate fluff?
10. Landing page match — does LP (if given) deliver on email promise?

Reference (gold-standard cold email to compare against):
{ref}

For EVERY dimension, return a DETAILED fix — not a 1-liner.

`fix` must include:
- before_state: what the current sequence does at this stage (or "[missing]" if absent)
- after_recommendation: specific email/branch to add — subject line + 1-2 line body sketch
- why: 1-sentence reason this works (cited principle if possible)
- effort: "low" (<1 day) | "med" (1-3 days) | "high" (full sequence redesign)
- expected_lift: rough activation/retention lift (e.g., "+8% trial→paid")

Return JSON only:
{{
  "overall_score_10": float,
  "dimensions": [
    {{
      "name": str,
      "score_10": int,
      "what_works": str,
      "gap_to_10": str,
      "fix": {{"before_state": str, "after_recommendation": str, "why": str, "effort": "low|med|high", "expected_lift": str}},
      "impact": "high|med|low"
    }}
  ],
  "priority_fixes": [
    {{"rank": 1, "fix_summary": str, "expected_lift": str, "first_step": str}},
    {{"rank": 2, ...}},
    {{"rank": 3, ...}}
  ]
}}"""


def score_sequence(sequence_desc: str) -> dict:
    """sequence_desc: free-text or JSON describing the email sequence to score."""
    ref = load_lifecycle_ref()
    resp = oai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": LIFECYCLE_RUBRIC.format(ref=ref)},
            {"role": "user", "content": f"Score this email sequence:\n\n{sequence_desc}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4000,
    )
    return json.loads(resp.choices[0].message.content)


def ltv_cac(
    cac_usd: float,
    monthly_arpu_usd: float,
    monthly_churn_rate: float = 0.05,
    gross_margin: float = 0.80,
    activation_rate: float = 0.40,
    trial_to_paid_rate: float = 0.15,
    expansion_rate: float = 0.10,
    referral_rate: float = 0.05,
) -> dict:
    """
    Compute unit economics using the STANDARD SaaS formula.
    Source: https://www.wallstreetprep.com/knowledge/ltv-cac-ratio/

    LTV = (ARPA × Gross Margin) ÷ Churn Rate
    CAC = total S&M spend ÷ new customers acquired (input as-is)
    LTV/CAC = LTV ÷ CAC

    Verdict thresholds (industry standard):
      ≥3.0x: ideal (healthy)
      1.0–3.0x: borderline / break-even
      <1.0x: burning cash
      >5.0x: under-investing in growth
    """
    # Standard formula: ARPA × GM × (1 / churn) — also written (ARPA × GM) / churn
    # Annual ARPA = monthly × 12; annual churn = (1-(1-monthly)^12). Keep monthly for consistency.
    monthly_contribution = monthly_arpu_usd * gross_margin  # gross profit per customer / month
    if monthly_churn_rate <= 0:
        lifetime_months = 36  # cap at 3 years if zero churn entered
    else:
        lifetime_months = 1 / monthly_churn_rate
    ltv = monthly_contribution * lifetime_months  # ≡ (ARPA × GM) / churn

    # Optional expansion uplift (NRR > 100%) — keep transparent, additive
    if expansion_rate > 0:
        ltv = ltv * (1 + expansion_rate)

    # Optional referral offset on CAC (each referred user reduces effective CAC)
    effective_cac = cac_usd * (1 - referral_rate) if referral_rate > 0 else cac_usd

    ltv_cac_ratio = ltv / effective_cac if effective_cac else 0
    payback_months = effective_cac / monthly_contribution if monthly_contribution else 0

    # Verdict per Wall Street Prep standard
    if ltv_cac_ratio >= 5:
        verdict = "under_investing"
    elif ltv_cac_ratio >= 3:
        verdict = "healthy"
    elif ltv_cac_ratio >= 1:
        verdict = "borderline"
    else:
        verdict = "burning_cash"

    diagnosis = []
    if ltv_cac_ratio >= 5:
        diagnosis.append(f"Ratio {round(ltv_cac_ratio,2)}x > 5x suggests under-investing in growth (Wall Street Prep). Consider spending more on acquisition.")
    if payback_months > 18:
        diagnosis.append(f"Payback {round(payback_months,1)}mo > 18mo — typical SaaS aims for <12mo. Check ARPA or churn.")
    if monthly_churn_rate > 0.07:
        diagnosis.append(f"Monthly churn {monthly_churn_rate*100:.1f}% > 7% (annual ~58%+). Caps LTV severely.")
    if trial_to_paid_rate < 0.05 and trial_to_paid_rate > 0:
        diagnosis.append(f"Trial→paid {trial_to_paid_rate*100:.1f}% < 5% — activation/onboarding likely broken (separate from LTV/CAC).")

    return {
        "ltv_usd": round(ltv, 2),
        "cac_usd": round(cac_usd, 2),
        "effective_paid_cac_usd": round(effective_cac, 2),
        "ltv_cac_ratio": round(ltv_cac_ratio, 2),
        "payback_months": round(payback_months, 1),
        "lifetime_months": round(lifetime_months, 1),
        "monthly_contribution_usd": round(monthly_contribution, 2),
        "verdict": verdict,
        "diagnosis": diagnosis,
        "formula": "LTV = (ARPA × Gross Margin) ÷ Churn Rate",
        "assumptions": {
            "monthly_arpu_usd": monthly_arpu_usd,
            "monthly_churn_rate": monthly_churn_rate,
            "gross_margin": gross_margin,
            "activation_rate": activation_rate,
            "trial_to_paid_rate": trial_to_paid_rate,
            "expansion_rate": expansion_rate,
            "referral_rate": referral_rate,
        },
        "sources": [
            "Wall Street Prep — LTV/CAC Ratio Formula: https://www.wallstreetprep.com/knowledge/ltv-cac-ratio/",
            "Porter Metrics — CAC/LTV Calculator: https://portermetrics.com/en/free-tools/calculators/free-cacltv-ratio/",
            "ChartMogul SaaS Benchmarks: https://chartmogul.com/reports/saas-benchmarks-report/",
        ],
    }
