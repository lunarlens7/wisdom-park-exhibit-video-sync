"""
Test script: play two videos to two external monitors.

Usage:
    python test_screens.py [video1] [video2] [monitor1] [monitor2]

Defaults:
    video1 = earth_turning.mp4, video2 = earth_turning.mp4
    monitor1 = 1, monitor2 = 2  (0 = primary, 1/2 = external)

Press 'q' to quit.
"""

import asyncio
import sys
import numpy as np
import cv2
from ffpyplayer.player import MediaPlayer


def list_monitors() -> list:
    try:
        from screeninfo import get_monitors
        return get_monitors()
    except Exception:
        return []


def get_monitor_offset(index: int) -> tuple[int, int]:
    monitors = list_monitors()
    if index < len(monitors):
        return monitors[index].x, monitors[index].y
    return 0, 0


def frame_to_bgr(img) -> np.ndarray:
    img_bytes = img.to_bytearray()[0]
    w, h = img.get_size()
    return cv2.cvtColor(
        np.frombuffer(img_bytes, dtype=np.uint8).reshape(h, w, 3),
        cv2.COLOR_RGB2BGR,
    )


def open_window(title: str, monitor_index: int) -> None:
    monitors = list_monitors()
    mon = monitors[monitor_index] if monitor_index < len(monitors) else None
    x, y = (mon.x, mon.y) if mon else (0, 0)
    w, h = (mon.width, mon.height) if mon else (1920, 1080)

    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    # Window must be rendered before moveWindow takes effect
    cv2.imshow(title, np.zeros((h, w, 3), dtype=np.uint8))
    cv2.waitKey(1)
    cv2.moveWindow(title, x, y)
    # Set fullscreen after moving so it goes fullscreen on the correct monitor
    cv2.setWindowProperty(title, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


async def play_video(path: str, title: str, monitor_index: int, stop_event: asyncio.Event, mute: bool = False) -> None:
    player = MediaPlayer(path, ff_opts={'an': True} if mute else {})
    open_window(title, monitor_index)
    while not stop_event.is_set():
        frame, val = player.get_frame()
        if val == "eof":
            player.seek(0, relative=False)
            await asyncio.sleep(0.1)
            continue
        if frame is not None:
            img, _ = frame
            cv2.imshow(title, frame_to_bgr(img))
            cv2.waitKey(1)
        await asyncio.sleep(0.001)


async def main(video1: str, video2: str, mon1: int, mon2: int) -> None:
    monitors = list_monitors()
    print(f"Detected {len(monitors)} monitor(s):")
    for i, m in enumerate(monitors):
        print(f"  [{i}] {m.name}  {m.width}x{m.height}  offset ({m.x},{m.y})")
    print(f"\nPlaying '{video1}' on monitor {mon1}, '{video2}' on monitor {mon2}")
    print("Press 'q' to quit.\n")

    stop = asyncio.Event()

    task1 = asyncio.create_task(play_video(video1, "Screen 1", mon1, stop, mute=False))
    task2 = asyncio.create_task(play_video(video2, "Screen 2", mon2, stop, mute=True))

    try:
        while True:
            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                break
            await asyncio.sleep(0.03)
    finally:
        stop.set()
        await asyncio.gather(task1, task2, return_exceptions=True)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    args = sys.argv[1:]
    v1 = args[0] if len(args) > 0 else "earth_turning.mp4"
    v2 = args[1] if len(args) > 1 else "earth_turning.mp4"
    m1 = int(args[2]) if len(args) > 2 else 1
    m2 = int(args[3]) if len(args) > 3 else 2

    asyncio.run(main(v1, v2, m1, m2))
