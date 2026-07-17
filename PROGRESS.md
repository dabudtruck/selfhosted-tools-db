# Progress

Status: **Both shows fully processed, full episode archives covered.**

## Summary

| Show | Episodes in DB | Episode range | Tools cataloged | Distinct tool names |
|---|---|---|---|---|
| Self-Hosted | 150 | 1–150 (complete, no gaps) | 1,078 | 907 |
| Linux Unplugged | 675 | 1–675 (complete, no gaps) | 4,613 | 4,101 |
| **Total** | **825** | | **5,691** | |

`tools.db` is built and committed. Both shows' full episode archives (not just recent RSS entries) are covered — see "Key discovery" below for why this was tractable in one pass.

## Key discovery that changed the approach

The task brief assumed the RSS feeds (`feeds.fireside.fm/selfhosted/rss` and
`feeds.jupiterbroadcasting.com/lup`) only contained the ~10 most recent
episodes, requiring separate scraping of the shows' website archive pages.
That turned out to be wrong: **both RSS feeds return their entire back
catalog** — 151 items (150 real episodes + 1 "coming soon" trailer) for
Self-Hosted, and 675 items for Linux Unplugged — each with full show notes
in `<content:encoded>`, including sponsor blocks and a "Links:" list of
every tool/resource mentioned, complete with title, URL, and (usually) a
one-line description.

This meant the entire dataset could be built by downloading the two RSS
files once (`curl`) and parsing them locally, rather than fetching 825
individual episode pages over the network. No web scraping of
`selfhosted.show` or `linuxunplugged.com` archive/tag pages was needed or
performed.

## Pipeline (scripts in `scripts/`, source data not checked in)

1. `curl` the two RSS feeds to local XML files.
2. `scripts/parse_feeds.py` — parses each `<item>`, extracts episode number
   (from the title's leading `NNN:` prefix, falling back to
   `<itunes:episode>`), title, air date, episode URL, and every `<li><a>`
   entry from the "Sponsored By" and "Links:" `<ul>` blocks in
   `content:encoded`, tagged by which section it came from.
3. `scripts/filter_categorize.py` — the judgment-heavy step:
   - Drops entries whose link domain (or exact phrase in the link title)
     matches a blocklist of non-tool content: podcast-boost/crypto-sats
     links, Jupiter Broadcasting membership/swag/merch links, sponsor
     ads for services that are not self-hostable software (cloud SaaS,
     training platforms, VPS providers, antivirus, hardware vendors),
     social media, video/YouTube links, news/tech-journalism sites,
     general Linux distro/kernel/community sites, conference/meetup/event
     pages, other Jupiter Broadcasting shows mentioned in passing, and
     blog-post/article links (as opposed to project/tool links).
   - Merges "Tool Name" + immediately-following "Tool Name on GitHub"
     list-item pairs into one entry (a common show-notes pattern) instead
     of double-counting.
   - Drops bare `github.com/<user>` profile-page links (no specific repo).
   - Infers a `category` per tool via keyword matching against name +
     description + URL, using a fixed category vocabulary (see below).
4. `scripts/load_db.py` — upserts episodes and (re-)inserts tools into
   `tools.db` per `schema.sql`, idempotently (safe to re-run after tuning
   the filter).

Steps 1–2 (raw parsing) are lossless and mechanical. Step 3 (filtering +
categorizing) is where judgment calls live — see below.

## Judgment calls

- **"Self-hosted tool" was interpreted broadly**, per the task brief's
  "err toward inclusion" guidance: any named software project, app, CLI
  tool, self-hostable service, or (for genuinely software-adjacent cases)
  a script/config repo, was kept. Pure hardware (SBCs, keyboards, network
  gear, phones), news articles, blog posts/opinion pieces, distro/kernel
  announcements, conference/meetup listings, and other podcasts mentioned
  in passing were excluded — these are explicitly out of scope per the
  task brief.
