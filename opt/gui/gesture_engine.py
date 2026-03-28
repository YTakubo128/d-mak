"""
インプロセス ジェスチャーエンジン
カメラはGUIプレビューが保持し、検出済みのジェスチャーIDだけを受け取って
OK サイン→ジェスチャー→API呼び出しの状態機械を動かす。
"""
import os
import sys
import time
from typing import Callable, Dict, List, Optional

# opt/ ディレクトリへのパス解決（gui/ サブパッケージから呼ばれる場合）
_opt_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _opt_dir not in sys.path:
    sys.path.insert(0, _opt_dir)

from performance_utils import GestureHandler, AsyncExecutor
from d_mak_execute import SwitchBotController


class _CallbackLogger:
    """log_callback をラップして logging.Logger 互換インターフェースを提供する"""

    def __init__(self, callback: Callable[[str, str], None]):
        self._cb = callback

    def info(self, msg: str):
        self._cb("INFO", msg)

    def warning(self, msg: str):
        self._cb("WARN", msg)

    def error(self, msg: str):
        self._cb("ERROR", msg)

    def debug(self, msg: str):
        pass  # デバッグログは表示しない

    def critical(self, msg: str):
        self._cb("ERROR", f"[CRITICAL] {msg}")


class GestureEngine:
    """
    d-mak.py のジェスチャー制御ロジックをインプロセスで再現するエンジン。

    使い方:
        engine = GestureEngine(config, log_callback)
        engine.start()
        # カメラプレビューから毎フレーム呼ぶ:
        engine.on_gesture_id(gesture_id)
        engine.stop()
    """

    def __init__(self, config: dict, log_callback: Callable[[str, str], None]):
        self.config = config
        self._log_cb = log_callback
        self._running = False

        gesture_cfg = config.get("gesture", {})
        switchbot_cfg = config.get("switchbot", {})

        # OK サイン設定
        self._ok_timeout: float = gesture_cfg.get("ok_sign_timeout_seconds", 7)
        self._ok_threshold: int = gesture_cfg.get("ok_sign_threshold_frames", 3)

        # ジェスチャー確定・クールダウン管理
        self._handler = GestureHandler(
            confirmation_frames=gesture_cfg.get("confirmation_frames", 10),
            cooldown_seconds=gesture_cfg.get("cooldown_seconds", 5),
        )
        self._executor = AsyncExecutor()

        # SwitchBot コントローラー
        token = switchbot_cfg.get("token", "")
        secret = switchbot_cfg.get("secret", "")
        _logger = _CallbackLogger(log_callback)
        self._controller = (
            SwitchBotController(token, secret, config, _logger)
            if token and secret
            else None
        )

        # OK サイン状態
        self._ok_active: bool = False
        self._ok_time: Optional[float] = None
        self._ok_frames: int = 0

        # デバイス・ジェスチャーマッピング
        self._device_lookup: Dict[str, dict] = self._build_device_lookup()
        self._gesture_actions: Dict[int, dict] = self._build_gesture_actions()

    # ──────────────────────────────────────────────
    # 公開 API
    # ──────────────────────────────────────────────

    def start(self) -> None:
        self._reset_ok()
        self._handler.reset_buffer()
        self._running = True
        self._log_cb("INFO", "Gesture engine started (in-process)")

    def stop(self) -> None:
        self._running = False
        self._reset_ok()
        self._handler.reset_buffer()
        self._log_cb("INFO", "Gesture engine stopped")

    def on_gesture_id(self, gesture_id: int) -> None:
        """カメラプレビューから毎フレーム呼ばれる"""
        if not self._running:
            return

        # OK サイン連続フレームを追跡（閾値以上で受付開始）
        if gesture_id == 4:
            self._ok_frames += 1
            if self._ok_frames >= self._ok_threshold and not self._ok_active:
                self._ok_active = True
                self._ok_time = time.time()
                self._log_cb(
                    "INFO",
                    f"OK sign CONFIRMED - accepting gesture for {self._ok_timeout}s",
                )
        else:
            self._ok_frames = 0

        # タイムアウト確認
        self._check_timeout()

        # ジェスチャー確定判定
        confirmed = self._handler.update_gesture(gesture_id)
        if confirmed is None:
            return

        if confirmed == 4:
            # OK サイン確定（update_gesture 経由）
            if not self._ok_active:
                self._ok_active = True
                self._ok_time = time.time()
                self._log_cb(
                    "INFO",
                    f"OK sign CONFIRMED - accepting gesture for {self._ok_timeout}s",
                )
            self._handler.reset_buffer()

        elif self._ok_active:
            remaining = self._remaining_ok_time()
            if remaining > 0:
                if self._handler.can_execute(confirmed):
                    self._log_cb(
                        "INFO",
                        f"Gesture {confirmed} executed within trigger window "
                        f"({remaining:.1f}s remaining)",
                    )
                    self._dispatch_gesture(confirmed)
                    self._handler.reset_buffer()
                    self._reset_ok()
            else:
                self._handler.reset_buffer()

    # ──────────────────────────────────────────────
    # 内部メソッド
    # ──────────────────────────────────────────────

    def _check_timeout(self) -> None:
        if self._ok_active and self._ok_time is not None:
            if time.time() - self._ok_time > self._ok_timeout:
                self._reset_ok()

    def _remaining_ok_time(self) -> float:
        if not self._ok_active or self._ok_time is None:
            return 0.0
        return max(0.0, self._ok_timeout - (time.time() - self._ok_time))

    def _reset_ok(self) -> None:
        self._ok_active = False
        self._ok_time = None
        self._ok_frames = 0

    def _dispatch_gesture(self, gesture_id: int) -> None:
        action = self._gesture_actions.get(gesture_id)
        if not action or not self._controller:
            return

        targets: List[dict] = action["targets"]
        self._log_cb(
            "INFO",
            f"Gesture detected: {action['name']} (ID: {gesture_id}) -> {len(targets)} target(s)",
        )

        for target in targets:
            device_id = target["id"]
            device_name = target.get("name", device_id)
            command = target.get("command", "toggle")
            parameter = target.get("parameter", "default")

            self._log_cb(
                "INFO",
                f"Trigger device: {device_name} ({device_id}) with {command}({parameter})",
            )

            if command == "toggle":
                self._executor.execute_async(self._controller.toggle_device, device_id)
            else:
                self._executor.execute_async(
                    self._controller.execute_command, device_id, command, parameter
                )

    def _build_device_lookup(self) -> Dict[str, dict]:
        lookup: Dict[str, dict] = {}
        for device in self.config.get("devices", []):
            if not isinstance(device, dict):
                continue
            device_id = device.get("id")
            if not device_id or device.get("enabled", True) is False:
                continue
            key = str(device.get("key", device_id))
            lookup[key] = {
                "id": device_id,
                "name": device.get("name", key),
                "type": device.get("type", "unknown"),
            }
        return lookup

    def _build_gesture_actions(self) -> Dict[int, dict]:
        gesture_name_map = {1: "パー", 2: "グー", 3: "ワン"}
        actions: Dict[int, dict] = {}

        for raw_id, device_keys in self.config.get("gesture_actions", {}).items():
            try:
                gid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if not isinstance(device_keys, list):
                continue

            targets = []
            for item in device_keys:
                if isinstance(item, str):
                    device_key, command, parameter = item, "toggle", "default"
                elif isinstance(item, dict):
                    device_key = item.get("device") or item.get("key")
                    command = str(item.get("command", "toggle"))
                    parameter = str(item.get("parameter", "default"))
                else:
                    continue

                device = self._device_lookup.get(str(device_key))
                if not device:
                    continue
                target = dict(device)
                target["command"] = command
                target["parameter"] = parameter
                targets.append(target)

            if targets:
                actions[gid] = {
                    "name": gesture_name_map.get(gid, f"Gesture-{gid}"),
                    "targets": targets,
                }

        return actions
