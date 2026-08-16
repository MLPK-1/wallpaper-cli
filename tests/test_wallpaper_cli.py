"""Tests for wallpaper-cli.

All network access and subprocess calls are mocked; the suite runs fully
offline and touches only temporary directories.
"""

import argparse
import json
import sys
import time
import unittest.mock as mock
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wallpaper_cli.main as m


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Redirect every path constant into a temp dir so tests never touch ~."""
    for attr in [
        "CONFIG_FILE", "PRESETS_FILE", "HISTORY_FILE", "WALLPAPER_DIR",
        "THUMB_DIR", "CURRENT_PATH", "GDM_SCRIPT", "DA_TOKEN_FILE",
    ]:
        monkeypatch.setattr(m, attr, tmp_path / attr)
    monkeypatch.setattr(m, "HOME", tmp_path)
    yield tmp_path


@pytest.fixture
def fake_console(monkeypatch):
    cons = mock.Mock()
    cons.print = mock.Mock()
    cons.status.return_value.__enter__ = mock.Mock()
    cons.status.return_value.__exit__ = mock.Mock()
    monkeypatch.setattr(m, "console", cons)
    return cons


# ── Version ───────────────────────────────────────────────────────────────────
def test_version_single_source():
    assert m.__version__ == "0.2.0"


# ── Config ───────────────────────────────────────────────────────────────────
def test_load_config_defaults():
    cfg = m.load_config()
    assert cfg["source"] == "auto"
    assert cfg["style"] == "realistic"
    assert cfg["interval_hours"] == 3
    assert cfg["resolution_width"] == 3840


def test_load_config_merges_saved():
    m.CONFIG_FILE.write_text(json.dumps({"query": "neon city", "style": "cyberpunk"}))
    cfg = m.load_config()
    assert cfg["query"] == "neon city"
    assert cfg["style"] == "cyberpunk"
    assert cfg["interval_hours"] == 3  # default filled in


def test_load_config_sanitizes_unknown_keys():
    m.CONFIG_FILE.write_text(json.dumps({
        "style": "bogus", "source": "nope", "color": "notacolor",
    }))
    cfg = m.load_config()
    assert cfg["style"] == "realistic"
    assert cfg["source"] == "auto"
    assert cfg["color"] is None


def test_load_config_coerces_numeric_garbage():
    m.CONFIG_FILE.write_text(json.dumps({
        "interval_hours": "abc", "resolution_width": "huge",
    }))
    cfg = m.load_config()
    assert cfg["interval_hours"] == 3
    assert cfg["resolution_width"] == 3840


def test_load_config_rejects_out_of_range():
    m.CONFIG_FILE.write_text(json.dumps({"interval_hours": 0, "resolution_width": 100}))
    cfg = m.load_config()
    assert cfg["interval_hours"] == 3
    assert cfg["resolution_width"] == 3840


def test_load_config_corrupt_json_falls_back():
    m.CONFIG_FILE.write_text("{not json!!")
    cfg = m.load_config()
    assert cfg["source"] == "auto"
    assert cfg["interval_hours"] == 3


def test_save_and_load_roundtrip():
    cfg = m.load_config()
    cfg["query"] = "ocean waves"
    cfg["interval_hours"] = 6
    m.save_config(cfg)
    assert json.loads(m.CONFIG_FILE.read_text())["query"] == "ocean waves"
    assert m.load_config()["query"] == "ocean waves"
    assert m.load_config()["interval_hours"] == 6


def test_save_config_atomic_no_tmp_leftover():
    m.save_config({"query": "x"})
    assert not list(m.CONFIG_FILE.parent.glob("*.tmp"))


# ── Presets ──────────────────────────────────────────────────────────────────
def test_presets_empty_by_default():
    assert m.load_presets() == {}


def test_presets_save_load_roundtrip():
    m.save_presets({"mine": {"style": "space", "source": "nasa", "query": "galaxy", "color": None, "interval_hours": 24}})
    assert m.load_presets()["mine"]["source"] == "nasa"


def test_presets_corrupt_json_falls_back():
    m.PRESETS_FILE.write_text("nope{")
    assert m.load_presets() == {}


# ── History ──────────────────────────────────────────────────────────────────
def test_history_empty_by_default():
    assert m.load_history() == []


def test_append_history_and_cap():
    for i in range(105):
        m.append_history({"date": f"2026-01-01T00:00:{i:02d}", "description": str(i)})
    hist = m.load_history()
    assert len(hist) == 100
    assert hist[-1]["description"] == "104"


def test_history_corrupt_json_falls_back():
    m.HISTORY_FILE.write_text("###")
    assert m.load_history() == []
    m.append_history({"date": "2026-01-01T00:00:00", "description": "ok"})
    assert len(m.load_history()) == 1


def test_history_write_is_atomic():
    m.append_history({"description": "one"})
    assert not list(m.HISTORY_FILE.parent.glob("*.tmp"))


# ── time_ago ─────────────────────────────────────────────────────────────────
def test_time_ago_fresh():
    assert m.time_ago(datetime.now().isoformat()) == "just now"


def test_time_ago_minutes():
    dt = (datetime.now() - timedelta(minutes=5)).isoformat()
    assert m.time_ago(dt) == "5m ago"


def test_time_ago_hours():
    dt = (datetime.now() - timedelta(hours=3)).isoformat()
    assert m.time_ago(dt) == "3h ago"


def test_time_ago_days():
    dt = (datetime.now() - timedelta(days=2)).isoformat()
    assert m.time_ago(dt) == "2d ago"


def test_time_ago_bad_input():
    assert m.time_ago("not-a-date") == "—"


# ── _auto_sources / resolve_source ───────────────────────────────────────────
def test_auto_sources_custom_style():
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["style"] = "custom"
    srcs = m._auto_sources(cfg)
    assert "wallhaven" in srcs and "reddit" in srcs
    assert "unsplash" not in srcs


def test_auto_sources_includes_keyed_when_configured():
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["unsplash_key"] = "k"
    cfg["pexels_key"] = "k"
    cfg["pixabay_key"] = "k"
    srcs = m._auto_sources(cfg)
    assert {"unsplash", "pexels", "pixabay"} <= set(srcs)


def test_auto_sources_space_style_includes_nasa():
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["style"] = "space"
    assert "nasa" in m._auto_sources(cfg)


def test_resolve_source_pinned():
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["source"] = "bing"
    assert m.resolve_source(cfg) == "bing"


def test_resolve_source_auto_picks_configured():
    cfg = m.DEFAULT_CONFIG.copy()
    with mock.patch.object(m.random, "choice", return_value="wallhaven"):
        assert m.resolve_source(cfg) == "wallhaven"


# ── _get retry ───────────────────────────────────────────────────────────────
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_get_success():
    with mock.patch.object(m.urllib.request, "urlopen", return_value=_FakeResp({"ok": True})):
        assert m._get("http://example.test/api") == {"ok": True}


def test_get_retries_on_429():
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) < 3:
            raise m.urllib.error.HTTPError("u", 429, "Too Many Requests", None, None)
        return _FakeResp({"ok": True})

    with mock.patch.object(m.time, "sleep"), \
         mock.patch.object(m.urllib.request, "urlopen", side_effect=flaky):
        assert m._get("http://example.test/api") == {"ok": True}
    assert len(calls) == 3


def test_get_does_not_retry_404():
    calls = []

    def fail(*a, **k):
        calls.append(1)
        raise m.urllib.error.HTTPError("u", 404, "Not Found", None, None)

    with mock.patch.object(m.time, "sleep"), \
         mock.patch.object(m.urllib.request, "urlopen", side_effect=fail):
        with pytest.raises(m.urllib.error.HTTPError):
            m._get("http://example.test/missing")
    assert len(calls) == 1


def test_get_gives_up_after_retries():
    def always_429(*a, **k):
        raise m.urllib.error.HTTPError("u", 429, "Too Many Requests", None, None)

    with mock.patch.object(m.time, "sleep") as sleep, \
         mock.patch.object(m.urllib.request, "urlopen", side_effect=always_429):
        with pytest.raises(m.urllib.error.HTTPError):
            m._get("http://example.test/api")
        # 3 attempts with 0.5s, 1s backoff
        assert sleep.call_count == 2


# ── Fetchers ─────────────────────────────────────────────────────────────────
def test_fetch_unsplash():
    payload = {
        "urls": {"full": "https://images.example.test/photo?ixid=1"},
        "links": {"html": "https://unsplash.com/p/1", "download_location": "https://api.unsplash.com/photos/1/dl"},
        "user": {"name": "Jane Photog"},
        "description": "Sunset",
        "location": {"name": "Lisbon"},
    }
    with mock.patch.object(m, "_get", return_value=payload), \
         mock.patch.object(m.urllib.request, "urlopen"):
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["unsplash_key"] = "k"
        cfg["resolution_width"] = 2560
        info = m.fetch_unsplash(cfg)
    assert info["source"] == "unsplash"
    assert "w=2560" in info["image_url"]
    assert info["photographer"] == "Jane Photog"


def test_fetch_wallhaven():
    payload = {"data": [{"path": "https://w.wallhaven.cc/full/1.jpg", "url": "https://wallhaven.cc/w/1",
                         "category": "anime", "resolution": "2560x1440"}]}
    with mock.patch.object(m, "_get", return_value=payload), \
         mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
        info = m.fetch_wallhaven(m.DEFAULT_CONFIG.copy())
    assert info["source"] == "wallhaven"
    assert info["image_url"].startswith("https://")


def test_fetch_wallhaven_no_results_raises():
    with mock.patch.object(m, "_get", return_value={"data": []}):
        with pytest.raises(ValueError, match="No Wallhaven results"):
            m.fetch_wallhaven(m.DEFAULT_CONFIG.copy())


def test_fetch_pexels():
    payload = {"photos": [{"src": {"original": "https://images.pexels.test/1.jpg"},
                           "url": "https://pexels.com/photo/1", "photographer": "P. E. Xels",
                           "alt": "Mountains"}]}
    with mock.patch.object(m, "_get", return_value=payload), \
         mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["pexels_key"] = "k"
        info = m.fetch_pexels(cfg)
    assert info["source"] == "pexels"
    assert info["description"] == "Mountains"


def test_fetch_pixabay():
    payload = {"hits": [{"largeImageURL": "https://cdn.pixabay.test/1.jpg",
                         "pageURL": "https://pixabay.com/1", "user": "Pix", "tags": "forest, trees"}]}
    with mock.patch.object(m, "_get", return_value=payload), \
         mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["pixabay_key"] = "k"
        info = m.fetch_pixabay(cfg)
    assert info["source"] == "pixabay"
    assert info["description"] == "Forest"


def test_fetch_reddit_success():
    post = {
        "data": {
            "is_video": False, "is_self": False,
            "url": "https://i.redd.it/abc.jpg",
            "preview": {"images": [{"source": {"width": 2560, "height": 1440}}]},
            "title": "A Mountain", "author": "photo_guy",
            "permalink": "/r/EarthPorn/comments/1/",
            "subreddit": "EarthPorn", "score": 500,
        }
    }
    payload = {"data": {"children": [post]}}
    with mock.patch.object(m, "_get", return_value=payload), \
         mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
        info = m.fetch_reddit(m.DEFAULT_CONFIG.copy())
    assert info["source"] == "reddit"
    assert info["photographer"] == "u/photo_guy"


def test_fetch_reddit_skips_videos_and_small():
    post = {
        "data": {
            "is_video": True, "is_self": False, "url": "https://i.redd.it/vid.mp4",
            "title": "Video", "author": "a", "permalink": "/r/x/1/",
            "subreddit": "x", "score": 1,
        }
    }
    small = {
        "data": {
            "is_video": False, "is_self": False,
            "url": "https://i.redd.it/small.jpg",
            "preview": {"images": [{"source": {"width": 800, "height": 600}}]},
            "title": "Small", "author": "b", "permalink": "/r/x/2/",
            "subreddit": "x", "score": 1,
        }
    }
    payload = {"data": {"children": [post, small]}}
    with mock.patch.object(m, "_get", return_value=payload):
        with pytest.raises(ValueError, match="No Reddit wallpapers"):
            m.fetch_reddit(m.DEFAULT_CONFIG.copy())


def test_fetch_nasa():
    payload = {"media_type": "image", "hdurl": "https://apod.nasa.gov/hd.jpg",
               "url": "https://apod.nasa.gov/small.jpg", "date": "2026-08-16",
               "copyright": "NASA", "title": "Andromeda"}
    with mock.patch.object(m, "_get", return_value=payload):
        info = m.fetch_nasa(m.DEFAULT_CONFIG.copy())
    assert info["source"] == "nasa"
    assert info["image_url"] == "https://apod.nasa.gov/hd.jpg"
    assert info["photo_url"] == "https://apod.nasa.gov/apod/ap260816.html"


def test_fetch_nasa_video_raises():
    with mock.patch.object(m, "_get", return_value={"media_type": "video"}):
        with pytest.raises(ValueError, match="not an image"):
            m.fetch_nasa(m.DEFAULT_CONFIG.copy())


def test_fetch_bing():
    payload = {"images": [{"urlbase": "/th?id=OHR.Test_ROW",
                           "url": "/th?id=OHR.Test_ROW_1920x1080.jpg",
                           "copyright": "© Test", "title": "Test Valley"}]}
    with mock.patch.object(m, "_get", return_value=payload), \
         mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
        info = m.fetch_bing(m.DEFAULT_CONFIG.copy())
    assert info["image_url"] == "https://www.bing.com/th?id=OHR.Test_ROW_UHD.jpg"
    assert info["source"] == "bing"


def test_fetch_bing_rejects_hostile_urlbase():
    for bad in ("https://evil.example/path", "//evil.example/path", "javascript:alert(1)"):
        payload = {"images": [{"urlbase": bad, "url": bad, "title": "t"}]}
        with mock.patch.object(m, "_get", return_value=payload), \
             mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
            with pytest.raises(ValueError, match="unexpected urlbase"):
                m.fetch_bing(m.DEFAULT_CONFIG.copy())


def test_fetch_deviantart_missing_creds_raises():
    cfg = m.DEFAULT_CONFIG.copy()
    with pytest.raises(ValueError, match="not configured"):
        m.fetch_deviantart(cfg)


def test_fetch_deviantart_with_token():
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["deviantart_client_id"] = "cid"
    cfg["deviantart_client_secret"] = "csec"
    m.DA_TOKEN_FILE.write_text(json.dumps({
        "access_token": "tok",
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
    }))
    search_payload = {"results": [{"tag_name": "landscape"}]}
    dev_payload = {"results": [{
        "is_mature": False,
        "content": {"src": "https://images.deviantart.test/1.jpg", "width": 1920, "height": 1080},
        "url": "https://deviantart.com/art/1", "title": "Misty Lake",
        "author": {"username": "da_artist"},
    }]}
    with mock.patch.object(m, "_get", side_effect=[search_payload, dev_payload]), \
         mock.patch.object(m.random, "choice", side_effect=lambda lst: lst[0]):
        info = m.fetch_deviantart(cfg)
    assert info["source"] == "deviantart"
    assert info["photographer"] == "da_artist"


# ── download_image ───────────────────────────────────────────────────────────
class _FakeBytesResp:
    def __init__(self, data, content_type="image/jpeg"):
        self.data = data
        self.headers = {"Content-Type": content_type}
        self._pos = 0

    def read(self, size=-1):
        if self._pos >= len(self.data):
            return b""
        chunk = self.data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_download_image_ok(tmp_path):
    dest = tmp_path / "current.jpg"
    with mock.patch.object(m.urllib.request, "urlopen", return_value=_FakeBytesResp(b"\xff\xd8jpegdata")):
        m.download_image("https://example.test/img.jpg", dest)
    assert dest.read_bytes() == b"\xff\xd8jpegdata"
    assert not list(tmp_path.glob("*.tmp"))


def test_download_image_rejects_non_image():
    with mock.patch.object(m.urllib.request, "urlopen",
                           return_value=_FakeBytesResp(b"<html>", content_type="text/html")):
        with pytest.raises(ValueError, match="non-image"):
            m.download_image("https://example.test/page", "/tmp/x.jpg")


def test_download_image_size_cap(tmp_path):
    dest = tmp_path / "big.jpg"
    huge = b"x" * (10 * 1024 * 1024)
    with mock.patch.object(m.urllib.request, "urlopen", return_value=_FakeBytesResp(huge)):
        with pytest.raises(ValueError, match="exceeded"):
            m.download_image("https://example.test/huge.jpg", dest, max_bytes=1024 * 1024)
    assert not dest.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_download_image_cleans_tmp_on_error(tmp_path):
    dest = tmp_path / "img.jpg"

    class _ExplodingResp(_FakeBytesResp):
        def read(self, size=-1):
            if self._pos > 3:
                raise ConnectionError("connection reset")
            return super().read(size)

    with mock.patch.object(m.urllib.request, "urlopen",
                           return_value=_ExplodingResp(b"\xff\xd8\xff\xe0jpegdata")):
        with pytest.raises(ConnectionError):
            m.download_image("https://example.test/img.jpg", dest)
    assert not dest.exists()
    assert not list(tmp_path.glob("*.tmp"))


# ── make_thumb ───────────────────────────────────────────────────────────────
def test_make_thumb_uses_magick_first():
    with mock.patch.object(m.shutil, "which",
                           side_effect=lambda t: "/usr/bin/magick" if t == "magick" else "/usr/bin/convert"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.return_value = mock.Mock()
        assert m.make_thumb("a.jpg", "b.jpg") is True
        assert run.call_args[0][0][0] == "magick"


def test_make_thumb_falls_back_to_convert():
    with mock.patch.object(m.shutil, "which",
                           side_effect=lambda t: None if t == "magick" else "/usr/bin/convert"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.return_value = mock.Mock()
        assert m.make_thumb("a.jpg", "b.jpg") is True
        assert run.call_args[0][0][0] == "convert"


def test_make_thumb_neither_tool():
    with mock.patch.object(m.shutil, "which", return_value=None):
        assert m.make_thumb("a.jpg", "b.jpg") is False


# ── apply_wallpaper ──────────────────────────────────────────────────────────
def test_apply_wallpaper_encodes_uri():
    with mock.patch.object(m.shutil, "which", return_value="/usr/bin/gsettings"), \
         mock.patch.object(m.subprocess, "run") as run:
        m.apply_wallpaper("/home/John Doe/Pictures/wallpapers/current.jpg")
    uris = [c[0][0][-1] for c in run.call_args_list]
    assert all("John%20Doe" in u for u in uris)
    assert all(u.startswith("file://") for u in uris)


def test_apply_wallpaper_no_gsettings():
    with mock.patch.object(m.shutil, "which", return_value=None):
        m.apply_wallpaper("/tmp/x.jpg")  # must not raise


# ── update_cron ──────────────────────────────────────────────────────────────
def test_update_cron_no_crontab(fake_console):
    with mock.patch.object(m.shutil, "which", return_value=None):
        assert m.update_cron(3) is False


def test_update_cron_adds_line():
    with mock.patch.object(m.shutil, "which", side_effect=lambda t: "/usr/bin/crontab" if t == "crontab" else "/usr/local/bin/wallpaper"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.side_effect = [mock.Mock(stdout="# existing\n"), None]
        assert m.update_cron(6) is True
        written = run.call_args_list[1].kwargs["input"]
        assert "0 */6 * * * /usr/local/bin/wallpaper _fetch" in written
        assert "# existing" in written


def test_update_cron_replaces_old_line():
    with mock.patch.object(m.shutil, "which", side_effect=lambda t: "/usr/bin/crontab" if t == "crontab" else "/usr/local/bin/wallpaper"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.side_effect = [mock.Mock(stdout="0 */3 * * * /usr/local/bin/wallpaper _fetch\n"), None]
        assert m.update_cron(12) is True
        written = run.call_args_list[1].kwargs["input"]
        assert "*/12" in written and "*/3" not in written
        assert written.count("_fetch") == 1


def test_update_cron_quotes_spaced_path():
    with mock.patch.object(m.shutil, "which", side_effect=lambda t: "/usr/bin/crontab" if t == "crontab" else "/home/John Doe/.local/bin/wallpaper"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.side_effect = [mock.Mock(stdout=""), None]
        assert m.update_cron(3) is True
        written = run.call_args_list[1].kwargs["input"]
        assert "'/home/John Doe/.local/bin/wallpaper' _fetch" in written


# ── cmd_set ──────────────────────────────────────────────────────────────────
def _set_args(setting, *values):
    return mock.Mock(setting=setting, value=list(values))


def test_cmd_set_query(fake_console):
    m.cmd_set(_set_args("query", "rainy", "city"))
    assert m.load_config()["query"] == "rainy city"


def test_cmd_set_style(fake_console):
    m.cmd_set(_set_args("style", "cyberpunk"))
    assert m.load_config()["style"] == "cyberpunk"


def test_cmd_set_style_invalid(fake_console):
    with mock.patch.object(m, "cmd_styles"):
        m.cmd_set(_set_args("style", "bogus"))
    assert m.load_config()["style"] == "realistic"


def test_cmd_set_source(fake_console):
    m.cmd_set(_set_args("source", "bing"))
    assert m.load_config()["source"] == "bing"


def test_cmd_set_source_invalid(fake_console):
    m.cmd_set(_set_args("source", "bogus"))
    assert m.load_config()["source"] == "auto"


def test_cmd_set_interval_lowercase(fake_console):
    with mock.patch.object(m.shutil, "which", return_value="/usr/bin/crontab"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.side_effect = [mock.Mock(stdout=""), None]
        m.cmd_set(_set_args("interval", "6h"))
    assert m.load_config()["interval_hours"] == 6


def test_cmd_set_interval_uppercase(fake_console):
    with mock.patch.object(m.shutil, "which", return_value="/usr/bin/crontab"), \
         mock.patch.object(m.subprocess, "run") as run:
        run.side_effect = [mock.Mock(stdout=""), None]
        m.cmd_set(_set_args("interval", "3H"))
    assert m.load_config()["interval_hours"] == 3


def test_cmd_set_interval_invalid(fake_console):
    m.cmd_set(_set_args("interval", "abc"))
    assert m.load_config()["interval_hours"] == 3


def test_cmd_set_resolution(fake_console):
    m.cmd_set(_set_args("resolution", "2560"))
    assert m.load_config()["resolution_width"] == 2560


def test_cmd_set_resolution_too_small(fake_console):
    m.cmd_set(_set_args("resolution", "100"))
    assert m.load_config()["resolution_width"] == 3840


def test_cmd_set_resolution_garbage(fake_console):
    m.cmd_set(_set_args("resolution", "huge"))
    assert m.load_config()["resolution_width"] == 3840


def test_cmd_set_color(fake_console):
    m.cmd_set(_set_args("color", "teal"))
    assert m.load_config()["color"] == "teal"


def test_cmd_set_color_none(fake_console):
    m.cmd_set(_set_args("color", "none"))
    assert m.load_config()["color"] is None


def test_cmd_set_api_keys(fake_console):
    m.cmd_set(_set_args("unsplash_key", "uk"))
    m.cmd_set(_set_args("pexels_key", "pk"))
    m.cmd_set(_set_args("pixabay_key", "pbk"))
    m.cmd_set(_set_args("nasa_key", "demo"))
    m.cmd_set(_set_args("deviantart_id", "cid"))
    m.cmd_set(_set_args("deviantart_secret", "csec"))
    cfg = m.load_config()
    assert cfg["unsplash_key"] == "uk"
    assert cfg["pexels_key"] == "pk"
    assert cfg["pixabay_key"] == "pbk"
    assert cfg["nasa_key"] == "DEMO_KEY"
    assert cfg["deviantart_client_id"] == "cid"
    assert cfg["deviantart_client_secret"] == "csec"


# ── do_fetch end-to-end ──────────────────────────────────────────────────────
def _patch_fetchers(**replacements):
    """Patch FETCHERS dict entries (the dict holds original function refs)."""
    return mock.patch.dict(m.FETCHERS, replacements, clear=False)


def test_do_fetch_auto_success(fake_console, tmp_path):
    wallhaven_info = {
        "image_url": "https://example.test/w.jpg",
        "photo_url": "https://wallhaven.cc/w/1",
        "photographer": None,
        "description": "Art 2560x1440",
        "location": None,
        "source": "wallhaven",
    }
    with mock.patch.object(m, "_auto_sources", return_value=["wallhaven"]), \
         mock.patch.object(m.random, "shuffle"), \
         _patch_fetchers(wallhaven=lambda cfg: wallhaven_info), \
         mock.patch.object(m, "download_image"), \
         mock.patch.object(m, "make_thumb", return_value=False), \
         mock.patch.object(m, "apply_wallpaper"), \
         mock.patch.object(m, "notify"):
        entry = m.do_fetch(silent=True)
    assert entry is not None
    assert entry["source"] == "wallhaven"
    assert entry["description"] == "Art 2560x1440"
    hist = m.load_history()
    assert hist[-1]["source"] == "wallhaven"


def test_do_fetch_auto_all_sources_fail(fake_console):
    with mock.patch.object(m, "_auto_sources", return_value=["wallhaven", "reddit"]), \
         mock.patch.object(m.random, "shuffle"), \
         _patch_fetchers(wallhaven=lambda cfg: (_ for _ in ()).throw(ValueError("no")),
                         reddit=lambda cfg: (_ for _ in ()).throw(ValueError("no"))):
        assert m.do_fetch(silent=True) is None
    assert m.load_history() == []


def test_do_fetch_pinned_source_error(fake_console):
    cfg = m.load_config()
    cfg["source"] = "unsplash"
    m.save_config(cfg)
    with _patch_fetchers(unsplash=lambda cfg: (_ for _ in ()).throw(ValueError("bad key"))):
        assert m.do_fetch(silent=True) is None


def test_do_fetch_unknown_source_defensive_branch(fake_console):
    """Config sanitization makes 'bogus' unreachable; exercise the guard anyway."""
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["source"] = "bogus"  # bypass load_config sanitization
    with mock.patch.object(m, "load_config", return_value=cfg), \
         mock.patch.object(m, "resolve_source", return_value="bogus"):
        assert m.do_fetch(silent=True) is None


def test_do_fetch_download_failure_no_history(fake_console):
    bing_info = {
        "image_url": "https://example.test/b.jpg",
        "photo_url": "https://bing.com/1", "photographer": None,
        "description": "Bing", "location": None, "source": "bing",
    }
    with mock.patch.object(m, "_auto_sources", return_value=["bing"]), \
         mock.patch.object(m.random, "shuffle"), \
         _patch_fetchers(bing=lambda cfg: bing_info), \
         mock.patch.object(m, "download_image", side_effect=ValueError("timeout")):
        assert m.do_fetch(silent=True) is None
    assert m.load_history() == []


def test_cmd_internal_fetch_exit_codes(fake_console):
    with mock.patch.object(m, "do_fetch", return_value={"description": "x"}), \
         mock.patch.object(m.sys, "exit") as ex:
        m.cmd_internal_fetch()
        ex.assert_called_once_with(0)
    with mock.patch.object(m, "do_fetch", return_value=None), \
         mock.patch.object(m.sys, "exit") as ex:
        m.cmd_internal_fetch()
        ex.assert_called_once_with(1)


# ── presets commands ─────────────────────────────────────────────────────────
def test_apply_preset_updates_config(fake_console):
    m.save_presets({"galaxy": {"style": "space", "source": "nasa", "query": "nebula",
                               "color": None, "interval_hours": 24}})
    with mock.patch.object(m, "update_cron") as uc:
        m._apply_preset("galaxy", m.load_presets()["galaxy"])
    cfg = m.load_config()
    assert cfg["_preset"] == "galaxy"
    assert cfg["style"] == "space"
    assert cfg["interval_hours"] == 24
    uc.assert_called_once_with(24)


def test_cmd_delete_preset(fake_console):
    m.save_presets({"one": {"style": "dark", "source": "auto", "query": "moody",
                            "color": None, "interval_hours": 3}})
    m.cmd_delete(argparse.Namespace(name="one"))
    assert "one" not in m.load_presets()


def test_cmd_delete_missing_preset(fake_console):
    m.cmd_delete(argparse.Namespace(name="nope"))  # must not raise


def test_cmd_use_preset(fake_console):
    m.save_presets({"forest": {"style": "nature", "source": "auto", "query": "trees",
                               "color": "green", "interval_hours": 6}})
    with mock.patch.object(m, "update_cron"):
        m.cmd_use(argparse.Namespace(name="forest"))
    assert m.load_config()["_preset"] == "forest"
    assert m.load_config()["query"] == "trees"


def test_cmd_restore_defaults(fake_console):
    m.save_presets({"x": {"style": "dark", "source": "auto", "query": "q",
                          "color": None, "interval_hours": 3}})
    q = mock.Mock()
    q.confirm.return_value.ask.return_value = True
    m.cmd_restore_defaults(q)
    assert m.load_presets() == {}


# ── history command ──────────────────────────────────────────────────────────
def test_cmd_history_empty(fake_console):
    m.cmd_history(mock.Mock(limit=10))  # must not raise


def test_cmd_history_limits(fake_console):
    for i in range(30):
        m.append_history({"date": datetime.now().isoformat(), "description": str(i),
                          "photographer": "p", "location": None, "query": "q",
                          "style": "realistic", "source": "bing"})
    m.cmd_history(mock.Mock(limit=5))  # must not raise


# ── status command ───────────────────────────────────────────────────────────
def test_cmd_status_empty(fake_console):
    m.cmd_status()  # must not raise


def test_cmd_status_with_history(fake_console):
    m.append_history({"date": datetime.now().isoformat(), "description": "Aurora",
                      "photographer": "p", "location": "Norway", "query": "sky",
                      "style": "space", "source": "nasa"})
    m.cmd_status()  # must not raise


# ── CLI dispatch ─────────────────────────────────────────────────────────────
def test_cli_version():
    with mock.patch.object(m.sys, "argv", ["wallpaper", "--version"]), \
         pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 0


def test_cli_fetch_internal_dispatch(fake_console):
    with mock.patch.object(m.sys, "argv", ["wallpaper", "_fetch"]), \
         mock.patch.object(m, "cmd_internal_fetch") as cif:
        m.main()
        cif.assert_called_once()
