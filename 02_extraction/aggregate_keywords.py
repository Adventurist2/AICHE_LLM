#!/usr/bin/env python3
"""
Stage 4 (combined) - aggregate every groq/extracted_results* folder into aggregate.json.

Auto-discovers every "groq/extracted_results" or "groq/extracted_results_<YYYY>"
directory, so re-running after adding a new year (or more files to an existing
year) needs no edits - just run it again.

Year is taken from the FOLDER NAME, not the "Year" field inside each record:
groq.ipynb's run_batch_extraction hardcodes "Year": 2023 on every record it
writes, regardless of which input folder was actually being processed, so that
field is not trustworthy across years.

Usage:
    python 02_extraction/aggregate_keywords.py [--output 02_extraction/aggregate.json]
"""

import os
import re
import json
import argparse

RESULTS_ROOT = "groq"
FOLDER_PATTERN = re.compile(r"^extracted_results(?:_(\d{4}))?$")
DEFAULT_YEAR = "2023"  # groq/extracted_results (no suffix) holds the 2023 program


# ── Canonicalization (kept identical to keyword_processor.ipynb) ───────────────

def canonical_kw(k: str) -> str:
    return re.sub(r"\s+", " ", (k or "").strip()).lower()


def canonical_country(c: str) -> str:
    s = (c or "").strip()
    return s.title() if s else s


def canonical_author(a: str) -> str:
    s = (a or "").strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def authors_from_authors_field(s):
    parts = []
    if s is None:
        return parts
    if isinstance(s, list):
        for elt in s:
            parts.extend(authors_from_authors_field(elt))
        return [p for p in (x.strip() for x in parts) if p]
    if isinstance(s, dict):
        name = (s.get("name") or s.get("author") or "").strip()
        aff = (s.get("affiliation") or s.get("affil") or "").strip()
        if name or aff:
            combined = f"{name} ({aff})" if aff else name
            return [combined.strip()] if combined.strip() else []
        s = json.dumps(s)
    s = str(s).strip()
    if not s:
        return []
    if any(sep in s for sep in (";", "\n", "|")):
        return [p.strip() for p in re.split(r";|\n|\|", s) if p.strip()]
    return [s]


# ── Folder discovery ─────────────────────────────────────────────────────────

def discover_year_folders(results_root: str):
    """Map every groq/extracted_results* directory to the year it holds."""
    mapping = {}
    if not os.path.isdir(results_root):
        raise SystemExit(f"'{results_root}' not found - run this from the repo root.")

    for name in sorted(os.listdir(results_root)):
        full = os.path.join(results_root, name)
        if not os.path.isdir(full):
            continue
        m = FOLDER_PATTERN.match(name)
        if not m:
            continue
        year = m.group(1) or DEFAULT_YEAR
        mapping[full] = year
    return mapping


# ── Core ─────────────────────────────────────────────────────────────────────

def process_folder(folder: str, year: str, raw_agg: dict) -> dict:
    """Fold every ext_*.json in `folder` into raw_agg, tagging records with `year`."""
    json_files = sorted(f for f in os.listdir(folder) if f.endswith(".json"))
    stats = {"files": 0, "papers": 0, "mentions": 0}

    for filename in json_files:
        filepath = os.path.join(folder, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                items = json.load(f)
            except json.JSONDecodeError as e:
                print(f"    skipping {filepath} ({e})")
                continue

        if isinstance(items, dict):
            items = [items]

        stats["files"] += 1

        for item in items:
            stats["papers"] += 1

            kws = item.get("keywords") or []
            if isinstance(kws, str):
                kws = [kws]

            countries_raw = item.get("countries") or []
            if isinstance(countries_raw, str):
                countries_raw = [countries_raw]
            countries = [canonical_country(c) for c in countries_raw if c]

            authors_field = item.get("authors") or item.get("author") or ""
            authors_clean = [canonical_author(a) for a in authors_from_authors_field(authors_field)]

            paper_ref = {
                "title": (item.get("title") or "").strip(),
                "source_file": filename,
                "source_folder": folder,
                "countries": countries,
                "authors": authors_clean,
            }

            for rawk in kws:
                if not rawk:
                    continue
                k = canonical_kw(rawk)
                if not k:
                    continue

                rec = raw_agg.setdefault(k, {
                    "total_count": 0,
                    "years": {},
                    "countries": {},
                    "authors": {},
                    "papers_by_year": {},
                })

                rec["total_count"] += 1
                rec["years"][year] = rec["years"].get(year, 0) + 1
                rec["papers_by_year"].setdefault(year, []).append(paper_ref)

                for c in countries:
                    rec["countries"][c] = rec["countries"].get(c, 0) + 1
                for a in authors_clean:
                    if a:
                        rec["authors"][a] = rec["authors"].get(a, 0) + 1

                stats["mentions"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Combine all groq/extracted_results* folders into aggregate.json")
    parser.add_argument("--output", default="02_extraction/aggregate.json", help="Output path (default: 02_extraction/aggregate.json)")
    parser.add_argument("--results-root", default=RESULTS_ROOT, help="Directory holding extracted_results* folders")
    args = parser.parse_args()

    year_folders = discover_year_folders(args.results_root)
    if not year_folders:
        raise SystemExit(f"No extracted_results* folders found under '{args.results_root}'.")

    print(f"Discovered {len(year_folders)} extraction folder(s):")
    for folder, year in year_folders.items():
        print(f"  {folder}  ->  year {year}")

    raw_agg = {}
    print()
    for folder, year in year_folders.items():
        print(f"Processing {folder} (year {year})...")
        stats = process_folder(folder, year, raw_agg)
        print(f"  {stats['files']} file(s), {stats['papers']} paper(s), {stats['mentions']} keyword mention(s)")

    # Sort each record's nested dicts for readability / diff-friendliness
    for rec in raw_agg.values():
        try:
            rec["years"] = dict(sorted(rec["years"].items(), key=lambda x: int(x[0])))
        except Exception:
            rec["years"] = dict(sorted(rec["years"].items()))
        try:
            rec["papers_by_year"] = dict(sorted(rec["papers_by_year"].items(), key=lambda x: int(x[0])))
        except Exception:
            rec["papers_by_year"] = dict(sorted(rec["papers_by_year"].items()))
        rec["countries"] = dict(sorted(rec["countries"].items(), key=lambda x: -x[1]))
        rec["authors"] = dict(sorted(rec["authors"].items(), key=lambda x: -x[1]))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw_agg, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Unique keywords: {len(raw_agg)}")
    print(f"Written to: {args.output}")
    print(f"\nNext: python 04_clustering/cluster_keywords.py {args.output}")


if __name__ == "__main__":
    main()
