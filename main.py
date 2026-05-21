import asyncio
import sys
from config import load_config, ConfigError
from vlc_poller import VlcPoller
from cue_engine import CueEngine
from device_controller import DeviceController
from discovery import discover_devices, print_devices

CONFIG_PATH = "config.yaml"
VLC_RETRY_INTERVAL = 2.0


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
            print("VLC connected. Starting sync loop.")
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
