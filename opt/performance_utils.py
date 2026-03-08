import time
import threading
from typing import Callable, Optional


class GestureHandler:
    """ジェスチャ認識及び実行管理"""
    
    def __init__(self, confirmation_frames: int = 10, cooldown_seconds: float = 5.0):
        """
        Args:
            confirmation_frames: ジェスチャ確定に必要なフレーム数
            cooldown_seconds: クールダウン時間（秒）
        """
        self.confirmation_frames = confirmation_frames
        self.cooldown_seconds = cooldown_seconds
        
        # 状態管理
        self.gesture_buffer = []  # 直近のジェスチャを保持
        self.last_execution_time = {}  # {gesture_id: timestamp}
        self.lock = threading.Lock()
    
    def update_gesture(self, current_gesture: int) -> Optional[int]:
        """
        ジェスチャを更新し、確定したジェスチャを返す
        
        Args:
            current_gesture: 現在のフレームで検出されたジェスチャ (0=無検出, 1=パー, 2=グー, 3=ワン)
        
        Returns:
            確定したジェスチャID、または None
        """
        with self.lock:
            # バッファにジェスチャを追加
            self.gesture_buffer.append(current_gesture)
            
            # バッファサイズを限定
            if len(self.gesture_buffer) > self.confirmation_frames:
                self.gesture_buffer.pop(0)
            
            # 十分なフレームが溜まったか確認
            if len(self.gesture_buffer) < self.confirmation_frames:
                return None
            
            # 直近confirmation_framesフレームが全て同じジェスチャか確認
            confirmed_gesture = self.gesture_buffer[0]
            if all(g == confirmed_gesture for g in self.gesture_buffer):
                # 無検出（0）は実行しない
                if confirmed_gesture == 0:
                    return None
                
                return confirmed_gesture
            
            return None
    
    def can_execute(self, gesture_id: int) -> bool:
        """
        ジェスチャの実行可能かどうか確認（クールダウン判定）
        
        Args:
            gesture_id: ジェスチャID
        
        Returns:
            実行可能な場合 True
        """
        with self.lock:
            current_time = time.time()
            last_time = self.last_execution_time.get(gesture_id, 0)
            
            if current_time - last_time >= self.cooldown_seconds:
                self.last_execution_time[gesture_id] = current_time
                return True
            
            return False
    
    def reset_buffer(self):
        """バッファをリセット（ジェスチャが失われた時）"""
        with self.lock:
            self.gesture_buffer.clear()


class AsyncExecutor:
    """非同期でAPI呼び出しを実行"""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.is_executing = False
    
    def execute_async(self, func: Callable, *args, **kwargs) -> threading.Thread:
        """
        関数を別スレッドで非同期実行
        
        Args:
            func: 実行する関数
            *args: 位置引数
            **kwargs: キーワード引数
        
        Returns:
            実行中のスレッドオブジェクト
        """
        def wrapper():
            with self.lock:
                if self.is_executing:
                    return
                self.is_executing = True
            
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"Error in async execution: {e}")
            finally:
                with self.lock:
                    self.is_executing = False
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return thread
    
    def is_busy(self) -> bool:
        """現在実行中かどうか"""
        with self.lock:
            return self.is_executing
