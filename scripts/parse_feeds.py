#!/usr/bin/env python3
"""Parse Self-Hosted and Linux Unplugged RSS feeds into structured JSON:
episodes + raw candidate link entries (before filtering/categorization)."""
import re, json, sys
from datetime import datetime
from bs4 import BeautifulSoup

def parse_feed(path, show_name):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    soup = BeautifulSoup(content, 'xml')
    items = soup.find_all('item')
    episodes = []
    for it in items:
        title_raw = it.find('title').get_text(strip=True) if it.find('title') else ''
        link_el = it.find('link')
        link = link_el.get_text(strip=True) if link_el else ''
        pub = it.find('pubDate')
        air_date = None
        if pub and pub.get_text(strip=True):
            try:
                dt = datetime.strptime(pub.get_text(strip=True), '%a, %d %b %Y %H:%M:%S %z')
                air_date = dt.strftime('%Y-%m-%d')
            except Exception:
                air_date = None
        # episode number: try leading "NNN:" in title, else itunes:episode
        m = re.match(r'^\s*(?:Episode\s+)?(\d+)\s*[:\-]', title_raw)
        ep_num = None
        if m:
            ep_num = int(m.group(1))
        else:
            ie = it.find('itunes:episode')
            if ie and ie.get_text(strip=True).isdigit():
                ep_num = int(ie.get_text(strip=True))
        # clean title: strip leading number prefix
        title_clean = re.sub(r'^\s*(?:Episode\s+)?\d+\s*[:\-]\s*', '', title_raw)
        # also strip trailing "| LINUX Unplugged NNN" or "| LUNNN" patterns
        title_clean = re.sub(r'\s*\|\s*LINUX Unplugged.*$', '', title_clean)
        title_clean = re.sub(r'\s*\|\s*LU\d+.*$', '', title_clean)

        content_encoded = it.find('content:encoded')
        html = content_encoded.get_text() if content_encoded else ''

        # skip trailer/coming-soon non-episodes (no episode number)
        if ep_num is None:
            episodes.append({
                'show': show_name, 'episode_number': None, 'title': title_clean,
                'air_date': air_date, 'url': link, 'raw_links': [], 'skip_reason': 'no_episode_number'
            })
            continue

        chtml = BeautifulSoup(html, 'lxml')
        raw_links = []
        # Walk top-level <p> and <ul> siblings to know context (Sponsored By vs Links)
        section = 'unknown'
        body = chtml.body if chtml.body else chtml
        for el in body.find_all(['p', 'ul'], recursive=False):
            if el.name == 'p':
                txt = el.get_text(strip=True).lower()
                if 'sponsored by' in txt:
                    section = 'sponsor'
                elif txt.startswith('links'):
                    section = 'links'
                elif 'support' in txt and el.find('a', rel='payment'):
                    section = 'support'
                continue
            if el.name == 'ul':
                for li in el.find_all('li', recursive=False):
                    a_tags = li.find_all('a')
                    if not a_tags:
                        continue
                    first_a = a_tags[0]
                    name = first_a.get('title') or first_a.get_text(strip=True)
                    href = first_a.get('href', '')
                    full_text = li.get_text(' ', strip=True)
                    # description = text after the link text, strip leading dash/colon/emdash
                    link_text = first_a.get_text(strip=True)
                    desc = full_text
                    if desc.startswith(link_text):
                        desc = desc[len(link_text):]
                    desc = desc.lstrip(' —–-:').strip()
                    # if there's a second <a> with same-ish text (sponsor pattern "name: desc-link"), merge desc from it
                    if len(a_tags) > 1:
                        second_text = a_tags[1].get_text(' ', strip=True)
                        if second_text and second_text not in (name,):
                            if not desc:
                                desc = second_text
                    raw_links.append({
                        'section': section, 'name': name.strip(), 'url': href.strip(),
                        'description': desc.strip()
                    })
        episodes.append({
            'show': show_name, 'episode_number': ep_num, 'title': title_clean.strip(),
            'air_date': air_date, 'url': link, 'raw_links': raw_links, 'skip_reason': None
        })
    return episodes

if __name__ == '__main__':
    sh = parse_feed('sh_rss.xml', 'Self-Hosted')
    lup = parse_feed('lup_rss.xml', 'Linux Unplugged')
    with open('sh_parsed.json', 'w') as f:
        json.dump(sh, f, indent=1)
    with open('lup_parsed.json', 'w') as f:
        json.dump(lup, f, indent=1)
    print('Self-Hosted episodes:', len(sh), 'with ep_num:', sum(1 for e in sh if e['episode_number'] is not None))
    print('LUP episodes:', len(lup), 'with ep_num:', sum(1 for e in lup if e['episode_number'] is not None))
    print('Self-Hosted total raw links:', sum(len(e['raw_links']) for e in sh))
    print('LUP total raw links:', sum(len(e['raw_links']) for e in lup))
