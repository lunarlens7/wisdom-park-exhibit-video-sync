# Video-Synced Lighting Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI app that polls VLC for playback position and triggers Tapo L530 light fades/color changes and P100 switch toggles at configured timestamps.

**Architecture:** An asyncio event loop polls VLC's HTTP interface every 200ms and feeds the current time to a cue engine that fires device actions. Fades run as concurrent asyncio tasks so they don't block the sync loop. All configuration lives in a single `config.yaml`.

**Tech Stack:** Python 3.13+, `aiohttp` (VLC polling), `plugp100` (Tapo device control), `PyYAML` (config), `pytest` + `pytest-asyncio` (tests)

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | CLI entry point — `run` and `discover` subcommands |
| `config.py` | Load and validate `config.yaml`; define dataclasses for all config types |
| `vlc_poller.py` | Poll VLC HTTP interface; return current playback position in seconds |
| `cue_engine.py` | Track cue state, compare playback position, fire actions, handle seek-back |
| `device_controller.py` | Wrap `plugp100`; expose `set_light()`, `fade()`, `set_switch()`; run fades as asyncio tasks |
| `discovery.py` | Scan local network for Tapo devices via `plugp100` discovery |
| `config.yaml` | User-edited show configuration (not tested, used as fixture in tests) |
| `requirements.txt` | Pinned dependencies |
| `README.md` | Setup and usage instructions |
| `tests/test_config.py` | Config loading and validation tests |
| `tests/test_vlc_poller.py` | VLC poller tests (mock HTTP) |
| `tests/test_cue_engine.py` | Cue engine state machine tests |
| `tests/test_device_controller.py` | Device controller tests (mock Tapo) |

---

## Task 1: Project scaffold and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
aiohttp>=3.9.5
PyYAML>=6.0.1
plugp100>=5.1.7
pytest>=9.0.0
pytest-asyncio>=1.3.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip3 install -r requirements.txt
```

Expected: All packages install without error. Verify with:
```bash
pip3 show plugp100 aiohttp PyYAML pytest pytest-asyncio
```

- [ ] **Step 3: Create `config.yaml` with example values**

```yaml
tapo:
  email: "you@example.com"
  password: "yourpassword"

vlc:
  host: "localhost"
  port: 8080
  password: "tapo_sync"
  poll_interval: 0.2

devices:
  main_light:
    type: l530
    ip: "192.168.1.101"
    initial_state:
      on: true
      brightness: 100
      hue: 30
      saturation: 80

  stage_switch:
    type: p100
    ip: "192.168.1.102"
    initial_state:
      on: false

cues:
  - at: 10.5
    device: main_light
    action: fade
    to_brightness: 20
    to_hue: 200
    to_saturation: 100
    duration: 5.0

  - at: 30.0
    device: stage_switch
    action: on

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

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 5: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config.yaml pytest.ini tests/__init__.py
git commit -m "feat: project scaffold and dependencies"
```

---

## Task 2: Config loading and validation

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
import pytest
from config import load_config, ConfigError

VALID_YAML = """
tapo:
  email: "test@example.com"
  password: "secret"

vlc:
  host: "localhost"
  port: 8080
  password: "vlcpass"
  poll_interval: 0.2

devices:
  main_light:
    type: l530
    ip: "192.168.1.101"
    initial_state:
      on: true
      brightness: 100
      hue: 30
      saturation: 80
  stage_switch:
    type: p100
    ip: "192.168.1.102"
    initial_state:
      on: false

cues:
  - at: 10.5
    device: main_light
    action: fade
    to_brightness: 20
    to_hue: 200
    to_saturation: 100
    duration: 5.0
  - at: 30.0
    device: stage_switch
    action: on
"""

def test_load_valid_config(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(VALID_YAML)
    cfg = load_config(str(f))
    assert cfg.tapo.email == "test@example.com"
    assert cfg.vlc.poll_interval == 0.2
    assert "main_light" in cfg.devices
    assert cfg.devices["main_light"].type == "l530"
    assert cfg.devices["main_light"].initial_state["brightness"] == 100
    assert len(cfg.cues) == 2

def test_missing_tapo_section(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text("vlc:\n  host: localhost\n  port: 8080\n  password: x\n  poll_interval: 0.2\ndevices: {}\ncues: []\n")
    with pytest.raises(ConfigError, match="tapo"):
        load_config(str(f))

def test_unknown_device_in_cue(tmp_path):
    bad = VALID_YAML.replace("main_light\n    action: fade", "nonexistent\n    action: fade")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="nonexistent"):
        load_config(str(f))

def test_unknown_device_type(tmp_path):
    bad = VALID_YAML.replace("type: l530", "type: unknown_model")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="unknown_model"):
        load_config(str(f))

def test_fade_cue_requires_duration(tmp_path):
    bad = VALID_YAML.replace("    duration: 5.0\n", "")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="duration"):
        load_config(str(f))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `config.py` doesn't exist yet.

- [ ] **Step 3: Implement `config.py`**

```python
from dataclasses import dataclass, field
from typing import Any
import yaml


