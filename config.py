from dataclasses import dataclass, field
from typing import Any
import os
import yaml
from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    pass


@dataclass
class TapoConfig:
    email: str
    password: str


@dataclass
class ScreenConfig:
    path: str
    window_title: str = "Exhibit"
    monitor: int = 0
    mute: bool = False


@dataclass
class VideoConfig:
    screens: list[ScreenConfig]
    loop: bool = True
    fullscreen: bool = False


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
    video: VideoConfig
    devices: dict[str, DeviceConfig]
    cues: list[CueConfig]
    dry_run: bool = False


VALID_DEVICE_TYPES = {"l530", "p100"}


def load_config(path: str) -> AppConfig:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")

    for section in ("video", "devices", "cues"):
        if section not in raw:
            raise ConfigError(f"Missing required section: '{section}'")

    email = os.environ.get("TAPO_EMAIL")
    password = os.environ.get("TAPO_PASSWORD")
    if not email or not password:
        raise ConfigError(
            "Missing Tapo credentials. Set the TAPO_EMAIL and TAPO_PASSWORD environment variables."
        )
    tapo = TapoConfig(email=email, password=password)

    video_raw = raw["video"]
    screens_raw = video_raw.get("screens") or []
    if not screens_raw:
        raise ConfigError("video.screens must contain at least one screen")
    screens = [
        ScreenConfig(
            path=_require(s, "path", f"video.screens[{i}]"),
            window_title=s.get("window_title", f"Screen {i + 1}"),
            monitor=s.get("monitor", i),
            mute=s.get("mute", False),
        )
        for i, s in enumerate(screens_raw)
    ]
    video = VideoConfig(
        screens=screens,
        loop=video_raw.get("loop", True),
        fullscreen=video_raw.get("fullscreen", False),
    )

    devices: dict[str, DeviceConfig] = {}
    for name, d in (raw["devices"] or {}).items():
        dtype = d.get("type")
        if dtype not in VALID_DEVICE_TYPES:
            raise ConfigError(f"Unknown device type '{dtype}' for device '{name}'. Valid types: {sorted(VALID_DEVICE_TYPES)}")
        devices[name] = DeviceConfig(
            type=dtype,
            ip=_require(d, "ip", f"devices.{name}"),
            initial_state=d.get("initial_state", {}),
        )

    cues: list[CueConfig] = []
    for i, c in enumerate(raw["cues"] or []):
        device_name = c.get("device")
        if device_name not in devices:
            raise ConfigError(f"Cue {i}: references unknown device '{device_name}'")
        action = str(c.get("action", "")).lower()
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

    return AppConfig(tapo=tapo, video=video, devices=devices, cues=cues, dry_run=bool(raw.get("dry_run", False)))


def _require(d: dict, key: str, section: str) -> Any:
    val = d.get(key)
    if val is None:
        raise ConfigError(f"Missing required field '{key}' in section '{section}'")
    return val
