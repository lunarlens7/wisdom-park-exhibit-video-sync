import asyncio
import sys
import numpy as np
import cv2
from ffpyplayer.player import MediaPlayer
from config import load_config, ConfigError
from cue_engine import CueEngine
from device_controller import DeviceController
from discovery import discover_devices, print_devices

CONFIG_PATH = "config.yaml"


async def run_show(config_path: str) -> None:
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)
    engine = CueEngine(cfg.cues)

    print("Applying initial device states...")
    for name, device in cfg.devices.items():
        print(f"  {name} ({device.type}) @ {device.ip}")
        await ctrl.apply_initial_state(device.ip, device.type, device.initial_state)

    player = MediaPlayer(cfg.video.path)

    if cfg.video.fullscreen:
        cv2.namedWindow(cfg.video.window_title, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(cfg.video.window_title, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    print(f"Playing: {cfg.video.path}")
    print("Press 'q' in the video window to quit.")

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

                img_bytes = img.to_bytearray()[0]
                w, h = img.get_size()
                np_img = np.frombuffer(img_bytes, dtype=np.uint8).reshape(h, w, 3)
                cv2.imshow(cfg.video.window_title, cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                fired_cues = engine.tick(pts)

                if engine.did_reset:
                    print(f"[{pts:.1f}s] Video reset — re-applying initial states")
                    for name, device in cfg.devices.items():
                        await ctrl.apply_initial_state(device.ip, device.type, device.initial_state)

                for cue in fired_cues:
                    device = cfg.devices[cue.device]
                    ip = device.ip
                    print(f"[{pts:.1f}s] Firing cue: {cue.device} → {cue.action}")

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
