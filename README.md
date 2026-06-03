# Wisdom Park Exhibit — Video Sync Lighting Controller

Plays videos on one or more monitors and syncs Tapo smart lights (L530, L630) and switches (P100) to the playback position.

## Requirements

- macOS or Windows
- Python 3.11+

## Windows: ffpyplayer installation

`ffpyplayer` compiles a C extension on install. This can fail on Windows even after installing the C++ Build Tools. Try these steps in order.

**Option 1 — Use a Developer Command Prompt**

Even with Build Tools installed, a regular PowerShell or Command Prompt window may not have the compiler on its PATH. Use the specialised prompt that ships with Build Tools:

1. Open the **Start menu** and search for **Developer Command Prompt for VS**
2. `cd` to the project directory
3. Run `pip install -r requirements.txt`

**Option 2 — Install C++ Build Tools (if not done yet)**

1. Download the installer from https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Select **Desktop development with C++** and complete the installation
3. Restart your terminal, then retry Option 1 above

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

  stage_switch:
    type: p100
    ip: "192.168.1.101"
    initial_state:
      on: false

cues:
  - at: 5
    devices: [main_light]
    action: fade
    to_brightness: 20
    duration: 5.0

  - at: 10
    devices: [stage_switch]
    action: "on"
```

The `monitor` index follows the OS display order (0 = primary, 1 = secondary, etc.). If you only have one screen, remove the second entry under `screens`.

If you don't know your device IPs, use the discover command (below), or run the GUI and click **Verify System** — it discovers devices and updates the config automatically.

## GUI (Windows)

`gui.py` is the primary interface for exhibit operation. It guides staff through setup verification before allowing the show to run.

```bash
python gui.py        # Windows
python3 gui.py       # macOS
```

**Verification checks (click Verify System):**
- Connected to the Exhibition WiFi (192.168.8.x subnet)
- All 6 Tapo devices found on the network
- Device IP addresses match `config.yaml` — mismatches are corrected automatically

After verification passes, the ready state is applied to all devices (overheads dim, spotlights at 50%, stage switch on).

**Buttons:**
| Button | Available when | Action |
|---|---|---|
| Verify System | Always | Runs setup checks and applies ready state |
| Start Program | Verified | Starts the show |
| Shut Down Lights | Verified | Turns off all devices |
| Cancel Show & Reset | Running | Stops the show and returns to verified state |

**Arduino button** (requires `hotkey.py` running — see below):
- Press while verified → starts the show
- Press while running → cancels the show and returns to verified state
- Press while unverified → does nothing

## Arduino button integration

`hotkey.py` listens on the Arduino serial port (COM4) and signals the GUI when the button is pressed. Run it in a separate terminal alongside `gui.py`:

```bash
python hotkey.py
```

When the Arduino sends `TRIGGER_KEYS`, `hotkey.py` writes a `.trigger` file that the GUI picks up within 200 ms. The GUI enforces the state checks — the button has no effect until verification has passed.

To change the COM port, edit `ARDUINO_PORT` at the top of `hotkey.py`.

## CLI usage

The show can also be run directly from the command line without the GUI:

```bash
# Start the show (videos open automatically)
python main.py run        # Windows
python3 main.py run       # macOS

# Seek to a position and pause before starting
python main.py run --preview 230     # pause at 2m10s, devices set to that state; SPACE to resume

# Start playback from a specific position (no pause)
python main.py run --seek 120        # start at 2m00s

# Turn off all devices defined in config
python main.py lights-off

# Find Tapo devices on your local network
python main.py discover

# Use a different config file
python main.py run /path/to/other-config.yaml
```

## Cue types

| Action | Device | Description |
|---|---|---|
| `fade` | l530, l630 | Smooth brightness transition over `duration` seconds |
| `set_light` | l530, l630 | Instant brightness change |
| `"on"` | l530, l630, p100 | Turn device on |
| `"off"` | l530, l630, p100 | Turn device off |

Cue timings are driven by the first screen's video position. Quote `"on"` and `"off"` in the YAML to prevent them being parsed as booleans.

## Building a Windows executable

Run `build_windows.bat` on the Windows machine to produce `dist\ExhibitController.exe`:

```bat
build_windows.bat
```

The `config.yaml` and `.env` files must sit next to the executable at runtime — copy them alongside the `.exe` after building.

## Running tests

```bash
python -m pytest tests/ -v      # Windows
python3 -m pytest tests/ -v     # macOS
```

## Moving to a new network

Run `python main.py discover` to find new device IPs and update `config.yaml`, or open the GUI and click **Verify System** — it detects IP changes and updates the config automatically.
