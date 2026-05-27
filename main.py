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


DEVICE_TIMEOUT = 5.0
SYNC_DRIFT_THRESHOLD = 0.3  # seconds of drift before correcting secondary player


async def _init_device(ctrl, name: str, device) -> None:
    print(f"  {name} ({device.type}) @ {device.ip}")
    try:
        await asyncio.wait_for(
            ctrl.apply_initial_state(device.ip, device.type, device.initial_state),
            timeout=DEVICE_TIMEOUT,
        )
    except Exception as e:
        print(f"  WARNING: {name} failed during init ({type(e).__name__}: {e}), continuing")


async def _apply_all_initial_states(ctrl, cfg) -> None:
    print("Applying initial device states...")
    await asyncio.gather(*[
        _init_device(ctrl, name, device)
        for name, device in cfg.devices.items()
    ])


async def _run_secondary(
    screen: ScreenConfig,
    loop: bool,
    fullscreen: bool,
    seek: float = 0.0,
    primary_pts: list[float] | None = None,
) -> None:
    try:
        player = MediaPlayer(screen.path, ff_opts={'an': True} if screen.mute else {})
        _open_window(screen.window_title, screen.monitor, fullscreen)
        seek_pending = seek > 0
        last_log = 0.0
        while True:
            frame, val = player.get_frame()
            if val == "eof":
                if loop:
                    player.seek(0, relative=False)
                    await asyncio.sleep(0.1)
                else:
                    break
            elif frame is not None:
                if seek_pending:
                    player.seek(seek, relative=False)
                    seek_pending = False
                    await asyncio.sleep(0.1)
                    continue
                img, sec_pts = frame
                if primary_pts is not None and sec_pts > 0:
                    drift = sec_pts - primary_pts[0]
                    now = asyncio.get_event_loop().time()
                    if now - last_log >= 1.0:
                        last_log = now
                        print(f"  [{screen.window_title}] sec={sec_pts:.3f}s  primary={primary_pts[0]:.3f}s  drift={drift:+.3f}s")
                    if abs(drift) < 5.0:
                        if drift > SYNC_DRIFT_THRESHOLD:
                            # Secondary is ahead — drop this frame
                            print(f"  [{screen.window_title}] DROP  drift={drift:+.3f}s")
                            continue
                        if drift < -SYNC_DRIFT_THRESHOLD:
                            # Secondary is behind — drain frames until caught up
                            print(f"  [{screen.window_title}] CATCH UP  drift={drift:+.3f}s")
                            while drift < -SYNC_DRIFT_THRESHOLD:
                                f2, _ = player.get_frame()
                                if f2 is None:
                                    break
                                img, sec_pts = f2
                                drift = sec_pts - primary_pts[0]
                cv2.imshow(screen.window_title, _frame_to_bgr(img))
                cv2.waitKey(1)
            await asyncio.sleep(0.001)
    except Exception as e:
        print(f"ERROR in secondary screen '{screen.window_title}': {e}")


async def run_show(config_path: str, seek: float = 0.0) -> None:
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
        await _apply_all_initial_states(ctrl, cfg)

    primary = cfg.video.screens[0]
    player = MediaPlayer(primary.path, ff_opts={'an': True} if primary.mute else {})
    _open_window(primary.window_title, primary.monitor, cfg.video.fullscreen)

    primary_pts: list[float] = [0.0]
    for screen in cfg.video.screens[1:]:
        asyncio.create_task(_run_secondary(screen, cfg.video.loop, cfg.video.fullscreen, seek=seek, primary_pts=primary_pts))

    print(f"Playing {len(cfg.video.screens)} screen(s). Press 'q' to quit.")

    seek_pending = seek > 0
    try:
        while True:
            frame, val = player.get_frame()

            if val == "eof":
                if cfg.video.loop:
                    primary_pts[0] = 0.0
                    player.seek(0, relative=False)
                    await asyncio.sleep(0.1)
                else:
                    break
            elif frame is not None:
                if seek_pending:
                    player.seek(seek, relative=False)
                    print(f"Seeking to {seek:.1f}s...")
                    seek_pending = False
                    await asyncio.sleep(0.1)
                    continue
                img, pts = frame
                primary_pts[0] = pts
                cv2.imshow(primary.window_title, _frame_to_bgr(img))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                fired_cues = engine.tick(pts)

                if not cfg.dry_run:
                    if engine.did_reset:
                        print(f"[{pts:.1f}s] Video reset — re-applying initial states")
                        asyncio.create_task(_apply_all_initial_states(ctrl, cfg))

                    for cue in fired_cues:
                        print(f"[{pts:.1f}s] Firing cue: {cue.devices} → {cue.action}")
                        for device_name in cue.devices:
                            device = cfg.devices[device_name]
                            ip = device.ip
                            dtype = device.type
                            if cue.action == "fade":
                                asyncio.create_task(ctrl.fade(
                                    ip,
                                    device_type=dtype,
                                    duration=cue.duration,
                                    to_brightness=cue.to_brightness,
                                ))
                            elif cue.action == "set_light":
                                asyncio.create_task(ctrl.set_light(
                                    ip,
                                    device_type=dtype,
                                    brightness=cue.brightness,
                                ))
                            elif cue.action == "on":
                                if dtype == "p100":
                                    asyncio.create_task(ctrl.set_switch(ip, True))
                                else:
                                    asyncio.create_task(ctrl.set_light(ip, device_type=dtype, on=True))
                            elif cue.action == "off":
                                if dtype == "p100":
                                    asyncio.create_task(ctrl.set_switch(ip, False))
                                else:
                                    asyncio.create_task(ctrl.set_light(ip, device_type=dtype, on=False))

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
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("config", nargs="?", default=CONFIG_PATH)
    run_parser.add_argument("--seek", type=float, default=0.0, metavar="SECONDS",
                            help="Start playback at this position in seconds")

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("config", nargs="?", default=CONFIG_PATH)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        asyncio.run(run_show(args.config, seek=args.seek))
    elif args.command == "discover":
        asyncio.run(run_discovery(args.config))


if __name__ == "__main__":
    main()
