# wallpaper-cli

A feature-rich wallpaper manager for Linux/GNOME with an interactive terminal UI.
Pulls images from multiple sources, rotates automatically on a schedule, and supports
presets so you can switch themes with a single command.

```
╭──────────────── 🖼  Wallpaper CLI ────────────────╮
│  last:  "Milky Way Over the Alps"  ·  nasa  ·  2h ago  │
│  mode:  🚀 space  ·  ⚙ auto  ·  every 24h            │
╰───────────────────────────────────────────────────╯

  j/k ↑↓ navigate   Enter select   Ctrl+C exit

? What would you like to do?
❯  🔄  Fetch new wallpaper now
   ⭐  Browse featured presets
   🎨  Switch active preset
   ✏   Create custom preset
   ...
```

## Image sources

| Source | Free | Requires key |
|---|---|---|
| 🌐 Wallhaven | ✅ | No |
| 🌍 Bing Daily | ✅ | No |
| 💬 Reddit | ✅ | No |
| 🚀 NASA APOD | ✅ | Optional (higher quota) |
| 🌄 Unsplash | ✅ | Yes (free) |
| 📸 Pexels | ✅ | Yes (free) |
| 🖼  Pixabay | ✅ | Yes (free) |
| 🎭 DeviantArt | ✅ | Yes (free OAuth app) |

Four sources (Wallhaven, Bing, Reddit, NASA) work with **no API keys at all**.

## Requirements

- Linux with GNOME desktop (uses `gsettings` to set the wallpaper)
- Python 3.9+
- `pipx` (recommended) or `pip`

## Installation

### With pipx (recommended for CLI tools)

```bash
# install pipx if you don't have it
sudo apt install pipx   # Ubuntu/Debian
pipx ensurepath

# install wallpaper-cli
pipx install git+https://github.com/MLPK-1/wallpaper-cli
```

### With pip

```bash
pip install --user git+https://github.com/MLPK-1/wallpaper-cli
```

After installation the `wallpaper` command is available in your terminal.

## First-time setup

Run the interactive menu:

```bash
wallpaper
```

The app works immediately using free sources (Wallhaven, Bing, Reddit, NASA APOD).
To add more sources, run **Setup API keys** from the menu, or:

```bash
wallpaper setup
```

Keys are stored locally in `~/.config/wallpaper/config.json` and never leave your machine.

## Usage

```
wallpaper                   open interactive menu (default)
wallpaper now               fetch a new wallpaper immediately
wallpaper setup             configure API keys
wallpaper featured          browse built-in presets
wallpaper new               create a custom preset
wallpaper use "My Preset"   switch to a saved preset
wallpaper presets           list all saved presets
wallpaper status            show current config and source status
wallpaper history           show recent wallpaper history
```

## Styles

| Style | Description |
|---|---|
| `realistic` | Photos of nature, cities, landscapes |
| `anime` | Illustrated anime and manga art |
| `space` | Astronomy and space photography |
| `minimal` | Clean, simple, minimalist designs |
| `dark` | Dark-themed art and photography |
| `custom` | Freeform — driven entirely by your query |

## Featured presets

Ten built-in presets are included (accessible from the menu or `wallpaper featured`):

- 🚀 NASA Photo of the Day
- 🌍 Bing World Scenery
- 🌸 Painted Landscapes
- 🏙 Cyberpunk Cities
- 🎮 Pixel Art Landscapes
- 💮 Anime Illustrations
- ✨ Deep Space
- 🎵 Lo-Fi Aesthetic
- ◻ Minimal Dark
- 🐉 Fantasy Worlds

## Automatic rotation (GNOME cron)

From the menu go to **Change settings → Interval** to set a rotation interval.
The app installs a cron job that runs `wallpaper _fetch` on that schedule.

## Optional: keyboard shortcut

To bind a key to fetch a new wallpaper instantly, add a custom shortcut in
**GNOME Settings → Keyboard → Custom Shortcuts** with the command `wallpaper now`.

A common choice is `Ctrl+Alt+M`.

## Upgrading

```bash
pipx upgrade wallpaper-cli
# or
pipx install --force git+https://github.com/MLPK-1/wallpaper-cli
```

## Uninstalling

```bash
pipx uninstall wallpaper-cli
```

Config and history are kept in `~/.config/wallpaper/` — delete that folder to fully clean up.

## Image licenses and copyright

**wallpaper-cli is a tool, not a content provider.** All images are fetched live from
third-party services at your request. Each image is subject to the license of its
original source:

| Source | License / terms |
|---|---|
| NASA APOD | U.S. government works — generally public domain. Some images credit contractors and may differ — check the APOD page. |
| Wallhaven | Images are user-submitted. License varies per image. For personal desktop use. |
| Reddit | Images are posted by users. License varies. For personal desktop use. |
| Unsplash | [Unsplash License](https://unsplash.com/license) — free for personal and commercial use, no attribution required. |
| Pexels | [Pexels License](https://www.pexels.com/license/) — free for personal use. |
| Pixabay | [Pixabay License](https://pixabay.com/service/license-summary/) — free for personal use. |
| DeviantArt | Images are copyrighted by their creators. For personal desktop use. |
| Bing Daily | Images are licensed by Microsoft. Bing does not publish an official API for these — this uses an undocumented endpoint. For personal desktop use only. |

**This tool is intended for personal desktop wallpaper use only.** Do not redistribute,
sell, or publish images obtained through it without verifying the license of each image.
The tool's own code is MIT licensed — that applies only to the software itself, not to
any images it downloads.
