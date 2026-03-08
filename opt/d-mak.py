import cv2
import yaml
import logging
from hand_gesture import HandGestureDetector
from performance_utils import GestureHandler, AsyncExecutor
from d_mak_execute import SwitchBotController, load_config


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
        self.controller = SwitchBotController(self.token, self.secret) if self.token and self.secret else None
        
        # カメラを初期化
        self.cap = cv2.VideoCapture(self.camera_device)
        self._setup_camera()
        
        # ジェスチャマッピング（例）
        self.gesture_map = {
            1: ("パー", "device-id-1"),  # パー → デバイス1
            2: ("グー", "device-id-2"),  # グー → デバイス2
            3: ("ワン", "device-id-3"),  # ワン → デバイス3
        }
        
        logger.info("HandGestureApp initialized")
    
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
        if gesture_id not in self.gesture_map or not self.controller:
            return
        
        gesture_name, device_id = self.gesture_map[gesture_id]
        logger.info(f"Gesture detected: {gesture_name} (ID: {gesture_id})")
        
        # 非同期で実行
        self.executor.execute_async(
            self.controller.toggle_device,
            device_id
        )
    
    def run(self):
        """メインループを実行"""
        logger.info("Starting gesture recognition...")
        
        frame_count = 0
        
        try:
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # ジェスチャを認識
                raw_gesture = self.gesture_detector.detect_pose(frame)
                
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
                
                # フレーム表示
                cv2.imshow('Hand Gesture Control', frame_with_landmarks)
                
                # 'q'キーで終了
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("Exiting...")
                    break
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """終了処理"""
        self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Cleanup complete")


if __name__ == '__main__':
    app = HandGestureApp("config.yaml")
    app.run()