class ConfigError(Exception):
    pass


@dataclass
class TapoConfig:
    email: str
    password: str


@dataclass
class VlcConfig:
    host: str
    port: int
    password: str
    poll_interval: float


@dataclass
class DeviceConfig:
    type: str
    ip: str
    initial_state: dict[str, Any]


@dataclass
class CueConfig:
    at: float
    device: str
    action: str
    duration: float | None = None
    to_brightness: int | None = None
    to_hue: int | None = None
    to_saturation: int | None = None
    brightness: int | None = None
    hue: int | None = None
    saturation: int | None = None


@dataclass
class AppConfig:
    tapo: TapoConfig
    vlc: VlcConfig
    devices: dict[str, DeviceConfig]
    cues: list[CueConfig]


VALID_DEVICE_TYPES = {"l530", "p100"}


def load_config(path: str) -> AppConfig:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")

    for section in ("tapo", "vlc", "devices", "cues"):
        if section not in raw:
            raise ConfigError(f"Missing required section: '{section}'")

    tapo = TapoConfig(
        email=raw["tapo"].get("email") or _require(raw["tapo"], "email", "tapo"),
        password=raw["tapo"].get("password") or _require(raw["tapo"], "password", "tapo"),
    )

    vlc_raw = raw["vlc"]
    vlc = VlcConfig(
        host=vlc_raw.get("host", "localhost"),
        port=vlc_raw.get("port", 8080),
        password=vlc_raw.get("password", ""),
        poll_interval=vlc_raw.get("poll_interval", 0.2),
    )

    devices: dict[str, DeviceConfig] = {}
    for name, d in (raw["devices"] or {}).items():
        dtype = d.get("type")
        if dtype not in VALID_DEVICE_TYPES:
            raise ConfigError(f"Unknown device type '{dtype}' for device '{name}'. Valid types: {sorted(VALID_DEVICE_TYPES)}")
        devices[name] = DeviceConfig(
            type=dtype,
            ip=d.get("ip") or _require(d, "ip", f"devices.{name}"),
            initial_state=d.get("initial_state", {}),
        )

    cues: list[CueConfig] = []
    for i, c in enumerate(raw["cues"] or []):
        device_name = c.get("device")
        if device_name not in devices:
            raise ConfigError(f"Cue {i}: references unknown device '{device_name}'")
        action = c.get("action")
        if action == "fade" and "duration" not in c:
            raise ConfigError(f"Cue {i} (fade at {c.get('at')}s): 'duration' is required for fade actions")
        cues.append(CueConfig(
            at=float(c["at"]),
            device=device_name,
            action=action,
            duration=c.get("duration"),
            to_brightness=c.get("to_brightness"),
            to_hue=c.get("to_hue"),
            to_saturation=c.get("to_saturation"),
            brightness=c.get("brightness"),
            hue=c.get("hue"),
            saturation=c.get("saturation"),
        ))

    return AppConfig(tapo=tapo, vlc=vlc, devices=devices, cues=cues)


