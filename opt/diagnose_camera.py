#!/usr/bin/env python
"""カメラ診断スクリプト"""

import cv2
import sys

print("=" * 60)
print("カメラ診断")
print("=" * 60)

# 1. OpenCV バージョン確認
print(f"\n[1] OpenCV バージョン: {cv2.__version__}")

# 2. 利用可能なカメラを検索
print("\n[2] 利用可能なカメラを検索中...")
available_cameras = []

for i in range(5):  # 0-4のカメラデバイスをチェック
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        available_cameras.append(i)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        print(f"  ✓ カメラ {i}: {width}x{height} @ {fps}fps")
        cap.release()
    else:
        print(f"  ✗ カメラ {i}: 利用不可")

if not available_cameras:
    print("\n❌ 利用可能なカメラが見つかりません")
    print("   - カメラが接続されているか確認してください")
    print("   - 別のアプリケーション（Zoomなど）がカメラを使用していないか確認してください")
    sys.exit(1)

# 3. デフォルトカメラでテスト
print(f"\n[3] デフォルトカメラ（デバイス0）でテスト中...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("  ✗ カメラを開けません")
    sys.exit(1)

# 解像度設定テスト
print("  解像度設定テスト:")
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))

print(f"    要求: 1280x720 @ 30fps")
print(f"    実際: {width}x{height} @ {fps}fps")

# フレーム取得テスト
print("  フレーム取得テスト...")
ret, frame = cap.read()

if ret and frame is not None:
    print(f"    ✓ フレーム取得成功 ({frame.shape[1]}x{frame.shape[0]})")
else:
    print("    ✗ フレーム取得失敗")
    cap.release()
    sys.exit(1)

cap.release()

print("\n" + "=" * 60)
print("✓ カメラ診断完了")
print("=" * 60)
print("\n推奨アクション:")
print("1. カメラが正常な場合：config.yaml でデバイス番号を確認")
print("2. 別のアプリケーションがカメラ使用中の場合：それを終了")
print("3. d-mak.py を実行")
