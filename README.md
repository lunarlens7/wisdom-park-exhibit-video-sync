# Wisdom Park Exhibit — Video Sync Lighting Controller

Plays videos on one or more monitors and syncs Tapo L530 lights and P100 switches to the playback position.

## Requirements

- macOS or Windows
- Python 3.11+

## Setup

**1. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**2. Set Tapo credentials**

Copy `.env.example` to `.env` and fill in your Tapo account details:

```bash
cp .env.example .env
```

```ini
TAPO_EMAIL=you@example.com
TAPO_PASSWORD=yourpassword
```

The `.env` file is gitignored — credentials are never committed. You can also set `TAPO_EMAIL` and `TAPO_PASSWORD` as regular shell environment variables if you prefer.

**3. Edit `config.yaml`**

Set your video files, monitor layout, device IPs, and cue list:

```yaml
video:
  loop: true
  fullscreen: false
  screens:
    - path: "video1.mp4"       # first video (drives cue timing)
      window_title: "Screen 1"
      monitor: 0               # primary monitor
    - path: "video2.mp4"       # second video (plays alongside)
      window_title: "Screen 2"
      monitor: 1               # secondary monitor

devices:
  main_light:
    type: l530
    ip: "192.168.1.100"
    initial_state:
      on: true
      brightness: 100
      hue: 30
      saturation: 80

  stage_switch:
    type: p100
    ip: "192.168.1.101"
    initial_state:
      on: false

cues:
  - at: 5
    device: main_light
    action: fade
    to_brightness: 20
    to_hue: 200
    to_saturation: 100
    duration: 5.0

  - at: 10
    device: stage_switch
    action: "on"
```

The `monitor` index follows the OS display order (0 = primary, 1 = secondary, etc.). If you only have one screen, remove the second entry under `screens`.

If you don't know your device IPs, use the discover command (below).

## Usage

```bash
# Start the show (videos open automatically)
python main.py run        # Windows
python3 main.py run       # macOS

# Find Tapo devices on your local network
python main.py discover

# Use a different config file
python main.py run /path/to/other-config.yaml
```

Press `q` in any video window to quit.

## Cue types

| Action | Device | Description |
|---|---|---|
| `fade` | l530 | Smooth transition of brightness/hue/saturation over `duration` seconds |
| `set_light` | l530 | Instant change of brightness/hue/saturation |
| `"on"` | p100 | Turn switch on |
| `"off"` | p100 | Turn switch off |

Cue timings are driven by the first screen's video position. Quote `"on"` and `"off"` in the YAML to prevent them being parsed as booleans.

## Moving to a new network

Run `python main.py discover` to find new device IPs, then update `config.yaml`.
