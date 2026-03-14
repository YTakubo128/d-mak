import base64
from typing import Callable, List, Tuple

import cv2
import tkinter as tk


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


class CameraPreview:
    def __init__(
        self,
        root: tk.Tk,
        label: tk.Label,
        width: int,
        height: int,
        log_callback: Callable[[str, str], None],
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

    def set_placeholder(self, message: str) -> None:
        self.photo = None
        self.label.configure(image="", text=message)

    def _frame_to_photo(self, frame) -> tk.PhotoImage | None:
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (self.width, self.height), interpolation=cv2.INTER_AREA)

            ok_png, png_buf = cv2.imencode(".png", resized)
            if ok_png:
                png_base64 = base64.b64encode(png_buf.tobytes()).decode("ascii")
                return tk.PhotoImage(data=png_base64)

            ok_ppm, ppm_buf = cv2.imencode(".ppm", resized)
            if ok_ppm:
                ppm_base64 = base64.b64encode(ppm_buf.tobytes()).decode("ascii")
                return tk.PhotoImage(data=ppm_base64, format="PPM")
            return None
        except Exception:
            return None

    def start(self, camera_index: int | None) -> None:
        self.stop()
        if camera_index is None:
            self.set_placeholder("Select a camera")
            return

        cap = try_open_camera(camera_index)
        if not cap.isOpened():
            cap.release()
            self.set_placeholder(f"Failed to open camera {camera_index}")
            self.log("ERROR", f"Failed to open camera {camera_index}")
            return

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap = cap
        self.log("INFO", f"Preview started on camera {camera_index}")
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
