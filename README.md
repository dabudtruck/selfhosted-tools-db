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
