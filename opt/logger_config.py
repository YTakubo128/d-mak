import logging
import logging.handlers
import os
from pathlib import Path


class LoggerConfig:
    """ロギング設定を管理するクラス"""
    
    _logger_instance = None
    _initialized = False
    
    @staticmethod
    def get_logger(name: str = "d-mak", config: dict = None) -> logging.Logger:
        """
        ロガーを取得または初期化
        
        Args:
            name: ロガー名
            config: 設定辞書 (from config.yaml)
        
        Returns:
            logging.Logger インスタンス
        """
        if LoggerConfig._logger_instance is not None:
            return LoggerConfig._logger_instance
        
        logger = logging.getLogger(name)
        
        if config is None:
            config = {}
        
        # 既に初期化されている場合はスキップ
        if LoggerConfig._initialized:
            return logger
        
        debug_config = config.get('debug', {})
        is_debug = debug_config.get('enabled', False)
        log_file = debug_config.get('log_file', 'app.log')
        
        # ログレベル設定
        log_level = logging.DEBUG if is_debug else logging.INFO
        logger.setLevel(log_level)
        
        # ハンドラーを削除（重複防止）
        logger.handlers.clear()
        
        # コンソール出力
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # ファイル出力（ロギング有効時のみ）
        if is_debug or log_file:
            try:
                # ログディレクトリがなければ作成
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # ロテーティングハンドラー（最大5ファイル、各10MBまで）
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5
                )
                file_handler.setLevel(log_level)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Failed to setup file logging: {e}")
        
        LoggerConfig._logger_instance = logger
        LoggerConfig._initialized = True
        
        return logger
    
    @staticmethod
    def reset():
        """ロガーのリセット"""
        LoggerConfig._logger_instance = None
        LoggerConfig._initialized = False
