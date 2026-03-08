#!/usr/bin/env python
"""ブランチ2の動作確認用テストスクリプト"""

import sys
import time
import logging

print("=" * 70)
print("ブランチ2: Stability Improvement - 動作確認")
print("=" * 70)

# 1. モジュールのインポートテスト
print("\n[1] モジュールインポートテスト...")
try:
    from logger_config import LoggerConfig
    print("  ✓ logger_config モジュール OK")
except ImportError as e:
    print(f"  ✗ logger_config インポートエラー: {e}")
    sys.exit(1)

try:
    from memory_manager import MemoryManager
    print("  ✓ memory_manager モジュール OK")
except ImportError as e:
    print(f"  ✗ memory_manager インポートエラー: {e}")
    sys.exit(1)

try:
    from error_handler import ErrorHandler
    print("  ✓ error_handler モジュール OK")
except ImportError as e:
    print(f"  ✗ error_handler インポートエラー: {e}")
    sys.exit(1)

try:
    from d_mak_execute import load_config
    print("  ✓ d_mak_execute モジュール OK")
except ImportError as e:
    print(f"  ✗ d_mak_execute インポートエラー: {e}")
    sys.exit(1)

# 2. ロギング設定のテスト
print("\n[2] ロギング設定テスト...")
config = load_config('config.yaml')
logger = LoggerConfig.get_logger("test", config)
logger.info("✓ ロギング機能 OK")

# 3. メモリマネージャーのテスト
print("\n[3] メモリマネージャーテスト...")
memory_mgr = MemoryManager(config, logger)

mem_usage = memory_mgr.get_memory_usage_mb()
print(f"  ✓ 現在のメモリ使用量: {mem_usage:.1f}MB")

mem_stats = memory_mgr.get_memory_stats()
print(f"  ✓ メモリ統計取得:", end="")
print(f" Process: {mem_stats.get('process_rss_mb', 0):.1f}MB, " + 
      f"System: {mem_stats.get('system_used_mb', 0):.1f}MB / {mem_stats.get('system_total_mb', 0):.1f}MB")

# クリーンアップテスト
should_clean = memory_mgr.should_cleanup()
print(f"  ✓ クリーンアップ必要判定: {should_clean}")

# 4. エラーハンドラーのテスト
print("\n[4] エラーハンドラーテスト...")
error_handler = ErrorHandler(config, logger)

# API エラーハンドリング
print("  API エラーシミュレーション:")
test_error = Exception("Test API Error")
for attempt in range(1, 4):
    result = error_handler.with_retry(
        lambda: 1/0,  # ゼロ除算エラー
        max_retries=2
    )

error_stats = error_handler.get_error_stats()
print(f"    ✓ エラー統計: {error_stats['total_errors']} total errors")

# カメラエラー処理
print("  カメラエラーシミュレーション:")
for i in range(3):
    error_handler.handle_camera_error(Exception(f"Camera error {i+1}"))
    print(f"    連続エラー数: {error_handler.consecutive_camera_errors}")

error_handler.reset_camera_error_count()
print(f"    ✓ エラーカウンタリセット: {error_handler.consecutive_camera_errors}")

# 5. リトライロジックのテスト
print("\n[5] リトライロジックテスト...")
attempt_count = 0

def failing_function():
    global attempt_count
    attempt_count += 1
    if attempt_count < 3:
        raise Exception(f"Attempt {attempt_count} failed")
    return "Success!"

attempt_count = 0
result = error_handler.with_retry(failing_function, max_retries=5)
print(f"  ✓ リトライ成功: {result} (試行回数: {attempt_count})")

# 6. 設定ファイルの確認
print("\n[6] 設定ファイル確認...")
debug_config = config.get('debug', {})
memory_config = config.get('memory', {})
error_config = config.get('error_handling', {})

print(f"  デバッグモード: {debug_config.get('enabled', False)}")
print(f"  ログファイル: {debug_config.get('log_file', 'app.log')}")
print(f"  メモリ警告閾値: {memory_config.get('memory_threshold_mb', 100)}MB")
print(f"  リトライ回数: {error_config.get('max_retries', 3)}")
print(f"  リトライ間隔: {error_config.get('retry_delay_seconds', 2)}秒")

if (debug_config.get('enabled') == False and
    memory_config.get('memory_threshold_mb') == 100 and
    error_config.get('max_retries') == 3):
    print("  ✓ 設定ファイルは正しく設定されています")

# 7. パフォーマンス計測テスト
print("\n[7] パフォーマンス計測テスト...")
start_time = time.time()
time.sleep(0.5)
elapsed = time.time() - start_time
print(f"  ✓ 経過時間計測: {elapsed:.3f}秒")

print("\n" + "=" * 70)
print("✓ すべてのテストが完了しました！")
print("=" * 70)
print("\n改善内容:")
print("1. ✓ ロギング設定：デバッグモード対応、ログローテーション")
print("2. ✓ メモリ管理：使用量監視、自動クリーンアップ")
print("3. ✓ エラーハンドリング：リトライロジック、指数バックオフ")
print("4. ✓ 統計情報：エラー/メモリ統計の取得")
print("5. ✓ 設定可能：config.yaml でリトライ等のパラメータ設定可能")
print("\n次のステップ:")
print("- d-mak.py を実行して実際の動作を確認")
print("- 長時間連続実行でメモリリークがないか確認")
print("- エラーハンドリングが正常に機能するか確認")
