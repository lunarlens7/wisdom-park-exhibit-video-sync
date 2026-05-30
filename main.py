import asyncio
import os
import sys
import numpy as np
import cv2
from ffpyplayer.player import MediaPlayer
from config import load_config, ConfigError, ScreenConfig, AppConfig
from cue_engine import CueEngine
from device_controller import DeviceController
from discovery import discover_devices, print_devices

CONFIG_PATH = "config.yaml"
AUDIO_PAUSE_FILE = ".audio_pause"


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


def _states_at(cfg: AppConfig, t: float) -> dict[str, dict]:
    """Compute the device state that would exist at time t by simulating all cues up to t."""
    states: dict[str, dict] = {}
    for name, dev in cfg.devices.items():
        states[name] = dict(dev.initial_state)

    for cue in sorted(cfg.cues, key=lambda c: c.at):
        if cue.at > t:
            break
        for name in cue.devices:
            s = states.setdefault(name, {})
            if cue.action == "on":
                s["on"] = True
            elif cue.action == "off":
                s["on"] = False
            elif cue.action == "fade" and cue.to_brightness is not None:
                from_b = s.get("brightness", 100)
                elapsed = min(t - cue.at, cue.duration)
                progress = elapsed / cue.duration if cue.duration else 1.0
                s["brightness"] = round(from_b + (cue.to_brightness - from_b) * progress)
                s["on"] = True

    return states


async def _init_device(ctrl, name: str, device, state=None) -> None:
    print(f"  {name} ({device.type}) @ {device.ip}")
    try:
        await asyncio.wait_for(
            ctrl.apply_initial_state(device.ip, device.type, state if state is not None else device.initial_state),
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
    reset_event: asyncio.Event | None = None,
    pause_event: asyncio.Event | None = None,
    primary_pts: list[float] | None = None,
) -> None:
    try:
        player = MediaPlayer(screen.path, ff_opts={'an': True} if screen.mute else {})
        _open_window(screen.window_title, screen.monitor, fullscreen)
        seek_pending = seek > 0
        last_log = 0.0
        paused = False
        while True:
            is_paused = pause_event is not None and pause_event.is_set()
            if is_paused != paused:
                player.set_pause(is_paused)
                paused = is_paused
            if is_paused:
                await asyncio.sleep(0.033)
                continue

            if reset_event is not None and reset_event.is_set():
                player = MediaPlayer(screen.path, ff_opts={'an': True} if screen.mute else {})
                await asyncio.sleep(0.1)
                continue

            frame, val = player.get_frame()
            if val == "eof":
                if loop:
                    player = MediaPlayer(screen.path, ff_opts={'an': True} if screen.mute else {})
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
                cv2.imshow(screen.window_title, _frame_to_bgr(img))
                cv2.waitKey(1)
            sleep_time = max(0.001, val) if isinstance(val, (int, float)) and frame is not None else 0.001
            await asyncio.sleep(sleep_time)
    except Exception as e:
        print(f"ERROR in secondary screen '{screen.window_title}': {e}")


async def run_audio_loop(path: str) -> None:
    """Play an audio file on a loop, pausing whenever AUDIO_PAUSE_FILE exists."""
    print(f"Background audio: {path}  (pause signal: {AUDIO_PAUSE_FILE})")
    paused = False
    # loop=0 tells ffpyplayer to repeat indefinitely
    player = MediaPlayer(path, ff_opts={'loop': 0})
    try:
        while True:
            should_pause = os.path.exists(AUDIO_PAUSE_FILE)
            if should_pause != paused:
                player.set_pause(should_pause)
                paused = should_pause
                print("Background audio paused." if paused else "Background audio resumed.")
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass


