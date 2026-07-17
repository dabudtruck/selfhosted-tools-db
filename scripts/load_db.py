#!/usr/bin/env python3
"""Load sh_tools.json / lup_tools.json into tools.db per schema.sql."""
import json, sqlite3, sys

DB_PATH = '/home/sb2/Nextcloud/Documents/Home/vscodefiles/selfhosted-tools-db/tools.db'

def load(show_key, path, conn):
    data = json.load(open(path))
    cur = conn.cursor()
    ep_count = 0
    tool_count = 0
    for ep in data:
        cur.execute(
            """INSERT INTO episodes (show, episode_number, title, air_date, url)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(show, episode_number) DO UPDATE SET
                 title=excluded.title, air_date=excluded.air_date, url=excluded.url""",
            (ep['show'], ep['episode_number'], ep['title'], ep['air_date'], ep['url'])
        )
        cur.execute("SELECT id FROM episodes WHERE show=? AND episode_number=?",
                     (ep['show'], ep['episode_number']))
        ep_id = cur.fetchone()[0]
        # clear any existing tools for this episode (idempotent re-run)
        cur.execute("DELETE FROM tools WHERE episode_id=?", (ep_id,))
        ep_count += 1
        for t in ep['tools']:
            name = t['name'].strip()
            if not name:
                continue
            url = t['url'].strip() or None
            desc = t['description'].strip() or None
            cur.execute(
                "INSERT INTO tools (episode_id, name, url, description, category) VALUES (?, ?, ?, ?, ?)",
                (ep_id, name, url, desc, t['category'])
            )
            tool_count += 1
    conn.commit()
    print(f'{show_key}: {ep_count} episodes, {tool_count} tools loaded')

if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    load('Self-Hosted', 'sh_tools.json', conn)
    load('Linux Unplugged', 'lup_tools.json', conn)
    cur = conn.cursor()
    cur.execute("SELECT show, COUNT(*) FROM episodes GROUP BY show")
    print(cur.fetchall())
    cur.execute("SELECT e.show, COUNT(*) FROM tools t JOIN episodes e ON t.episode_id=e.id GROUP BY e.show")
    print(cur.fetchall())
    conn.close()
