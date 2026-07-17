-- Schema for the self-hosted tools reference database.
-- Catalogs every self-hosted software tool/app mentioned in the show notes
-- of the "Self-Hosted" (selfhosted.show) and "LINUX Unplugged"
-- (linuxunplugged.com) podcasts, both Jupiter Broadcasting shows.

CREATE TABLE IF NOT EXISTS episodes (
  id INTEGER PRIMARY KEY,
  show TEXT NOT NULL CHECK (show IN ('Self-Hosted', 'Linux Unplugged')),
  episode_number INTEGER,
  title TEXT,
  air_date TEXT,        -- ISO 8601 (YYYY-MM-DD)
  url TEXT,
  UNIQUE (show, episode_number)
);

CREATE TABLE IF NOT EXISTS tools (
  id INTEGER PRIMARY KEY,
  episode_id INTEGER NOT NULL REFERENCES episodes(id),
  name TEXT NOT NULL,
  url TEXT,              -- project homepage/repo link, if given in show notes
  description TEXT,      -- verbatim or lightly-trimmed show notes description
  category TEXT          -- inferred, e.g. monitoring, media, networking, backup, dashboard, security, productivity
);

CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name);
CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category);
CREATE INDEX IF NOT EXISTS idx_episodes_show ON episodes(show);
