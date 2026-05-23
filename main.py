import asyncio
import sys
import numpy as np
import cv2
from ffpyplayer.player import MediaPlayer
from config import load_config, ConfigError, ScreenConfig
from cue_engine import CueEngine
from device_controller import DeviceController
from discovery import discover_devices, print_devices

CONFIG_PATH = "config.yaml"


def _frame_to_bgr(img) -> np.ndarray:
    img_bytes = img.to_bytearray()[0]
    w, h = img.get_size()
    return cv2.cvtColor(
        np.frombuffer(img_bytes, dtype=np.uint8).reshape(h, w, 3),
        cv2.COLOR_RGB2BGR,
    )


def _open_window(title: str, monitor: int, fullscreen: bool) -> None:
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        mon = monitors[monitor] if monitor < len(monitors) else None
    except Exception:
        mon = None
    x, y = (mon.x, mon.y) if mon else (0, 0)
    w, h = (mon.width, mon.height) if mon else (1920, 1080)

    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    # Window must be rendered before moveWindow takes effect
    cv2.imshow(title, np.zeros((h, w, 3), dtype=np.uint8))
    cv2.waitKey(1)
    cv2.moveWindow(title, x, y)
    if fullscreen:
        # Set fullscreen after moving so it goes fullscreen on the correct monitor
        cv2.setWindowProperty(title, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


async def _run_secondary(screen: ScreenConfig, loop: bool, fullscreen: bool) -> None:
    player = MediaPlayer(screen.path, ff_opts={'an': True} if screen.mute else {})
    _open_window(screen.window_title, screen.monitor, fullscreen)
    while True:
        frame, val = player.get_frame()
        if val == "eof":
            if loop:
                player.seek(0, relative=False)
                await asyncio.sleep(0.1)
            else:
                break
        elif frame is not None:
            img, _ = frame
            cv2.imshow(screen.window_title, _frame_to_bgr(img))
            cv2.waitKey(1)
        await asyncio.sleep(0.001)


async def run_show(config_path: str) -> None:
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)
    engine = CueEngine(cfg.cues)

    if cfg.dry_run:
        print("Dry run mode — skipping device commands.")
    else:
        print("Applying initial device states...")
        for name, device in cfg.devices.items():
            print(f"  {name} ({device.type}) @ {device.ip}")
            await ctrl.apply_initial_state(device.ip, device.type, device.initial_state)

    primary = cfg.video.screens[0]
    player = MediaPlayer(primary.path, ff_opts={'an': True} if primary.mute else {})
    _open_window(primary.window_title, primary.monitor, cfg.video.fullscreen)

    for screen in cfg.video.screens[1:]:
        asyncio.create_task(_run_secondary(screen, cfg.video.loop, cfg.video.fullscreen))

    print(f"Playing {len(cfg.video.screens)} screen(s). Press 'q' to quit.")

    try:
        while True:
            frame, val = player.get_frame()

            if val == "eof":
                if cfg.video.loop:
                    player.seek(0, relative=False)
                    await asyncio.sleep(0.1)
                else:
                    break
            elif frame is not None:
                img, pts = frame
                cv2.imshow(primary.window_title, _frame_to_bgr(img))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                fired_cues = engine.tick(pts)

                if not cfg.dry_run:
                    if engine.did_reset:
                        print(f"[{pts:.1f}s] Video reset — re-applying initial states")
                        for name, device in cfg.devices.items():
                            await ctrl.apply_initial_state(device.ip, device.type, device.initial_state)

                    for cue in fired_cues:
                        print(f"[{pts:.1f}s] Firing cue: {cue.devices} → {cue.action}")
                        for device_name in cue.devices:
                            ip = cfg.devices[device_name].ip
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

            await asyncio.sleep(0.001)
    finally:
        cv2.destroyAllWindows()


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
        print("Usage: python main.py [run|discover]")
        sys.exit(1)

    command = sys.argv[1]
    config_path = sys.argv[2] if len(sys.argv) > 2 else CONFIG_PATH

    if command == "run":
        asyncio.run(run_show(config_path))
    elif command == "discover":
        asyncio.run(run_discovery(config_path))


if __name__ == "__main__":
    main()
