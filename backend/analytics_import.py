"""
Analytics import — parse an analytics export into a normalised page-metric shape.

v1 supports Google Analytics 4 only. Mixpanel and Microsoft Clarity are
deliberately not implemented: their export schemas have not been verified
against a real file, and guessing a parser produces silently wrong data.
"""
import csv, io, re

# Header words that identify the real header row in a GA4 export.
# GA4 CSVs open with metadata preamble lines (# comments, report name,
# date range) before the actual column headers.
GA4_PATH_HINTS = ("page path", "landing page", "page title", "screen class", "page location")
GA4_METRIC_HINTS = ("views", "sessions", "users", "engagement", "bounce", "conversions")


def _clean(s: str) -> str:
    return (s or "").strip().strip('"').lower()


def _to_number(raw):
    """GA4 numbers arrive with commas, percentages, or time strings."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("%", "")
    if not s or s in {"-", "N/A"}:
        return None
    # mm:ss or hh:mm:ss -> seconds
    if ":" in s:
        try:
            parts = [float(p) for p in s.split(":")]
            secs = 0.0
            for p in parts:
                secs = secs * 60 + p
            return secs
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_header_row(rows) -> int:
    """
    Return the index of the real header row, skipping GA4's preamble.
    A header row is one that contains a recognised path column AND at least
    one recognised metric column.
    """
    for i, row in enumerate(rows[:40]):  # header is never deep in the file
        cells = [_clean(c) for c in row]
        joined = " | ".join(cells)
        has_path = any(h in joined for h in GA4_PATH_HINTS)
        has_metric = any(h in joined for h in GA4_METRIC_HINTS)
        if has_path and has_metric:
            return i
    return -1


def _map_columns(header) -> dict:
    """
    GA4 column names vary by report type, so match on substrings rather than
    exact names. Returns {field: column_index}.
    """
    idx = {}
    for i, raw in enumerate(header):
        c = _clean(raw)
        if not c:
            continue
        if "path" in c or "landing page" in c or "page location" in c:
            idx.setdefault("path", i)
        elif "page title" in c and "path" not in idx:
            idx.setdefault("path", i)
        elif "view" in c and "per user" not in c:
            idx.setdefault("views", i)
        elif "active users" in c or c == "users" or "total users" in c:
            idx.setdefault("users", i)
        elif "session" in c and "per" not in c:
            idx.setdefault("sessions", i)
        elif "bounce" in c:
            idx.setdefault("bounce_rate", i)
        elif "engagement time" in c or "avg. time" in c or "average time" in c:
            idx.setdefault("avg_time", i)
        elif "conversion" in c or "key event" in c:
            idx.setdefault("conversions", i)
    return idx


def normalise_path(raw: str) -> str:
    """
    Analytics paths and scored URLs never match on a naive compare.
    Strip protocol, domain, query string, fragment and trailing slash.
    """
    if not raw:
        return ""
    p = str(raw).strip()
    p = re.sub(r"^https?://[^/]+", "", p)   # drop protocol + domain
    p = p.split("?")[0].split("#")[0]       # drop query + fragment
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1:
        p = p.rstrip("/")
    return p or "/"


def parse_ga4(content: str) -> dict:
    """Parse a GA4 CSV export into the normalised shape."""
    warnings = []
    rows = list(csv.reader(io.StringIO(content)))
    if not rows:
        raise ValueError("File is empty.")

    h = _find_header_row(rows)
    if h == -1:
        raise ValueError(
            "Could not find a header row with a page column and a metric column. "
            "Export a report that includes page paths (Reports -> Pages and screens)."
        )
    if h > 0:
        warnings.append(f"Skipped {h} preamble row(s) before the header.")

    header = rows[h]
    idx = _map_columns(header)
    if "path" not in idx:
        raise ValueError("No page path column found in the export.")

    unmapped = [c for i, c in enumerate(header) if i not in idx.values() and _clean(c)]
    if unmapped:
        warnings.append("Columns read but not used: " + ", ".join(unmapped[:8]))

    out, skipped = [], 0
    for row in rows[h + 1:]:
        if not row or len(row) <= idx["path"]:
            continue
        raw_path = (row[idx["path"]] or "").strip()
        # GA4 appends a totals/grand-total row and sometimes blank separators
        if not raw_path or raw_path.lower().lstrip("# ") in {
            "totals", "total", "grand total", "(not set)"
        }:
            skipped += 1
            continue
        path = normalise_path(raw_path)
        if not path:
            skipped += 1
            continue
        rec = {"path": path}
        for field, i in idx.items():
            if field == "path":
                continue
            rec[field] = _to_number(row[i]) if i < len(row) else None
        out.append(rec)

    if not out:
        raise ValueError("Header found but no data rows could be read.")
    if skipped:
        warnings.append(f"Skipped {skipped} unusable row(s).")

    return {
        "source": "ga4",
        "row_count": len(out),
        "columns_found": sorted(k for k in idx if k != "path"),
        "warnings": warnings,
        "rows": out,
    }


PARSERS = {"ga4": parse_ga4}
SUPPORTED = {"ga4"}
NOT_YET = {
    "mixpanel": "Mixpanel export format not yet verified against a real file.",
    "clarity": "Microsoft Clarity export format not yet verified against a real file.",
    "plausible": "Plausible exports a ZIP of multiple CSVs — not supported in v1.",
}


def parse_export(content: str, source: str) -> dict:
    src = (source or "").strip().lower()
    if src in NOT_YET:
        raise ValueError(NOT_YET[src])
    if src not in PARSERS:
        raise ValueError(f"Unknown source '{source}'. Supported: {', '.join(sorted(SUPPORTED))}.")
    return PARSERS[src](content)


def detect_source(content: str, filename: str = ""):
    """Best-effort guess so the UI can pre-select the radio button."""
    head = content[:4000].lower()
    if "# ----" in head or "nth day" in head or "google analytics" in head:
        return "ga4"
    if _find_header_row(list(csv.reader(io.StringIO(content[:8000])))) != -1:
        return "ga4"
    return None


def match_to_page(rows, page_url: str):
    """Find the analytics row matching a scored page URL."""
    target = normalise_path(page_url)
    for r in rows:
        if r.get("path") == target:
            return r
    return None
