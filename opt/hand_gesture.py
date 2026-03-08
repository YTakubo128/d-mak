import math
import mediapipe as mp


class HandGestureDetector:
    """手のジェスチャを認識"""
    
    def __init__(self, detection_confidence: float = 0.5):
        """
        Args:
            detection_confidence: 検出信頼度 (0.0-1.0)
        """
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=detection_confidence
        )
    
    @staticmethod
    def calc_distance(p0, p1) -> float:
        """2点間の距離を計算"""
        a1 = p1.x - p0.x
        a2 = p1.y - p0.y
        return math.sqrt(a1 * a1 + a2 * a2)
    
    @staticmethod
    def calc_angle(p0, p1, p2) -> float:
        """3点を使った角度を計算"""
        a1 = p1.x - p0.x
        a2 = p1.y - p0.y
        b1 = p2.x - p1.x
        b2 = p2.y - p1.y
        
        try:
            angle = math.acos(
                (a1 * b1 + a2 * b2) / 
                (math.sqrt((a1 * a1 + a2 * a2) * (b1 * b1 + b2 * b2)))
            ) * 180 / math.pi
            return angle
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    @staticmethod
    def calc_finger_angle(p0, p1, p2, p3, p4) -> float:
        """指（5点）の角度合計を計算"""
        result = 0
        result += HandGestureDetector.calc_angle(p0, p1, p2)
        result += HandGestureDetector.calc_angle(p1, p2, p3)
        result += HandGestureDetector.calc_angle(p2, p3, p4)
        return result
    
    def detect_pose(self, frame) -> int:
        """
        フレームからジェスチャを検出
        
        Args:
            frame: OpenCV フレーム (BGR形式)
        
        Returns:
            ジェスチャID: 0=無検出, 1=パー, 2=グー, 3=ワン
        """
        import cv2
        
        # BGR to RGB変換
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 手を検出
        results = self.hands.process(frame_rgb)
        
        if not results.multi_hand_landmarks:
            return 0  # 無検出
        
        # 最初の手のランドマークを取得
        hand_landmarks = results.multi_hand_landmarks[0]
        
        # 各指の状態を判定
        thumb_is_open = self.calc_finger_angle(
            hand_landmarks.landmark[0],
            hand_landmarks.landmark[1],
            hand_landmarks.landmark[2],
            hand_landmarks.landmark[3],
            hand_landmarks.landmark[4]
        ) < 70
        
        first_finger_is_open = self.calc_finger_angle(
            hand_landmarks.landmark[0],
            hand_landmarks.landmark[5],
            hand_landmarks.landmark[6],
            hand_landmarks.landmark[7],
            hand_landmarks.landmark[8]
        ) < 100
        
        second_finger_is_open = self.calc_finger_angle(
            hand_landmarks.landmark[0],
            hand_landmarks.landmark[9],
            hand_landmarks.landmark[10],
            hand_landmarks.landmark[11],
            hand_landmarks.landmark[12]
        ) < 100
        
        third_finger_is_open = self.calc_finger_angle(
            hand_landmarks.landmark[0],
            hand_landmarks.landmark[13],
            hand_landmarks.landmark[14],
            hand_landmarks.landmark[15],
            hand_landmarks.landmark[16]
        ) < 100
        
        fourth_finger_is_open = self.calc_finger_angle(
            hand_landmarks.landmark[0],
            hand_landmarks.landmark[17],
            hand_landmarks.landmark[18],
            hand_landmarks.landmark[19],
            hand_landmarks.landmark[20]
        ) < 100
        
        # ジェスチャの判定
        # パー：全ての指が開いている
        if (thumb_is_open and first_finger_is_open and 
            second_finger_is_open and third_finger_is_open and 
            fourth_finger_is_open):
            return 1  # パー
        
        # グー：全ての指が閉じている
        if (not first_finger_is_open and not second_finger_is_open and 
            not third_finger_is_open and not fourth_finger_is_open):
            return 2  # グー
        
        # ワン：人差し指のみ開いている
        if (first_finger_is_open and not second_finger_is_open and 
            not third_finger_is_open and not fourth_finger_is_open):
            return 3  # ワン
        
        return 0  # その他
    
    def visualize_landmarks(self, frame, draw: bool = True):
        """
        ランドマークをフレーム上に描画
        
        Args:
            frame: OpenCV フレーム
            draw: 描画するか
        
        Returns:
            描画済みのフレーム
        """
        import cv2
        
        if not draw:
            return frame
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        if results.multi_hand_landmarks:
            mp_drawing = mp.solutions.drawing_utils
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS
                )
        
        return frame