def _require(d: dict, key: str, section: str) -> Any:
    val = d.get(key)
    if val is None:
        raise ConfigError(f"Missing required field '{key}' in section '{section}'")
    return val
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config loading and validation"
```

---

## Task 3: VLC poller

**Files:**
- Create: `vlc_poller.py`
- Create: `tests/test_vlc_poller.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_vlc_poller.py`:

```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from vlc_poller import VlcPoller

@pytest.mark.asyncio
async def test_returns_playback_position():
    poller = VlcPoller(host="localhost", port=8080, password="secret")
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"time": 42.5, "state": "playing"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("vlc_poller.aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session_cls.return_value = mock_session
        position = await poller.get_position()

    assert position == 42.5

@pytest.mark.asyncio
async def test_returns_none_when_vlc_unreachable():
    poller = VlcPoller(host="localhost", port=8080, password="secret")
    with patch("vlc_poller.aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_session_cls.return_value = mock_session
        position = await poller.get_position()

    assert position is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_vlc_poller.py -v
```

Expected: `ImportError` — `vlc_poller.py` doesn't exist yet.

- [ ] **Step 3: Implement `vlc_poller.py`**

```python
import aiohttp
from base64 import b64encode


class VlcPoller:
    def __init__(self, host: str, port: int, password: str):
        self._url = f"http://{host}:{port}/requests/status.json"
        token = b64encode(f":{password}".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}"}

    async def get_position(self) -> float | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=1.0)) as resp:
                    data = await resp.json()
                    return float(data["time"])
        except Exception:
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_vlc_poller.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add vlc_poller.py tests/test_vlc_poller.py
git commit -m "feat: VLC HTTP poller"
```

---

## Task 4: Device controller

**Files:**
- Create: `device_controller.py`
- Create: `tests/test_device_controller.py`

The device controller wraps `plugp100`. It maintains a **tracked state** dict per device (brightness, hue, saturation, on) that it updates after every command — this is what the cue engine uses to know the "from" values for fades.

**`plugp100` API used:**
- Connect: `DeviceConnectConfiguration(host, credentials)` → `await connect(config)` → `await device.update()`
- L530 (`TapoBulb`): `device.set_brightness(int)`, `device.set_hue_saturation(int, int)`, `device.turn_on()`, `device.turn_off()`
- P100 (`TapoPlug`): `device.turn_on()`, `device.turn_off()`
- Credentials: `AuthCredential(email, password)`

- [ ] **Step 1: Write failing tests**

Create `tests/test_device_controller.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from device_controller import DeviceController

def make_controller():
    return DeviceController(email="test@x.com", password="secret")

@pytest.mark.asyncio
async def test_set_switch_on(monkeypatch):
    ctrl = make_controller()
    mock_device = AsyncMock()
    monkeypatch.setattr(ctrl, "_get_p100", AsyncMock(return_value=mock_device))
    await ctrl.set_switch("192.168.1.1", True)
    mock_device.turn_on.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_switch_off(monkeypatch):
    ctrl = make_controller()
    mock_device = AsyncMock()
    monkeypatch.setattr(ctrl, "_get_p100", AsyncMock(return_value=mock_device))
    await ctrl.set_switch("192.168.1.1", False)
    mock_device.turn_off.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_light_updates_tracked_state(monkeypatch):
    ctrl = make_controller()
    mock_device = AsyncMock()
    monkeypatch.setattr(ctrl, "_get_l530", AsyncMock(return_value=mock_device))
    await ctrl.set_light("192.168.1.2", brightness=80, hue=120, saturation=60)
    state = ctrl.get_state("192.168.1.2")
    assert state["brightness"] == 80
    assert state["hue"] == 120
    assert state["saturation"] == 60

