import base64
import os
import sys
from typing import Callable, List, Optional, Tuple

import cv2
import tkinter as tk

# HandGestureDetector のインポート（gui/ の親ディレクトリ = opt/ から）
try:
    _opt_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _opt_dir not in sys.path:
        sys.path.insert(0, _opt_dir)
    from hand_gesture import HandGestureDetector as _HandGestureDetector
    _GESTURE_AVAILABLE = True
except Exception:
    _GESTURE_AVAILABLE = False


def try_open_camera(index: int):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    return cap


def build_tapo_rtsp_url(ip: str, username: str, password: str, stream: str = "stream1") -> str:
    """Tapo C220 の RTSP URL を生成する"""
    return f"rtsp://{username}:{password}@{ip}/{stream}"


def discover_cameras(max_devices: int = 10) -> List[Tuple[int | str, str]]:
    """USBカメラを列挙して返す。Tapoカメラは GUI 側で別途追加する。"""
    cameras: List[Tuple[int | str, str]] = []
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


class CameraPreview:
    def __init__(
        self,
        root: tk.Tk,
        label: tk.Label,
        width: int,
        height: int,
        log_callback: Callable[[str, str], None],
        gesture_overlay: bool = False,
        gesture_callback: Optional[Callable[[int], None]] = None,
    ):
        self.root = root
        self.label = label
        self.width = width
        self.height = height
        self.log = log_callback

        self.cap = None
        self.photo = None
        self.error_reported = False
        self.after_id = None

        # ジェスチャーオーバーレイ
        self._gesture_detector = None
        self._last_gesture_id: int = 0
        self.gesture_callback = gesture_callback

        if gesture_overlay and _GESTURE_AVAILABLE:
            try:
                self._gesture_detector = _HandGestureDetector()
            except Exception as e:
                log_callback("WARN", f"Gesture overlay unavailable: {e}")

    def set_placeholder(self, message: str) -> None:
        self.photo = None
        self.label.configure(image="", text=message)

    def _frame_to_photo(self, frame) -> tk.PhotoImage | None:
        try:
            resized = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)

            # imencode(".png") handles BGR→RGB internally, so pass BGR frame directly
            ok_png, png_buf = cv2.imencode(".png", resized)
            if ok_png:
                png_base64 = base64.b64encode(png_buf.tobytes()).decode("ascii")
                return tk.PhotoImage(data=png_base64)

            # PPM fallback: convert to RGB since PPM is raw bytes (no auto-conversion)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            ok_ppm, ppm_buf = cv2.imencode(".ppm", rgb)
            if ok_ppm:
                ppm_base64 = base64.b64encode(ppm_buf.tobytes()).decode("ascii")
                return tk.PhotoImage(data=ppm_base64, format="PPM")
            return None
        except Exception:
            return None

    def start(self, source: int | str | None) -> None:
        """カメラを起動する。source は USB カメラ番号 (int) または RTSP URL (str)。"""
        self.stop()
        if source is None:
            self.set_placeholder("Select a camera")
            return

        if isinstance(source, str):
            # RTSP ストリーム（Tapo C220 など）
            cap = cv2.VideoCapture(source)
            label = "RTSP stream"
        else:
            # USB カメラ
            cap = try_open_camera(source)
            label = f"camera {source}"

        if not cap.isOpened():
            cap.release()
            self.set_placeholder(f"Failed to open {label}")
            self.log("ERROR", f"Failed to open {label}")
            return

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap = cap
        self.log("INFO", f"Preview started on {label}")
        self._update_frame()

    def stop(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.cap is not None:
            self.log("INFO", "Preview stopped")
            self.cap.release()
            self.cap = None

    def _update_frame(self) -> None:
        if self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.set_placeholder("Preview not available")
            self.after_id = self.root.after(200, self._update_frame)
            return

        # ジェスチャー検出とランドマーク描画（1回のMediaPipe処理）
        if self._gesture_detector is not None:
            try:
                gesture_id, frame = self._gesture_detector.detect_and_draw(frame)
                self._last_gesture_id = gesture_id
                # 毎フレーム呼ぶ（エンジンの状態機械はフレーム単位で動く）
                if self.gesture_callback:
                    self.gesture_callback(gesture_id)
            except Exception:
                pass  # オーバーレイ失敗時もプレビューは継続

        photo = self._frame_to_photo(frame)
        if photo is None:
            if not self.error_reported:
                self.log("ERROR", "Camera preview conversion failed")
                self.error_reported = True
            self.set_placeholder("Preview conversion failed")
            self.after_id = self.root.after(200, self._update_frame)
            return

        self.error_reported = False
        self.photo = photo
        self.label.configure(image=self.photo, text="")
        self.after_id = self.root.after(66, self._update_frame)
