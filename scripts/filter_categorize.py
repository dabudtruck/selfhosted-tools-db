#!/usr/bin/env python3
"""Filter raw candidate links down to genuine self-hosted tools/software,
dedup repo-link follow-ups, and infer a category. Outputs sh_tools.json /
lup_tools.json for review before DB load."""
import json, re
from urllib.parse import urlparse

# Domains that are essentially never a self-hosted *tool* in this context:
# news/media, social, event/community, JB-show-internal, sponsor-noise,
# generic distro/kernel sites, hardware storefronts, cloud-VPS sponsors,
# training platforms, proprietary cloud-only SaaS.
DOMAIN_BLOCKLIST = {
    'phoronix.com','arstechnica.com','theverge.com','zdnet.com','theregister.com',
    'techcrunch.com','omgubuntu.co.uk','fedoramagazine.org','lwn.net',
    'news.ycombinator.com','9to5linux.com','gamingonlinux.com','medium.com',
    'twitter.com','x.com','reddit.com','matrix.to','imgur.com','play.google.com',
    'amazon.com','bit.ly','youtube.com','youtu.be','tiktok.com','instagram.com',
    'facebook.com','linkedin.com','mastodon.social','mastodon.online',
    'meetup.com','sessionize.com','socallinuxexpo.org','linuxfestnorthwest.org',
    'eventbrite.com','allthingsopen.org',
    'podcastindex.org','fountain.fm','jupitersignal.memberful.com',
    'jupiterbroadcasting.com','jupitergarage.com','extras.show',
    'feed.jupiter.zone','linuxunplugged.com','selfhosted.show','strike.me',
    'bitcoinwell.com','getalby.com','river.com','coinbase.com',
    'linode.com','do.co','digitalocean.com','vultr.com','aws.amazon.com',
    'kolide.com','acloudguru.com','linuxacademy.com','pluralsight.com',
    'udemy.com','coursera.org',
    '1password.com','lastpass.com',
    'redhat.com','ubuntu.com','fedoraproject.org','kde.org','nixos.org',
    'discourse.ubuntu.com','discourse.nixos.org','docs.fedoraproject.org',
    'wiki.archlinux.org','nixos.wiki','lore.kernel.org','kernel.org',
    'debian.org','opensuse.org','gnome.org','blogs.gnome.org',
    'gitlab.gnome.org','distrowatch.com','endeavouros.com','manjaro.org',
    'system76.com','linux.ting.com','cloudfree.shop','raspberrypi.com',
    'aliexpress.com','ebay.com','newegg.com','bhphotovideo.com',
    'gist.github.com','pastebin.com','paste.docs.lol','md.ktz.cloud',
    'blog.ktz.me','slexy.org','hastebin.com',
    'en.wikipedia.org','wikipedia.org','wiki.debian.org',
    'spotify.com','open.spotify.com','soundcloud.com','apple.co',
    'podcasts.apple.com','overcast.fm',
    'lwn.net','openbenchmarking.org','distrotube.com',
    'gofundme.com','kickstarter.com','indiegogo.com','patreon.com',
    'store.steampowered.com','steamcommunity.com',
    'linuxjournal.com','itsfoss.com','betanews.com','techrepublic.com',
    'bleepingcomputer.com','theregister.co.uk','wired.com','engadget.com',
    'venturebeat.com','cnet.com','pcgamer.com','tomshardware.com',
    'anandtech.com','servethehome.com',
    'crowdstrike.com','keeb.io','prusa3d.com','zimaboard.com',
    'blog.cloudflare.com','developers.home-assistant.io','flightaware.store',
    'blog.linuxserver.io','serverbuilds.net','chrislas.com','xeiaso.net',
    'teknikaldomain.me','pitchfork.com','45homelab.com','xda-developers.com',
    'cablefree.net','architecting.it','howtogeek.com','bestbuy.com',
    'blog.prusa3d.com','amzn.to','topclack.com','store.minisforum.com',
    'minisforum.com','mylocalbytes.com','store.untrustedsource.com',
    'untrustedsource.com','thingiverse.com','thehelpfulidiot.com',
    'walmart.com','microcenter.com','frys.com','costco.com',
    'digikey.com','mouser.com','sparkfun.com','adafruit.com',
    'crowdsupply.com','tindie.com','banggood.com',
    'freebsd.org','opensuse.org','docs.google.com','osradar.com',
    '9to5google.com','ting.com','tuxedocomputers.com','protondb.com',
    'soundguys.com','rockylinux.org','jingos.com','exponent.fm','puri.sm',
    'archlinux.org','distrowatch.com','omgubuntu.co.uk','9to5mac.com',
    'macrumors.com','androidauthority.com','androidpolice.com',
    'phonearena.com','gsmarena.com','notebookcheck.net','slashgear.com',
    'liliputing.com','pcworld.com','forbes.com','businessinsider.com',
    'huggingface.co',
    'nvidia.com','gnu.org','fsf.org','canonical.com','blog.elementary.io',
    'ubports.com','stopthemingmy.app','whydoesaptnotusehttps.com',
    'blogspot.com','space.com','doyensec.com','gettogether.community',
    'strawpoll.me','ubuntuupdates.org','pretalx.seagl.org','workable.com',
    'passthroughpo.st','ssh.com','winehq.org','elementary.io',
    'linuxacademy.workable.com','clearlinux.org','tuxdigital.com',
    'hpdevone.com',
    'acloud.guru','backblaze.com','joincrowdhealth.com','datadog.com',
    'mailroute.net','planetnix.com','texascybersummit.org',
    'unpluggedcore.com','webroot.com','yardhouse.com','2.5admins.com',
    'colonyevents.com','texaslinuxfest.org','linuxheadlines.show',
    'forms.gle','configcat.com','entropy.works','0pointer.net',
    'nasa.gov','sciencealert.com','inverse.com','bbc.com','npr.org',
    'i.redd.it','redd.it','sam.gov','sifive.com','chrislewicki.com',
    'newscientist.com','popsci.com','gizmodo.com','sciencedaily.com',
}