@pytest.mark.asyncio
async def test_set_light_partial_update_preserves_existing_state(monkeypatch):
    ctrl = make_controller()
    ctrl._state["192.168.1.2"] = {"brightness": 50, "hue": 30, "saturation": 80, "on": True}
    mock_device = AsyncMock()
    monkeypatch.setattr(ctrl, "_get_l530", AsyncMock(return_value=mock_device))
    await ctrl.set_light("192.168.1.2", brightness=90)
    state = ctrl.get_state("192.168.1.2")
    assert state["brightness"] == 90
    assert state["hue"] == 30    # unchanged
    assert state["saturation"] == 80  # unchanged

@pytest.mark.asyncio
async def test_set_light_warns_on_device_error(monkeypatch, capsys):
    ctrl = make_controller()
    monkeypatch.setattr(ctrl, "_get_l530", AsyncMock(side_effect=Exception("unreachable")))
    await ctrl.set_light("192.168.1.2", brightness=50)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out or "warning" in captured.out.lower()

@pytest.mark.asyncio
async def test_fade_interpolates_brightness(monkeypatch):
    ctrl = make_controller()
    ctrl._state["192.168.1.2"] = {"brightness": 100, "hue": 0, "saturation": 0, "on": True}
    calls = []
    async def fake_set_light(ip, brightness=None, hue=None, saturation=None):
        calls.append(brightness)
    monkeypatch.setattr(ctrl, "set_light", fake_set_light)
    await ctrl.fade("192.168.1.2", to_brightness=0, duration=0.1, steps=5)
    # Should have called set_light multiple times with decreasing brightness
    assert len(calls) >= 2
    assert calls[-1] == 0
    assert calls[0] > calls[-1]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_device_controller.py -v
```

Expected: `ImportError` — `device_controller.py` doesn't exist yet.

- [ ] **Step 3: Implement `device_controller.py`**

```python
import asyncio
from typing import Any
from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration


class DeviceController:
    def __init__(self, email: str, password: str):
        self._credentials = AuthCredential(email, password)
        self._state: dict[str, dict[str, Any]] = {}

    def get_state(self, ip: str) -> dict[str, Any]:
        return self._state.get(ip, {})

    def set_state(self, ip: str, **kwargs: Any) -> None:
        if ip not in self._state:
            self._state[ip] = {}
        self._state[ip].update(kwargs)

    async def _connect(self, ip: str):
        config = DeviceConnectConfiguration(host=ip, credentials=self._credentials)
        device = await connect(config)
        await device.update()
        return device

    async def _get_l530(self, ip: str):
        return await self._connect(ip)

    async def _get_p100(self, ip: str):
        return await self._connect(ip)

    async def set_switch(self, ip: str, on: bool) -> None:
        try:
            device = await self._get_p100(ip)
            if on:
                await device.turn_on()
            else:
                await device.turn_off()
            self.set_state(ip, on=on)
        except Exception as e:
            print(f"WARNING: Could not reach switch {ip}: {e}")

    async def set_light(
        self,
        ip: str,
        brightness: int | None = None,
        hue: int | None = None,
        saturation: int | None = None,
        on: bool | None = None,
    ) -> None:
        try:
            device = await self._get_l530(ip)
            if on is not None:
                if on:
                    await device.turn_on()
                else:
                    await device.turn_off()
            if brightness is not None or hue is not None or saturation is not None:
                current = self.get_state(ip)
                b = brightness if brightness is not None else current.get("brightness", 100)
                h = hue if hue is not None else current.get("hue", 0)
                s = saturation if saturation is not None else current.get("saturation", 100)
                await device.set_hue_saturation(h, s)
                await device.set_brightness(b)
            self.set_state(
                ip,
                **({} if brightness is None else {"brightness": brightness}),
                **({} if hue is None else {"hue": hue}),
                **({} if saturation is None else {"saturation": saturation}),
                **({} if on is None else {"on": on}),
            )
        except Exception as e:
            print(f"WARNING: Could not reach light {ip}: {e}")

    async def apply_initial_state(self, ip: str, device_type: str, state: dict[str, Any]) -> None:
        on = state.get("on", True)
        if device_type == "p100":
            await self.set_switch(ip, on)
        elif device_type == "l530":
            await self.set_light(
                ip,
                brightness=state.get("brightness"),
                hue=state.get("hue"),
                saturation=state.get("saturation"),
                on=on,
            )
            self.set_state(ip, **state)

    async def fade(
        self,
        ip: str,
        duration: float,
        to_brightness: int | None = None,
        to_hue: int | None = None,
        to_saturation: int | None = None,
        steps: int = 20,
    ) -> None:
        current = self.get_state(ip)
        from_b = current.get("brightness", 100)
        from_h = current.get("hue", 0)
        from_s = current.get("saturation", 100)

        target_b = to_brightness if to_brightness is not None else from_b
        target_h = to_hue if to_hue is not None else from_h
        target_s = to_saturation if to_saturation is not None else from_s

        interval = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            b = round(from_b + (target_b - from_b) * t) if to_brightness is not None else None
            h = round(from_h + (target_h - from_h) * t) if to_hue is not None else None
            s = round(from_s + (target_s - from_s) * t) if to_saturation is not None else None
            await self.set_light(ip, brightness=b, hue=h, saturation=s)
            await asyncio.sleep(interval)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_device_controller.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add device_controller.py tests/test_device_controller.py
