"""
Standalone Arduino trigger — use this only when running main.py directly
without the GUI. The GUI (gui.py) has Arduino support built in.
"""
import serial
import subprocess
import sys
import time

ARDUINO_PORT = "COM4"
CONFIG_PATH = "config.yaml"

_show_process: subprocess.Popen | None = None


def _trigger():
    global _show_process
    if _show_process is not None and _show_process.poll() is None:
        print("Stopping current show...")
        _show_process.terminate()
        try:
            _show_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _show_process.kill()

    print("Starting show...")
    _show_process = subprocess.Popen([sys.executable, "main.py", "run", CONFIG_PATH])


try:
    ser = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
    time.sleep(2)
    print(f"Arduino ready on {ARDUINO_PORT}. Waiting for button press...")
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8").strip()
            if line == "TRIGGER_KEYS":
                print("Button pressed — starting/resetting sequence")
                _trigger()
except KeyboardInterrupt:
    if _show_process is not None and _show_process.poll() is None:
        _show_process.terminate()
except Exception as e:
    print(f"Error on {ARDUINO_PORT}: {e}")
