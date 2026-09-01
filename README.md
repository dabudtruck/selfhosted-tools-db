# Self-Hosted Tools Reference Database

**Live site: [dabudtruck.github.io/selfhosted-tools-db](https://dabudtruck.github.io/selfhosted-tools-db/)** — search all 4,888 tools in the browser, no setup required.

A searchable catalog of every self-hosted software tool/app mentioned in the show notes of two Jupiter Broadcasting podcasts:

- **Self-Hosted** ([selfhosted.show](https://selfhosted.show/)) — dedicated self-hosting show, ~150 episodes as of 2026-07.
- **LINUX Unplugged** ([linuxunplugged.com](https://linuxunplugged.com/)) — general Linux talk show, 675+ episodes as of 2026-07, self-hosted software is a recurring but not exclusive topic.

Built 2026-07-17 as a reference for future homelab tool decisions — rather than re-searching from scratch each time, query this database for what's already been vetted/discussed on these shows. Published 2026-09-01 as a public site since it's useful well beyond one homelab.

## Structure

`tools.db` — SQLite database, schema in `schema.sql`. Two tables: `episodes` (show/number/title/date/url) and `tools` (name/url/description/category, linked to the episode it was mentioned in).

`scripts/` — the extraction pipeline used to build the database from each
show's RSS feed (`parse_feeds.py` → `filter_categorize.py` → `load_db.py`),
plus `dedupe_and_export.py`, which collapses repeat mentions of the same
tool into one entry (aggregating every episode it came up in) and exports
`docs/data/tools.json` for the live site. Re-run the first three to pick up
new episodes, then `dedupe_and_export.py` to refresh the site's data; see
`PROGRESS.md` for details.

Exact-name dedup only catches literal repeats. Some products (Nextcloud
being the worst offender — dozens of show-notes entries that were really
blog posts, GitHub issues, and NixOS-deployment writeups all about the one
tool) needed manual curation on top of that. `scripts/aliases.json` holds
it: a `merge` map folds noisy name variants into one canonical entry, an
`overrides` map forces a clean name/description on that entry instead of
picking one of the raw variants, and a `families` map groups genuinely
distinct sub-apps (Nextcloud Notes, Nextcloud AIO, etc.) under a shared
parent so the site nests them instead of showing each as its own row. Add
more entries there to curate other duplicated tools — no code changes
needed, `dedupe_and_export.py` reads it automatically.

This is a *software* tools database — physical hardware (SBCs, Zigbee/
Z-Wave radios, sensors, cameras, NAS enclosures, routers-as-a-box, etc.)
is out of scope for it. `aliases.json`'s `hardware_exclude` list (123
entries as of the last full sweep) pulls those out of `docs/data/tools.json`
entirely; `dedupe_and_export.py` writes them to their own
`docs/data/hardware.json` instead (deduped/aggregated the same way, just
not linked from the site yet — a real hardware inventory page is future
work, not built here). Add more names to `hardware_exclude` as new ones
turn up; it matches on the raw show-notes name, same as `merge`/`families`.

## Community corrections & additions

Every tool row on the live site has a "Suggest a fix" link, and the header
has a "missing a tool? suggest it" link — both just open a pre-filled
GitHub issue (labeled `correction` or `addition`), no account/backend of
mine involved beyond GitHub's own. No live ratings or comments by design —
this stays a static, no-backend site; corrections get triaged and merged
into `tools.db` by hand (or via a future script keyed on issue label),
then re-exported with `dedupe_and_export.py`.

## Live site (`docs/`)

Static search page, no backend — `docs/index.html` + `docs/app.js` fetch
`docs/data/tools.json` once and do all searching/filtering client-side.
Served by GitHub Pages directly from this branch's `docs/` folder. To
refresh after re-running the pipeline:

```bash
sqlite3 tools.db < schema.sql   # if rebuilding from scratch
python3 scripts/dedupe_and_export.py tools.db docs/data/tools.json
git add docs/data/tools.json && git commit -m "Refresh tool catalog" && git push
```

## Querying

```bash
sqlite3 tools.db "SELECT name, description, category FROM tools WHERE name LIKE '%kuma%';"
sqlite3 tools.db "SELECT t.name, t.description, e.title, e.episode_number, e.show FROM tools t JOIN episodes e ON t.episode_id = e.id WHERE t.category = 'monitoring';"
```

## Coverage

Complete: all 150 Self-Hosted episodes (1–150) and all 675 Linux Unplugged
episodes (1–675), 5,663 cataloged tool mentions total. See `PROGRESS.md`
for the full build notes, methodology, and known data-quality caveats
(Linux Unplugged's show notes are noisier than Self-Hosted's, being a
general Linux talk show rather than a dedicated self-hosting show).
