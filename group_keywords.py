"""
Keyword grouping pipeline for 19k+ research keywords.
Steps:
  1. Rule-based deduplication (plurals, special chars, known abbreviations)
  2. Semantic clustering via sentence-transformers embeddings + cosine similarity
  3. Output new JSON with grouped_with + canonical_keyword fields
"""

import json
import re
import unicodedata
from collections import defaultdict

import urllib.request
import time

# ─── CONFIG ───────────────────────────────────────────────────────────────────
INPUT_FILE   = "/mnt/user-data/uploads/aggregate.json"
OUTPUT_FILE  = "/mnt/user-data/outputs/keywords_grouped.json"
LOG_FILE     = "/mnt/user-data/outputs/grouping_log.txt"

SEMANTIC_BATCH_SIZE = 300   # keywords per API call
RETRY_DELAY         = 5     # seconds between retries on rate limit

# Common abbreviation expansions (lowercase key → canonical phrase)
ABBREV_MAP = {
    "co2":   "carbon dioxide",
    "h2o":   "water",
    "h2s":   "hydrogen sulfide",
    "ch4":   "methane",
    "n2":    "nitrogen",
    "o2":    "oxygen",
    "h2":    "hydrogen",
    "nox":   "nitrogen oxides",
    "sox":   "sulfur oxides",
    "vle":   "vapor-liquid equilibrium",
    "lle":   "liquid-liquid equilibrium",
    "sle":   "solid-liquid equilibrium",
    "md":    "molecular dynamics",
    "mc":    "monte carlo",
    "dft":   "density functional theory",
    "ml":    "machine learning",
    "dl":    "deep learning",
    "nn":    "neural network",
    "ai":    "artificial intelligence",
    "cfd":   "computational fluid dynamics",
    "pde":   "partial differential equation",
    "ode":   "ordinary differential equation",
    "il":    "ionic liquid",
    "ils":   "ionic liquid",
    "mea":   "monoethanolamine",
    "mdea":  "methyldiethanolamine",
    "pz":    "piperazine",
    "dea":   "diethanolamine",
    "ccs":   "carbon capture and storage",
    "ccus":  "carbon capture utilization and storage",
    "tga":   "thermogravimetric analysis",
    "dsc":   "differential scanning calorimetry",
    "nmr":   "nuclear magnetic resonance",
    "ftir":  "fourier transform infrared spectroscopy",
    "gc":    "gas chromatography",
    "hplc":  "high performance liquid chromatography",
    "pvt":   "pressure volume temperature",
    "eos":   "equation of state",
    "saft":  "statistical associating fluid theory",
    "pr":    "peng-robinson",
    "srk":   "soave-redlich-kwong",
    "mof":   "metal-organic framework",
    "cof":   "covalent organic framework",
    "zeolite": "zeolite",
    "htc":   "hydrothermal carbonization",
    "htl":   "hydrothermal liquefaction",
    "pyc":   "pyrolysis",
    "atm":   "atmosphere",
    "rpm":   "revolutions per minute",
    "cstr":  "continuous stirred tank reactor",
    "pfr":   "plug flow reactor",
    "mpc":   "model predictive control",
    "pid":   "proportional integral derivative",
    "lca":   "life cycle assessment",
    "tac":   "total annualized cost",
    "capex": "capital expenditure",
    "opex":  "operational expenditure",
    "ro":    "reverse osmosis",
    "mf":    "microfiltration",
    "uf":    "ultrafiltration",
    "nf":    "nanofiltration",
    "ed":    "electrodialysis",
    "ghe":   "greenhouse effect",
    "ghg":   "greenhouse gas",
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def normalize(text):
    """Lowercase, strip unicode dashes/special chars, collapse spaces."""
    text = text.lower().strip()
    # replace unicode dashes / hyphens with regular hyphen
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]", "-", text)
    # collapse multiple spaces/hyphens
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"-+", "-", text)
    return text


def depluralize(text):
    """Very simple English depluralization for common patterns."""
    # e.g. "ionic liquids" -> "ionic liquid"
    if text.endswith("ies") and len(text) > 4:
        return text[:-3] + "y"
    if text.endswith("ses") and len(text) > 4:
        return text[:-2]  # "processes" -> "process" not perfect but ok
    if text.endswith("s") and not text.endswith("ss") and len(text) > 3:
        return text[:-1]
    return text


