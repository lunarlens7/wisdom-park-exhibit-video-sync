import serial
import time

ARDUINO_PORT = "COM4"
TRIGGER_FILE = ".trigger"

try:
    ser = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
    time.sleep(2)
    print(f"Arduino ready on {ARDUINO_PORT}. Waiting for button press...")
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8").strip()
            if line == "TRIGGER_KEYS":
                print("Button pressed — signalling GUI")
                open(TRIGGER_FILE, "w").close()
except KeyboardInterrupt:
    pass
except Exception as e:
    print(f"Error on {ARDUINO_PORT}: {e}")
