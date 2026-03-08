import time
import logging
from typing import Callable, Any, Optional
from enum import Enum


class ErrorSeverity(Enum):
    """エラーの重大度"""
    LOW = 1          # 軽度（自動リカバリ可能）
    MEDIUM = 2       # 中度（ユーザー注意必要）
    HIGH = 3         # 重度（システム停止可能性）


class ErrorHandler:
    """エラー処理と自動リカバリを管理"""
    
    def __init__(self, config: dict = None, logger: logging.Logger = None):
        """
        Args:
            config: エラーハンドリング設定 (from config.yaml)
            logger: ロガーインスタンス
        """
        self.config = config or {}
        self.logger = logger or logging.getLogger(__name__)
        
        # エラー処理設定を取得
        error_config = self.config.get('error_handling', {})
        self.max_retries = error_config.get('max_retries', 3)
        self.retry_delay_seconds = error_config.get('retry_delay_seconds', 2)
        self.camera_reconnect_delay = error_config.get('camera_reconnect_delay', 5)
        self.max_consecutive_errors = error_config.get('max_consecutive_errors', 5)
        
        # エラーカウンタ
        self.consecutive_camera_errors = 0
        self.consecutive_api_errors = 0
        self.total_errors = 0
    
    def handle_camera_error(self, error: Exception) -> Optional[str]:
        """
        カメラエラーをハンドル
        
        Args:
            error: 例外オブジェクト
        
        Returns:
            リカバリ推奨アクション（文字列）またはNone
        """
        self.consecutive_camera_errors += 1
        self.total_errors += 1
        
        self.logger.error(f"Camera error (count: {self.consecutive_camera_errors}): {error}")
        
        if self.consecutive_camera_errors >= self.max_consecutive_errors:
            self.logger.critical("Max consecutive camera errors reached. May need manual intervention.")
            return "manual_intervention"
        
        self.logger.info(f"Attempting camera reconnect in {self.camera_reconnect_delay}s...")
        time.sleep(self.camera_reconnect_delay)
        
        return "retry_camera"
    
    def reset_camera_error_count(self):
        """カメラエラーカウンタをリセット"""
        self.consecutive_camera_errors = 0
    
    def handle_api_error(self, error: Exception, attempt: int = 1) -> Optional[str]:
        """
        APIエラーをハンドル（リトライロジック）
        
        Args:
            error: 例外オブジェクト
            attempt: 試行回数
        
        Returns:
            アクション: "retry", "skip", "abort" など
        """
        self.consecutive_api_errors += 1
        self.total_errors += 1
        
        self.logger.warning(f"API error (attempt {attempt}/{self.max_retries}): {error}")
        
        # リトライ可能か確認
        if attempt < self.max_retries:
            # 指数バックオフ: 2s, 4s, 8s ...
            delay = self.retry_delay_seconds * (2 ** (attempt - 1))
            self.logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)
            return "retry"
        
        self.logger.error(f"API error after {self.max_retries} attempts. Skipping.")
        return "skip"
    
    def reset_api_error_count(self):
        """APIエラーカウンタをリセット"""
        self.consecutive_api_errors = 0
    
    def with_retry(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> Any:
        """
        リトライロジック付きで関数を実行
        
        Args:
            func: 実行する関数
            *args: 位置引数
            max_retries: 最大リトライ回数（Noneはデフォルト値使用）
            **kwargs: キーワード引数
        
        Returns:
            関数の戻り値、またはリトライ全て失敗時は None
        """
        max_retries = max_retries or self.max_retries
        attempt = 0
        
        while attempt < max_retries:
            try:
                attempt += 1
                result = func(*args, **kwargs)
                self.reset_api_error_count()
                return result
            except Exception as e:
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                
                if attempt >= max_retries:
                    self.logger.error(f"Failed after {max_retries} attempts")
                    return None
                
                # 指数バックオフ
                delay = self.retry_delay_seconds * (2 ** (attempt - 1))
                self.logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
        
        return None
    
    def get_error_stats(self) -> dict:
        """
        エラー統計を取得
        
        Returns:
            エラー統計辞書
        """
        return {
            'total_errors': self.total_errors,
            'consecutive_camera_errors': self.consecutive_camera_errors,
            'consecutive_api_errors': self.consecutive_api_errors,
            'max_consecutive_threshold': self.max_consecutive_errors
        }
    
    def reset_all_error_counts(self):
        """全エラーカウンタをリセット"""
        self.consecutive_camera_errors = 0
        self.consecutive_api_errors = 0
