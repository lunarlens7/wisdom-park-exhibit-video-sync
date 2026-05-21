from dataclasses import dataclass
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
        email=_require(raw["tapo"], "email", "tapo"),
        password=_require(raw["tapo"], "password", "tapo"),
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
            ip=_require(d, "ip", f"devices.{name}"),
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
