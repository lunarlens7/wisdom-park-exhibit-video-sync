# Video-Synced Lighting Controller — Design Spec

**Date:** 2026-05-21
**Status:** Approved

## Overview

A Python CLI app that tracks VLC video playback position and triggers Tapo smart device actions (L530 light fades/color changes, P100 switch toggles) at configured timestamps. Intended for a Wisdom Park museum exhibit where lighting must stay in sync with a looping video.

---

## Architecture

Four modules wired together by `main.py`:

```
┌─────────────────────────────────────────────────┐
│                   main.py                        │
│                                                  │
│  ┌──────────┐   ┌──────────┐   ┌─────────────┐  │
│  │  VLC     │   │  Cue     │   │  Device     │  │
│  │  Poller  │──▶│  Engine  │──▶│  Controller │  │
│  └──────────┘   └──────────┘   └─────────────┘  │
│                      │                           │
│                 ┌────▼─────┐                     │
│                 │  config  │                     │
│                 │  .yaml   │                     │
│                 └──────────┘                     │
└─────────────────────────────────────────────────┘
```

- **VLC Poller** (`vlc_poller.py`) — polls VLC's HTTP interface every 200ms, returns current playback position in seconds as a float
- **Cue Engine** (`cue_engine.py`) — loads the YAML config, tracks which cues have fired, triggers actions when playback position crosses a cue's timestamp; resets cues when video is seeked backward
- **Device Controller** (`device_controller.py`) — wraps `python-tapo`; exposes `set_light()`, `fade()`, `set_switch()`; fades run as independent asyncio tasks so they don't block the sync loop
- **Discovery** (`discovery.py`) — UDP broadcast scan for Tapo devices on the local network; used for one-time setup when moving to a new network

**Concurrency:** Python asyncio. The main loop polls VLC and checks cues; fade tasks run concurrently without blocking position tracking.

---

## Config File Format

Single `config.yaml` the user edits. All device names are arbitrary labels.

```yaml
tapo:
  email: "you@example.com"
  password: "yourpassword"

vlc:
  host: "localhost"
  port: 8080
  password: "tapo_sync"
  poll_interval: 0.2   # seconds between VLC polls

devices:
  main_light:
    type: l530
    ip: "192.168.1.101"
    initial_state:
      on: true
      brightness: 100
      hue: 30          # 0–360
      saturation: 80   # 0–100

  stage_switch:
    type: p100
    ip: "192.168.1.102"
    initial_state:
      on: false

cues:
  # Fade brightness and color over 5 seconds starting at 10.5s
  - at: 10.5
    device: main_light
    action: fade
    to_brightness: 20
    to_hue: 200
    to_saturation: 100
    duration: 5.0

  # Instant switch toggle
  - at: 30.0
    device: stage_switch
    action: on

  # Instant light state change
  - at: 45.0
    device: main_light
    action: set_light
    brightness: 80
    hue: 120
    saturation: 60

  - at: 60.0
    device: stage_switch
    action: off
```

### Cue rules

- `action: fade` — smoothly transitions any specified properties (`to_brightness`, `to_hue`, `to_saturation`) from current tracked state to target over `duration` seconds. Omitted properties stay unchanged.
- `action: set_light` — instant change to specified properties. Omitted properties stay unchanged.
- `action: on` / `action: off` — for P100 switches only.
- Cues are **one-shot**: fire once, then skip on subsequent polls. Reset when video is seeked backward past their timestamp.

---

## VLC Setup

VLC must be launched with its HTTP interface enabled:

```bash
vlc --intf http --http-password tapo_sync --http-port 8080 your_video.mp4
```

Or set permanently in VLC: `Tools → Preferences → Interface → Main interfaces → Web`.

The poller reads `http://<host>:<port>/requests/status.json` and extracts the `time` field.

---

## CLI

```bash
# Install dependencies
pip install -r requirements.txt

# Apply initial device states and start sync engine
python main.py run

# Scan local network and print found Tapo devices with IPs
python main.py discover
```

---

## Project Structure

```
wisdom-park-exhibit-video-sync/
├── main.py                # CLI entry point
├── config.yaml            # user-edited config
├── vlc_poller.py          # VLC HTTP polling
├── cue_engine.py          # cue loading, state tracking, triggering
├── device_controller.py   # python-tapo wrapper, fade logic
├── discovery.py           # UDP broadcast device discovery
├── requirements.txt
└── README.md              # setup instructions
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| VLC not running / unreachable | Print message, retry every 2s; do not crash |
| Tapo device unreachable | Log warning, skip cue; show continues |
| Bad config (missing field, wrong type) | Validate on startup, print exact error, exit cleanly |
| Video seeked backward | Reset cues ahead of new position so they re-fire |
| Video loops / seeks to near 0 | Re-apply all `initial_state` values and reset all cues |

---

## Out of Scope (MVP)

- GUI or timeline editor
- Tapo cloud API (local network only)
- Multiple simultaneous videos
- Color temperature control (Kelvin mode) — hue/saturation covers the exhibit's needs
