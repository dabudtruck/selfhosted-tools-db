#!/usr/bin/env python3
"""Classify docs/data/tools.json entries as APP (real software: a service,
CLI tool, script, utility, library, or config project someone installs/runs)
vs JUNK (not software itself: news, blog posts, reviews, tutorials/how-tos,
forum threads, GitHub issue/PR references, papers, podcast notes,
orgs/communities, benchmarks, marketing pages). APPs also get tagged SCRIPT
if they're a small one-off utility/snippet rather than a full standalone
app/service.

Uses tcloudserver's local Ollama (granite3.1-dense:8b) in batches, writes
results incrementally to a checkpoint file so it's resumable, and validates
each batch's output shape before accepting it (retries malformed batches).
"""
import json
import os
import re
import sys
import time
import urllib.request

TOOLS_PATH = "docs/data/tools.json"
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_PATH = os.path.join(_SCRIPT_DIR, ".classify_checkpoint.jsonl")
FAILED_PATH = os.path.join(_SCRIPT_DIR, ".classify_failed.json")
OLLAMA_URL = "http://192.168.1.170:11434/api/generate"
MODEL = "granite3.1-dense:8b"
BATCH_SIZE = 25
MAX_RETRIES = 3

SYSTEM = """You are classifying entries from a database built from self-hosting podcast show notes. Each entry has a NAME, a DESCRIPTION (may be blank), and a URL DOMAIN (may be blank) - a strong hint: github.com/gitlab.com/sourcehut/codeberg/flathub.org/f-droid.org/hub.docker.com/pypi.org/npmjs.com/crates.io usually means real software; a news/blog/forum/wiki/YouTube/social-media domain usually means an article, not software. Classify each as exactly one of:

APP - a real piece of software someone can install, run, or use: a self-hosted service/application, a CLI tool, a script, a utility, a library, a browser extension, a config/IaC project (e.g. a NixOS or Ansible config repo), a firmware project. Keep even small scripts/one-off utilities here.
JUNK - NOT itself a piece of software: a news article, blog post, product review, tutorial/how-to guide, forum thread, GitHub issue or pull request reference (titles like "· Issue #123 ·" or "Pull Request #"), research paper, podcast episode note, organization/community/conference, benchmark or comparison writeup, marketing/announcement page, a person or brand name with no software attached.

If APP, also decide SIZE:
FULL - a standalone application or service with its own real footprint (Nextcloud, Frigate, Pi-hole, a whole project/repo).
SMALL - a tiny one-off script, snippet, single CLI utility, or config file (not a whole application).
If JUNK, SIZE is irrelevant, just write "-".

Output EXACTLY one line per entry, in order, nothing else - no preamble, no blank lines, no commentary:
<number>|<APP|JUNK>|<FULL|SMALL|->

Example output for 3 entries:
1|APP|FULL
2|JUNK|-
3|APP|SMALL
"""


def ollama_call(prompt):
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())["response"]


LINE_RE = re.compile(r"^\s*(\d+)\s*\|\s*(APP|JUNK)\s*\|\s*(FULL|SMALL|-)\s*$", re.I)


def parse(output, expected_n):
    result = {}
    for line in output.strip().splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        idx, cls, size = int(m.group(1)), m.group(2).upper(), m.group(3).upper()
        result[idx] = (cls, size)
    if len(result) != expected_n or set(result.keys()) != set(range(1, expected_n + 1)):
        return None
    return result


def already_done():
    done = set()
    try:
        with open(CHECKPOINT_PATH) as f:
            for line in f:
                rec = json.loads(line)
                done.add(rec["name"])
    except FileNotFoundError:
        pass
    return done


def main():
    tools = json.load(open(TOOLS_PATH))
    done = already_done()
    todo = [t for t in tools if t["name"] not in done]
    print(f"{len(tools)} total, {len(done)} already classified, {len(todo)} remaining", file=sys.stderr)

    ckpt = open(CHECKPOINT_PATH, "a")
    failed = []

    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        prompt_lines = []
        for n, t in enumerate(batch, 1):
            desc = (t.get("description") or "").strip().replace("\n", " ")[:200]
            url = (t.get("url") or "").strip()
            domain = ""
            if url:
                m = re.match(r"https?://(?:www\.)?([^/]+)", url)
                domain = m.group(1) if m else url[:40]
            prompt_lines.append(f"{n}. NAME: {t['name']}\n   DESCRIPTION: {desc}\n   URL DOMAIN: {domain}")
        prompt = "\n".join(prompt_lines)

        result = None
        for attempt in range(MAX_RETRIES):
            try:
                output = ollama_call(prompt)
            except Exception as e:
                print(f"batch {i}: request error {e}, retry {attempt+1}", file=sys.stderr)
                time.sleep(3)
                continue
            result = parse(output, len(batch))
            if result:
                break
            print(f"batch {i}: malformed output (attempt {attempt+1}), retrying", file=sys.stderr)
            time.sleep(1)

        if not result:
            print(f"batch {i}: FAILED after {MAX_RETRIES} attempts, marking for manual review", file=sys.stderr)
            failed.extend(t["name"] for t in batch)
            continue

        for n, t in enumerate(batch, 1):
            cls, size = result[n]
            ckpt.write(json.dumps({"name": t["name"], "cls": cls, "size": size}) + "\n")
        ckpt.flush()
        done_count = i + len(batch)
        print(f"{done_count}/{len(todo)} classified", file=sys.stderr)

    ckpt.close()
    if failed:
        json.dump(failed, open(FAILED_PATH, "w"), indent=1)
        print(f"{len(failed)} entries failed classification, see {FAILED_PATH}", file=sys.stderr)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
