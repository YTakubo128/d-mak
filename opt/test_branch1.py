#!/usr/bin/env python
"""ブランチ1の動作確認用テストスクリプト"""

import sys

print("=" * 60)
print("ブランチ1: Performance Optimization - 動作確認")
print("=" * 60)

# 1. モジュールのインポートテスト
print("\n[1] モジュールインポートテスト...")
try:
    from hand_gesture import HandGestureDetector
    print("  ✓ hand_gesture モジュール OK")
except ImportError as e:
    print(f"  ✗ hand_gesture インポートエラー: {e}")
    sys.exit(1)

try:
    from performance_utils import GestureHandler, AsyncExecutor
    print("  ✓ performance_utils モジュール OK")
except ImportError as e:
    print(f"  ✗ performance_utils インポートエラー: {e}")
    sys.exit(1)

try:
    from d_mak_execute import SwitchBotController, load_config
    print("  ✓ d_mak_execute モジュール OK")
except ImportError as e:
    print(f"  ✗ d_mak_execute インポートエラー: {e}")
    sys.exit(1)

# 2. 設定ファイルのテスト
print("\n[2] 設定ファイル読み込みテスト...")
config = load_config('config.yaml')
camera_config = config.get('camera', {})
gesture_config = config.get('gesture', {})

print(f"  ✓ config.yaml 読み込み OK")
print(f"    - カメラ解像度: {camera_config.get('resolution')} (720p対応)")
print(f"    - FPS: {camera_config.get('fps')}")
print(f"    - ジェスチャ確定フレーム: {gesture_config.get('confirmation_frames')}")
print(f"    - クールダウン: {gesture_config.get('cooldown_seconds')}秒")

# 3. GestureHandlerのテスト
print("\n[3] GestureHandlerの動作テスト...")
gesture_handler = GestureHandler(
    confirmation_frames=gesture_config.get('confirmation_frames', 10),
    cooldown_seconds=gesture_config.get('cooldown_seconds', 5)
)

# ジェスチャ確定の流れをシミュレート
print("  ジェスチャシーケンステスト:")
print("    - 同じジェスチャ(3=ワン)を10フレーム連続入力")
for i in range(10):
    result = gesture_handler.update_gesture(3)
    print(f"      フレーム {i+1}: {result if result else 'None'}")

if result == 3:
    print("  ✓ ジェスチャ確定機能 OK")
else:
    print("  ✗ ジェスチャ確定エラー")
    sys.exit(1)

# 4. クールダウンテスト
print("\n[4] クールダウン機能テスト...")
gesture_handler.reset_buffer()

# 1回目の実行
can_execute_1 = gesture_handler.can_execute(3)
print(f"  1回目の実行: {can_execute_1} (期待値: True)")

# 2回目の実行（すぐ）
can_execute_2 = gesture_handler.can_execute(3)
print(f"  2回目の実行（直後）: {can_execute_2} (期待値: False)")

if can_execute_1 and not can_execute_2:
    print("  ✓ クールダウン機能 OK")
else:
    print("  ✗ クールダウン機能エラー")

# 5. AsyncExecutorのテスト
print("\n[5] AsyncExecutor非同期テスト...")
executor = AsyncExecutor()

test_result = []

def test_function(value):
    import time
    time.sleep(0.1)
    test_result.append(value)

thread = executor.execute_async(test_function, "テスト実行")
thread.join()  # スレッド終了まで待機

if test_result == ["テスト実行"]:
    print("  ✓ AsyncExecutor機能 OK")
else:
    print("  ✗ AsyncExecutor機能エラー")

# 6. HandGestureDetectorのインスタンス化テスト
print("\n[6] HandGestureDetectorのテスト...")
try:
    detector = HandGestureDetector(detection_confidence=0.5)
    print("  ✓ HandGestureDetector インスタンス化 OK")
except Exception as e:
    print(f"  ✗ HandGestureDetector エラー: {e}")

print("\n" + "=" * 60)
print("✓ すべてのテストが完了しました！")
print("=" * 60)
print("\n次のステップ:")
print("1. config.yaml に SwitchBot API トークンを入力")
print("2. d-mak.py を実行（カメラが必要）")
print("3. ジェスチャを認識して家電を操作できます")
