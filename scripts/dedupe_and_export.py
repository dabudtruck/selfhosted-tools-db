#!/usr/bin/env python3
"""Dedupe tools.db into a single tools.json for the static search page.

One entry per tool (case-insensitive name match), with an aggregated
mentions[] list of every episode it came up in.

Also applies scripts/aliases.json, which handles three things exact-name
dedup can't: folding many noisy show-notes name variants of one product
into a single canonical entry ("merge"), grouping genuinely distinct
sub-products under a shared parent for display ("families") instead of
each cluttering the flat search results, and setting aside physical
hardware products ("hardware_exclude") into their own hardware.json since
this is meant to be a software tools database. See that file for details.
"""
import sqlite3
import json
import os
import sys
from collections import defaultdict

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "tools.db"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "tools.json"
HARDWARE_OUT_PATH = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(OUT_PATH), "hardware.json")
OTHER_OUT_PATH = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(OUT_PATH), "other.json")
ALIASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aliases.json")
CLASSIFICATION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "software_classification.json")

with open(ALIASES_PATH) as f:
    aliases = json.load(f)
merge_map = {k.lower(): v.lower() for k, v in aliases.get("merge", {}).items()}
overrides = {k.lower(): v for k, v in aliases.get("overrides", {}).items()}
# Physical hardware products (SBCs, sensors, dongles, cases, routers-as-a-box,
# etc). Out of scope for a software tools database per Tim's call - pulled
# into their own hardware.json (not published/linked yet) instead of the
# main list. Matched against the raw show-notes name, same as merge/family
# keys above.
hardware_exclude = {n.strip().lower() for n in aliases.get("hardware_exclude", [])}

# APP vs JUNK (article/news/tutorial/GitHub issue/forum thread/etc - not
# itself a piece of software) classification, keyed by the *canonical*
# tool name (after merge/family/override, not the raw show-notes name).
# One-time bulk pass via a local LLM (see helpfiles), reviewed by hand;
# not meant to be hand-edited like aliases.json - re-run the classifier
# to refresh it. Missing key defaults to APP/FULL so a name this file
# hasn't seen yet (a new episode, a new alias override) never silently
# vanishes.
try:
    with open(CLASSIFICATION_PATH) as f:
        classification = json.load(f)
except FileNotFoundError:
    classification = {}

# Hand-curated names (an override's display name, or a family parent) are
# never auto-excluded, no matter what the classifier said - these are
# already manually verified real software. Caught a real bug this way:
# the classifier had marked "Home Assistant" and "Nextcloud Cookbook"
# themselves as JUNK.
never_exclude = {ov["name"] for ov in overrides.values() if "name" in ov}
# family membership itself gets resolved onto `never_exclude` below, once
# all_tools exists and each tool's actual (correctly-cased) name is known -
# see the "in never_exclude" loop.

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
by_key_hardware = defaultdict(list)
for r in rows:
    raw_key = r["name"].strip().lower()
    if raw_key in hardware_exclude:
        by_key_hardware[raw_key].append(r)
        continue
    key = merge_map.get(raw_key, raw_key)
    by_key[key].append(r)


def build_tools(by_key):
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
    return tools


all_tools = build_tools(by_key)
hardware = build_tools(by_key_hardware)

never_exclude |= {t["name"] for t in all_tools if "family" in t}

tools = []
other = []
for t in all_tools:
    cls, size = classification.get(t["name"], ["APP", "FULL"])
    if t["name"] in never_exclude:
        cls, size = "APP", size if size != "-" else "FULL"
    if cls == "JUNK":
        other.append(t)
    else:
        t["size"] = size
        tools.append(t)

with open(OUT_PATH, "w") as f:
    json.dump(tools, f, separators=(",", ":"))
with open(HARDWARE_OUT_PATH, "w") as f:
    json.dump(hardware, f, separators=(",", ":"))
with open(OTHER_OUT_PATH, "w") as f:
    json.dump(other, f, separators=(",", ":"))

print(f"{len(rows)} raw mentions -> {len(tools)} apps "
      f"({len(hardware)} hardware, {len(other)} non-software set aside)", file=sys.stderr)
cats = defaultdict(int)
for t in tools:
    cats[t["category"]] += 1
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {c}: {n}", file=sys.stderr)