git commit -m "feat: device controller with fade support"
```

---

## Task 5: Cue engine

**Files:**
- Create: `cue_engine.py`
- Create: `tests/test_cue_engine.py`

The cue engine takes the current playback position and a list of `CueConfig` objects, tracks which have fired, and returns a list of actions to execute. It is pure logic — no I/O.

- [ ] **Step 1: Write failing tests**

Create `tests/test_cue_engine.py`:

```python
import pytest
from config import CueConfig
from cue_engine import CueEngine

def make_engine(cues):
    return CueEngine(cues)

def cue(at, device, action, **kwargs):
    return CueConfig(at=at, device=device, action=action, **kwargs)

def test_fires_cue_when_position_passes_timestamp():
    engine = make_engine([cue(10.0, "light", "on")])
    result = engine.tick(10.1)
    assert len(result) == 1
    assert result[0].device == "light"

def test_does_not_fire_cue_before_timestamp():
    engine = make_engine([cue(10.0, "light", "on")])
    result = engine.tick(9.9)
    assert result == []

def test_cue_fires_only_once():
    engine = make_engine([cue(10.0, "light", "on")])
    engine.tick(10.1)
    result = engine.tick(10.2)
    assert result == []

def test_fires_multiple_cues_at_same_tick():
    engine = make_engine([
        cue(5.0, "light", "on"),
        cue(5.0, "switch", "off"),
    ])
    result = engine.tick(5.1)
    assert len(result) == 2

def test_seek_backward_resets_cues_ahead_of_new_position():
    engine = make_engine([cue(10.0, "light", "on"), cue(20.0, "switch", "off")])
    engine.tick(25.0)  # fires both
    engine.tick(8.0)   # seek back to 8s — should reset both cues
    result = engine.tick(10.1)
    assert len(result) == 1
    assert result[0].device == "light"

def test_seek_to_zero_resets_all_cues():
    engine = make_engine([cue(5.0, "light", "on"), cue(15.0, "switch", "off")])
    engine.tick(20.0)
    engine.tick(0.0)
    result1 = engine.tick(5.1)
    result2 = engine.tick(15.1)
    assert len(result1) == 1
    assert len(result2) == 1

def test_returns_reset_signal_on_seek_to_near_zero():
    engine = make_engine([cue(10.0, "light", "on")])
    engine.tick(30.0)
    did_reset = engine.tick(0.5)
    assert engine.did_reset  # engine exposes whether a full reset just occurred
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cue_engine.py -v
```

Expected: `ImportError` — `cue_engine.py` doesn't exist yet.

- [ ] **Step 3: Implement `cue_engine.py`**

```python
from config import CueConfig

