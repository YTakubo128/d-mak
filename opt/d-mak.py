import cv2
import yaml
import logging
from typing import Dict, List
from hand_gesture import HandGestureDetector
from performance_utils import GestureHandler, AsyncExecutor
from d_mak_execute import SwitchBotController, load_config
from switchbot_api_list import get_callable_commands, get_command
from logger_config import LoggerConfig
from memory_manager import MemoryManager
from error_handler import ErrorHandler


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HandGestureApp:
    """ハンドジェスチャを使った家電制御アプリ"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Args:
            config_path: 設定ファイルのパス
        """
        # 設定を読み込み
        self.config = load_config(config_path)
        
        # ロギング設定
        global logger
        logger = LoggerConfig.get_logger("d-mak", self.config)
        
        # メモリマネージャーを初期化
        self.memory_manager = MemoryManager(self.config, logger)
        
        # エラーハンドラーを初期化
        self.error_handler = ErrorHandler(self.config, logger)
        
        # カメラ設定
        camera_config = self.config.get('camera', {})
        self.camera_width = camera_config.get('resolution', [1280, 720])[0]
        self.camera_height = camera_config.get('resolution', [1280, 720])[1]
        self.camera_fps = camera_config.get('fps', 30)
        self.camera_device = camera_config.get('device_number', 0)
        
        # ジェスチャ設定
        gesture_config = self.config.get('gesture', {})
        confirmation_frames = gesture_config.get('confirmation_frames', 10)
        cooldown_seconds = gesture_config.get('cooldown_seconds', 5)
        detection_confidence = gesture_config.get('detection_confidence', 0.5)
        
        # SwitchBot設定
        switchbot_config = self.config.get('switchbot', {})
        self.token = switchbot_config.get('token', '')
        self.secret = switchbot_config.get('secret', '')
        
        # 初期化
        self.gesture_detector = HandGestureDetector(detection_confidence)
        self.gesture_handler = GestureHandler(confirmation_frames, cooldown_seconds)
        self.executor = AsyncExecutor()
        self.controller = SwitchBotController(self.token, self.secret, self.config, logger) if self.token and self.secret else None
        
        # カメラを初期化
        self.cap = cv2.VideoCapture(self.camera_device)
        self._setup_camera()
        
        # デバイス設定をロード（gesture_actionsで参照できるようキーを作成）
        self.device_lookup = self._build_device_lookup()

        # ジェスチャごとの実行対象デバイス一覧をロード
        self.gesture_actions = self._build_gesture_actions()
        
        logger.info("HandGestureApp initialized")

    def _build_device_lookup(self) -> Dict[str, dict]:
        """config.yaml の devices セクションからデバイス参照辞書を作成"""
        lookup: Dict[str, dict] = {}
        devices = self.config.get('devices', [])

        for idx, device in enumerate(devices):
            if not isinstance(device, dict):
                logger.warning(f"devices[{idx}] is not an object. Skipped.")
                continue

            device_id = device.get('id')
            if not device_id:
                logger.warning(f"devices[{idx}] has no id. Skipped.")
                continue

            if device.get('enabled', True) is False:
                continue

            key = str(device.get('key', device_id))
            lookup[key] = {
                'id': device_id,
                'name': device.get('name', key),
                'type': device.get('type', 'unknown')
            }

        return lookup

    def _build_gesture_actions(self) -> Dict[int, dict]:
        """config.yaml の gesture_actions を読み込み、ジェスチャ実行設定を構築"""
        gesture_name_map = {1: "パー", 2: "グー", 3: "ワン"}
        actions: Dict[int, dict] = {}
        raw_actions = self.config.get('gesture_actions', {})

        for raw_gesture_id, device_keys in raw_actions.items():
            try:
                gesture_id = int(raw_gesture_id)
            except (TypeError, ValueError):
                logger.warning(f"Invalid gesture id in gesture_actions: {raw_gesture_id}")
                continue

            if not isinstance(device_keys, list):
                logger.warning(f"gesture_actions[{raw_gesture_id}] must be a list")
                continue

            targets = []
            for item in device_keys:
                # 後方互換: "light_main" のような文字列指定は toggle 扱い
                if isinstance(item, str):
                    device_key = item
                    command = 'toggle'
                    parameter = 'default'
                elif isinstance(item, dict):
                    device_key = item.get('device') or item.get('key')
                    command = str(item.get('command', 'toggle'))
                    parameter = str(item.get('parameter', 'default'))
                else:
                    logger.warning(
                        f"Unsupported action format in gesture_actions[{raw_gesture_id}]: {item}"
                    )
                    continue

                device = self.device_lookup.get(str(device_key))
                if not device:
                    logger.warning(
                        f"Unknown device key in gesture_actions[{raw_gesture_id}]: {device_key}"
                    )
                    continue

                device_type = device.get('type', '')
                known_commands = get_callable_commands(device_type)
                if known_commands and command != 'toggle' and get_command(device_type, command) is None:
                    logger.warning(
                        f"Command '{command}' is not listed for device type '{device_type}'. "
                        f"gesture_actions[{raw_gesture_id}] entry skipped."
                    )
                    continue
                if not known_commands and command != 'toggle':
                    logger.info(
                        f"Device type '{device_type}' has no command catalog entry. "
                        f"Execute '{command}' without catalog validation."
                    )

                target = dict(device)
                target['command'] = command
                target['parameter'] = parameter
                targets.append(target)

            if targets:
                actions[gesture_id] = {
                    'name': gesture_name_map.get(gesture_id, f"Gesture-{gesture_id}"),
                    'targets': targets
                }

        # 後方互換: gesture_actions が未設定の場合は従来の固定マッピングを使用
        if not actions:
            actions = {
                1: {
                    'name': 'パー',
                    'targets': [
                        {
                            'id': 'device-id-1',
                            'name': 'default-1',
                            'type': 'unknown',
                            'command': 'toggle',
                            'parameter': 'default',
                        }
                    ]
                },
                2: {
                    'name': 'グー',
                    'targets': [
                        {
                            'id': 'device-id-2',
                            'name': 'default-2',
                            'type': 'unknown',
                            'command': 'toggle',
                            'parameter': 'default',
                        }
                    ]
                },
                3: {
                    'name': 'ワン',
                    'targets': [
                        {
                            'id': 'device-id-3',
                            'name': 'default-3',
                            'type': 'unknown',
                            'command': 'toggle',
                            'parameter': 'default',
                        }
                    ]
                },
            }

        return actions
    
    def _setup_camera(self):
        """カメラをセットアップ"""
        if not self.cap.isOpened():
            logger.error("カメラが開けません")
            return
        
        # 解像度を設定（タイムアウト付き）
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.camera_fps)
        except Exception as e:
            logger.warning(f"Camera resolution setup failed: {e}")
        
        # バッファサイズを1に設定（最新フレームのみ保持）
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception as e:
            logger.warning(f"Buffer size setup failed: {e}")
        
        # 実際に設定された解像度を取得
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        
        logger.info(f"Camera setup: Requested {self.camera_width}x{self.camera_height} @ {self.camera_fps}fps")
        logger.info(f"Camera setup: Actual {actual_width}x{actual_height} @ {actual_fps}fps")
    
    def handle_gesture(self, gesture_id: int):
        """ジェスチャに対応したアクションを実行"""
        if gesture_id not in self.gesture_actions or not self.controller:
            return
        
        action = self.gesture_actions[gesture_id]
        gesture_name = action['name']
        targets: List[dict] = action['targets']

        logger.info(f"Gesture detected: {gesture_name} (ID: {gesture_id}) -> {len(targets)} target(s)")

        # 1ジェスチャで複数デバイスを非同期実行
        for target in targets:
            device_id = target['id']
            device_name = target.get('name', device_id)
            command = target.get('command', 'toggle')
            parameter = target.get('parameter', 'default')

            logger.info(
                f"Trigger device: {device_name} ({device_id}) with {command}({parameter})"
            )

            if command == 'toggle':
                self.executor.execute_async(self.controller.toggle_device, device_id)
            else:
                self.executor.execute_async(
                    self.controller.execute_command,
                    device_id,
                    command,
                    parameter,
                )
    
    def run(self):
        """メインループを実行"""
        logger.info("Starting gesture recognition...")
        
        frame_count = 0
        
        try:
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    self.error_handler.handle_camera_error(Exception("Frame read failed"))
                    break
                
                frame_count += 1
                
                try:
                    # ジェスチャを認識
                    raw_gesture = self.gesture_detector.detect_pose(frame)
                    self.error_handler.reset_camera_error_count()  # エラーカウンタをリセット
                    
                    # ジェスチャを更新・確定を判定
                    confirmed_gesture = self.gesture_handler.update_gesture(raw_gesture)
                    
                    # 確定したジェスチャがある場合
                    if confirmed_gesture is not None:
                        # クールダウンを確認して実行
                        if self.gesture_handler.can_execute(confirmed_gesture):
                            self.handle_gesture(confirmed_gesture)
                            self.gesture_handler.reset_buffer()
                        else:
                            logger.debug(f"Gesture {confirmed_gesture} is on cooldown")
                    
                    # ランドマークを描画（デバッグ用）
                    frame_with_landmarks = self.gesture_detector.visualize_landmarks(frame, draw=True)
                    
                    # フレーム情報を表示
                    gesture_name_map = {0: "None", 1: "Paper", 2: "Fist", 3: "One"}
                    gesture_display = gesture_name_map.get(raw_gesture, "Unknown")
                    confirmed_display = gesture_name_map.get(confirmed_gesture, "None") if confirmed_gesture else "None"
                    
                    cv2.putText(
                        frame_with_landmarks,
                        f"Current: {gesture_display} | Confirmed: {confirmed_display}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )
                    cv2.putText(
                        frame_with_landmarks,
                        f"Frame: {frame_count} | Buffer: {len(self.gesture_handler.gesture_buffer)}/{self.gesture_handler.confirmation_frames}",
                        (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )
                    
                    # メモリ使用量を表示
                    mem_mb = self.memory_manager.get_memory_usage_mb()
                    cv2.putText(
                        frame_with_landmarks,
                        f"Memory: {mem_mb:.1f}MB",
                        (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )

                    cv2.putText(
                        frame_with_landmarks,
                        'PRESS "q" key to Exit',
                        (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )
                    
                    # フレーム表示
                    cv2.imshow('Hand Gesture Control', frame_with_landmarks)
                    
                    # メモリクリーンアップが必要か確認
                    if self.memory_manager.should_cleanup():
                        self.memory_manager.cleanup()
                    
                    # 定期的なパフォーマンスログ
                    if frame_count % 300 == 0:  # 300フレームごと
                        mem_stats = self.memory_manager.get_memory_stats()
                        error_stats = self.error_handler.get_error_stats()
                        logger.info(f"Stats - Frame: {frame_count}, Memory: {mem_stats.get('process_rss_mb', 0):.1f}MB, Errors: {error_stats['total_errors']}")
                    
                    # 'q'キーで終了
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("Exiting by user request...")
                        break
                
                except Exception as e:
                    logger.error(f"Error in main loop frame {frame_count}: {e}")
                    self.error_handler.handle_camera_error(e)
                    if self.error_handler.consecutive_camera_errors >= self.error_handler.max_consecutive_errors:
                        logger.critical("Too many consecutive errors. Exiting.")
                        break
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.critical(f"Critical error in run loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """終了処理"""
        self.cap.release()
        cv2.destroyAllWindows()
        
        # 最終統計を出力
        mem_stats = self.memory_manager.get_memory_stats()
        error_stats = self.error_handler.get_error_stats()
        
        logger.info("Final Statistics:")
        logger.info(f"  Memory: {mem_stats.get('process_rss_mb', 0):.1f}MB")
        logger.info(f"  Total Errors: {error_stats['total_errors']}")
        logger.info(f"  Camera Errors: {error_stats['consecutive_camera_errors']}")
        logger.info(f"  API Errors: {error_stats['consecutive_api_errors']}")
        logger.info("Cleanup complete")


if __name__ == '__main__':
    app = HandGestureApp("config.yaml")
    app.run()