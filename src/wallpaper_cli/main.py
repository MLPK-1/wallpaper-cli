"""wallpaper — modern wallpaper manager CLI"""

__version__ = "0.1.0"

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

# ── Paths ─────────────────────────────────────────────────────────────────────
HOME = Path.home()
CONFIG_FILE  = HOME / ".config" / "wallpaper" / "config.json"
PRESETS_FILE = HOME / ".config" / "wallpaper" / "presets.json"
HISTORY_FILE = HOME / ".local" / "share" / "wallpaper" / "history.json"
WALLPAPER_DIR = HOME / "Pictures" / "wallpapers"
THUMB_DIR     = WALLPAPER_DIR / "thumbs"
CURRENT_PATH  = WALLPAPER_DIR / "current.jpg"
GDM_SCRIPT    = HOME / ".config" / "wallpaper" / "update_gdm_wallpaper.sh"
DA_TOKEN_FILE = HOME / ".config" / "wallpaper" / "deviantart_token.json"

# ── Sources ───────────────────────────────────────────────────────────────────
SOURCES = {
    "unsplash":    {"icon": "🌄", "description": "High-res photography (Unsplash)"},
    "wallhaven":   {"icon": "🎨", "description": "Curated art & anime (Wallhaven)"},
    "pexels":      {"icon": "📸", "description": "Free stock photography (Pexels)"},
    "pixabay":     {"icon": "🖼",  "description": "Free images & illustrations (Pixabay)"},
    "reddit":      {"icon": "🤖", "description": "Community curated (Reddit — auto subreddit)"},
    "deviantart":  {"icon": "🎭", "description": "Fan art & illustrations (DeviantArt)"},
    "nasa":        {"icon": "🚀", "description": "NASA Astronomy Picture of the Day"},
    "bing":        {"icon": "🌍", "description": "Bing daily world photography (no key needed)"},
}

# ── Styles ────────────────────────────────────────────────────────────────────
STYLES = {
    "realistic":    {"source": "unsplash",  "icon": "📷", "description": "Real-world photography"},
    "anime":        {"source": "wallhaven", "icon": "🎌", "description": "Anime & illustrated art",     "categories": "010"},
    "nature":       {"source": "unsplash",  "icon": "🌿", "description": "Natural landscapes",          "extra": "nature"},
    "abstract":     {"source": "unsplash",  "icon": "🎨", "description": "Abstract & artistic",         "extra": "abstract art"},
    "cyberpunk":    {"source": "wallhaven", "icon": "🌆", "description": "Cyberpunk & neon aesthetics", "categories": "111", "extra": "cyberpunk"},
    "minimal":      {"source": "unsplash",  "icon": "◻",  "description": "Clean minimalism",            "extra": "minimal clean"},
    "space":        {"source": "unsplash",  "icon": "🚀", "description": "Space & cosmos",              "extra": "space cosmos galaxy"},
    "city":         {"source": "unsplash",  "icon": "🏙",  "description": "Urban cityscapes",            "extra": "cityscape urban"},
    "architecture": {"source": "unsplash",  "icon": "🏛",  "description": "Architecture",                "extra": "architecture"},
    "dark":         {"source": "unsplash",  "icon": "🌑", "description": "Dark & moody tones",          "extra": "dark moody"},
    "custom":       {"source": "auto",      "icon": "🔍", "description": "Freeform keywords — query only"},
}

# ── Reddit subreddit maps ─────────────────────────────────────────────────────
# Ordered by quality / relevance
REDDIT_STYLE_SUBS = {
    "realistic":    ["wallpapers", "EarthPorn", "wqhd_wallpapers", "ITookAPicture"],
    "anime":        ["AnimeWallpaper", "Animewallpaper", "anime_wallpaper"],
    "nature":       ["EarthPorn", "naturewallpaper", "NatureIsFuckingLit", "SkyPorn"],
    "abstract":     ["AbstractWallpapers", "generative", "Art"],
    "cyberpunk":    ["Cyberpunk", "synthwave", "vaporwaveaesthetics", "retrofuturism"],
    "minimal":      ["MinimalWallpaper", "minimalism"],
    "space":        ["spaceporn", "astrophotography", "Astronomy"],
    "city":         ["CityPorn", "urbanphotography", "LiminalSpace"],
    "architecture": ["ArchitecturePorn", "brutalism", "architecture"],
    "dark":         ["Amoledbackgrounds", "darkwallpaper", "LiminalSpace"],
    "custom":       ["wallpapers", "wqhd_wallpapers", "ImaginaryWorlds", "gaming"],
}

REDDIT_QUERY_SUBS = {
    "mountain":  ["EarthPorn", "hiking"],
    "ocean":     ["OceanPorn", "BeachPorn", "EarthPorn"],
    "forest":    ["EarthPorn", "forests"],
    "city":      ["CityPorn", "urbanphotography"],
    "space":     ["spaceporn", "astrophotography"],
    "anime":     ["AnimeWallpaper", "animewallpaper"],
    "dark":      ["Amoledbackgrounds"],
    "abstract":  ["AbstractWallpapers"],
    "minimal":   ["MinimalWallpaper"],
    "sunset":    ["SkyPorn", "EarthPorn"],
    "snow":      ["EarthPorn", "winterporn"],
    "night":     ["Amoledbackgrounds", "CityPorn"],
    "neon":      ["Cyberpunk", "synthwave"],
    "cyber":     ["Cyberpunk", "retrofuturism"],
    "fantasy":   ["ImaginaryLandscapes", "ImaginaryWorlds"],
    "landscape": ["EarthPorn", "wqhd_wallpapers"],
    "rain":      ["EarthPorn", "mildlyinteresting"],
    "sky":       ["SkyPorn", "EarthPorn"],
    "lake":      ["EarthPorn", "SkyPorn"],
    "desert":    ["EarthPorn", "DesertPorn"],
    "lofi":      ["LiminalSpace", "analog", "Amoledbackgrounds"],
    "moody":     ["Amoledbackgrounds", "LiminalSpace", "darkwallpaper"],
}

# ── Color maps for each source ────────────────────────────────────────────────
COLORS = {
    # name: (unsplash, wallhaven_hex, pexels, pixabay)
    "red":             ("red",             "cc0000",        "red",        "red"),
    "orange":          ("orange",          "ff6600",        "orange",     "orange"),
    "yellow":          ("yellow",          "ffff00",        "yellow",     "yellow"),
    "green":           ("green",           "669900",        "green",      "green"),
    "teal":            ("teal",            "66cccc",        "turquoise",  "turquoise"),
    "blue":            ("blue",            "0066cc",        "blue",       "blue"),
    "purple":          ("purple",          "663399",        "violet",     "lilac"),
    "magenta":         ("magenta",         "ea4c88",        "pink",       "pink"),
    "black":           ("black",           "000000",        "black",      "black"),
    "white":           ("white",           "ffffff",        "white",      "white"),
    "black_and_white": ("black_and_white", "000000,cccccc", "gray",       "grayscale"),
}

QUERY_SUGGESTIONS = [
    "mountain landscape", "rainy city", "forest", "ocean waves",
    "cherry blossom", "neon city", "desert dunes", "snowy peaks",
    "sunset horizon", "misty lake",
]

DEFAULT_CONFIG = {
    "source": "auto",
    "query": "mountain",
    "style": "realistic",
    "color": None,
    "interval_hours": 3,
    "resolution_width": 3840,
    "unsplash_key": "",
    "pexels_key": "",
    "pixabay_key": "",
    "deviantart_client_id": "",
    "deviantart_client_secret": "",
    "nasa_key": "DEMO_KEY",
}

