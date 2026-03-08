import json
import time
import hashlib
import hmac
import base64
import uuid
import requests
import yaml
import os
from typing import Optional


class SwitchBotController:
    """SwitchBot API を操作するクラス"""
    
    def __init__(self, token: str, secret: str, config: dict = None, logger = None):
        """
        Args:
            token: SwitchBot APIトークン
            secret: SwitchBot シークレットキー
            config: 設定辞書
            logger: ロガーインスタンス
        """
        self.token = token
        self.secret = secret
        self.base_url = "https://api.switch-bot.com/v1.1"
        self.config = config or {}
        
        import logging
        self.logger = logger or logging.getLogger(__name__)
        
        # リトライ設定を取得
        error_config = self.config.get('error_handling', {})
        self.max_retries = error_config.get('max_retries', 3)
        self.retry_delay = error_config.get('retry_delay_seconds', 2)
        self.api_timeout = 10  # API呼び出しタイムアウト（秒）
    
    def _create_header(self) -> dict:
        """APIヘッダーを生成"""
        apiHeader = {}
        nonce = uuid.uuid4()
        t = int(round(time.time() * 1000))
        string_to_sign = '{}{}{}'.format(self.token, t, nonce)
        
        string_to_sign = bytes(string_to_sign, 'utf-8')
        secret = bytes(self.secret, 'utf-8')
        
        sign = base64.b64encode(
            hmac.new(secret, msg=string_to_sign, digestmod=hashlib.sha256).digest()
        )
        
        apiHeader['Authorization'] = self.token
        apiHeader['Content-Type'] = 'application/json'
        apiHeader['charset'] = 'utf8'
        apiHeader['t'] = str(t)
        apiHeader['sign'] = str(sign, 'utf-8')
        apiHeader['nonce'] = str(nonce)
        
        return apiHeader
    
    def get_device_status(self, device_id: str) -> Optional[dict]:
        """
        デバイスの状態を取得
        
        Args:
            device_id: デバイスID
        
        Returns:
            デバイス状態情報、またはエラー時は None
        """
        try:
            headers = self._create_header()
            response = requests.get(
                f"{self.base_url}/devices/{device_id}/status",
                headers=headers,
                timeout=self.api_timeout
            )
            response.raise_for_status()
            return json.loads(response.text)
        except requests.Timeout:
            self.logger.error(f"API timeout: get_device_status for {device_id}")
            return None
        except requests.RequestException as e:
            self.logger.error(f"Error getting device status: {e}")
            return None
    
    def execute_command(self, device_id: str, command: str, parameter: str = "default") -> bool:
        """
        デバイスにコマンドを実行
        
        Args:
            device_id: デバイスID
            command: コマンド (turnOn, turnOff, toggle etc)
            parameter: パラメータ
        
        Returns:
            成功時は True、失敗時は False
        """
        try:
            headers = self._create_header()
            param = {
                "command": command,
                "parameter": parameter,
                "commandType": "command"
            }
            param_json = json.dumps(param)
            
            response = requests.post(
                f"{self.base_url}/devices/{device_id}/commands",
                data=param_json,
                headers=headers,
                timeout=self.api_timeout
            )
            response.raise_for_status()
            self.logger.info(f"Command executed: {command} on {device_id}")
            return True
        except requests.Timeout:
            self.logger.error(f"API timeout: execute_command for {device_id}")
            return False
        except requests.RequestException as e:
            self.logger.error(f"Error executing command: {e}")
            return False
    
    def toggle_device(self, device_id: str) -> bool:
        """
        デバイスの ON/OFF を切り替え（リトライロジック付き）
        
        Args:
            device_id: デバイスID
        
        Returns:
            成功時は True
        """
        import time
        
        for attempt in range(1, self.max_retries + 1):
            try:
                status_response = self.get_device_status(device_id)
                if not status_response or 'body' not in status_response:
                    self.logger.warning(f"Failed to get device status (attempt {attempt})")
                    
                    if attempt < self.max_retries:
                        delay = self.retry_delay * (2 ** (attempt - 1))
                        self.logger.info(f"Retrying in {delay}s...")
                        time.sleep(delay)
                    continue
                
                power_state = status_response['body'].get('power', 'unknown')
                
                if power_state == "on":
                    command = "turnOff"
                elif power_state == "off":
                    command = "turnOn"
                else:
                    self.logger.error(f"Unknown power state: {power_state}")
                    return False
                
                return self.execute_command(device_id, command)
            
            except Exception as e:
                self.logger.warning(f"Error during toggle (attempt {attempt}): {e}")
                
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    self.logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to toggle device after {self.max_retries} attempts")
                    return False
        
        return False


def load_config(config_path: str = "config.yaml") -> dict:
    """設定ファイルを読み込む"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return {}


def executeOne(device_id: str = None, token: str = None, secret: str = None, config: dict = None, logger = None):
    """
    デバイスを操作（レガシー互換性のための関数）
    
    Args:
        device_id: デバイスID (Noneの場合、config.yamlから読み込み)
        token: APIトークン
        secret: シークレットキー
        config: 設定辞書
        logger: ロガーインスタンス
    """
    import logging
    
    logger = logger or logging.getLogger(__name__)
    
    # 設定ファイルから値を取得
    if device_id is None or token is None or secret is None:
        if config is None:
            config = load_config()
        
        if device_id is None:
            device_id = config.get('_default_device_id')
        if token is None:
            token = config.get('switchbot', {}).get('token', '')
        if secret is None:
            secret = config.get('switchbot', {}).get('secret', '')
    
    if not token or not secret:
        logger.error("Error: API token or secret is not configured")
        return False
    
    controller = SwitchBotController(token, secret, config, logger)
    return controller.toggle_device(device_id)


if __name__ == '__main__':
    executeOne()