async def run_show(config_path: str, seek: float = 0.0, preview: float = 0.0) -> None:
    open(AUDIO_PAUSE_FILE, "w").close()
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        os.unlink(AUDIO_PAUSE_FILE)
        print(f"Config error: {e}")
        sys.exit(1)

    ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)
    engine = CueEngine(cfg.cues)

    if preview > 0:
        seek = preview

    if cfg.dry_run:
        print("Dry run mode — skipping device commands.")
    elif preview > 0:
        print(f"Preview mode — applying device states as of {preview:.0f}s...")
        computed = _states_at(cfg, preview)
        await asyncio.gather(*[
            _init_device(ctrl, name, dev, computed.get(name, {}))
            for name, dev in cfg.devices.items()
        ])
    else:
        await _apply_all_initial_states(ctrl, cfg)

    primary = cfg.video.screens[0]
    ff_opts = {'an': True} if (primary.mute or preview > 0) else {}
    player = MediaPlayer(primary.path, ff_opts=ff_opts)
    _open_window(primary.window_title, primary.monitor, cfg.video.fullscreen)

    primary_pts: list[float] = [0.0]
    reset_event = asyncio.Event()
    pause_event = asyncio.Event()
    for screen in cfg.video.screens[1:]:
        asyncio.create_task(_run_secondary(screen, cfg.video.loop, cfg.video.fullscreen, seek=seek, reset_event=reset_event, pause_event=pause_event, primary_pts=primary_pts))

    print(f"Playing {len(cfg.video.screens)} screen(s). Press 'q' to quit.")

    seek_pending = seek > 0
    pause_pending = preview > 0
    try:
        while True:
            frame, val = player.get_frame()

            if val == "eof":
                if cfg.video.loop:
                    reset_event.set()
                    player = MediaPlayer(primary.path, ff_opts={'an': True} if primary.mute else {})
                    await asyncio.sleep(0.1)
                    reset_event.clear()
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

                if pause_pending and pts >= preview - 1.0:
                    engine.tick(preview)  # mark all cues up to preview time as fired
                    pause_pending = False
                    frozen_frame = _frame_to_bgr(img)
                    player.set_pause(True)
                    pause_event.set()
                    print(f"Paused at {preview:.0f}s — press SPACE to resume, Q to quit")
                    while True:
                        cv2.imshow(primary.window_title, frozen_frame)
                        key = cv2.waitKey(33) & 0xFF
                        if key == ord(' '):
                            break
                        if key == ord('q'):
                            return
                    pause_event.clear()
                    player = MediaPlayer(primary.path, ff_opts={'an': True} if primary.mute else {})
                    player.seek(preview, relative=False)
                    await asyncio.sleep(0.1)
                    continue

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

            sleep_time = max(0.001, val) if isinstance(val, (int, float)) and frame is not None else 0.001
            await asyncio.sleep(sleep_time)
    finally:
        if os.path.exists(AUDIO_PAUSE_FILE):
            os.unlink(AUDIO_PAUSE_FILE)
        cv2.destroyAllWindows()


async def run_lights_off(config_path: str) -> None:
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)
    print("Turning off all devices...")
    await asyncio.gather(*[
        _init_device(ctrl, name, device, {"on": False})
        for name, device in cfg.devices.items()
    ])
    print("Done.")


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
    run_parser.add_argument("--preview", type=float, default=0.0, metavar="SECONDS",
                            help="Seek to SECONDS, apply device states as of that time, and pause until SPACE")

    audio_parser = subparsers.add_parser("audio")
    audio_parser.add_argument("path", nargs="?", default="sample.mp3",
                              help="Audio file to loop (default: sample.mp3)")

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("config", nargs="?", default=CONFIG_PATH)

    lights_off_parser = subparsers.add_parser("lights-off")
    lights_off_parser.add_argument("config", nargs="?", default=CONFIG_PATH)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        asyncio.run(run_show(args.config, seek=args.seek, preview=args.preview))
    elif args.command == "audio":
        asyncio.run(run_audio_loop(args.path))
    elif args.command == "discover":
        asyncio.run(run_discovery(args.config))
    elif args.command == "lights-off":
        asyncio.run(run_lights_off(args.config))


if __name__ == "__main__":
    main()