FEATURED_PRESETS = [
    {
        "key": "nasa-daily",
        "icon": "🚀",
        "name": "NASA Photo of the Day",
        "description": "Real NASA astronomy imagery, changes every 24h",
        "style": "space", "source": "nasa", "query": "space", "color": None, "interval_hours": 24,
    },
    {
        "key": "bing-world",
        "icon": "🌍",
        "name": "Bing World Scenery",
        "description": "Microsoft's curated world photography, refreshes every 3h",
        "style": "realistic", "source": "bing", "query": "nature", "color": None, "interval_hours": 3,
    },
    {
        "key": "painted-landscapes",
        "icon": "🌸",
        "name": "Painted Landscapes",
        "description": "Dreamy hand-painted fantasy landscapes and scenery",
        "style": "custom", "source": "auto", "query": "painted fantasy landscape scenery", "color": None, "interval_hours": 3,
    },
    {
        "key": "cyberpunk-cities",
        "icon": "🌆",
        "name": "Cyberpunk Cities",
        "description": "Neon-drenched futuristic urban cityscapes",
        "style": "cyberpunk", "source": "wallhaven", "query": "cyberpunk city neon", "color": None, "interval_hours": 3,
    },
    {
        "key": "pixel-art",
        "icon": "🎮",
        "name": "Pixel Art Landscapes",
        "description": "Retro pixel art scenes and environments",
        "style": "custom", "source": "auto", "query": "pixel art landscape", "color": None, "interval_hours": 3,
    },
    {
        "key": "anime-art",
        "icon": "🎌",
        "name": "Anime Illustrations",
        "description": "High-quality curated anime art from Wallhaven",
        "style": "anime", "source": "wallhaven", "query": "anime", "color": None, "interval_hours": 3,
    },
    {
        "key": "deep-space",
        "icon": "✨",
        "name": "Deep Space",
        "description": "Galaxies, nebulae and cosmic wonders",
        "style": "space", "source": "auto", "query": "galaxy nebula cosmos", "color": None, "interval_hours": 6,
    },
    {
        "key": "lofi-aesthetic",
        "icon": "🎵",
        "name": "Lo-Fi Aesthetic",
        "description": "Chill moody lo-fi art and dark photography",
        "style": "dark", "source": "auto", "query": "lofi aesthetic chill", "color": None, "interval_hours": 3,
    },
    {
        "key": "minimal-dark",
        "icon": "◻",
        "name": "Minimal Dark",
        "description": "Clean dark minimalist wallpapers",
        "style": "minimal", "source": "wallhaven", "query": "minimal dark", "color": "black", "interval_hours": 6,
    },
    {
        "key": "fantasy-worlds",
        "icon": "🐉",
        "name": "Fantasy Worlds",
        "description": "Epic fantasy landscapes and illustrations",
        "style": "custom", "source": "auto", "query": "fantasy landscape epic", "color": None, "interval_hours": 3,
    },
]

console = Console()


# ── Config & presets ──────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = {**DEFAULT_CONFIG, **json.load(f)}
    else:
        cfg = DEFAULT_CONFIG.copy()
    # Sanitize color: must be a known key or None
    if cfg.get("color") not in (list(COLORS.keys()) + [None]):
        cfg["color"] = None
    return cfg


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def load_presets():
    if PRESETS_FILE.exists():
        with open(PRESETS_FILE) as f:
            return json.load(f)
    return {}


def save_presets(presets):
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=2)


def _auto_sources(cfg):
    style = cfg.get("style", "realistic")
    # Stock photo platforms return unrelated results for fandom/gaming queries.
    # Custom style is designed for specific topics — only use art/community sources.
    if style == "custom":
        sources = ["wallhaven", "reddit"]
        if cfg.get("deviantart_client_id") and cfg.get("deviantart_client_secret"):
            sources.append("deviantart")
        return sources

    sources = ["wallhaven", "reddit", "bing"]
    if cfg.get("unsplash_key"):
        sources.append("unsplash")
    if cfg.get("pexels_key"):
        sources.append("pexels")
    if cfg.get("pixabay_key"):
        sources.append("pixabay")
    if cfg.get("deviantart_client_id") and cfg.get("deviantart_client_secret"):
        sources.append("deviantart")
    # NASA: great for space/realistic styles
    if style in ("space", "realistic"):
        sources.append("nasa")
    return sources


def resolve_source(cfg):
    """Return the actual source to use; 'auto' picks randomly from all configured sources."""
    src = cfg.get("source", "auto")
    if src != "auto":
        return src
    return random.choice(_auto_sources(cfg))