def rule_based_canonical(kw):
    """Return a normalized form used for rule-based grouping."""
    norm = normalize(kw)
    # expand abbreviations (whole-word only)
    words = norm.split()
    expanded = [ABBREV_MAP.get(w, w) for w in words]
    norm = " ".join(expanded)
    # depluralize last word
    parts = norm.split()
    if parts:
        parts[-1] = depluralize(parts[-1])
    return " ".join(parts)


def merge_keyword_data(base, extra):
    """Merge extra keyword block into base in-place."""
    base["total_count"] = base.get("total_count", 0) + extra.get("total_count", 0)

    for year, cnt in extra.get("years", {}).items():
        base.setdefault("years", {})[year] = base["years"].get(year, 0) + cnt

    for country, cnt in extra.get("countries", {}).items():
        base.setdefault("countries", {})[country] = base["countries"].get(country, 0) + cnt

    for author, cnt in extra.get("authors", {}).items():
        base.setdefault("authors", {})[author] = base["authors"].get(author, 0) + cnt

    for year, papers in extra.get("papers_by_year", {}).items():
        existing = base.setdefault("papers_by_year", {}).setdefault(year, [])
        seen = {(p["title"], p.get("source_file", "")) for p in existing}
        for p in papers:
            key = (p["title"], p.get("source_file", ""))
            if key not in seen:
                existing.append(p)
                seen.add(key)
    return base


# ─── STEP 1: RULE-BASED GROUPING ─────────────────────────────────────────────

def rule_based_grouping(data):
    """
    Group keywords by their normalized/expanded form.
    Returns:
      - groups: dict {canonical_kw: [list of original kw strings in this group]}
      - ungrouped: list of original kw strings that are unique after rules
    """
    print("Step 1: Rule-based grouping...")

    norm_to_originals = defaultdict(list)
    for kw in data.keys():
        norm = rule_based_canonical(kw)
        norm_to_originals[norm].append(kw)

    groups = {}       # canonical_original_kw -> [alias_original_kws]
    ungrouped = []    # original kws that are the only one in their norm group

    for norm, originals in norm_to_originals.items():
        if len(originals) == 1:
            ungrouped.append(originals[0])
        else:
            # pick canonical: longest total_count first, else shortest string
            canonical = max(originals, key=lambda k: data[k].get("total_count", 0))
            aliases = [k for k in originals if k != canonical]
            groups[canonical] = aliases

    print(f"  Rule-based: {len(groups)} groups found, {len(ungrouped)} keywords still ungrouped")
    return groups, ungrouped


# ─── STEP 2: SEMANTIC CLUSTERING VIA ANTHROPIC API ──────────────────────────

SEMANTIC_PROMPT = """You are a research keyword deduplication expert for chemical engineering and related sciences.

Below is a numbered list of research keywords. Identify groups of keywords that refer to the SAME or very similar concept (synonyms, abbreviations vs full form, plural/singular of same term, minor phrasing differences).

BE CONSERVATIVE — only group keywords that clearly mean the same thing. Do NOT group related-but-distinct concepts (e.g. "absorption" and "adsorption" are different; "CO2 capture" and "CO2 storage" are different).

Keywords:
{keyword_list}

Return ONLY a JSON array of groups. Each group must have:
- "canonical": best representative keyword (prefer full form over abbreviation, singular, most common phrasing)
- "members": ALL keywords in this group INCLUDING canonical

Only include groups with 2+ members. Omit keywords with no match.
Return ONLY valid JSON, no explanation, no markdown fences."""


