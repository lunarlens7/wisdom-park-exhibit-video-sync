import asyncio
import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont
import yaml

from config import load_config, ConfigError
from device_controller import DeviceController
from discovery import discover_devices

CONFIG_PATH = "config.yaml"
AUDIO_FILE = "night_audio.mp3"
AUDIO_PAUSE_FILE = ".audio_pause"
ARDUINO_PORT = "COM4"
ARDUINO_BAUD = 9600

READY_STATE = {
    "main_light":       {"on": True,  "brightness": 1},
    "overhead_light_2": {"on": True,  "brightness": 1},
    "spotlight_1":      {"on": True,  "brightness": 50},
    "spotlight_2":      {"on": True,  "brightness": 50},
    "spotlight_3":      {"on": True,  "brightness": 50},
    "stage_switch":     {"on": True},
}

DEVICE_TIMEOUT = 8.0

CHECK_PENDING = "—"
CHECK_PASS    = "✓"
CHECK_FAIL    = "✗"

COLOR_PASS    = "#2ecc71"
COLOR_FAIL    = "#e74c3c"
COLOR_PENDING = "#888888"
COLOR_WARN    = "#f39c12"
COLOR_BG      = "#1a1a2e"
COLOR_PANEL   = "#16213e"
COLOR_BTN_BG  = "#0f3460"
COLOR_BTN_FG  = "#e0e0e0"
COLOR_ACCENT  = "#e94560"


class ExhibitApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wisdom Park Exhibit Controller")
        self.configure(bg=COLOR_BG)
        self.resizable(False, False)

        self._state = "idle"
        self._app_shutdown = threading.Event()
        self._show_proc: subprocess.Popen | None = None
        self._audio_proc: subprocess.Popen | None = None
        self._ctrl: DeviceController | None = None
        # asyncio loop in background thread for all device ops
        self._async_loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._async_loop.run_forever, daemon=True)
        t.start()

        self._build_ui()
        self._set_state("idle")
        threading.Thread(target=self._arduino_thread, daemon=True).start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        bold  = tkfont.Font(family="Helvetica", size=13, weight="bold")
        small = tkfont.Font(family="Helvetica", size=12)

        # Title
        tk.Label(self, text="WISDOM PARK EXHIBIT CONTROLLER",
                 bg=COLOR_BG, fg="white",
                 font=tkfont.Font(family="Helvetica", size=16, weight="bold"),
                 pady=16).pack(fill="x")

        # Warning banner
        warn_frame = tk.Frame(self, bg=COLOR_WARN, pady=8)
        warn_frame.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(warn_frame, text="⚠   Remember: turn the PROJECTOR on before the TV",
                 bg=COLOR_WARN, fg="black",
                 font=bold).pack()

        # Verification panel
        vf = tk.LabelFrame(self, text=" Verification ", bg=COLOR_PANEL, fg="white",
                           font=bold, padx=14, pady=10, bd=1, relief="groove")
        vf.pack(fill="x", padx=16, pady=(0, 8))

        self._check_labels: dict[str, tk.Label] = {}
        self._check_text_labels: dict[str, tk.Label] = {}

        checks = [
            ("wifi",    "WiFi — Exhibition network (192.168.8.x)"),
            ("devices", "Devices found on network"),
            ("ips",     "IP addresses match config"),
        ]
        for key, label_text in checks:
            row = tk.Frame(vf, bg=COLOR_PANEL)
            row.pack(fill="x", pady=3)
            icon_lbl = tk.Label(row, text=CHECK_PENDING, width=3,
                                bg=COLOR_PANEL, fg=COLOR_PENDING,
                                font=tkfont.Font(family="Helvetica", size=14, weight="bold"))
            icon_lbl.pack(side="left")
            text_lbl = tk.Label(row, text=label_text, bg=COLOR_PANEL, fg="#dddddd",
                                font=small, anchor="w")
            text_lbl.pack(side="left", fill="x")
            self._check_labels[key] = icon_lbl
            self._check_text_labels[key] = text_lbl

        self._verify_btn = tk.Button(vf, text="Verify System",
                                     bg="#2980b9", fg="white",
                                     font=bold, relief="flat", padx=20, pady=8,
                                     cursor="hand2",
                                     command=self._on_verify)
        self._verify_btn.pack(pady=(12, 2))

        # Action buttons
        af = tk.Frame(self, bg=COLOR_BG)
        af.pack(fill="x", padx=16, pady=(4, 4))

        self._start_btn = tk.Button(af, text="Start Program",
                                    bg="#27ae60", fg="white",
                                    font=bold, relief="flat", padx=24, pady=12,
                                    cursor="hand2", state="disabled",
                                    command=self._on_start)
        self._start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._shutdown_btn = tk.Button(af, text="Shut Down Lights",
                                       bg="#c0392b", fg="white",
                                       font=bold, relief="flat", padx=24, pady=12,
                                       cursor="hand2", state="disabled",
                                       command=self._on_shutdown)
        self._shutdown_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self._cancel_btn = tk.Button(self, text="Cancel Show & Reset",
                                     bg=COLOR_ACCENT, fg="white",
                                     font=bold, relief="flat", padx=24, pady=10,
                                     cursor="hand2",
                                     command=self._on_cancel)
        self._cancel_btn.pack(fill="x", padx=16, pady=(0, 4))
        self._cancel_btn.pack_forget()

        # Log area
        lf = tk.LabelFrame(self, text=" Log ", bg=COLOR_PANEL, fg="white",
                            font=bold, padx=8, pady=6, bd=1, relief="groove")
        lf.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        self._log_text = tk.Text(lf, height=10, bg="#0d0d1a", fg="#cccccc",
                                 font=("Courier", 11), relief="flat",
                                 state="disabled", wrap="word")
        scroll = ttk.Scrollbar(lf, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.minsize(w, h)

    # ── State machine ─────────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self._state = state
        if state == "idle":
            self._verify_btn.config(state="normal", text="Verify System")
            self._start_btn.config(state="disabled")
            self._shutdown_btn.config(state="disabled")
            self._cancel_btn.pack_forget()
        elif state == "verifying":
            self._verify_btn.config(state="disabled", text="Verifying…")
            self._start_btn.config(state="disabled")
            self._shutdown_btn.config(state="disabled")
            self._cancel_btn.pack_forget()
        elif state == "verified":
            self._verify_btn.config(state="normal", text="Re-Verify")
            self._start_btn.config(state="normal")
            self._shutdown_btn.config(state="normal")
            self._cancel_btn.pack_forget()
        elif state == "running":
            self._verify_btn.config(state="disabled")
            self._start_btn.config(state="disabled")
            self._shutdown_btn.config(state="disabled")
            self._cancel_btn.pack(fill="x", padx=16, pady=(0, 4))

    def _set_check(self, key: str, status: str):
        lbl = self._check_labels[key]
        if status == CHECK_PASS:
            lbl.config(text=CHECK_PASS, fg=COLOR_PASS)
        elif status == CHECK_FAIL:
            lbl.config(text=CHECK_FAIL, fg=COLOR_FAIL)
        else:
            lbl.config(text=CHECK_PENDING, fg=COLOR_PENDING)

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        def _do():
            self._log_text.config(state="normal")
            self._log_text.insert("end", msg + "\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self.after(0, _do)

    # ── Verification ──────────────────────────────────────────────────────────

    def _on_verify(self):
        for key in self._check_labels:
            self._set_check(key, CHECK_PENDING)
        self._check_text_labels["devices"].config(text="Devices found on network")
        self._set_state("verifying")
        self._log("── Starting verification ──")
        threading.Thread(target=self._do_verify, daemon=True).start()

    def _do_verify(self):
        passed = True

        # 1. WiFi
        wifi_ok = self._check_wifi()
        self.after(0, lambda ok=wifi_ok: self._set_check("wifi", CHECK_PASS if ok else CHECK_FAIL))
        if wifi_ok:
            self._log("WiFi: connected to Exhibition network")
        else:
            self._log("WiFi: NOT on 192.168.8.x network — check WiFi connection")
            passed = False

        # 2. Load config
        try:
            cfg = load_config(CONFIG_PATH)
        except ConfigError as e:
            self._log(f"Config error: {e}")
            self.after(0, lambda: self._set_state("idle"))
            return

        email, password = cfg.tapo.email, cfg.tapo.password
        config_devices = cfg.devices  # {name: DeviceConfig}

        # 3. Discovery
        self._log("Scanning for Tapo devices…")
        try:
            future = asyncio.run_coroutine_threadsafe(
                discover_devices(email, password, timeout=12.0),
                self._async_loop,
            )
            discovered = future.result(timeout=15)
        except Exception as e:
            self._log(f"Discovery failed: {e}")
            self.after(0, lambda: self._set_check("devices", CHECK_FAIL))
            self.after(0, lambda: self._set_check("ips", CHECK_FAIL))
            self.after(0, lambda: self._set_state("idle"))
            return

        expected = len(config_devices)
        found = len(discovered)
        self.after(0, lambda f=found, e=expected:
                   self._check_text_labels["devices"].config(text=f"Devices — {f}/{e} found on network"))

        if found < expected:
            self.after(0, lambda: self._set_check("devices", CHECK_FAIL))
            self.after(0, lambda: self._set_check("ips", CHECK_FAIL))
            self._log(
                f"Only {found}/{expected} devices found. "
                "Check that all devices have power, then click Verify again."
            )
            passed = False
        else:
            self.after(0, lambda: self._set_check("devices", CHECK_PASS))

            # 4. IP reconciliation (always run — catches type mismatches too)
            if self._reconcile_ips(config_devices, discovered):
                self.after(0, lambda: self._set_check("ips", CHECK_PASS))
            else:
                self._log("WARNING: Some devices could not be remapped — check config.yaml")
                self.after(0, lambda: self._set_check("ips", CHECK_FAIL))
                passed = False

        if not passed:
            self.after(0, lambda: self._set_state("idle"))
            self._log("── Verification FAILED — address issues above, then retry ──")
            return

        # Reload config after possible IP update, build controller
        try:
            cfg = load_config(CONFIG_PATH)
        except ConfigError as e:
            self._log(f"Config reload error: {e}")
            self.after(0, lambda: self._set_state("idle"))
            return

        self._ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)

        # Apply ready state
        self._log("Applying ready state to devices…")
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._apply_ready_state(cfg),
                self._async_loop,
            )
            future.result(timeout=30)
        except Exception as e:
            self._log(f"WARNING: Ready state partially failed: {e}")

        self._log("── Verification PASSED — ready to run ──")
        self._start_audio()
        self.after(0, lambda: self._set_state("verified"))

    def _check_wifi(self) -> bool:
        try:
            addrs = socket.getaddrinfo(socket.gethostname(), None)
            for addr in addrs:
                ip = addr[4][0]
                if ip.startswith("192.168.8."):
                    return True
        except Exception:
            pass
        return False

    def _reconcile_ips(self, config_devices: dict, discovered: list[dict]) -> bool:
        def tokens(s: str) -> set[str]:
            return set(s.lower().replace("_", " ").replace("-", " ").split())

        # Group discovered devices by model type (case-insensitive)
        by_type: dict[str, list[dict]] = {}
        for d in discovered:
            by_type.setdefault(d["model"].lower(), []).append(d)

        # Assign each config device to its best-matching discovered device
        # using type filter + name-token overlap score
        assignments: dict[str, dict] = {}
        used: set[str] = set()

        for name, dev in config_devices.items():
            candidates = [
                d for d in by_type.get(dev.type.lower(), [])
                if d["ip"] not in used
            ]
            if not candidates:
                self._log(f"  WARNING: no available {dev.type} device for '{name}'")
                continue
            config_tokens = tokens(name)
            best = max(candidates,
                       key=lambda d: len(config_tokens & tokens(d.get("name", ""))))
            assignments[name] = best
            used.add(best["ip"])

        if len(assignments) != len(config_devices):
            return False

        # Find IPs that need updating
        changes = {
            name: dev for name, dev in assignments.items()
            if config_devices[name].ip != dev["ip"]
        }
        if not changes:
            self._log("IP addresses match config — no update needed")
            return True

        for name, dev in changes.items():
            old_ip = config_devices[name].ip
            self._log(f"  {name}: {old_ip} → {dev['ip']} ({dev['model']} \"{dev['name']}\")")

        try:
            with open(CONFIG_PATH) as f:
                raw = yaml.safe_load(f)
            for name, dev in assignments.items():
                raw["devices"][name]["ip"] = dev["ip"]
            with open(CONFIG_PATH, "w") as f:
                yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)
            self._log("config.yaml updated.")
        except Exception as e:
            self._log(f"ERROR writing config.yaml: {e}")
            return False

        return True

    # ── Ready state ───────────────────────────────────────────────────────────

    async def _apply_ready_state(self, cfg=None):
        if cfg is None:
            try:
                cfg = load_config(CONFIG_PATH)
            except ConfigError:
                return
        if self._ctrl is None:
            self._ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)

        async def _apply_one(name, dev):
            state = READY_STATE.get(name, dev.initial_state)
            try:
                await asyncio.wait_for(
                    self._ctrl.apply_initial_state(dev.ip, dev.type, state),
                    timeout=DEVICE_TIMEOUT,
                )
            except Exception as e:
                print(f"  WARNING: {name} ready-state failed: {e}")

        await asyncio.gather(*[_apply_one(n, d) for n, d in cfg.devices.items()])

    # ── Show control ──────────────────────────────────────────────────────────

    def _on_start(self):
        if self._state != "verified":
            return
        self._set_state("running")
        self._log("── Starting show ──")
        threading.Thread(target=self._show_runner, daemon=True).start()

    def _show_runner(self):
        try:
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            self._show_proc = subprocess.Popen([sys.executable, script, "run", CONFIG_PATH])
            self._show_proc.wait()
        except Exception as e:
            self._log(f"Show error: {e}")
        finally:
            self._show_proc = None
        self.after(0, self._on_show_ended)

    def _on_show_ended(self):
        self._log("── Show ended — resetting to ready state ──")
        # Ensure audio pause file is gone so the audio loop resumes
        try:
            os.unlink(AUDIO_PAUSE_FILE)
        except OSError:
            pass
        future = asyncio.run_coroutine_threadsafe(self._apply_ready_state(), self._async_loop)
        threading.Thread(target=self._wait_reset, args=(future,), daemon=True).start()

    def _wait_reset(self, future):
        try:
            future.result(timeout=30)
            self._log("Ready state applied.")
        except Exception as e:
            self._log(f"WARNING: ready state partially failed: {e}")
        self.after(0, lambda: self._set_state("verified"))

    def _on_cancel(self):
        if self._state != "running":
            return
        self._log("Cancelling show…")
        if self._show_proc is not None and self._show_proc.poll() is None:
            self._show_proc.terminate()

    # ── Shut down lights ──────────────────────────────────────────────────────

    def _on_shutdown(self):
        if self._state != "verified":
            return
        self._log("Turning off all devices…")
        self._shutdown_btn.config(state="disabled")
        self._start_btn.config(state="disabled")

        async def _off():
            try:
                cfg = load_config(CONFIG_PATH)
            except ConfigError as e:
                self._log(f"Config error: {e}")
                return
            if self._ctrl is None:
                self._ctrl = DeviceController(cfg.tapo.email, cfg.tapo.password)

            async def _off_one(name, dev):
                try:
                    await asyncio.wait_for(
                        self._ctrl.apply_initial_state(dev.ip, dev.type, {"on": False}),
                        timeout=DEVICE_TIMEOUT,
                    )
                except Exception as e:
                    self._log(f"  WARNING: {name} failed: {e}")

            await asyncio.gather(*[_off_one(n, d) for n, d in cfg.devices.items()])

        def _run():
            future = asyncio.run_coroutine_threadsafe(_off(), self._async_loop)
            try:
                future.result(timeout=30)
                self._log("All devices off.")
            except Exception as e:
                self._log(f"Shutdown error: {e}")
            self.after(0, lambda: self._start_btn.config(state="normal"))
            self.after(0, lambda: self._shutdown_btn.config(state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    # ── Arduino ───────────────────────────────────────────────────────────────

    def _arduino_thread(self):
        try:
            import serial
            import time
            ser = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
            time.sleep(2)
            self._log(f"Arduino connected on {ARDUINO_PORT}")
            while not self._app_shutdown.is_set():
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode("utf-8").strip()
                        if line == "TRIGGER_KEYS":
                            self.after(0, self._on_arduino_trigger)
                    except Exception:
                        pass
        except Exception as e:
            self._log(f"Arduino ({ARDUINO_PORT}): {e} — physical button unavailable")

    def _on_arduino_trigger(self):
        if self._state == "verified":
            self._log("Button pressed — starting show")
            self._on_start()
        elif self._state == "running":
            self._log("Button pressed — cancelling show")
            self._on_cancel()

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _start_audio(self):
        if self._audio_proc is not None and self._audio_proc.poll() is None:
            return  # already running
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        audio = os.path.join(os.path.dirname(os.path.abspath(__file__)), AUDIO_FILE)
        if not os.path.exists(audio):
            self._log(f"Audio file '{AUDIO_FILE}' not found — skipping background audio")
            return
        self._audio_proc = subprocess.Popen([sys.executable, script, "audio", audio])
        self._log(f"Background audio started ({AUDIO_FILE})")

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _on_close(self):
        self._app_shutdown.set()
        for proc in (self._show_proc, self._audio_proc):
            if proc is not None and proc.poll() is None:
                proc.terminate()
        try:
            os.unlink(AUDIO_PAUSE_FILE)
        except OSError:
            pass
        self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        self.destroy()


def main():
    app = ExhibitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
