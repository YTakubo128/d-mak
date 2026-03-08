# d-mak

MediaPipeで手のジェスチャを認識し、SwitchBotデバイスを操作するアプリです。

## 必要なもの
- Webカメラ
- SwitchBot Hub
- 操作対象のSwitchBotデバイス
- SwitchBot APIトークン/シークレット

## 現在の動作仕様
- `OKサイン` を起動トリガーとして使います。
- OKサインを認識すると、`ok_sign_timeout_seconds`（デフォルト7秒）の受付時間が開始されます。
- 受付時間内に `パー / グー / ワン` のいずれかを認識すると、`gesture_actions` に従って実行します。
- 1回実行したら受付は終了します。

## 設定ファイル
`opt/config.yaml` の `gesture` セクションで次を調整できます。

```yaml
gesture:
     confirmation_frames: 10
     cooldown_seconds: 5
     detection_confidence: 0.5
     ok_sign_timeout_seconds: 7
     ok_sign_threshold_frames: 3
     ok_sign_distance_threshold: 0.05
```

## 実行
`opt` ディレクトリで実行します。

```powershell
python d-mak.py
```

## 動作確認手順（固定シナリオ）
1. OKサインを出す。
2. 7秒以内にパーを出し、想定デバイスが動くことを確認する。
3. OKサインを出して7秒待ち、時間切れ後のジェスチャが無視されることを確認する。
4. OKサインなしでジェスチャを出し、実行されないことを確認する。
5. 実行直後に連続ジェスチャを出し、クールダウンが効くことを確認する。

## トラブルシュート
- カメラが開けない場合:
     - カメラ接続を確認する。
     - 他アプリがカメラを使用していないか確認する。
     - 複数カメラ環境では `config.yaml` の `camera.device_number` を変更する。
