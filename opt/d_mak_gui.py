import os
import signal
import subprocess
import sys
import base64
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from typing import List, Tuple

import cv2
import yaml


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config_path: str, config: dict) -> None:
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def try_open_camera(index: int):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    return cap


def discover_cameras(max_devices: int = 10) -> List[Tuple[int, str]]:
    cameras: List[Tuple[int, str]] = []
    for i in range(max_devices):
        cap = try_open_camera(i)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            label = f"Camera {i} ({width}x{height} @ {fps}fps)"
            cameras.append((i, label))
        cap.release()
    return cameras


class DMakGuiApp:
    STATUS_COLORS = {
        "stopped": "#6c757d",
        "running": "#198754",
        "restarting": "#fd7e14",
        "error": "#dc3545",
        "no-camera": "#dc3545",
        "saved": "#0d6efd",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("d-mak launcher")
        self.root.geometry("760x600")
        self.root.resizable(False, False)

        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.config_path = os.path.join(self.base_dir, "config.yaml")
        self.monitor_exe_path = os.path.join(self.base_dir, "d-mak-monitor.exe")
        self.monitor_script_path = os.path.join(self.base_dir, "d-mak.py")

        self.config = load_config(self.config_path)
        self.process: subprocess.Popen | None = None
        self.cameras: List[Tuple[int, str]] = []
        self.preview_cap = None
        self.preview_photo = None
        self.preview_width = 640
        self.preview_height = 360

        self.selected_camera = tk.StringVar()
        self.status_text = tk.StringVar(value="Status: stopped")
        self.status_level = "stopped"

        self._build_ui()
        self.refresh_cameras(initial=True)
        self._poll_process()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="d-mak monitor control", font=("Segoe UI", 13, "bold"))
        title.pack(anchor="w")

        desc = ttk.Label(
            container,
            text="Select a camera and toggle monitoring on/off. Running monitor opens its own OpenCV window.",
        )
        desc.pack(anchor="w", pady=(4, 14))

        camera_row = ttk.Frame(container)
        camera_row.pack(fill="x", pady=(0, 12))

        ttk.Label(camera_row, text="Camera:", width=12).pack(side="left")

        self.camera_combo = ttk.Combobox(
            camera_row,
            state="readonly",
            textvariable=self.selected_camera,
            width=45,
        )
        self.camera_combo.pack(side="left", padx=(0, 8))
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_changed)

        refresh_button = ttk.Button(camera_row, text="Refresh", command=self.refresh_cameras)
        refresh_button.pack(side="left")

        action_row = ttk.Frame(container)
        action_row.pack(fill="x", pady=(0, 12))

        self.toggle_button = ttk.Button(action_row, text="Start monitoring", command=self.toggle_monitoring)
        self.toggle_button.pack(side="left")

        stop_button = ttk.Button(action_row, text="Stop", command=self.stop_monitoring)
        stop_button.pack(side="left", padx=(8, 0))

        status_row = ttk.Frame(container)
        status_row.pack(fill="x")

        self.status_indicator = tk.Canvas(status_row, width=16, height=16, highlightthickness=0)
        self.status_indicator.pack(side="left", padx=(0, 8))
        self.status_dot = self.status_indicator.create_oval(2, 2, 14, 14, fill=self.STATUS_COLORS["stopped"], outline="")

        status_label = ttk.Label(status_row, textvariable=self.status_text)
        status_label.pack(side="left")

        info = ttk.Label(
            container,
            text="Tip: Press 'q' in the OpenCV window to stop monitoring from the monitor side.",
        )
        info.pack(anchor="w", pady=(8, 0))

        preview_group = ttk.LabelFrame(container, text="Camera preview", padding=8)
        preview_group.pack(fill="both", expand=True, pady=(10, 0))

        self.preview_label = tk.Label(
            preview_group,
            text="No camera preview",
            width=80,
            height=22,
            bg="#111111",
            fg="#dddddd",
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)

        self._set_status("stopped", "Status: stopped")

    def _set_status(self, level: str, message: str) -> None:
        color = self.STATUS_COLORS.get(level, self.STATUS_COLORS["error"])
        self.status_level = level
        self.status_text.set(message)
        self.status_indicator.itemconfigure(self.status_dot, fill=color)

    def refresh_cameras(self, initial: bool = False) -> None:
        self.cameras = discover_cameras(max_devices=10)
        if not self.cameras:
            self.camera_combo["values"] = []
            self.selected_camera.set("")
            self._set_status("no-camera", "Status: no camera found")
            self._stop_preview()
            self._set_preview_placeholder("No camera preview")
            if not initial:
                messagebox.showwarning("No camera", "No available camera device was found.")
            return

        labels = [label for _, label in self.cameras]
        self.camera_combo["values"] = labels

        config_camera = self.config.get("camera", {}).get("device_number", 0)
        default_index = 0
        for idx, (cam_idx, _) in enumerate(self.cameras):
            if cam_idx == config_camera:
                default_index = idx
                break

        current_label = self.selected_camera.get()
        if current_label in labels:
            self.camera_combo.current(labels.index(current_label))
        else:
            self.camera_combo.current(default_index)

        self._restart_preview()

    def _set_preview_placeholder(self, message: str) -> None:
        self.preview_photo = None
        self.preview_label.configure(image="", text=message)

    def _frame_to_photo(self, frame) -> tk.PhotoImage | None:
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (self.preview_width, self.preview_height), interpolation=cv2.INTER_AREA)
            ok, ppm_buf = cv2.imencode(".ppm", resized)
            if not ok:
                return None
            ppm_base64 = base64.b64encode(ppm_buf.tobytes()).decode("ascii")
            return tk.PhotoImage(data=ppm_base64, format="PPM")
        except Exception:
            return None

    def _start_preview(self) -> None:
        self._stop_preview()

        camera_index = self._selected_camera_index()
        if camera_index is None:
            self._set_preview_placeholder("Select a camera")
            return

        cap = try_open_camera(camera_index)
        if not cap.isOpened():
            cap.release()
            self._set_preview_placeholder(f"Failed to open camera {camera_index}")
            return

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.preview_cap = cap
        self._update_preview_frame()

    def _stop_preview(self) -> None:
        if self.preview_cap is not None:
            self.preview_cap.release()
            self.preview_cap = None

    def _restart_preview(self) -> None:
        self._start_preview()

    def _update_preview_frame(self) -> None:
        if self.preview_cap is None:
            return

        ret, frame = self.preview_cap.read()
        if not ret or frame is None:
            self._set_preview_placeholder("Preview not available")
            self.root.after(200, self._update_preview_frame)
            return

        photo = self._frame_to_photo(frame)
        if photo is None:
            self._set_preview_placeholder("Preview conversion failed")
            self.root.after(200, self._update_preview_frame)
            return

        self.preview_photo = photo
        self.preview_label.configure(image=self.preview_photo, text="")
        self.root.after(66, self._update_preview_frame)

    def _selected_camera_index(self) -> int | None:
        label = self.selected_camera.get()
        for idx, text in self.cameras:
            if text == label:
                return idx
        return None

    def _save_selected_camera_to_config(self) -> bool:
        camera_index = self._selected_camera_index()
        if camera_index is None:
            messagebox.showerror("Camera", "Please select a valid camera.")
            return False

        self.config.setdefault("camera", {})["device_number"] = camera_index
        save_config(self.config_path, self.config)
        return True

    def _on_camera_changed(self, _event=None) -> None:
        if not self._save_selected_camera_to_config():
            return

        if self.process and self.process.poll() is None:
            self._set_status("restarting", "Status: restarting monitor with new camera...")
            self.stop_monitoring()
            self.start_monitoring()
        else:
            self._set_status("saved", "Status: camera selection saved")

        self._restart_preview()

    def toggle_monitoring(self) -> None:
        if self.process and self.process.poll() is None:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        if self.process and self.process.poll() is None:
            self._set_status("running", "Status: already running")
            return

        if not self._save_selected_camera_to_config():
            return

        command: List[str]
        if os.path.exists(self.monitor_exe_path):
            command = [self.monitor_exe_path]
        elif os.path.exists(self.monitor_script_path):
            command = [sys.executable, self.monitor_script_path]
        else:
            self._set_status("error", "Status: launch target is missing")
            messagebox.showerror(
                "Launch error",
                f"Monitor target not found: {self.monitor_exe_path} or {self.monitor_script_path}",
            )
            return

        self.process = subprocess.Popen(
            command,
            cwd=self.base_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )

        self.toggle_button.configure(text="Stop monitoring")
        self._set_status("running", f"Status: running (PID {self.process.pid})")

    def stop_monitoring(self) -> None:
        if not self.process or self.process.poll() is not None:
            self.process = None
            self.toggle_button.configure(text="Start monitoring")
            self._set_status("stopped", "Status: stopped")
            return

        proc = self.process
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.wait(timeout=3)
            else:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            proc.kill()
            proc.wait(timeout=3)

        self.process = None
        self.toggle_button.configure(text="Start monitoring")
        self._set_status("stopped", "Status: stopped")

    def _poll_process(self) -> None:
        if self.process and self.process.poll() is not None:
            code = self.process.returncode
            self.process = None
            self.toggle_button.configure(text="Start monitoring")
            self._set_status("stopped", f"Status: stopped (exit {code})")
        self.root.after(1000, self._poll_process)

    def _on_close(self) -> None:
        self.stop_monitoring()
        self._stop_preview()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DMakGuiApp(root)
    root.mainloop()