# (domain, path-prefix) pairs to block — same domain hosts both the real
# tool/docs AND a news/marketing blog; only the blog path is noise.
DOMAIN_PATH_BLOCKLIST = [
    ('home-assistant.io', '/blog'),
    ('nextcloud.com', '/news'),
    ('nextcloud.com', '/conference'),
]

# substrings in netloc that indicate blocklist (catches subdomains not enumerated)
DOMAIN_SUBSTR_BLOCKLIST = [
    'memberful.com','jupiterbroadcasting.com','fireside.fm',
]

NAME_PHRASE_BLOCKLIST = [
    'boost', 'swag', 'sticker', 'discount', 'coupon', 'garage sale',
    'membership', 'support self-hosted', 'support linux unplugged',
    'support the show', 'grab sats', 'sats with', 'sats around',
    'highlights - youtube', 'on youtube', 'youtube channel',
    'live stream', 'members stream', "member's stream", 'meetup',
    'live show', 'jupiter party', 'jupiter.party', 'annual membership',
    'monthly membership', 'become a member', 'chat with us', 'join our',
    'community forum', 'telegram', 'irc channel', 'discord',
    'mailing list', 'newsletter signup', 'follow us', 'follow on',
    'our mastodon', 'our twitter', 'wiki page for this episode',
    'episode wiki', 'show notes', 'recap of', 'ama with', 'roundup',
    'funding', 'donate', 'sponsor us', 'newsletter',
]

BLOG_SUFFIX_RE = re.compile(r'\bblog$', re.IGNORECASE)

# JB's other podcasts (mentions of another show, not a tool)
OTHER_SHOW_PHRASE_BLOCKLIST = [
    'coder radio', 'office hours', 'techsnap', 'user error',
    'choose linux', 'ask noah show', 'this week in linux',
    'data hoarders', 'really linux', 'scan your network podcast',
    'dam software podcast', 'linux action news', 'plus ultra',
    'zoo con', 'jupiter extras', 'linux headlines', '2.5 admins',
    'linux downtime', 'self-hosted podcast episode',
]

EVENT_PHRASE_BLOCKLIST = [
    'linux fest', 'linuxfest', 'texas linux', 'tuxies', 'colony events',
    'scale ', 'socallinuxexpo', 'conference 20', 'summit 20',
    'pacific northwest party', 'tui challenge rules', 'nominations for',
]

GITHUB_FOLLOWUP_RE = re.compile(
    r'^(.*?)\s*(?:on github|\(github\)|- github|github repo|source(?: code)?|repo)\s*$',
    re.IGNORECASE)


