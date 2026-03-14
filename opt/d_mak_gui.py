import os
import sys
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from typing import List, Tuple

from gui.camera_service import CameraPreview, discover_cameras
from gui.config_store import load_config, save_config
from gui.log_panel import LogPanel
from gui.monitor_runner import MonitorRunner


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
        self.cameras: List[Tuple[int, str]] = []
        self.monitor = MonitorRunner(self.base_dir, self.monitor_exe_path, self.monitor_script_path)
        self.preview: CameraPreview | None = None
        self.log_panel: LogPanel | None = None

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

        log_group = ttk.LabelFrame(container, text="Log", padding=8)
        log_group.pack(fill="both", expand=True, pady=(10, 0))

        self.log_panel = LogPanel(log_group, max_lines=300)

        self.preview = CameraPreview(
            root=self.root,
            label=self.preview_label,
            width=640,
            height=360,
            log_callback=self._append_log,
        )

        self._set_status("stopped", "Status: stopped")
        self._append_log("INFO", "GUI initialized")

    def _set_status(self, level: str, message: str) -> None:
        color = self.STATUS_COLORS.get(level, self.STATUS_COLORS["error"])
        self.status_level = level
        self.status_text.set(message)
        self.status_indicator.itemconfigure(self.status_dot, fill=color)

    def _append_log(self, level: str, message: str) -> None:
        if self.log_panel is not None:
            self.log_panel.append(level, message)

    def _drain_log_queue(self) -> None:
        for line in self.monitor.drain_output():
            stripped = line.rstrip()
            if stripped:
                self._append_log("MON", stripped)

    def refresh_cameras(self, initial: bool = False) -> None:
        self.cameras = discover_cameras(max_devices=10)
        if not self.cameras:
            self.camera_combo["values"] = []
            self.selected_camera.set("")
            self._set_status("no-camera", "Status: no camera found")
            if self.preview is not None:
                self.preview.stop()
                self.preview.set_placeholder("No camera preview")
            self._append_log("WARN", "No camera device detected")
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
        self._append_log("INFO", f"Camera list refreshed ({len(self.cameras)} found)")

    def _restart_preview(self) -> None:
        if self.preview is not None:
            self.preview.start(self._selected_camera_index())

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

        if self.monitor.is_running():
            self._set_status("restarting", "Status: restarting monitor with new camera...")
            self._append_log("INFO", "Restarting monitor due to camera change")
            self.stop_monitoring()
            self.start_monitoring()
        else:
            self._set_status("saved", "Status: camera selection saved")
            idx = self._selected_camera_index()
            if idx is not None:
                self._append_log("INFO", f"Camera selection saved: {idx}")

        self._restart_preview()

    def toggle_monitoring(self) -> None:
        if self.monitor.is_running():
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        if self.monitor.is_running():
            self._set_status("running", "Status: already running")
            self._append_log("INFO", "Monitor is already running")
            return

        if not self._save_selected_camera_to_config():
            return

        try:
            proc = self.monitor.start()
        except FileNotFoundError:
            self._set_status("error", "Status: launch target is missing")
            self._append_log("ERROR", "Monitor launch target not found")
            messagebox.showerror(
                "Launch error",
                f"Monitor target not found: {self.monitor_exe_path} or {self.monitor_script_path}",
            )
            return

        self.toggle_button.configure(text="Stop monitoring")
        self._set_status("running", f"Status: running (PID {proc.pid})")
        self._append_log("INFO", f"Monitor started (PID {proc.pid})")

    def stop_monitoring(self) -> None:
        stopped = self.monitor.stop()
        if not stopped:
            self.toggle_button.configure(text="Start monitoring")
            self._set_status("stopped", "Status: stopped")
            self._append_log("INFO", "Monitor is already stopped")
            return

        self.toggle_button.configure(text="Start monitoring")
        self._set_status("stopped", "Status: stopped")
        self._append_log("INFO", "Monitor stopped")

    def _poll_process(self) -> None:
        self._drain_log_queue()
        code = self.monitor.poll_exit_code()
        if code is not None:
            self.monitor.process = None
            self.toggle_button.configure(text="Start monitoring")
            self._set_status("stopped", f"Status: stopped (exit {code})")
            self._append_log("INFO", f"Monitor exited with code {code}")
        self.root.after(1000, self._poll_process)

    def _on_close(self) -> None:
        self.stop_monitoring()
        if self.preview is not None:
            self.preview.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DMakGuiApp(root)
    root.mainloop()