# ── History ───────────────────────────────────────────────────────────────────
def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def append_history(entry):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history = load_history()
    history.append(entry)
    if len(history) > 100:
        history = history[-100:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ── Helpers ───────────────────────────────────────────────────────────────────
def time_ago(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
        s = (datetime.now() - dt).total_seconds()
        if s < 60:    return "just now"
        if s < 3600:  return f"{int(s / 60)}m ago"
        if s < 86400: return f"{int(s / 3600)}h ago"
        return f"{int(s / 86400)}d ago"
    except Exception:
        return "—"


def update_cron(hours):
    if not shutil.which("crontab"):
        console.print(
            "  [yellow]⚠[/yellow]  [bold]crontab[/bold] not found — auto-rotation not set up.\n"
            "  Install [bold]cron[/bold] ([dim]sudo apt install cron[/dim]) or add a systemd timer manually."
        )
        return False
    wallpaper_bin = shutil.which("wallpaper") or str(HOME / ".local" / "bin" / "wallpaper")
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        new_lines = []
        replaced = False
        for line in lines:
            if "update_wallpaper.sh" in line or ("wallpaper" in line and "_fetch" in line):
                new_lines.append(f"0 */{hours} * * * {wallpaper_bin} _fetch")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f"0 */{hours} * * * {wallpaper_bin} _fetch")
        subprocess.run(["crontab", "-"], input="\n".join(new_lines) + "\n", text=True, check=True)
        return True
    except Exception as e:
        console.print(f"[red]Failed to update cron: {e}[/red]")
        return False


def require_questionary():
    import questionary
    return questionary


# ── HTTP helper ───────────────────────────────────────────────────────────────
def _get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "WallpaperCLI/2.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ── Fetchers ──────────────────────────────────────────────────────────────────
def fetch_unsplash(cfg):
    style_info = STYLES.get(cfg.get("style", "realistic"), {})
    full_query = f"{cfg['query']} {style_info.get('extra', '')}".strip()
    params = {"query": full_query, "orientation": "landscape", "client_id": cfg["unsplash_key"]}
    if cfg.get("color") and cfg["color"] in COLORS:
        params["color"] = COLORS[cfg["color"]][0]

    data = _get("https://api.unsplash.com/photos/random?" + urllib.parse.urlencode(params))
    image_url = data["urls"]["full"] + f"&w={cfg['resolution_width']}"

    try:
        urllib.request.urlopen(
            urllib.request.Request(
                data["links"]["download_location"],
                headers={"Authorization": f"Client-ID {cfg['unsplash_key']}", "User-Agent": "WallpaperCLI/2.0"},
            ), timeout=5,
        )
    except Exception:
        pass

    loc = data.get("location") or {}
    location = loc.get("name") or ", ".join(filter(None, [loc.get("city"), loc.get("country")])) or None

    return {
        "image_url": image_url,
        "photo_url": data["links"]["html"],
        "photographer": data["user"]["name"],
        "description": data.get("description") or data.get("alt_description") or "Untitled",
        "location": location,
        "source": "unsplash",
    }


def fetch_wallhaven(cfg):
    style_info = STYLES.get(cfg.get("style", "realistic"), {})
    extra = style_info.get("extra", "")
    full_query = f"{extra} {cfg['query']}".strip()
    categories = style_info.get("categories", "111")

    params = {
        "q": full_query, "purity": "100", "categories": categories,
        "sorting": "random", "atleast": "2560x1440", "ratios": "16x9",
    }
    if cfg.get("color") and cfg["color"] in COLORS:
        params["colors"] = COLORS[cfg["color"]][1]

    data = _get("https://wallhaven.cc/api/v1/search?" + urllib.parse.urlencode(params))
    results = data.get("data", [])
    if not results:
        raise ValueError(f"No Wallhaven results for: {full_query!r}")

    chosen = random.choice(results)
    return {
        "image_url": chosen["path"],
        "photo_url": chosen["url"],
        "photographer": None,
        "description": f"{chosen.get('category', 'Wallpaper').title()}  {chosen.get('resolution', '')}".strip(),
        "location": None,
        "source": "wallhaven",
    }


def fetch_pexels(cfg):
    style_info = STYLES.get(cfg.get("style", "realistic"), {})
    full_query = f"{cfg['query']} {style_info.get('extra', '')}".strip()
    params = {"query": full_query, "orientation": "landscape", "per_page": 80, "size": "large"}
    if cfg.get("color") and cfg["color"] in COLORS:
        params["color"] = COLORS[cfg["color"]][2]

    data = _get(
        "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(params),
        headers={"Authorization": cfg["pexels_key"]},
    )
    photos = data.get("photos", [])
    if not photos:
        raise ValueError(f"No Pexels results for: {full_query!r}")

    chosen = random.choice(photos)
    return {
        "image_url": chosen["src"]["original"],
        "photo_url": chosen["url"],
        "photographer": chosen.get("photographer"),
        "description": chosen.get("alt") or "Untitled",
        "location": None,
        "source": "pexels",
    }


def fetch_pixabay(cfg):
    style_info = STYLES.get(cfg.get("style", "realistic"), {})
    full_query = f"{cfg['query']} {style_info.get('extra', '')}".strip()
    params = {
        "key": cfg["pixabay_key"],
        "q": full_query,
        "image_type": "photo",
        "orientation": "horizontal",
        "min_width": 1920,
        "min_height": 1080,
        "per_page": 80,
        "order": "popular",
        "safesearch": "true",
    }
    if cfg.get("color") and cfg["color"] in COLORS:
        params["color"] = COLORS[cfg["color"]][3]

    data = _get("https://pixabay.com/api/?" + urllib.parse.urlencode(params))
    hits = data.get("hits", [])
    if not hits:
        raise ValueError(f"No Pixabay results for: {full_query!r}")

    chosen = random.choice(hits)
    return {
        "image_url": chosen.get("largeImageURL") or chosen["webformatURL"],
        "photo_url": chosen["pageURL"],
        "photographer": chosen.get("user"),
        "description": chosen.get("tags", "Untitled").split(",")[0].strip().title(),
        "location": None,
        "source": "pixabay",
    }


def fetch_reddit(cfg, allow_fallback=False):
    style = cfg.get("style", "realistic")
    query = cfg.get("query", "").strip().lower()
    color = cfg.get("color")
    if color and color != "black_and_white":
        query = f"{query} {color}".strip()
    elif color == "black_and_white":
        query = f"{query} black and white".strip()

    # Build subreddit pool: query keyword hints first, then style defaults
    candidates = []
    for keyword, subs in REDDIT_QUERY_SUBS.items():
        if keyword in query:
            candidates.extend(subs)
    candidates.extend(REDDIT_STYLE_SUBS.get(style, ["wallpapers"]))
    seen = set()
    subreddits = [s for s in candidates if not (s in seen or seen.add(s))]

    reddit_headers = {"User-Agent": "WallpaperCLI/2.0 (wallpaper manager)"}

    def _filter(posts):
        images = []
        for post in posts:
            p = post["data"]
            if p.get("is_video") or p.get("is_self"):
                continue
            url = p.get("url", "")
            if not url.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            preview = (p.get("preview") or {}).get("images", [{}])
            src = (preview[0].get("source") or {}) if preview else {}
            w, h = src.get("width", 0), src.get("height", 0)
            if w < 1920 or h < 1000:
                continue
            ratio = w / h if h else 0
            if ratio < 1.5 or ratio > 2.5:
                continue
            images.append({
                "url": url,
                "title": p.get("title", "Untitled"),
                "author": p.get("author", "unknown"),
                "permalink": f"https://reddit.com{p.get('permalink', '')}",
                "subreddit": p.get("subreddit", ""),
                "score": p.get("score", 0),
            })
        return images

    def _pick(images):
        images.sort(key=lambda x: x["score"], reverse=True)
        chosen = random.choice(images[:20])
        return {
            "image_url": chosen["url"],
            "photo_url": chosen["permalink"],
            "photographer": f"u/{chosen['author']}",
            "description": chosen["title"][:80],
            "location": f"r/{chosen['subreddit']}",
            "source": "reddit",
        }

    # ── Primary: search by query across subreddit pool ────────────────────────
    multi = "+".join(subreddits[:6])
    for period in [random.choice(["month", "year"]), "all"]:
        try:
            params = urllib.parse.urlencode({
                "q": query, "sort": "top", "t": period,
                "restrict_sr": "on", "limit": 100,
            })
            data = _get(
                f"https://www.reddit.com/r/{multi}/search.json?{params}",
                headers=reddit_headers,
            )
            images = _filter(data["data"]["children"])
            if images:
                return _pick(images)
        except Exception:
            continue

    # ── Fallback: top posts (only when Reddit is the explicit sole source) ─────
    if allow_fallback:
        pool = subreddits[:4]
        random.shuffle(pool)
        for subreddit in pool:
            try:
                period = random.choice(["week", "month"])
                data = _get(
                    f"https://www.reddit.com/r/{subreddit}/top.json?limit=100&t={period}",
                    headers=reddit_headers,
                )
                images = _filter(data["data"]["children"])
                if images:
                    return _pick(images)
            except Exception:
                continue

    raise ValueError(f"No Reddit wallpapers found for: {query!r}")


def fetch_deviantart(cfg):
    client_id = cfg.get("deviantart_client_id", "")
    client_secret = cfg.get("deviantart_client_secret", "")
    if not client_id or not client_secret:
        raise ValueError("DeviantArt client_id / client_secret not configured")

    # ── Token (cached, refreshed when expired) ────────────────────────────────
    token = None
    if DA_TOKEN_FILE.exists():
        with open(DA_TOKEN_FILE) as f:
            cached = json.load(f)
        if datetime.fromisoformat(cached["expires_at"]) > datetime.now():
            token = cached["access_token"]

    if not token:
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode()
        req = urllib.request.Request(
            "https://www.deviantart.com/oauth2/token",
            data=body,
            headers={
                "User-Agent": "WallpaperCLI/2.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
        token = result["access_token"]
        expires_at = (datetime.now() + timedelta(seconds=result.get("expires_in", 3600) - 60)).isoformat()
        DA_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DA_TOKEN_FILE, "w") as f:
            json.dump({"access_token": token, "expires_at": expires_at}, f)

    # ── Search ────────────────────────────────────────────────────────────────
    query = cfg.get("query", "wallpaper")
    style = cfg.get("style", "realistic")
    color = cfg.get("color")
    style_extra = STYLES.get(style, {}).get("extra", "")
    base_tag = f"{style_extra} {query}".strip() if style != "custom" else query
    # Append color hint to help tag resolution find color-themed results
    color_hint = color.replace("_", " ") if color else ""
    tag = f"{base_tag} {color_hint}".strip() if color_hint else base_tag
    auth_headers = {"Authorization": f"Bearer {token}"}

    def _deviations_for_tag(t, offset=0):
        params = urllib.parse.urlencode({
            "tag": t, "limit": 50, "offset": offset, "mature_content": "false",
        })
        return _get(f"https://www.deviantart.com/api/v1/oauth2/browse/tags?{params}", headers=auth_headers)

    def _resolve_tags(q):
        """Use tags/search autocomplete to find real DA tag names for a query."""
        params = urllib.parse.urlencode({"tag_name": q, "limit": 5})
        data = _get(f"https://www.deviantart.com/api/v1/oauth2/browse/tags/search?{params}", headers=auth_headers)
        return [r["tag_name"] for r in data.get("results", [])]

    def _search_home():
        params = urllib.parse.urlencode({"limit": 50, "mature_content": "false"})
        return _get(f"https://www.deviantart.com/api/v1/oauth2/browse/home?{params}", headers=auth_headers)

    def _good(results):
        out = []
        for d in results:
            if d.get("is_mature"):
                continue
            c = d.get("content") or {}
            w, h = c.get("width", 0), c.get("height", 0)
            if not c.get("src") or w < 1280 or h < 720:
                continue
            # Must be landscape with a wallpaper-like aspect ratio (16:10 to 21:9)
            ratio = w / h
            if ratio < 1.5 or ratio > 2.5:
                continue
            out.append(d)
        return out

    # Step 1: resolve query to real DA tags
    resolved_tags = _resolve_tags(tag)

    # Step 2: collect deviations from each resolved tag
    good = []
    for t in resolved_tags[:3]:
        data = _deviations_for_tag(t)
        good += _good(data.get("results", []))

    # Fallback: home feed
    if not good:
        data = _search_home()
        good = _good(data.get("results", []))

    if not good:
        raise ValueError(f"No DeviantArt wallpapers found for: {query!r}")

    chosen = random.choice(good)
    content = chosen["content"]
    author = (chosen.get("author") or {}).get("username", "unknown")

    return {
        "image_url": content["src"],
        "photo_url": chosen.get("url", ""),
        "photographer": author,
        "description": chosen.get("title", "Untitled"),
        "location": None,
        "source": "deviantart",
    }


def fetch_nasa(cfg):
    api_key = cfg.get("nasa_key") or "DEMO_KEY"
    params = urllib.parse.urlencode({"api_key": api_key, "hd": "true"})
    data = _get(f"https://api.nasa.gov/planetary/apod?{params}")
    if data.get("media_type") != "image":
        raise ValueError("Today's NASA APOD is not an image (it's a video)")
    image_url = data.get("hdurl") or data.get("url")
    if not image_url:
        raise ValueError("No image URL in NASA APOD response")
    date_slug = (data.get("date") or "").replace("-", "")[2:]
    return {
        "image_url": image_url,
        "photo_url": f"https://apod.nasa.gov/apod/ap{date_slug}.html",
        "photographer": (data.get("copyright") or "NASA").strip(),
        "description": data.get("title", "NASA APOD"),
        "location": None,
        "source": "nasa",
    }


def fetch_bing(cfg):
    data = _get("https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=en-US")
    images = data.get("images", [])
    if not images:
        raise ValueError("No Bing wallpapers returned")
    chosen = random.choice(images)
    urlbase = chosen.get("urlbase", "")
    # Validate urlbase is a plain path so it cannot redirect to a different host
    if not urlbase.startswith("/") or "//" in urlbase or "@" in urlbase:
        raise ValueError(f"Bing returned unexpected urlbase: {urlbase!r}")
    url_field = chosen.get("url", "")
    return {
        "image_url": f"https://www.bing.com{urlbase}_UHD.jpg",
        "photo_url": f"https://www.bing.com{url_field}",
        "photographer": chosen.get("copyright", "Microsoft Bing"),
        "description": chosen.get("title", "Bing Daily Wallpaper"),
        "location": None,
        "source": "bing",
    }


# ── Image handling ────────────────────────────────────────────────────────────
def download_image(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "WallpaperCLI/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        content_type = r.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise ValueError(f"Server returned non-image content-type: {content_type!r}")
        # Write to a temp file then atomically replace to avoid a partial file
        # being used as wallpaper if the download is interrupted mid-way.
        tmp = Path(str(dest) + ".tmp")
        try:
            with open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            os.replace(tmp, dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise


def make_thumb(src, dst):
    try:
        subprocess.run(
            ["convert", str(src), "-resize", "128x128^", "-gravity", "Center", "-extent", "128x128", str(dst)],
            check=True, capture_output=True,
        )
        return True
    except Exception:
        return False


def apply_wallpaper(path):
    if not shutil.which("gsettings"):
        print(
            "wallpaper: gsettings not found — is GNOME installed? "
            "Wallpaper was downloaded but not applied.",
            file=sys.stderr,
        )
        return
    uri = f"file://{path}"
    for schema, key in [
        ("org.gnome.desktop.background", "picture-uri"),
        ("org.gnome.desktop.background", "picture-uri-dark"),
        ("org.gnome.desktop.screensaver", "picture-uri"),
    ]:
        subprocess.run(["gsettings", "set", schema, key, uri], capture_output=True)


def notify(title, body, icon=None):
    os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
    cmd = ["notify-send", "--transient", "-t", "5000", title, body]
    if icon and Path(icon).exists():
        cmd += ["-i", str(icon)]
    subprocess.run(cmd, capture_output=True)


# ── Core fetch ────────────────────────────────────────────────────────────────
FETCHERS = {
    "unsplash":   fetch_unsplash,
    "wallhaven":  fetch_wallhaven,
    "pexels":     fetch_pexels,
    "pixabay":    fetch_pixabay,
    "reddit":     fetch_reddit,
    "deviantart": fetch_deviantart,
    "nasa":       fetch_nasa,
    "bing":       fetch_bing,
}


def do_fetch(silent=False):
    cfg = load_config()
    is_auto = cfg.get("source", "auto") == "auto"
    style = cfg.get("style", "realistic")

    _err_console = Console(stderr=True) if silent else console

    def _log(msg):
        _err_console.print(f"  [red]✗[/red] {msg}")

    info = None

    if is_auto:
        # Try sources in random order; skip any that fail to find topic-matching content
        sources = _auto_sources(cfg)
        random.shuffle(sources)
        for source in sources:
            fetcher = FETCHERS.get(source)
            if not fetcher:
                continue
            try:
                info = fetcher(cfg)
                break
            except Exception:
                continue
        if info is None:
            _log("No sources returned a matching wallpaper for this query")
            return None
    else:
        source = resolve_source(cfg)
        fetcher = FETCHERS.get(source)
        if not fetcher:
            _log(f"Unknown source: {source}")
            return None
        try:
            # Reddit as sole source: allow fallback to top posts
            info = fetch_reddit(cfg, allow_fallback=True) if source == "reddit" else fetcher(cfg)
        except Exception as e:
            _log(f"Fetch failed ({source}): {e}")
            return None

    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    try:
        download_image(info["image_url"], CURRENT_PATH)
    except Exception as e:
        _log(f"Download failed: {e}")
        return None

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    thumb_path = THUMB_DIR / f"{ts}.jpg"
    make_thumb(CURRENT_PATH, thumb_path)
    apply_wallpaper(CURRENT_PATH)

    if GDM_SCRIPT.exists():
        subprocess.run(["sudo", str(GDM_SCRIPT), str(CURRENT_PATH)], capture_output=True)

    entry = {
        "date": datetime.now().isoformat(),
        "query": cfg["query"], "style": style, "source": source,
        "photographer": info.get("photographer"),
        "description": info.get("description", "Untitled"),
        "location": info.get("location"),
        "photo_url": info.get("photo_url"),
        "path": str(CURRENT_PATH),
        "thumb_path": str(thumb_path) if thumb_path.exists() else None,
    }
    append_history(entry)

    desc = entry["description"]
    photog = entry.get("photographer")
    loc = entry.get("location")
    notif_body = f"by {photog}" if photog else ""
    if loc:
        notif_body = f"{notif_body}  {loc}".strip()
    if not notif_body:
        notif_body = f"{style} · {source}"
    notify("Wallpaper Updated", f"{desc}\n{notif_body}", entry.get("thumb_path"))

    return entry


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_status(_args=None):
    cfg = load_config()
    history = load_history()
    icon = STYLES.get(cfg.get("style", "realistic"), {}).get("icon", "🖼")
    source = resolve_source(cfg)
    source_icon = SOURCES.get(source, {}).get("icon", "")

    if history:
        latest = history[-1]
        desc = latest.get("description") or "Untitled"
        photog = latest.get("photographer")
        location = latest.get("location") or ""
        fetched = time_ago(latest.get("date"))
        parts = []
        if photog:   parts.append(f"[dim]by[/dim] {photog}")
        if location: parts.append(location)
        body = "\n".join(filter(None, [
            f'[bold]"{desc}"[/bold]',
            "  [dim]·[/dim]  ".join(parts) or None,
            f"[dim]Fetched:[/dim] {fetched}  [dim]·[/dim]  [dim]Query:[/dim] [cyan]{latest.get('query', cfg['query'])}[/cyan]  [dim]via[/dim] {latest.get('source', source)}",
        ]))
    else:
        body = "[dim]No history yet — run [bold]wallpaper now[/bold] to fetch one[/dim]"

    interval = cfg.get("interval_hours", 3)
    next_str = "—"
    if history:
        try:
            remaining = (datetime.fromisoformat(history[-1]["date"]) + timedelta(hours=interval)) - datetime.now()
            if remaining.total_seconds() > 0:
                h, m = int(remaining.total_seconds() // 3600), int((remaining.total_seconds() % 3600) // 60)
                next_str = f"{h}h {m}m" if h else f"{m}m"
            else:
                next_str = "soon"
        except Exception:
            pass

    src_display = f"auto → {source}" if cfg.get("source") == "auto" else source

    console.print()
    console.print(Panel(
        body,
        title=f"{icon}  Current Wallpaper",
        subtitle=f"[dim]style: {cfg.get('style')}  ·  source: {src_display}  ·  every {interval}h  ·  next ~{next_str}[/dim]",
        border_style="bright_blue", padding=(1, 2),
    ))
    color_part = f"  [dim]color:[/dim] [yellow]{cfg['color']}[/yellow]" if cfg.get("color") else ""
    console.print(
        f"  [dim]query:[/dim] [cyan]{cfg['query']}[/cyan]"
        f"  [dim]style:[/dim] [magenta]{cfg.get('style')}[/magenta]"
        f"  [dim]source:[/dim] {source_icon} [green]{src_display}[/green]"
        f"{color_part}  [dim]interval:[/dim] [green]{interval}h[/green]"
    )
    console.print()
    console.print("  [dim]wallpaper [bold]now[/bold] · [bold]history[/bold] · [bold]presets[/bold] · [bold]new[/bold] · [bold]set[/bold][/dim]")
    console.print()


def cmd_history(args=None):
    history = load_history()
    if not history:
        console.print(Panel("[dim]No history yet.[/dim]", border_style="dim"))
        return

    limit = getattr(args, "limit", 20)
    entries = list(reversed(history))[:limit]

    table = Table(box=box.ROUNDED, border_style="bright_blue", header_style="bold cyan")
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("When", width=10)
    table.add_column("Description", width=28)
    table.add_column("Credit", width=18)
    table.add_column("Location / Sub", width=16)
    table.add_column("Query", width=14)
    table.add_column("Style", width=10)
    table.add_column("Source", width=10)

    for i, e in enumerate(entries, 1):
        loc = e.get("location") or "—"
        style = e.get("style", "realistic")
        source = e.get("source", "—")
        src_icon = SOURCES.get(source, {}).get("icon", "")
        table.add_row(
            str(i), time_ago(e.get("date", "")),
            (e.get("description") or "—")[:27],
            (e.get("photographer") or "—")[:17],
            loc[:15] + "…" if len(loc) > 15 else loc,
            e.get("query", "—"),
            f"{STYLES.get(style, {}).get('icon', '')} {style}",
            f"{src_icon} {source}",
        )

    console.print()
    console.print(table)
    console.print(f"\n  [dim]Showing {len(entries)} of {len(history)} total[/dim]\n")


def cmd_now(_args=None):
    console.print()
    with console.status("[cyan]Fetching new wallpaper…[/cyan]"):
        entry = do_fetch(silent=False)
    if entry:
        desc = entry.get("description") or "New wallpaper"
        photog = entry.get("photographer")
        loc = entry.get("location")
        src = entry.get("source", "")
        console.print(f"  [green]✓[/green]  [bold]{desc}[/bold]")
        if photog:
            console.print(f"     [dim]by[/dim] {photog}" + (f"  [dim]via[/dim] {loc}" if loc else ""))
        console.print(f"     [dim]source:[/dim] {SOURCES.get(src, {}).get('icon', '')} {src}")
    console.print()


def cmd_set(args):
    cfg = load_config()
    setting = getattr(args, "setting", None)
    value = getattr(args, "value", [])

    if not setting:
        console.print()
        console.print("  wallpaper set [bold cyan]query[/bold cyan]             [dim]\"your topic\"[/dim]")
        console.print("  wallpaper set [bold cyan]style[/bold cyan]             [dim]anime | realistic | cyberpunk | custom …[/dim]")
        console.print("  wallpaper set [bold cyan]source[/bold cyan]            [dim]auto | unsplash | pexels | pixabay | reddit | wallhaven | deviantart | nasa | bing[/dim]")
        console.print("  wallpaper set [bold cyan]interval[/bold cyan]          [dim]3h[/dim]")
        console.print("  wallpaper set [bold cyan]color[/bold cyan]             [dim]blue | teal | red … | none[/dim]")
        console.print("  wallpaper set [bold cyan]unsplash_key[/bold cyan]      [dim]<api_key>[/dim]")
        console.print("  wallpaper set [bold cyan]pexels_key[/bold cyan]        [dim]<api_key>[/dim]")
        console.print("  wallpaper set [bold cyan]pixabay_key[/bold cyan]       [dim]<api_key>[/dim]")
        console.print("  wallpaper set [bold cyan]nasa_key[/bold cyan]          [dim]<api_key>  (or 'demo' for free DEMO_KEY)[/dim]")
        console.print("  wallpaper set [bold cyan]deviantart_id[/bold cyan]     [dim]<client_id>[/dim]")
        console.print("  wallpaper set [bold cyan]deviantart_secret[/bold cyan] [dim]<client_secret>[/dim]")
        console.print()
        return

    if setting == "query":
        if not value:
            console.print('[red]Usage:[/red] wallpaper set query "your topic"')
            return
        cfg["query"] = " ".join(value)
        console.print(f'\n  [green]✓[/green]  Query → [cyan]{cfg["query"]}[/cyan]')

    elif setting == "style":
        if not value or value[0] not in STYLES:
            console.print("[red]Unknown style.[/red]")
            cmd_styles()
            return
        style = value[0]
        cfg["style"] = style
        console.print(f'\n  [green]✓[/green]  Style → [magenta]{style}[/magenta]  [dim]({STYLES[style]["description"]})[/dim]')

    elif setting == "source":
        valid = ["auto"] + list(SOURCES.keys())
        if not value or value[0] not in valid:
            console.print("[red]Unknown source.[/red]  Options: " + "  ".join(valid))
            return
        cfg["source"] = value[0]
        label = f"auto (uses style default)" if value[0] == "auto" else value[0]
        console.print(f'\n  [green]✓[/green]  Source → [green]{label}[/green]')

    elif setting == "interval":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set interval 3h")
            return
        try:
            hours = int(value[0].rstrip("h"))
            if hours < 1:
                raise ValueError("interval must be at least 1")
        except (ValueError, IndexError):
            console.print("[red]Must be a positive number of hours, e.g. 3 or 3h[/red]")
            return
        cfg["interval_hours"] = hours
        if not update_cron(hours):
            return
        console.print(f"\n  [green]✓[/green]  Interval → [green]{hours}h[/green]")

    elif setting == "color":
        color_names = list(COLORS.keys())
        if not value:
            console.print("  [dim]Available:[/dim] " + "  ".join(color_names) + "  none\n")
            return
        color = value[0].lower()
        if color == "none":
            cfg["color"] = None
            console.print("\n  [green]✓[/green]  Color filter removed")
        elif color not in COLORS:
            console.print("[red]Unknown color.[/red]  Try: " + "  ".join(color_names))
            return
        else:
            cfg["color"] = color
            console.print(f"\n  [green]✓[/green]  Color → [yellow]{color}[/yellow]")

    elif setting == "unsplash_key":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set unsplash_key <api_key>")
            return
        cfg["unsplash_key"] = value[0]
        console.print("\n  [green]✓[/green]  Unsplash API key saved")

    elif setting == "pexels_key":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set pexels_key <api_key>")
            return
        cfg["pexels_key"] = value[0]
        console.print("\n  [green]✓[/green]  Pexels API key saved")

    elif setting == "pixabay_key":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set pixabay_key <api_key>")
            return
        cfg["pixabay_key"] = value[0]
        console.print("\n  [green]✓[/green]  Pixabay API key saved")

    elif setting == "nasa_key":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set nasa_key <api_key>  (or 'demo')")
            return
        cfg["nasa_key"] = "DEMO_KEY" if value[0].lower() == "demo" else value[0]
        console.print("\n  [green]✓[/green]  NASA API key saved")

    elif setting == "deviantart_id":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set deviantart_id <your_client_id>")
            return
        cfg["deviantart_client_id"] = value[0]
        console.print(f"\n  [green]✓[/green]  DeviantArt client_id saved")

    elif setting == "deviantart_secret":
        if not value:
            console.print("[red]Usage:[/red] wallpaper set deviantart_secret <your_client_secret>")
            return
        cfg["deviantart_client_secret"] = value[0]
        # Invalidate cached token so it re-authenticates with new credentials
        if DA_TOKEN_FILE.exists():
            DA_TOKEN_FILE.unlink()
        console.print(f"\n  [green]✓[/green]  DeviantArt client_secret saved")

    save_config(cfg)
    console.print("  [dim]Run [bold]wallpaper now[/bold] to apply immediately[/dim]\n")


def cmd_styles(_args=None):
    cfg = load_config()
    current = cfg.get("style", "realistic")

    table = Table(box=box.ROUNDED, border_style="bright_blue", header_style="bold cyan")
    table.add_column("", width=3)
    table.add_column("Style", width=14)
    table.add_column("Description", width=30)
    table.add_column("Default source", width=12)

    for name, info in STYLES.items():
        is_cur = name == current
        table.add_row(
            info.get("icon", ""),
            f"[bold cyan]{name}[/bold cyan]" if is_cur else name,
            info["description"] + (" [dim]← current[/dim]" if is_cur else ""),
            info["source"],
        )

    console.print()
    console.print(Panel(table, title="Available Styles", border_style="bright_blue", padding=(0, 1)))
    console.print("  [dim]wallpaper set style [bold]<name>[/bold][/dim]\n")


def cmd_sources(_args=None):
    cfg = load_config()
    current = resolve_source(cfg)
    configured = cfg.get("source", "auto")

    table = Table(box=box.ROUNDED, border_style="bright_blue", header_style="bold cyan")
    table.add_column("", width=3)
    table.add_column("Source", width=12)
    table.add_column("Description", width=38)
    table.add_column("Key", width=8)

    key_map = {
        "unsplash":   bool(cfg.get("unsplash_key")),
        "wallhaven":  True,
        "pexels":     bool(cfg.get("pexels_key")),
        "pixabay":    bool(cfg.get("pixabay_key")),
        "reddit":     True,
        "deviantart": bool(cfg.get("deviantart_client_id") and cfg.get("deviantart_client_secret")),
        "nasa":       True,
        "bing":       True,
    }

    for name, info in SOURCES.items():
        is_cur = name == current
        has_key = key_map.get(name, False)
        key_str = "[green]✓[/green]" if has_key else "[dim]—[/dim]"
        table.add_row(
            info.get("icon", ""),
            f"[bold cyan]{name}[/bold cyan]" if is_cur else name,
            info["description"] + (" [dim]← active[/dim]" if is_cur else ""),
            key_str,
        )

    console.print()
    mode = f"[dim]pinned to[/dim] [green]{configured}[/green]" if configured != "auto" else "[dim]auto (follows style)[/dim]"
    console.print(Panel(table, title=f"Sources  —  {mode}", border_style="bright_blue", padding=(0, 1)))
    console.print("  [dim]wallpaper set source [bold]<name>[/bold] | auto[/dim]\n")


def cmd_presets(_args=None):
    presets = load_presets()
    cfg = load_config()

    if not presets:
        console.print(Panel(
            "[dim]No presets saved yet.\n\nRun [bold]wallpaper new[/bold] to create one.[/dim]",
            border_style="dim", padding=(1, 2),
        ))
        return

    active = cfg.get("_preset")
    table = Table(box=box.ROUNDED, border_style="bright_blue", header_style="bold cyan")
    table.add_column("", width=2)
    table.add_column("Name", width=20)
    table.add_column("Style", width=12)
    table.add_column("Source", width=10)
    table.add_column("Query", width=16)
    table.add_column("Color", width=12)
    table.add_column("Interval", width=9, justify="right")

    for name, p in presets.items():
        is_active = name == active
        style = p.get("style", "realistic")
        src = p.get("source", "auto")
        src_icon = SOURCES.get(src, {}).get("icon", "") if src != "auto" else "⚙"
        icon = STYLES.get(style, {}).get("icon", "")
        table.add_row(
            "›" if is_active else "",
            f"[bold cyan]{name}[/bold cyan]" if is_active else name,
            f"{icon} {style}",
            f"{src_icon} {src}",
            p.get("query", "—"),
            p.get("color") or "[dim]none[/dim]",
            f"{p.get('interval_hours', 3)}h",
        )

    console.print()
    console.print(Panel(table, title="Saved Presets", border_style="bright_blue", padding=(0, 1)))
    console.print("  [dim]wallpaper [bold]use[/bold] <name>   wallpaper [bold]new[/bold]   wallpaper [bold]delete[/bold] <name>[/dim]\n")


def cmd_new(_args=None):
    q = require_questionary()
    cfg = load_config()
    presets = load_presets()

    console.print()
    console.print(Rule("[bold cyan]  New Preset  [/bold cyan]", style="bright_blue"))
    console.print()

    # ── Name ──────────────────────────────────────────────────────────────────
    name = q.text(
        "Preset name:",
        validate=lambda v: "Name can't be empty" if not v.strip() else True,
    ).ask()
    if name is None: return
    name = name.strip()

    if name in presets:
        if not q.confirm(f'"{name}" already exists. Overwrite?', default=False).ask():
            return

    # ── Style ─────────────────────────────────────────────────────────────────
    console.print()
    style = q.select(
        "Style:",
        choices=[
            q.Choice(title=f"{info['icon']}  {sname:<14} {info['description']}", value=sname)
            for sname, info in STYLES.items()
        ],
        default=cfg.get("style", "realistic"),
    ).ask()
    if style is None: return

    # ── Source ────────────────────────────────────────────────────────────────
    console.print()
    default_src = STYLES[style]["source"]
    source = q.select(
        "Source:",
        choices=[
            q.Choice(title=f"⚙   auto              Use style default ({default_src})", value="auto"),
        ] + [
            q.Choice(title=f"{info['icon']}  {sname:<14} {info['description']}", value=sname)
            for sname, info in SOURCES.items()
        ],
        default="auto",
    ).ask()
    if source is None: return

    # ── Query ─────────────────────────────────────────────────────────────────
    console.print()
    query_pick = q.select(
        "Query topic:",
        choices=[q.Choice(title=s, value=s) for s in QUERY_SUGGESTIONS]
               + [q.Choice(title="✏  type your own…", value="__custom__")],
    ).ask()
    if query_pick is None: return
    if query_pick == "__custom__":
        query = q.text("Enter query:").ask()
        if not query: return
    else:
        query = query_pick

    # ── Color ─────────────────────────────────────────────────────────────────
    console.print()
    color = q.select(
        "Dominant color filter:",
        choices=[q.Choice(title="none — no filter", value=None)]
               + [q.Choice(title=c, value=c) for c in COLORS],
    ).ask()

    # ── Interval ──────────────────────────────────────────────────────────────
    console.print()
    interval = q.select(
        "Refresh interval:",
        choices=[
            q.Choice("1h  — changes every hour",  value=1),
            q.Choice("2h",                         value=2),
            q.Choice("3h  — default",             value=3),
            q.Choice("6h",                         value=6),
            q.Choice("12h",                        value=12),
            q.Choice("24h — once a day",           value=24),
        ],
        default=cfg.get("interval_hours", 3),
    ).ask()
    if interval is None: return

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule(style="bright_blue"))
    style_icon = STYLES.get(style, {}).get("icon", "")
    src_icon = SOURCES.get(source, {}).get("icon", "⚙")
    console.print(f"  [bold]{name}[/bold]")
    console.print(
        f"  {style_icon} [magenta]{style}[/magenta]  ·  {src_icon} [green]{source}[/green]  ·  "
        f"[cyan]{query}[/cyan]" +
        (f"  ·  [yellow]{color}[/yellow]" if color else "") +
        f"  ·  [green]{interval}h[/green]"
    )
    console.print()

    presets[name] = {"style": style, "source": source, "query": query, "color": color, "interval_hours": interval}
    save_presets(presets)
    console.print(f"  [green]✓[/green]  Preset [bold]\"{name}\"[/bold] saved\n")

    if q.confirm("Apply this preset now?", default=True).ask():
        _apply_preset(name, presets[name])


def cmd_delete(args):
    presets = load_presets()
    if not presets:
        console.print("\n  [dim]No presets to delete.[/dim]\n")
        return

    name = getattr(args, "name", None)
    if not name:
        q = require_questionary()
        console.print()
        console.print("  [dim]j/k ↑↓ navigate   Enter select   Ctrl+C cancel[/dim]\n")
        choices = [q.Choice(title=pname, value=pname) for pname in presets]
        choices.append(q.Separator())
        choices.append(q.Choice("← Cancel", "__cancel__"))
        name = q.select("Delete preset:", choices=choices).ask()
        if name is None or name == "__cancel__":
            return

    if name not in presets:
        console.print(f"\n  [red]Preset not found:[/red] {name}\n  Run [bold]wallpaper presets[/bold] to see all\n")
        return

    del presets[name]
    save_presets(presets)

    cfg = load_config()
    if cfg.get("_preset") == name:
        cfg.pop("_preset", None)
        save_config(cfg)

    console.print(f"\n  [green]✓[/green]  Preset [bold]\"{name}\"[/bold] deleted\n")


def cmd_use(args):
    presets = load_presets()
    if not presets:
        console.print("\n  [dim]No presets yet — run [bold]wallpaper new[/bold][/dim]\n")
        return

    name = getattr(args, "name", None)
    if not name:
        q = require_questionary()
        console.print()
        console.print("  [dim]j/k ↑↓ navigate   Enter select   Ctrl+C cancel[/dim]\n")
        choices = []
        for pname, p in presets.items():
            style = p.get("style", "realistic")
            src = p.get("source", "auto")
            icon = STYLES.get(style, {}).get("icon", "")
            src_icon = SOURCES.get(src, {}).get("icon", "⚙")
            color = p.get("color") or "no color"
            choices.append(q.Choice(
                title=f"{pname}   [{icon} {style} · {src_icon} {src} · {p.get('query')} · {color} · {p.get('interval_hours', 3)}h]",
                value=pname,
            ))
        choices.append(q.Separator())
        choices.append(q.Choice("← Cancel", "__cancel__"))
        name = q.select("Switch to preset:", choices=choices).ask()
        if name is None or name == "__cancel__":
            return

    if name not in presets:
        console.print(f"\n  [red]Preset not found:[/red] {name}\n  Run [bold]wallpaper presets[/bold] to see all\n")
        return

    _apply_preset(name, presets[name])


def _apply_preset(name, preset):
    cfg = load_config()
    cfg.update({
        "query":          preset["query"],
        "style":          preset["style"],
        "source":         preset.get("source", "auto"),
        "color":          preset.get("color"),
        "interval_hours": preset.get("interval_hours", 3),
        "_preset":        name,
    })
    save_config(cfg)
    update_cron(cfg["interval_hours"])

    src = preset.get("source", "auto")
    style = preset["style"]
    src_label = f"auto → {STYLES.get(style, {}).get('source', 'unsplash')}" if src == "auto" else src
    style_icon = STYLES.get(style, {}).get("icon", "")
    color_part = f"  [yellow]{preset.get('color')}[/yellow]" if preset.get("color") else ""
    console.print(
        f"\n  [green]✓[/green]  Preset [bold]\"{name}\"[/bold] active  "
        f"{style_icon} [magenta]{style}[/magenta]  ·  [green]{src_label}[/green]  ·  "
        f"[cyan]{preset['query']}[/cyan]{color_part}  ·  [green]{preset.get('interval_hours', 3)}h[/green]"
    )
    console.print("  [dim]Run [bold]wallpaper now[/bold] to fetch immediately[/dim]\n")


def cmd_setup(_args=None):
    q = require_questionary()
    cfg = load_config()

    console.print()
    console.print(Rule("[bold cyan]  API Setup  [/bold cyan]", style="bright_blue"))
    console.print()

    table = Table(box=box.ROUNDED, border_style="bright_blue", header_style="bold cyan")
    table.add_column("Source", width=14)
    table.add_column("Status", width=14)
    table.add_column("How to get a key", width=44)

    def _status(key, always_ready=False):
        if always_ready:
            return "[green]✓ Ready[/green]", ""
        val = cfg.get(key, "")
        if val and val != "DEMO_KEY":
            return "[green]✓ Configured[/green]", ""
        if key == "nasa_key":
            return "[yellow]~ Demo key[/yellow]", "api.nasa.gov (free, 30 req/h)"
        return "[dim]✗ Not set[/dim]", ""

    rows = [
        ("bing",      "🌍 Bing",       True,  False, "No key needed"),
        ("reddit",    "🤖 Reddit",      True,  False, "No key needed"),
        ("wallhaven", "🎨 Wallhaven",   True,  False, "No key needed"),
        ("nasa_key",  "🚀 NASA",        False, False, "api.nasa.gov — free signup"),
        ("unsplash_key",  "🌄 Unsplash",   False, False, "unsplash.com/developers — free"),
        ("pexels_key",    "📸 Pexels",     False, False, "pexels.com/api — free"),
        ("pixabay_key",   "🖼  Pixabay",    False, False, "pixabay.com/api — free"),
        ("deviantart_client_id", "🎭 DeviantArt", False, False, "deviantart.com/developers"),
    ]
    for key, label, always_ready, _, howto in rows:
        st, _ = _status(key, always_ready)
        table.add_row(label, st, howto if not always_ready else "[dim]—[/dim]")

    console.print(Panel(table, title="Source Status", border_style="bright_blue", padding=(0, 1)))
    console.print()

    console.print("  [dim]j/k ↑↓ navigate   Space toggle   a select all   Enter confirm   Ctrl+C cancel[/dim]\n")
    sources_to_configure = q.checkbox(
        "Which sources would you like to configure?",
        choices=[
            q.Choice("🚀  NASA APOD      (free key — more quota than DEMO_KEY)", "nasa"),
            q.Choice("🌄  Unsplash       (free key)", "unsplash"),
            q.Choice("📸  Pexels         (free key)", "pexels"),
            q.Choice("🖼   Pixabay        (free key)", "pixabay"),
            q.Choice("🎭  DeviantArt     (OAuth app — client ID + secret)", "deviantart"),
        ],
    ).ask()
    if sources_to_configure is None:
        return

    for src in (sources_to_configure or []):
        console.print()
        if src == "nasa":
            console.print("  Get a free key at [bold]api.nasa.gov[/bold]  (or press Enter to keep using DEMO_KEY)")
            val = q.text("NASA API key:", default=cfg.get("nasa_key", "DEMO_KEY")).ask()
            if val:
                cfg["nasa_key"] = val.strip()
        elif src == "unsplash":
            console.print("  Get a free key at [bold]unsplash.com/developers[/bold]")
            val = q.text("Unsplash access key:", default=cfg.get("unsplash_key", "")).ask()
            if val:
                cfg["unsplash_key"] = val.strip()
        elif src == "pexels":
            console.print("  Get a free key at [bold]pexels.com/api[/bold]")
            val = q.text("Pexels API key:", default=cfg.get("pexels_key", "")).ask()
            if val:
                cfg["pexels_key"] = val.strip()
        elif src == "pixabay":
            console.print("  Get a free key at [bold]pixabay.com/api[/bold]")
            val = q.text("Pixabay API key:", default=cfg.get("pixabay_key", "")).ask()
            if val:
                cfg["pixabay_key"] = val.strip()
        elif src == "deviantart":
            console.print("  Create an app at [bold]deviantart.com/developers/apps[/bold]")
            cid = q.text("DeviantArt client_id:", default=cfg.get("deviantart_client_id", "")).ask()
            csec = q.text("DeviantArt client_secret:", default=cfg.get("deviantart_client_secret", "")).ask()
            if cid:
                cfg["deviantart_client_id"] = cid.strip()
            if csec:
                cfg["deviantart_client_secret"] = csec.strip()
                if DA_TOKEN_FILE.exists():
                    DA_TOKEN_FILE.unlink()

    save_config(cfg)
    console.print(f"\n  [green]✓[/green]  Configuration saved\n")


def cmd_featured(_args=None):
    q = require_questionary()
    cfg = load_config()

    console.print()
    console.print(Panel(
        "[bold white]Ready-to-use presets[/bold white]\n[dim]Select one to save and activate it immediately.[/dim]",
        title="[bold cyan]⭐  Featured Presets[/bold cyan]",
        border_style="cyan", padding=(0, 2),
    ))
    console.print()
    console.print("  [dim]j/k ↑↓ navigate   Enter confirm   Ctrl+C cancel[/dim]\n")

    choices = []
    for fp in FEATURED_PRESETS:
        src = fp["source"]
        needs_key = (
            (src == "unsplash" and not cfg.get("unsplash_key")) or
            (src == "deviantart" and not cfg.get("deviantart_client_id"))
        )
        note = "  (needs API key)" if needs_key else ""
        choices.append(q.Choice(
            title=f"{fp['icon']}  {fp['name']:<30} {fp['description']}{note}",
            value=fp["key"],
        ))
    choices.append(q.Separator())
    choices.append(q.Choice("←  Back to menu", value="__back__"))

    key = q.select("Select a preset:", choices=choices).ask()
    if key is None or key == "__back__":
        return

    fp = next(f for f in FEATURED_PRESETS if f["key"] == key)
    preset_data = {k: fp[k] for k in ("style", "source", "query", "color", "interval_hours")}
    presets = load_presets()
    presets[fp["name"]] = preset_data
    save_presets(presets)
    _apply_preset(fp["name"], preset_data)

    if q.confirm("Fetch a wallpaper now?", default=True).ask():
        cmd_now()


def cmd_settings_menu(q=None):
    if q is None:
        q = require_questionary()

    while True:
        cfg      = load_config()
        style    = cfg.get("style", "realistic")
        source   = cfg.get("source", "auto")
        query    = cfg.get("query", "")
        color    = cfg.get("color") or "none"
        interval = cfg.get("interval_hours", 3)

        style_icon = STYLES.get(style, {}).get("icon", "")
        src_icon   = SOURCES.get(source, {}).get("icon", "⚙")

        console.print()
        console.print(Panel(
            f"  {style_icon} [bold]{style}[/bold]   {src_icon} {source}   every [bold]{interval}h[/bold]\n"
            f"  query: [cyan]{query or '(none)'}[/cyan]   color: [yellow]{color}[/yellow]",
            title="[bold magenta]⚙  Settings[/bold magenta]",
            border_style="magenta", padding=(0, 1),
        ))
        console.print("  [dim]j/k ↑↓ navigate   Enter confirm   Ctrl+C cancel[/dim]\n")

        choice = q.select(
            "Change setting:",
            choices=[
                q.Choice(f"🔍  Query / topic     current: {query!r}", "query"),
                q.Choice(f"🎨  Style             current: {style}", "style"),
                q.Choice(f"📡  Source            current: {source}", "source"),
                q.Choice(f"⏱   Interval          current: {interval}h", "interval"),
                q.Choice(f"🎞   Color filter      current: {color}", "color"),
                q.Separator(),
                q.Choice("←  Back to menu", "__back__"),
            ],
        ).ask()

        if choice is None or choice == "__back__":
            break

        cfg = load_config()

        if choice == "query":
            console.print("  [dim]j/k ↑↓ move   Enter confirm   Ctrl+C cancel[/dim]\n")
            val = q.text("New query:", default=cfg.get("query", "")).ask()
            if val is not None:
                cfg["query"] = val.strip()
                save_config(cfg)
                console.print(f"  [green]✓[/green]  Query → [cyan]{val.strip() or '(cleared)'}[/cyan]")

        elif choice == "style":
            console.print("  [dim]j/k ↑↓ navigate   Enter confirm   Ctrl+C cancel[/dim]\n")
            val = q.select("Style:", choices=[
                q.Choice(f"{info['icon']}  {name:<14} {info['description']}", name)
                for name, info in STYLES.items()
            ] + [q.Separator(), q.Choice("← Cancel", "__cancel__")],
            default=cfg.get("style", "realistic")).ask()
            if val is not None and val != "__cancel__":
                cfg["style"] = val
                save_config(cfg)
                console.print(f"  [green]✓[/green]  Style → [magenta]{val}[/magenta]")

        elif choice == "source":
            console.print("  [dim]j/k ↑↓ navigate   Enter confirm   Ctrl+C cancel[/dim]\n")
            val = q.select("Source:", choices=[
                q.Choice("⚙   auto              Pick randomly from all configured sources", "auto"),
            ] + [
                q.Choice(f"{info['icon']}  {name:<14} {info['description']}", name)
                for name, info in SOURCES.items()
            ] + [q.Separator(), q.Choice("← Cancel", "__cancel__")],
            default=cfg.get("source", "auto")).ask()
            if val is not None and val != "__cancel__":
                cfg["source"] = val
                save_config(cfg)
                console.print(f"  [green]✓[/green]  Source → [green]{val}[/green]")

        elif choice == "interval":
            console.print("  [dim]j/k ↑↓ navigate   Enter confirm   Ctrl+C cancel[/dim]\n")
            val = q.select("Refresh interval:", choices=[
                q.Choice("1h  — changes every hour", 1),
                q.Choice("2h", 2),
                q.Choice("3h  — default", 3),
                q.Choice("6h", 6),
                q.Choice("12h", 12),
                q.Choice("24h — once a day", 24),
                q.Separator(),
                q.Choice("← Cancel", "__cancel__"),
            ], default=cfg.get("interval_hours", 3)).ask()
            if val is not None and val != "__cancel__":
                cfg["interval_hours"] = val
                save_config(cfg)
                update_cron(val)
                console.print(f"  [green]✓[/green]  Interval → [green]{val}h[/green]")

        elif choice == "color":
            console.print("  [dim]j/k ↑↓ navigate   Enter confirm   Ctrl+C cancel[/dim]\n")
            cur = cfg.get("color") or "__none__"
            val = q.select("Color filter:", choices=[
                q.Choice("none — no filter", "__none__"),
            ] + [q.Choice(c, c) for c in COLORS] + [
                q.Separator(), q.Choice("← Cancel", "__cancel__"),
            ], default=cur).ask()
            if val is not None and val != "__cancel__":
                actual = None if val == "__none__" else val
                cfg["color"] = actual
                save_config(cfg)
                console.print(f"  [green]✓[/green]  Color → [yellow]{actual or 'none'}[/yellow]")

        console.print()


def cmd_restore_defaults(q=None):
    if q is None:
        q = require_questionary()

    presets = load_presets()
    if not presets:
        console.print("\n  [dim]No custom presets to remove.[/dim]\n")
        return

    names = ", ".join(f"[bold]{n}[/bold]" for n in presets)
    console.print(f"\n  {len(presets)} preset(s) will be removed: {names}")
    console.print("  [dim]API keys and settings are NOT affected.[/dim]\n")

    confirmed = q.confirm("Delete all custom presets?", default=False).ask()
    if confirmed:
        PRESETS_FILE.write_text("{}")
        console.print("  [green]✓[/green]  All custom presets cleared. API keys unchanged.\n")
    else:
        console.print("  [dim]Cancelled.[/dim]\n")


def _pause():
    """Print a dim prompt and wait for Enter before re-rendering the menu."""
    try:
        console.print("\n  [dim]── Press Enter to return to menu ──[/dim]")
        input()
    except (KeyboardInterrupt, EOFError):
        pass


def cmd_menu(_args=None):
    q = require_questionary()

    while True:
        cfg     = load_config()
        history = load_history()
        style   = cfg.get("style", "realistic")
        source  = cfg.get("source", "auto")
        preset  = cfg.get("_preset")
        query   = cfg.get("query", "")
        icon    = STYLES.get(style, {}).get("icon", "")
        src_icon = SOURCES.get(source, {}).get("icon", "⚙")

        if history:
            latest = history[-1]
            desc   = (latest.get("description") or "Unknown")[:54]
            src_h  = latest.get("source", "")
            ago    = time_ago(latest.get("date", ""))
            last_line = f"[bold]{desc}[/bold]  [dim]·  {src_h}  ·  {ago}[/dim]"
        else:
            last_line = "[dim]No wallpaper fetched yet[/dim]"

        if preset:
            cfg_line = f"[cyan]{preset}[/cyan]  [dim]·[/dim]  {icon} {style}  [dim]·[/dim]  {src_icon} {source}  [dim]·[/dim]  every {cfg.get('interval_hours', 3)}h"
        else:
            q_str    = f"  [dim]·[/dim]  [cyan]{query}[/cyan]" if query else ""
            cfg_line = f"{icon} {style}  [dim]·[/dim]  {src_icon} {source}{q_str}  [dim]·[/dim]  every {cfg.get('interval_hours', 3)}h"

        console.print()
        console.print(Panel(
            f"[dim]last:[/dim]  {last_line}\n[dim]mode:[/dim]  {cfg_line}",
            title="[bold blue]🖼  Wallpaper CLI[/bold blue]",
            border_style="blue", padding=(0, 2),
        ))
        console.print("  [dim]j/k ↑↓ navigate   Enter select   Ctrl+C exit[/dim]\n")

        choice = q.select(
            "What would you like to do?",
            choices=[
                q.Choice("🔄  Fetch new wallpaper now",    "now"),
                q.Choice("⭐  Browse featured presets",     "featured"),
                q.Choice("🎨  Switch active preset",        "use"),
                q.Choice("✏   Create custom preset",        "new"),
                q.Choice("🗑   Delete a preset",             "delete"),
                q.Separator(),
                q.Choice("⚙   Change settings",            "settings"),
                q.Choice("🔑  Setup API keys",              "setup"),
                q.Choice("↺   Restore defaults",            "restore"),
                q.Separator(),
                q.Choice("📊  View status",                 "status"),
                q.Choice("📜  View history",                "history"),
                q.Choice("📋  List presets",                "presets"),
                q.Separator(),
                q.Choice("✗   Exit",                       "exit"),
            ],
        ).ask()

        if choice is None or choice == "exit":
            break
        elif choice == "now":
            cmd_now()
        elif choice == "featured":
            cmd_featured()
        elif choice == "use":
            cmd_use(argparse.Namespace(name=None))
        elif choice == "new":
            cmd_new()
        elif choice == "delete":
            cmd_delete(argparse.Namespace(name=None))
        elif choice == "settings":
            cmd_settings_menu(q)
        elif choice == "setup":
            cmd_setup()
        elif choice == "restore":
            cmd_restore_defaults(q)
        elif choice == "status":
            cmd_status()
            _pause()
        elif choice == "history":
            cmd_history(argparse.Namespace(limit=10))
            _pause()
        elif choice == "presets":
            cmd_presets()
            _pause()


def cmd_internal_fetch(_args=None):
    entry = do_fetch(silent=True)
    sys.exit(0 if entry else 1)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="wallpaper",
        description="Wallpaper CLI — Unsplash, Pexels, Pixabay, Wallhaven, Reddit, DeviantArt, NASA, Bing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Run with no arguments to open the interactive menu.\n\n"
            "Examples:\n"
            "  wallpaper                   # interactive menu\n"
            "  wallpaper setup             # configure API keys\n"
            "  wallpaper featured          # browse built-in presets\n"
            "  wallpaper now               # fetch immediately\n"
            "  wallpaper set query \"rainy city\"\n"
            "  wallpaper set style anime\n"
            "  wallpaper set source nasa\n"
            "  wallpaper set interval 6h\n"
            "  wallpaper set color teal\n"
            "  wallpaper new               # create custom preset\n"
            "  wallpaper use \"my preset\"\n"
            "  wallpaper history -n 30\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"wallpaper-cli {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    sub.add_parser("menu",     help="Open the interactive menu (default when no args)")
    sub.add_parser("setup",    help="Configure API keys interactively")
    sub.add_parser("featured", help="Browse and activate built-in featured presets")
    sub.add_parser("status",   help="Show current wallpaper info and active settings")
    sub.add_parser("now",      help="Fetch a new wallpaper immediately")
    sub.add_parser("styles",   help="List available style presets")
    sub.add_parser("sources",  help="List available image sources and their status")
    sub.add_parser("presets",  help="List saved named presets")
    sub.add_parser("new",      help="Create a new named preset interactively")

    d = sub.add_parser("delete", help="Delete a saved preset")
    d.add_argument("name", nargs="?", metavar="name", help="Preset name")

    h = sub.add_parser("history", help="Show wallpaper history")
    h.add_argument("--limit", "-n", type=int, default=20, metavar="N",
                   help="Number of entries to show (default: 20)")

    u = sub.add_parser("use", help="Switch to a saved preset (interactive if no name given)")
    u.add_argument("name", nargs="?", metavar="name", help="Preset name")

    s = sub.add_parser("set", help="Change a setting")
    s.add_argument("setting", nargs="?", metavar="setting",
                   choices=["query", "style", "source", "interval", "color",
                            "unsplash_key", "pexels_key", "pixabay_key", "nasa_key",
                            "deviantart_id", "deviantart_secret"],
                   help="query | style | source | interval | color | unsplash_key | pexels_key | pixabay_key | nasa_key | deviantart_id | deviantart_secret")
    s.add_argument("value", nargs="*", metavar="value")

    if len(sys.argv) > 1 and sys.argv[1] == "_fetch":
        cmd_internal_fetch()
        return

    args = parser.parse_args()

    dispatch = {
        None:       cmd_menu,
        "menu":     cmd_menu,
        "setup":    cmd_setup,
        "featured": cmd_featured,
        "status":   cmd_status,
        "history":  cmd_history,
        "now":      cmd_now,
        "styles":   cmd_styles,
        "sources":  cmd_sources,
        "presets":  cmd_presets,
        "new":      cmd_new,
        "delete":   cmd_delete,
        "use":      cmd_use,
        "set":      cmd_set,
    }
    try:
        dispatch.get(args.command, cmd_menu)(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