def domain_blocked(url):
    if not url:
        return False
    p = urlparse(url)
    netloc = p.netloc.lower().replace('www.', '')
    for dom in DOMAIN_BLOCKLIST:
        if netloc == dom or netloc.endswith('.' + dom):
            return True
    for sub in DOMAIN_SUBSTR_BLOCKLIST:
        if sub in netloc:
            return True
    for dom, prefix in DOMAIN_PATH_BLOCKLIST:
        if netloc == dom and p.path.startswith(prefix):
            return True
    return False


def name_blocked(name):
    n = name.lower()
    if BLOG_SUFFIX_RE.search(name.strip()):
        return True
    for p in NAME_PHRASE_BLOCKLIST + OTHER_SHOW_PHRASE_BLOCKLIST + EVENT_PHRASE_BLOCKLIST:
        if p in n:
            return True
    return False


def github_profile_page(url):
    """True if url is a bare github.com/<user-or-org> profile page (no repo)."""
    if not url:
        return False
    p = urlparse(url)
    if p.netloc.lower().replace('www.', '') != 'github.com':
        return False
    segs = [s for s in p.path.split('/') if s]
    return len(segs) == 1


CATEGORY_RULES = [
    # (category, keywords to match against name+description+url, case-insens)
    ('media', ['jellyfin','plex','emby','navidrome','audiobookshelf','kavita','komga',
               'immich','photoprism','photostructure','tube','tubearchivist','metube',
               'yt-dlp','video','music','podcast player','photo','streaming','together tube',
               'stash','radarr','sonarr','lidarr','readarr','bazarr','prowlarr','overseerr',
               'jellyseerr','ombi','picard','beets','navidrome','funkwhale','airsonic',
               'invidious','freetube','peertube','owncast','streama','kodi']),
    ('monitoring', ['uptime kuma','grafana','prometheus','netdata','zabbix','monit',
                     'healthcheck','statping','gatus','glances','observability',
                     'metrics','uptime','status page','alertmanager','loki','beszel',
                     'checkmk','icinga','nagios']),
    ('networking', ['pihole','pi-hole','adguard','wireguard','tailscale','netbird',
                     'nebula','zerotier','vpn','headscale','openwrt','router','dns server',
                     'unbound','dnsmasq','traefik','nginx proxy manager','caddy','haproxy',
                     'reverse proxy','load balancer','network','firewall','switch','vlan',
                     'cloudflare tunnel','frp','ngrok','tunnel','mesh network','tor ',
                     'cockpit','netmaker']),
    ('security', ['vaultwarden','bitwarden','keepass','passbolt','vault','2fa','totp',
                   'authelia','authentik','keycloak','ldap','sso','crowdsec','fail2ban',
                   'wazuh','security key','yubikey','encryption','pgp','gpg','password manager',
                   'zitadel','openbao']),
    ('backup', ['restic','borg','borgbackup','duplicati','rclone','backup','snapshot',
                 'kopia','urbackup','veeam','timeshift','syncthing']),
    ('storage', ['nextcloud','owncloud','seafile','minio','ceph','zfs','truenas',
                  'unraid','openmediavault','nas','s3','object storage','filerun',
                  'filebrowser','garage','storj','ipfs']),
    ('dashboard', ['homepage','heimdall','homer','dashy','organizr','flame','dashboard',
                    'glance','homarr','startpage']),
    ('automation', ['home assistant','homeassistant','esphome','zigbee','z-wave','zwave',
                      'node-red','n8n','automation','klipper','octoprint','moonraker',
                      'domoticz','openhab','ioBroker']),
    ('containers', ['docker','podman','kubernetes','k3s','k8s','portainer','yacht',
                      'dockge','container','helm chart','nomad','lxc','proxmox',
                      'coolify','dokploy','casaos']),
    ('communication', ['matrix','element','synapse','mattermost','rocket.chat','xmpp',
                         'jitsi','discord alternative','signal','email server','mailcow',
                         'postfix','forum software','discourse forum','nextcloud talk',
                         'chat server','sms gateway']),
    ('productivity', ['vaultwarden','obsidian','notion alternative','joplin','trilium',
                        'wiki','bookstack','wikijs','wiki.js','notes app','todo','kanban',
                        'planka','vikunja','focalboard','task manager','calendar','contacts',
                        'radicale','baikal','paperless','document management','bookmark',
                        'linkding','shiori','readeck','wallabag','miniflux','freshrss',
                        'rss reader','feed reader']),
    ('ai', ['ollama','llm','chatgpt','openai','gpt','llama','stable diffusion',
             'automatic1111','langchain','localai','gpt4all','whisper','mcp','model context protocol',
             'text generation','ai agent','claude code','opencode']),
    ('development', ['gitea','forgejo','gitlab self','github alternative','ci/cd',
                       'jenkins','drone ci','woodpecker','code server','vscode server',
                       'nixos config','flake','devcontainer']),
    ('gaming', ['game server','minecraft server','game streaming','sunshine','moonlight',
                 'steam link','emulation','retroarch','game pass alternative']),
    ('identity', ['authelia','authentik','keycloak','ldap','sso','zitadel']),
    ('analytics', ['plausible','umami','matomo','google analytics alternative',
                    'web analytics','fathom analytics']),
    ('remote-access', ['rustdesk','guacamole','anydesk','teamviewer','vnc','rdp',
                         'remote desktop','meshcentral','moonlight','sunshine',
                         'x11vnc','novnc','ttyd','parsec','kvm switch','pikvm',
                         'tailscale ssh']),
]

