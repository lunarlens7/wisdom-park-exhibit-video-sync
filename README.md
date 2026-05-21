# Wisdom Park Exhibit — Video Sync Lighting Controller

Syncs Tapo L530 smart lights and P100 switches to VLC video playback.

## Requirements

- macOS
- Python 3.11+
- VLC media player

## Setup

**1. Install Python dependencies**

```bash
pip3 install -r requirements.txt
```

**2. Configure VLC**

Launch VLC with its HTTP interface enabled:

```bash
/Applications/VLC.app/Contents/MacOS/VLC \
  --extraintf http \
  --http-password tapo_sync \
  --http-port 8080 \
  /path/to/your/video.mp4
```

Or enable it permanently in VLC: `VLC menu → Preferences → Interface → Main interfaces → Web`.

**3. Set Tapo credentials**

Copy `.env.example` to `.env` and fill in your Tapo account details:

```bash
cp .env.example .env
```

```ini
TAPO_EMAIL=you@example.com
TAPO_PASSWORD=yourpassword
```

The `.env` file is gitignored — credentials are never committed. You can also set `TAPO_EMAIL` and `TAPO_PASSWORD` as regular shell environment variables if you prefer.

**4. Edit `config.yaml`**

Fill in your device IPs and cue list. See `config.yaml` for the full format.

If you don't know your device IPs, use the discover command (below).

## Usage

```bash
# Start the sync engine (VLC must be running first)
python3 main.py run

# Find Tapo devices on your local network
python3 main.py discover

# Use a different config file
python3 main.py run /path/to/other-config.yaml
```

## Cue types

| Action | Device | Description |
|---|---|---|
| `fade` | l530 | Smooth transition of brightness/hue/saturation over `duration` seconds |
| `set_light` | l530 | Instant change of brightness/hue/saturation |
| `on` | p100 | Turn switch on |
| `off` | p100 | Turn switch off |

## Moving to a new network

Run `python3 main.py discover` to find new IPs, then update `config.yaml`.
