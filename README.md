# Self-Hosted Tools Reference Database

A local, searchable catalog of every self-hosted software tool/app mentioned in the show notes of two Jupiter Broadcasting podcasts:

- **Self-Hosted** ([selfhosted.show](https://selfhosted.show/)) — dedicated self-hosting show, ~150 episodes as of 2026-07.
- **LINUX Unplugged** ([linuxunplugged.com](https://linuxunplugged.com/)) — general Linux talk show, 675+ episodes as of 2026-07, self-hosted software is a recurring but not exclusive topic.

Built 2026-07-17 as a reference for future homelab tool decisions — rather than re-searching from scratch each time, query this database for what's already been vetted/discussed on these shows.

## Structure

`tools.db` — SQLite database, schema in `schema.sql`. Two tables: `episodes` (show/number/title/date/url) and `tools` (name/url/description/category, linked to the episode it was mentioned in).

## Querying

```bash
sqlite3 tools.db "SELECT name, description, category FROM tools WHERE name LIKE '%kuma%';"
sqlite3 tools.db "SELECT t.name, t.description, e.title, e.episode_number, e.show FROM tools t JOIN episodes e ON t.episode_id = e.id WHERE t.category = 'monitoring';"
```

## Coverage

See `PROGRESS.md` for build status — this is a large dataset (potentially 800+ episodes combined), built incrementally.
