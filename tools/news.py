"""News feed tool — hacking, microcontrollers, Linux, and world/war headlines via RSS."""
import urllib.request
import xml.etree.ElementTree as ET
import threading
from datetime import datetime
from tools.base import Tool

# ── Feed definitions ──────────────────────────────────────────────────────────

FEEDS = {
    'hacking': [
        ('The Hacker News',   'https://feeds.feedburner.com/TheHackersNews'),
        ('BleepingComputer',  'https://www.bleepingcomputer.com/feed/'),
        ('Krebs on Security', 'https://krebsonsecurity.com/feed/'),
    ],
    'microcontroller': [
        ('Hackaday',    'https://hackaday.com/blog/feed/'),
        ('Hackster.io', 'https://www.hackster.io/news.atom'),
    ],
    'linux': [
        ('Phoronix', 'https://www.phoronix.com/rss.php'),
        ('LWN',      'https://lwn.net/headlines/rss'),
    ],
    'world': [
        ('BBC World',   'https://feeds.bbci.co.uk/news/world/rss.xml'),
        ('Al Jazeera',  'https://www.aljazeera.com/xml/rss/all.xml'),
    ],
    'space': [
        ('NASA',           'https://www.nasa.gov/feed/'),
        ('Space.com',      'https://www.space.com/feeds/all'),
        ('SpaceFlightNow', 'https://spaceflightnow.com/feed/'),
    ],
}

# War/conflict keywords — used to filter world news for war-specific queries
_WAR_KEYWORDS = [
    'war', 'attack', 'bomb', 'strike', 'missile', 'troops', 'ukraine', 'russia',
    'gaza', 'israel', 'conflict', 'military', 'killed', 'offensive', 'ceasefire',
    'nato', 'invasion', 'soldier', 'weapons', 'drone', 'airstrike', 'casualties',
]

_FETCH_TIMEOUT = 6  # seconds per feed


# ── RSS parsing ───────────────────────────────────────────────────────────────

def _fetch_feed(url: str, limit: int = 5) -> list[str]:
    """Fetch an RSS/Atom feed and return up to `limit` item titles."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AliceNews/1.0'})
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)

        titles = []
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        # RSS 2.0
        for item in root.iter('item'):
            t = item.findtext('title')
            if t:
                titles.append(t.strip())
            if len(titles) >= limit:
                break

        # Atom
        if not titles:
            for entry in root.iter('{http://www.w3.org/2005/Atom}entry'):
                t = entry.findtext('{http://www.w3.org/2005/Atom}title')
                if t:
                    titles.append(t.strip())
                if len(titles) >= limit:
                    break

        return titles
    except Exception:
        return []


def _fetch_category(category: str, limit: int = 3) -> list[tuple[str, str]]:
    """Fetch headlines for a category. Returns list of (source, title)."""
    results = []
    for source, url in FEEDS.get(category, []):
        titles = _fetch_feed(url, limit=limit)
        for t in titles:
            results.append((source, t))
        if results:
            break  # got something from first feed — don't need fallbacks
    return results[:limit]


def _fetch_all_parallel(categories: list[str], limit_each: int = 3) -> dict[str, list]:
    """Fetch all categories in parallel. Returns {category: [(source, title)]}."""
    out = {}
    threads = []

    def _worker(cat):
        out[cat] = _fetch_category(cat, limit=limit_each)

    for cat in categories:
        t = threading.Thread(target=_worker, args=(cat,), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=_FETCH_TIMEOUT + 1)

    return out


# ── Public helper for startup_greeting.py ────────────────────────────────────

def fetch_news_briefing(limit_each: int = 1) -> str:
    """Fetch one headline per category for the morning greeting.

    Returns a short string like:
      "Today in the news: [hacking] ... [microcontrollers] ... [linux] ... [world] ..."
    Returns empty string if all feeds fail.
    """
    data = _fetch_all_parallel(['hacking', 'microcontroller', 'linux', 'world', 'space'], limit_each)

    parts = []
    labels = {
        'hacking': 'Hacking',
        'microcontroller': 'Microcontrollers',
        'linux': 'Linux',
        'world': 'World',
        'space': 'Space',
    }
    for cat in ['hacking', 'microcontroller', 'linux', 'world', 'space']:
        headlines = data.get(cat, [])
        if headlines:
            _, title = headlines[0]
            parts.append(f"{labels[cat]}: {title}")

    if not parts:
        return ''
    return "Here's a quick news hit: " + '. '.join(parts) + '.'


# ── Tool class ────────────────────────────────────────────────────────────────

class NewsTool(Tool):
    name = "news"
    description = "Fetch latest headlines — hacking, microcontrollers, Linux, war/world, space/science"
    triggers = [
        "what's the news", "what is the news", "any news",
        "hacking news", "security news", "cyber news",
        "microcontroller news", "embedded news", "arduino news", "esp news", "hackaday",
        "linux news", "phoronix",
        "world news", "war news", "war updates", "what's happening in the world",
        "space news", "nasa news", "rocket news", "astronomy news", "cosmos news",
        "news briefing", "news update", "latest news", "give me the news",
        "what happened today", "today's news",
    ]

    def execute(self, query: str) -> str:
        tl = query.lower()

        # Determine which categories to fetch
        want_hacking = any(p in tl for p in ['hack', 'security', 'cyber', 'breach', 'exploit'])
        want_mcu = any(p in tl for p in ['microcontroller', 'embedded', 'arduino', 'esp', 'hackaday', 'raspberry'])
        want_linux = any(p in tl for p in ['linux', 'phoronix', 'kernel'])
        want_world = any(p in tl for p in ['world', 'war', 'current event', 'what happened', 'what is happening'])
        want_space = any(p in tl for p in ['space', 'nasa', 'rocket', 'satellite', 'astronomy', 'cosmos', 'planet', 'mars', 'moon', 'orbit', 'spacecraft', 'iss', 'spacex', 'launch'])

        # Default: all categories
        if not any([want_hacking, want_mcu, want_linux, want_world, want_space]):
            want_hacking = want_mcu = want_linux = want_world = want_space = True

        cats = []
        if want_hacking:      cats.append('hacking')
        if want_mcu:          cats.append('microcontroller')
        if want_linux:        cats.append('linux')
        if want_world:        cats.append('world')
        if want_space:        cats.append('space')

        data = _fetch_all_parallel(cats, limit_each=3)

        sections = []
        labels = {
            'hacking': 'Hacking & Security',
            'microcontroller': 'Microcontrollers & Makers',
            'linux': 'Linux',
            'world': 'World & War',
            'space': 'Space & Science',
        }

        for cat in cats:
            headlines = data.get(cat, [])
            if not headlines:
                sections.append(f"{labels[cat]}: nothing fetched, feeds might be down.")
                continue

            # For war queries, filter headlines by war keywords first
            if cat == 'world' and want_world and 'war' in tl:
                war_headlines = [(s, t) for s, t in headlines
                                 if any(k in t.lower() for k in _WAR_KEYWORDS)]
                if war_headlines:
                    headlines = war_headlines

            lines = [f"{labels[cat]}:"]
            for source, title in headlines[:3]:
                lines.append(f"  • {title}  ({source})")
            sections.append('\n'.join(lines))

        if not sections:
            return "Couldn't fetch any news right now — feeds might be down."

        return '\n\n'.join(sections)