- **Sponsor-read ads were mostly excluded**, but genuinely self-hostable
  sponsor tools were kept when they're plausible homelab software (e.g.
  Tailscale, Unraid, Nebula/Defined Networking, Bitwarden). Sponsors that
  are inherently non-self-hostable (Datadog, Backblaze consumer backup,
  Webroot, A Cloud Guru, MailRoute, CrowdHealth, cloud VPS providers) were
  excluded even when pitched as "self-hosted"-adjacent, since they're
  fundamentally third-party SaaS, not something you install yourself.
- **1Password was excluded, Bitwarden was kept** — both are password-
  manager sponsors, but only Bitwarden (via Vaultwarden etc.) is genuinely
  self-hostable; 1Password is cloud-only.
- **Category vocabulary** was kept intentionally fixed and small:
  `monitoring, media, networking, security, backup, storage, dashboard,
  automation, containers, communication, productivity, ai, development,
  gaming, identity, analytics, remote-access, other`. Roughly 55% of
  Self-Hosted tools and 67% of Linux Unplugged tools landed in a specific
  category via keyword match; the rest fell to `other` rather than forcing
  a guess — `other` is a legitimate, intentionally large bucket, not a
  failure state.
- **Duplicate tool names across episodes are expected and preserved.**
  Each row in `tools` is one *mention* of a tool in one episode's show
  notes (matching the schema's `episode_id` foreign key), not a
  deduplicated global tool registry. A tool discussed in 10 episodes
  appears as 10 rows, each with that episode's own description/URL as
  given in that episode's notes. Capitalization of the same tool can also
  vary between episodes (e.g. `Immich` vs `immich`) since descriptions are
  taken close to verbatim from each episode's own show notes.
- **Self-Hosted episode 150 ("Self-Hosted Coming Soon") trailer** (no
  episode number, no real content) was excluded from the episode count.

## Known quality gaps / what's NOT fully clean

- **Linux Unplugged is inherently noisier** than Self-Hosted, being a
  general Linux talk show rather than a dedicated self-hosting show. Even
  after blocklist filtering, its "Links:" sections routinely mix in
  driver-download pages, distro release announcements, hardware product
  pages, personal dotfiles/infra repos, one-off blog posts, and
  conference/meetup pages that weren't fully caught by the blocklist. I
  iterated the blocklist across several spot-check rounds (~50-item random
  samples, multiple passes) and it converged well, but at ~4,600 kept
  Linux Unplugged entries, a residual single-digit-percent of non-tool
  noise almost certainly remains — treat `category = 'other'` LUP rows
  with somewhat more skepticism than Self-Hosted ones.
- **Self-Hosted is much cleaner** — it's a dedicated self-hosting show,
  so nearly everything in its "Links:" sections is genuinely on-topic.
  Residual noise there is minimal (a handful of borderline
  articles/resources may have slipped through).
- **Categorization is keyword-based, not semantic** — a tool can be
  miscategorized if its name/description happens to contain an unrelated
  keyword (e.g. a note mentioning "snapshot" pulling a tool into
  `backup`). Spot-checked but not exhaustively verified across all ~5,700
  rows.
- **No web-scraping fallback was needed/attempted** for either show, since
  the RSS feeds already contained full archives with rich show notes. If
  a future episode's notes are ever thin in RSS, the site's per-episode
  pages (`selfhosted.show/<n>`, `linuxunplugged.com/<n>`) would be the
  fallback source, but this wasn't required for the current 1–150 /
  1–675 ranges.
- **GitHub gists, personal blogs, and single-file config repos** were
  deliberately excluded as "resources" rather than "tools" — this could
  under-count some genuinely useful configs/scripts, but keeps the
  dataset focused on installable software/services per the task's
  definition.

## To refresh/extend later

New episodes: re-run `curl` on the two RSS URLs, then re-run
`scripts/parse_feeds.py`, `scripts/filter_categorize.py`,
`scripts/load_db.py` in that order from a directory containing the fresh
`sh_rss.xml` / `lup_rss.xml` (the scripts currently expect those filenames
in the working directory, and `load_db.py` has the destination `tools.db`
path hardcoded to this repo). The loader is idempotent per
`(show, episode_number)`, so re-running after adding new episodes to the
RSS files is safe and won't duplicate existing rows.
