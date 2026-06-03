import serial
import pyautogui
import time

# Change 'COM3' to match your Arduino's active port from Device Manager
ARDUINO_PORT = 'COM3' 

try:
    ser = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
    time.sleep(2) # Let the Arduino reset cycle finish
    print("System active! Click inside your target terminal window now...")
    print("Waiting for green button press...")
except Exception as e:
    print(f"Error opening port {ARDUINO_PORT}. Is the Arduino Serial Monitor closed? \nDetails: {e}")
    exit()

while True:

    if ser.in_waiting > 0:
        raw_data = ser.readline().decode('utf-8').strip()
        
        if raw_data == "TRIGGER_KEYS":
            print("Button click detected! Simulating: [Up Arrow] -> [Enter]")
            
            # 1. Press and release the Up Arrow key
            pyautogui.press('up')
            
            # 2. Tiny delay to allow terminal string history to render smoothly
            time.sleep(0.05) 
            
            # 3. Press and release the Enter key to execute
            pyautogui.press('enter') 