NEAR_ZERO_THRESHOLD = 1.0  # seconds — seeks to within this of 0 trigger a full reset


class CueEngine:
    def __init__(self, cues: list[CueConfig]):
        self._cues = cues
        self._fired: set[int] = set()
        self._last_position: float = 0.0
        self.did_reset: bool = False

    def tick(self, position: float) -> list[CueConfig]:
        self.did_reset = False

        # Detect seek backward
        if position < self._last_position - 0.5:
            if position <= NEAR_ZERO_THRESHOLD:
                # Full reset — unfired all cues
                self._fired.clear()
                self.did_reset = True
            else:
                # Partial reset — only unfired cues whose timestamp is after new position
                self._fired = {
                    i for i in self._fired if self._cues[i].at <= position
                }

        self._last_position = position

        to_fire = []
        for i, cue in enumerate(self._cues):
            if i not in self._fired and cue.at <= position:
                self._fired.add(i)
                to_fire.append(cue)

        return to_fire
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cue_engine.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add cue_engine.py tests/test_cue_engine.py
git commit -m "feat: cue engine with seek-back handling"
```

---

## Task 6: Discovery module

**Files:**
- Create: `discovery.py`

Discovery uses `plugp100`'s `TapoDiscovery.scan()`. No unit tests here — discovery requires real network hardware. We'll test it manually.

- [ ] **Step 1: Implement `discovery.py`**

```python
from plugp100.common.credentials import AuthCredential
from plugp100.discovery.tapo_discovery import TapoDiscovery


async def discover_devices(email: str, password: str, timeout: float = 5.0) -> list[dict]:
    credentials = AuthCredential(email, password)
    found = []
    try:
        discovered = await TapoDiscovery.scan(timeout=timeout)
        for d in discovered:
            try:
                device = await d.get_tapo_device(credentials)
                await device.update()
                found.append({
                    "ip": d.ip,
                    "type": type(device).__name__,
                    "name": getattr(device, "nickname", "unknown"),
                })
                await device.client.close()
            except Exception:
                found.append({"ip": d.ip, "type": d.device_type, "name": "unknown"})
    except Exception as e:
        print(f"Discovery error: {e}")
    return found


def print_devices(devices: list[dict]) -> None:
    if not devices:
        print("No Tapo devices found on the local network.")
        return
    print(f"Found {len(devices)} device(s):\n")
    for d in devices:
        print(f"  {d['type']:<12} @ {d['ip']:<18}  (name: \"{d['name']}\")")
```

- [ ] **Step 2: Commit**

```bash
git add discovery.py
git commit -m "feat: Tapo device discovery"
```

---

## Task 7: Main entry point and sync loop

**Files:**
- Create: `main.py`

This wires everything together. No unit tests — integration is verified by running against real devices.

- [ ] **Step 1: Implement `main.py`**

```python
import asyncio
import sys
from config import load_config, ConfigError
from vlc_poller import VlcPoller
from cue_engine import CueEngine
from device_controller import DeviceController
from discovery import discover_devices, print_devices

CONFIG_PATH = "config.yaml"
VLC_RETRY_INTERVAL = 2.0  # seconds to wait before retrying VLC connection


