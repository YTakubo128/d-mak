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
from gui.gesture_engine import GestureEngine


class DMakGuiApp:
    STATUS_COLORS = {
        "stopped": "#6c757d",
        "running": "#198754",
        "restarting": "#fd7e14",
        "error": "#dc3545",
        "no-camera": "#dc3545",
        "saved": "#0d6efd",
    }

    # Alexa風の青グラデーションサイクル（暗→明→暗でパルス感を演出）
    ALEXA_BLUE_CYCLE = [
        "#003f88", "#0057b8", "#007dcc", "#0099ff",
        "#00baff", "#00d4ff", "#00baff", "#0099ff",
        "#007dcc", "#0057b8",
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("d-mak launcher")
        self.root.geometry("760x820")
        self.root.resizable(True, True)
        self.root.minsize(760, 820)

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
        self.border_flash_id: str | None = None
        self.preview_frame: tk.Frame | None = None
        self._border_anim_active: bool = False
        self._border_anim_step: int = 0
        self._border_anim_id: str | None = None
        self._border_anim_timeout_id: str | None = None
        self._api_status_reset_id: str | None = None
        self._last_displayed_gesture: int = -1
        self._engine: GestureEngine = GestureEngine(self.config, self._append_log)

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

        # API ステータス行
        api_row = ttk.Frame(container)
        api_row.pack(fill="x", pady=(6, 0))

        self.api_indicator = tk.Canvas(api_row, width=16, height=16, highlightthickness=0)
        self.api_indicator.pack(side="left", padx=(0, 8))
        self.api_dot = self.api_indicator.create_oval(2, 2, 14, 14, fill="#444444", outline="")

        self.api_status_text = tk.StringVar(value="API: idle")
        api_status_label = ttk.Label(api_row, textvariable=self.api_status_text)
        api_status_label.pack(side="left")

        info = ttk.Label(
            container,
            text="Tip: Press 'q' in the OpenCV window to stop monitoring from the monitor side.",
        )
        info.pack(anchor="w", pady=(8, 0))

        preview_group = ttk.LabelFrame(container, text="Camera preview", padding=8)
        preview_group.pack(fill="x", pady=(10, 0))

        # 16:9固定サイズ (640x360) のフレームでラベルを包む（枠線フラッシュ用）
        self.preview_frame = tk.Frame(
            preview_group,
            width=640,
            height=360,
            bg="#111111",
            highlightthickness=5,
            highlightbackground="#222222",
        )
        self.preview_frame.pack_propagate(False)
        self.preview_frame.pack()

        self.preview_label = tk.Label(
            self.preview_frame,
            text="No camera preview",
            bg="#111111",
            fg="#dddddd",
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)

        # ジェスチャー状態表示ラベル（プレビュー枠の直下）
        self.gesture_label = tk.Label(
            preview_group,
            text="",
            font=("Segoe UI", 11),
            bg=self.root.cget("bg"),
            fg="#888888",
            anchor="w",
            padx=4,
        )
        self.gesture_label.pack(fill="x", pady=(4, 2))

        log_group = ttk.LabelFrame(container, text="Log", padding=8)
        log_group.pack(fill="both", expand=True, pady=(10, 0))

        self.log_panel = LogPanel(log_group, max_lines=300)

        self.preview = CameraPreview(
            root=self.root,
            label=self.preview_label,
            width=640,
            height=360,
            log_callback=self._append_log,
            gesture_overlay=True,
            gesture_callback=self._on_gesture_detected,
        )

        self._set_status("stopped", "Status: stopped")
        self._append_log("INFO", "GUI initialized")

    # ジェスチャーID → (表示テキスト, 文字色)
    _GESTURE_DISPLAY = {
        0: ("",                "#888888"),
        1: ("✋  パー",         "#00cc66"),
        2: ("✊  グー",         "#ff8800"),
        3: ("☝  ワン",         "#ffcc00"),
        4: ("👌  OK サイン",   "#00ccff"),
    }

    def _on_gesture_detected(self, gesture_id: int) -> None:
        """カメラプレビューのジェスチャー検出コールバック（毎フレーム呼ばれる）"""
        # ラベル・枠線は変化時のみ更新
        if gesture_id != self._last_displayed_gesture:
            self._last_displayed_gesture = gesture_id
            text, color = self._GESTURE_DISPLAY.get(gesture_id, ("", "#888888"))
            self.gesture_label.configure(text=text, fg=color)

            # OKサイン検出中は枠を青く（Alexaアニメーション中は干渉しない）
            if self.preview_frame is not None and not self._border_anim_active:
                if gesture_id == 4:
                    self.preview_frame.configure(highlightbackground="#00d4ff")
                else:
                    self.preview_frame.configure(highlightbackground="#222222")

        # インプロセスエンジンに毎フレーム渡す
        self._engine.on_gesture_id(gesture_id)

    # API ステータス定義: (ドット色, テキスト)
    _API_STATES = {
        "idle":      ("#444444", "API: idle"),
        "calling":   ("#0099ff", "API: リクエスト中..."),
        "retrying":  ("#fd7e14", "API: リトライ中..."),
        "success":   ("#198754", "API: コマンド送信完了"),
        "timeout":   ("#dc3545", "API: タイムアウト"),
        "error":     ("#dc3545", "API: エラー"),
        "failed":    ("#dc3545", "API: 送信失敗（リトライ上限）"),
    }

    def _set_api_status(self, state: str, auto_reset_ms: int | None = None) -> None:
        """APIステータスインジケータを更新する"""
        dot_color, text = self._API_STATES.get(state, self._API_STATES["idle"])
        self.api_dot_color = dot_color
        self.api_status_text.set(text)
        self.api_indicator.itemconfigure(self.api_dot, fill=dot_color)

        # 既存のリセットタイマーをキャンセル
        if self._api_status_reset_id is not None:
            self.root.after_cancel(self._api_status_reset_id)
            self._api_status_reset_id = None

        if auto_reset_ms is not None:
            self._api_status_reset_id = self.root.after(
                auto_reset_ms, lambda: self._set_api_status("idle")
            )

    def _set_status(self, level: str, message: str) -> None:
        color = self.STATUS_COLORS.get(level, self.STATUS_COLORS["error"])
        self.status_level = level
        self.status_text.set(message)
        self.status_indicator.itemconfigure(self.status_dot, fill=color)

    def _append_log(self, level: str, message: str) -> None:
        if self.log_panel is not None:
            self.log_panel.append(level, message)
        # インプロセスエンジン・サブプロセス両方のログからイベント検出
        self._process_log_event(message)

    def _process_log_event(self, message: str) -> None:
        """ログメッセージを見てUI演出・APIステータスを更新（共通処理）"""
        if not hasattr(self, "api_indicator"):
            return  # UI初期化前は無視
        # 枠線演出
        if "OK sign CONFIRMED" in message:
            self._start_blue_anim()
        elif "executed within trigger window" in message:
            self._stop_blue_anim()
            self._flash_border("#198754", 1000)
        # API ステータス
        if "Trigger device:" in message:
            self._set_api_status("calling")
        elif "Command executed:" in message:
            self._set_api_status("success", auto_reset_ms=3000)
        elif "Retrying in" in message:
            self._set_api_status("retrying")
        elif "API timeout:" in message:
            self._set_api_status("timeout", auto_reset_ms=5000)
        elif "Error executing command:" in message or "Error getting device status:" in message:
            self._set_api_status("error", auto_reset_ms=5000)
        elif "Failed to toggle device after" in message:
            self._set_api_status("failed", auto_reset_ms=8000)

    def _start_blue_anim(self) -> None:
        """Alexa風の青いグラデーションアニメーションを開始"""
        self._stop_blue_anim()
        self._border_anim_active = True
        self._border_anim_step = 0
        self._step_blue_anim()
        # configのok_sign_timeout_secondsに合わせて自動停止
        timeout_ms = int(self.config.get("gesture", {}).get("ok_sign_timeout_seconds", 7) * 1000)
        self._border_anim_timeout_id = self.root.after(timeout_ms, self._stop_blue_anim)

    def _step_blue_anim(self) -> None:
        """アニメーションの1フレームを更新（80msごと）"""
        if not self._border_anim_active:
            return
        color = self.ALEXA_BLUE_CYCLE[self._border_anim_step % len(self.ALEXA_BLUE_CYCLE)]
        if self.preview_frame is not None:
            self.preview_frame.configure(highlightbackground=color)
        self._border_anim_step += 1
        self._border_anim_id = self.root.after(80, self._step_blue_anim)

    def _stop_blue_anim(self) -> None:
        """アニメーションを停止して枠線をリセット"""
        self._border_anim_active = False
        if self._border_anim_id is not None:
            self.root.after_cancel(self._border_anim_id)
            self._border_anim_id = None
        if self._border_anim_timeout_id is not None:
            self.root.after_cancel(self._border_anim_timeout_id)
            self._border_anim_timeout_id = None
        if self.preview_frame is not None:
            self.preview_frame.configure(highlightbackground="#222222")

    def _flash_border(self, color: str, duration_ms: int = 800) -> None:
        """Camera previewの枠線を指定色でフラッシュし、duration_ms後にリセット"""
        if self.border_flash_id is not None:
            self.root.after_cancel(self.border_flash_id)
        if self.preview_frame is not None:
            self.preview_frame.configure(highlightbackground=color)
        self.border_flash_id = self.root.after(duration_ms, self._reset_border)

    def _reset_border(self) -> None:
        """枠線色をデフォルトに戻す"""
        self.border_flash_id = None
        if self.preview_frame is not None:
            self.preview_frame.configure(highlightbackground="#222222")

    def _drain_log_queue(self) -> None:
        for line in self.monitor.drain_output():
            stripped = line.rstrip()
            if stripped:
                # _append_log 内で _process_log_event も呼ばれる
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

        if self._engine._running:
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
        if self._engine._running:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        if self._engine._running:
            self._set_status("running", "Status: already running")
            self._append_log("INFO", "Monitor is already running")
            return

        if not self._save_selected_camera_to_config():
            return

        # インプロセスエンジンを起動（プレビューはそのまま継続）
        self._engine = GestureEngine(self.config, self._append_log)
        self._engine.start()
        self.toggle_button.configure(text="Stop monitoring")
        self._set_status("running", "Status: running (in-process)")

    def stop_monitoring(self) -> None:
        if not self._engine._running:
            self.toggle_button.configure(text="Start monitoring")
            self._set_status("stopped", "Status: stopped")
            self._append_log("INFO", "Monitor is already stopped")
            return

        self._engine.stop()
        self.toggle_button.configure(text="Start monitoring")
        self._set_status("stopped", "Status: stopped")

    def _poll_process(self) -> None:
        # サブプロセス出力の取り込み（将来的な互換用に残す）
        self._drain_log_queue()
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
