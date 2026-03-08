import psutil
import gc
import logging
import time
from typing import Optional


class MemoryManager:
    """メモリ使用量の監視と管理"""
    
    def __init__(self, config: dict = None, logger: logging.Logger = None):
        """
        Args:
            config: メモリ設定 (from config.yaml)
            logger: ロガーインスタンス
        """
        self.config = config or {}
        self.logger = logger or logging.getLogger(__name__)
        
        # メモリ設定を取得
        memory_config = self.config.get('memory', {})
        self.max_buffer_size = memory_config.get('max_buffer_size', 100)
        self.cleanup_interval = memory_config.get('cleanup_interval', 300)
        self.memory_threshold_mb = memory_config.get('memory_threshold_mb', 100)
        self.mediapipe_reinit_interval = memory_config.get('mediapipe_reinit_interval', 3600)
        
        # 状態
        self.last_cleanup_time = time.time()
        self.last_mediapipe_reinit_time = time.time()
        self.process = psutil.Process()
    
    def get_memory_usage_mb(self) -> float:
        """
        現在のメモリ使用量を取得（MB）
        
        Returns:
            メモリ使用量（MB）
        """
        try:
            return self.process.memory_info().rss / (1024 * 1024)
        except Exception as e:
            self.logger.warning(f"Failed to get memory usage: {e}")
            return 0.0
    
    def check_memory_threshold(self) -> bool:
        """
        メモリ使用量が閾値を超えているか確認
        
        Returns:
            閾値超過時 True
        """
        current_memory = self.get_memory_usage_mb()
        
        if current_memory > self.memory_threshold_mb:
            self.logger.warning(
                f"Memory usage high: {current_memory:.1f}MB / {self.memory_threshold_mb}MB"
            )
            return True
        
        return False
    
    def should_cleanup(self) -> bool:
        """
        クリーンアップが必要か確認
        
        Returns:
            クリーンアップが必要な場合 True
        """
        elapsed = time.time() - self.last_cleanup_time
        return elapsed >= self.cleanup_interval or self.check_memory_threshold()
    
    def cleanup(self):
        """メモリをクリーンアップ"""
        try:
            current_memory_before = self.get_memory_usage_mb()
            
            # ガベージコレクション実行
            gc.collect()
            
            current_memory_after = self.get_memory_usage_mb()
            freed = current_memory_before - current_memory_after
            
            if freed > 0:
                self.logger.debug(
                    f"Memory cleanup: {current_memory_before:.1f}MB -> {current_memory_after:.1f}MB "
                    f"(freed: {freed:.1f}MB)"
                )
            
            self.last_cleanup_time = time.time()
        except Exception as e:
            self.logger.error(f"Memory cleanup failed: {e}")
    
    def should_reinit_mediapipe(self) -> bool:
        """
        MediaPipeの再初期化が必要か確認
        
        Returns:
            再初期化が必要な場合 True
        """
        elapsed = time.time() - self.last_mediapipe_reinit_time
        return elapsed >= self.mediapipe_reinit_interval
    
    def mark_mediapipe_reinit(self):
        """MediaPipe再初期化時刻を更新"""
        self.last_mediapipe_reinit_time = time.time()
    
    def get_memory_stats(self) -> dict:
        """
        メモリ統計情報を取得
        
        Returns:
            メモリ統計辞書
        """
        try:
            mem_info = self.process.memory_info()
            virtual_memory = psutil.virtual_memory()
            
            return {
                'process_rss_mb': mem_info.rss / (1024 * 1024),
                'process_vms_mb': mem_info.vms / (1024 * 1024),
                'system_total_mb': virtual_memory.total / (1024 * 1024),
                'system_used_mb': virtual_memory.used / (1024 * 1024),
                'system_percent': virtual_memory.percent,
                'threshold_mb': self.memory_threshold_mb
            }
        except Exception as e:
            self.logger.error(f"Failed to get memory stats: {e}")
            return {}