def infer_category(name, desc, url):
    # Word-boundary matching, not plain substring — plain "in" matching let
    # short/ambiguous keywords false-positive badly (e.g. 'monit' inside
    # "Monitor"/"Monitoring", 'nas' inside "NASA's", 'mcp' inside a URL
    # path like "mcpelauncher").
    text = f'{name} {desc} {url}'.lower()
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            pattern = r'\b' + re.escape(kw.strip()) + r'\b'
            if re.search(pattern, text):
                return cat
    return 'other'


def process(parsed_path, out_path):
    episodes = json.load(open(parsed_path))
    out = []
    stats = {'total_raw': 0, 'kept': 0, 'blocked_domain': 0, 'blocked_phrase': 0,
              'dedup_github': 0, 'empty_name': 0}
    for ep in episodes:
        if ep['episode_number'] is None:
            continue
        kept_links = []
        raw = ep['raw_links']
        i = 0
        while i < len(raw):
            l = raw[i]
            stats['total_raw'] += 1
            name, url, desc = l['name'].strip(), l['url'].strip(), l['description'].strip()
            if not name or name in ('.', '-'):
                stats['empty_name'] += 1
                i += 1
                continue
            if domain_blocked(url):
                stats['blocked_domain'] += 1
                i += 1
                continue
            if name_blocked(name):
                stats['blocked_phrase'] += 1
                i += 1
                continue
            if github_profile_page(url):
                stats['blocked_domain'] += 1
                i += 1
                continue
            # look ahead: is next item a "X on GitHub" follow-up for this same tool?
            if i + 1 < len(raw):
                nxt = raw[i + 1]
                m = GITHUB_FOLLOWUP_RE.match(nxt['name'].strip())
                if m and not nxt['description'].strip():
                    base = m.group(1).strip().lower()
                    cur_base = re.sub(r'^pick:\s*', '', name.strip().lower())
                    if base and (base == cur_base or base in cur_base or cur_base in base):
                        # merge: prefer existing url, else use github url
                        if not url:
                            url = nxt['url'].strip()
                        stats['dedup_github'] += 1
                        i += 2
                        kept_links.append({'name': re.sub(r'^pick:\s*', '', name, flags=re.I).strip(),
                                            'url': url, 'description': desc})
                        stats['kept'] += 1
                        continue
            kept_links.append({'name': re.sub(r'^pick:\s*', '', name, flags=re.I).strip(),
                                'url': url, 'description': desc})
            stats['kept'] += 1
            i += 1
        out.append({
            'show': ep['show'], 'episode_number': ep['episode_number'],
            'title': ep['title'], 'air_date': ep['air_date'], 'url': ep['url'],
            'tools': [
                {**t, 'category': infer_category(t['name'], t['description'], t['url'])}
                for t in kept_links
            ]
        })
    json.dump(out, open(out_path, 'w'), indent=1)
    print(out_path, stats)
    return out

if __name__ == '__main__':
    process('sh_parsed.json', 'sh_tools.json')
    process('lup_parsed.json', 'lup_tools.json')