async def run_show(config_path: str) -> None:
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)
    poller = VlcPoller(cfg.vlc.host, cfg.vlc.port, cfg.vlc.password)
    engine = CueEngine(cfg.cues)

    print("Applying initial device states...")
    for name, device in cfg.devices.items():
        print(f"  {name} ({device.type}) @ {device.ip}")
        await ctrl.apply_initial_state(device.ip, device.type, device.initial_state)

    print("Waiting for VLC...")
    while True:
        position = await poller.get_position()
        if position is not None:
            print(f"VLC connected. Starting sync loop.")
            break
        await asyncio.sleep(VLC_RETRY_INTERVAL)

    while True:
        position = await poller.get_position()
        if position is None:
            print("VLC unreachable, retrying...")
            await asyncio.sleep(VLC_RETRY_INTERVAL)
            continue

        fired_cues = engine.tick(position)

        if engine.did_reset:
            print(f"[{position:.1f}s] Video reset — re-applying initial states")
            for name, device in cfg.devices.items():
                await ctrl.apply_initial_state(device.ip, device.type, device.initial_state)

        for cue in fired_cues:
            device = cfg.devices[cue.device]
            ip = device.ip
            print(f"[{position:.1f}s] Firing cue: {cue.device} → {cue.action}")

            if cue.action == "fade":
                asyncio.create_task(ctrl.fade(
                    ip,
                    duration=cue.duration,
                    to_brightness=cue.to_brightness,
                    to_hue=cue.to_hue,
                    to_saturation=cue.to_saturation,
                ))
            elif cue.action == "set_light":
                asyncio.create_task(ctrl.set_light(
                    ip,
                    brightness=cue.brightness,
                    hue=cue.hue,
                    saturation=cue.saturation,
                ))
            elif cue.action == "on":
                asyncio.create_task(ctrl.set_switch(ip, True))
            elif cue.action == "off":
                asyncio.create_task(ctrl.set_switch(ip, False))

        await asyncio.sleep(cfg.vlc.poll_interval)


async def run_discovery(config_path: str) -> None:
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    print("Scanning local network for Tapo devices...")
    devices = await discover_devices(cfg.tapo.email, cfg.tapo.password)
    print_devices(devices)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("run", "discover"):
        print("Usage: python3 main.py [run|discover]")
        sys.exit(1)

    command = sys.argv[1]
    config_path = sys.argv[2] if len(sys.argv) > 2 else CONFIG_PATH

    if command == "run":
        asyncio.run(run_show(config_path))
    elif command == "discover":
        asyncio.run(run_discovery(config_path))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: main entry point and sync loop"
```

---

## Task 8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
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
  --intf http \
  --http-password tapo_sync \
  --http-port 8080 \
  /path/to/your/video.mp4
```

Or enable it permanently in VLC: `VLC menu → Preferences → Interface → Main interfaces → Web`.

**3. Edit `config.yaml`**

Fill in your Tapo account credentials, device IPs, and cue list. See `config.yaml` for the full format.

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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and usage instructions"
```

---

## Task 9: Full test suite pass

- [ ] **Step 1: Run the complete test suite**

```bash
pytest tests/ -v
```

Expected output — all tests passing:
```
tests/test_config.py::test_load_valid_config PASSED
tests/test_config.py::test_missing_tapo_section PASSED
tests/test_config.py::test_unknown_device_in_cue PASSED
tests/test_config.py::test_unknown_device_type PASSED
tests/test_config.py::test_fade_cue_requires_duration PASSED
tests/test_vlc_poller.py::test_returns_playback_position PASSED
tests/test_vlc_poller.py::test_returns_none_when_vlc_unreachable PASSED
tests/test_device_controller.py::test_set_switch_on PASSED
tests/test_device_controller.py::test_set_switch_off PASSED
tests/test_device_controller.py::test_set_light_updates_tracked_state PASSED
tests/test_device_controller.py::test_set_light_partial_update_preserves_existing_state PASSED
tests/test_device_controller.py::test_set_light_warns_on_device_error PASSED
tests/test_device_controller.py::test_fade_interpolates_brightness PASSED
tests/test_cue_engine.py::test_fires_cue_when_position_passes_timestamp PASSED
tests/test_cue_engine.py::test_does_not_fire_cue_before_timestamp PASSED
tests/test_cue_engine.py::test_cue_fires_only_once PASSED
tests/test_cue_engine.py::test_fires_multiple_cues_at_same_tick PASSED
tests/test_cue_engine.py::test_seek_backward_resets_cues_ahead_of_new_position PASSED
tests/test_cue_engine.py::test_seek_to_zero_resets_all_cues PASSED
tests/test_cue_engine.py::test_returns_reset_signal_on_seek_to_near_zero PASSED
```

- [ ] **Step 2: Fix any failures before proceeding**
