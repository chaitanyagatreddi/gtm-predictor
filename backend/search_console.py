"""
Search Console import — parse a GSC Performance export into a normalised shape.

CSV only. The Search Console API needs a Google Cloud project, an OAuth
consent screen and per-user token storage; a CSV proves the data is useful
first, with none of that.
"""
import csv, io

from analytics_import import _clean, _to_number

# GSC localises headers and rewords them between exports, so match on
# substrings rather than exact names.
QUERY_HINTS = ("top queries", "query", "queries", "search term")
PAGE_HINTS = ("top pages", "page", "url", "landing page")
METRIC_HINTS = ("clicks", "impressions", "ctr", "position")

ZIP_SIGNATURE = "PK\x03\x04"


def _find_header_row(rows) -> int:
    """The header is the first row naming a key column and a metric column."""
    for i, row in enumerate(rows[:40]):
        joined = " | ".join(_clean(c) for c in row)
        has_key = any(h in joined for h in QUERY_HINTS + PAGE_HINTS)
        has_metric = any(h in joined for h in METRIC_HINTS)
        if has_key and has_metric:
            return i
    return -1


def _map_columns(header):
    """
    Returns {field: index} plus "_key_kind".

    A queries export and a pages export carry identical metrics, so the key
    column is what distinguishes them, and callers need to know which they got
    rather than being handed the wrong thing silently.
    """
    idx = {}
    for i, raw in enumerate(header):
        c = _clean(raw)
        if not c:
            continue
        if "click" in c:
            idx.setdefault("clicks", i)
        elif "impression" in c:
            idx.setdefault("impressions", i)
        elif "ctr" in c or "click through" in c:
            idx.setdefault("ctr", i)
        elif "position" in c:
            idx.setdefault("position", i)
        elif "key" not in idx and any(h in c for h in QUERY_HINTS):
            idx["key"] = i
            idx["_key_kind"] = "query"
        elif "key" not in idx and any(h in c for h in PAGE_HINTS):
            idx["key"] = i
            idx["_key_kind"] = "page"
    return idx


def _normalise_ctr(values):
    """
    GSC writes CTR as "3.4%" in some exports and 0.034 in others, and reading
    one as the other is off by 100x while still looking plausible. Anything
    above 1 is treated as a percentage; a genuine CTR cannot exceed 1.
    """
    real = [v for v in values if v is not None]
    if not real:
        return False
    return max(real) > 1


def parse_gsc(content: str) -> dict:
    if content.startswith(ZIP_SIGNATURE):
        raise ValueError(
            "That looks like the ZIP that Search Console exports. Unzip it and "
            "upload Queries.csv (or Pages.csv) from inside."
        )

    warnings = []
    rows = list(csv.reader(io.StringIO(content)))
    if not rows:
        raise ValueError("That file is empty.")

    h = _find_header_row(rows)
    if h == -1:
        raise ValueError(
            "No Search Console columns found. Export from Performance › "
            "Export › CSV, then upload Queries.csv or Pages.csv."
        )
    if h > 0:
        warnings.append(f"Skipped {h} row(s) before the header.")

    header = rows[h]
    idx = _map_columns(header)
    if "key" not in idx:
        raise ValueError(
            "No query or page column found. Found: "
            + ", ".join(c for c in header if _clean(c))
        )

    kind = idx.pop("_key_kind", "query")
    key_col = idx["key"]
    metric_cols = {k: v for k, v in idx.items() if k != "key"}
    if not metric_cols:
        raise ValueError("No clicks, impressions, CTR or position column found.")

    unmapped = [c for i, c in enumerate(header) if i not in idx.values() and _clean(c)]
    if unmapped:
        warnings.append("Columns read but not used: " + ", ".join(unmapped[:8]))

    out = []
    for row in rows[h + 1:]:
        # A blank row ends the table; GSC appends nothing after it, but a
        # user-edited sheet might.
        if not row or not any((c or "").strip() for c in row):
            break
        if len(row) <= key_col:
            continue
        key = (row[key_col] or "").strip()
        if not key:
            continue
        rec = {"key": key}
        for field, i in metric_cols.items():
            rec[field] = _to_number(row[i]) if i < len(row) else None
        # Zero-impression rows are real data, not noise, so they are kept.
        out.append(rec)

    if not out:
        raise ValueError("Header found but no data rows followed it.")

    if "ctr" in metric_cols:
        as_percent = _normalise_ctr([r.get("ctr") for r in out])
        if as_percent:
            for r in out:
                if r.get("ctr") is not None:
                    r["ctr"] = r["ctr"] / 100.0
        warnings.append(
            "CTR read as a percentage and stored as a fraction."
            if as_percent else
            "CTR read as a fraction."
        )

    return {
        "source": "gsc",
        "key_kind": kind,
        "row_count": len(out),
        "columns_found": sorted(metric_cols),
        "warnings": warnings,
        "rows": out,
    }