def call_anthropic(prompt, retries=3):
    import urllib.request, urllib.error
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 529 or "overloaded" in body.lower():
                print(f"    API overloaded, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"    HTTP {e.code}: {body[:200]}")
                raise
    raise RuntimeError("Anthropic API failed after retries")


def semantic_grouping_api(keywords, data):
    """
    Batch keywords into groups of SEMANTIC_BATCH_SIZE, ask Claude to find
    synonyms within each batch, then return all found groups.
    """
    if not keywords:
        return [], keywords

    print(f"  Semantic grouping {len(keywords)} keywords in batches of {SEMANTIC_BATCH_SIZE}...")

    all_semantic_groups = []
    total_batches = (len(keywords) + SEMANTIC_BATCH_SIZE - 1) // SEMANTIC_BATCH_SIZE

    for batch_num in range(total_batches):
        start = batch_num * SEMANTIC_BATCH_SIZE
        batch = keywords[start:start + SEMANTIC_BATCH_SIZE]

        kw_list = "\n".join(f"{i+1}. {kw}" for i, kw in enumerate(batch))
        prompt = SEMANTIC_PROMPT.format(keyword_list=kw_list)

        print(f"  Batch {batch_num+1}/{total_batches} ({len(batch)} keywords)...", end=" ", flush=True)

        try:
            resp = call_anthropic(prompt)
            text = "".join(b.get("text","") for b in resp.get("content",[]))
            text = text.strip()
            # strip markdown fences if present
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

            if not text or text == "[]":
                print("no groups")
                continue

            groups = json.loads(text)

            # Map back from canonical string to original keyword strings in batch
            batch_lower = {k.lower().strip(): k for k in batch}
            valid_groups = []
            for g in groups:
                members_original = []
                for m in g.get("members", []):
                    orig = batch_lower.get(m.lower().strip())
                    if orig:
                        members_original.append(orig)
                if len(members_original) >= 2:
                    # pick canonical from originals
                    canon_lower = g.get("canonical","").lower().strip()
                    canon_orig = batch_lower.get(canon_lower) or members_original[0]
                    valid_groups.append({"canonical": canon_orig, "members": members_original})

            all_semantic_groups.extend(valid_groups)
            print(f"{len(valid_groups)} groups")

        except Exception as e:
            print(f"ERROR: {e} — skipping batch")
            continue

        # small pause to be polite to API
        time.sleep(0.5)

    print(f"  Semantic total: {len(all_semantic_groups)} groups found")
    return all_semantic_groups


# ─── STEP 3: BUILD OUTPUT ────────────────────────────────────────────────────

def build_output(data, rule_groups, semantic_groups):
    """
    Merge all groups and build the final output dict.
    Each keyword entry gets:
      - canonical_keyword: the chosen representative
      - grouped_with: list of aliases merged into this entry
    """
    print("Step 3: Building output JSON...")

    all_merges = {}  # canonical_original -> [alias_originals]

    for canonical, aliases in rule_groups.items():
        all_merges[canonical] = list(aliases)

    for g in semantic_groups:
        canonical = g["canonical"]
        aliases = [m for m in g["members"] if m != canonical]
        if canonical in all_merges:
            all_merges[canonical].extend(aliases)
        else:
            all_merges[canonical] = aliases

    all_aliases = set()
    for aliases in all_merges.values():
        all_aliases.update(aliases)

    result = {}

    for kw, kw_data in data.items():
        if kw in all_aliases:
            continue

        entry = json.loads(json.dumps(kw_data))

        if kw in all_merges:
            aliases = all_merges[kw]
            for alias in aliases:
                if alias in data:
                    entry = merge_keyword_data(entry, data[alias])
            entry["canonical_keyword"] = kw
            entry["grouped_with"] = aliases
        else:
            entry["canonical_keyword"] = kw
            entry["grouped_with"] = []

        result[kw] = entry

    return result, all_merges


def main():
    import os
    os.makedirs("/mnt/user-data/outputs", exist_ok=True)

    print(f"Loading {INPUT_FILE}...")
    with open(INPUT_FILE) as f:
        data = json.load(f)
    print(f"Total keywords: {len(data)}")

    # Step 1
    rule_groups, ungrouped_after_rules = rule_based_grouping(data)

    # Step 2
    print(f"\nStep 2: Semantic grouping on {len(ungrouped_after_rules)} ungrouped keywords...")
    semantic_group_list = semantic_grouping_api(ungrouped_after_rules, data)

    # Step 3
    print()
    result, all_merges = build_output(data, rule_groups, semantic_group_list)

    total_groups = sum(1 for v in result.values() if v["grouped_with"])
    total_aliases = sum(len(v["grouped_with"]) for v in result.values())
    print(f"\nSummary:")
    print(f"  Original keywords : {len(data)}")
    print(f"  Output keywords   : {len(result)}")
    print(f"  Keywords merged   : {total_aliases}")
    print(f"  Groups formed     : {total_groups}")

    print(f"\nWriting to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    with open(LOG_FILE, "w") as f:
        f.write("KEYWORD GROUPING LOG\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Original keywords : {len(data)}\n")
        f.write(f"Output keywords   : {len(result)}\n")
        f.write(f"Keywords merged   : {total_aliases}\n")
        f.write(f"Groups formed     : {total_groups}\n\n")
        f.write("RULE-BASED GROUPS\n" + "-" * 40 + "\n")
        for canon, aliases in sorted(rule_groups.items()):
            f.write(f"  [{canon}] <- {aliases}\n")
        f.write("\nSEMANTIC GROUPS\n" + "-" * 40 + "\n")
        for g in semantic_group_list:
            f.write(f"  [{g['canonical']}] <- {[m for m in g['members'] if m != g['canonical']]}\n")

    print("Done!")


if __name__ == "__main__":
    main()
