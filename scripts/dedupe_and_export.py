#!/usr/bin/env python3
"""Dedupe tools.db into a single tools.json for the static search page.

One entry per tool (case-insensitive name match), with an aggregated
mentions[] list of every episode it came up in.

Also applies scripts/aliases.json, which handles two things exact-name
dedup can't: folding many noisy show-notes name variants of one product
into a single canonical entry ("merge"), and grouping genuinely distinct
sub-products under a shared parent for display ("families") instead of
each cluttering the flat search results. See that file for details.
"""
import sqlite3
import json
import os
import sys
from collections import defaultdict

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "tools.db"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "tools.json"
ALIASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aliases.json")

with open(ALIASES_PATH) as f:
    aliases = json.load(f)
merge_map = {k.lower(): v.lower() for k, v in aliases.get("merge", {}).items()}
overrides = {k.lower(): v for k, v in aliases.get("overrides", {}).items()}

# key (lowercase canonical name) -> family id, for both parents and members
family_of = {}
family_label = {}
for fam_id, fam in aliases.get("families", {}).items():
    family_label[fam_id] = fam["label"]
    family_of[fam["parent"].lower()] = fam_id
    for member in fam["members"]:
        family_of[member.lower()] = fam_id

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT t.name, t.url, t.description, t.category,
           e.show, e.episode_number, e.title, e.air_date, e.url AS episode_url
    FROM tools t
    JOIN episodes e ON t.episode_id = e.id
    ORDER BY e.air_date
""").fetchall()

by_key = defaultdict(list)
for r in rows:
    key = r["name"].strip().lower()
    key = merge_map.get(key, key)
    by_key[key].append(r)

tools = []
for key, group in by_key.items():
    # canonical display name: the longest variant (usually the most complete)
    name = max((g["name"].strip() for g in group), key=len)

    # best description: longest non-empty one across all mentions
    descs = [g["description"].strip() for g in group if g["description"] and g["description"].strip()]
    description = max(descs, key=len) if descs else ""

    # best url: first non-empty, preferring one that isn't a bare podcast-note link
    urls = [g["url"].strip() for g in group if g["url"] and g["url"].strip()]
    url = urls[0] if urls else ""

    # category: most common non-"other" category among mentions, else "other"
    cat_counts = defaultdict(int)
    for g in group:
        c = (g["category"] or "other").strip().lower()
        cat_counts[c] += 1
    non_other = {c: n for c, n in cat_counts.items() if c != "other"}
    category = max(non_other, key=non_other.get) if non_other else "other"

    mentions = sorted(
        (
            {
                "show": g["show"],
                "episode": g["episode_number"],
                "title": g["title"],
                "date": g["air_date"],
                "url": g["episode_url"],
            }
            for g in group
        ),
        key=lambda m: m["date"] or "",
    )

    ov = overrides.get(key, {})
    name = ov.get("name", name)
    url = ov.get("url", url)
    description = ov.get("description", description)
    category = ov.get("category", category)

    tool = {
        "name": name,
        "url": url,
        "description": description,
        "category": category,
        "mentions": mentions,
        "mentionCount": len(mentions),
    }

    fam_id = family_of.get(key)
    if fam_id:
        tool["family"] = fam_id
        tool["familyLabel"] = family_label[fam_id]
        tool["isFamilyParent"] = (key == aliases["families"][fam_id]["parent"].lower())

    tools.append(tool)

tools.sort(key=lambda t: t["name"].lower())

with open(OUT_PATH, "w") as f:
    json.dump(tools, f, separators=(",", ":"))

print(f"{len(rows)} raw mentions -> {len(tools)} distinct tools", file=sys.stderr)
cats = defaultdict(int)
for t in tools:
    cats[t["category"]] += 1
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {c}: {n}", file=sys.stderr)
