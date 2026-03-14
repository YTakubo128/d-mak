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

## GUIランチャー（カメラ選択 / 監視ON-OFF）
`opt` ディレクトリで次を実行すると、GUIから監視制御できます。

```powershell
python d_mak_gui.py
```

GUIでできること:
- 接続中カメラの一覧取得（`Refresh`）
- プルダウンでカメラ切り替え（実行中は自動再起動）
- 監視プロセスの `Start monitoring` / `Stop monitoring`

補足:
- 監視本体は `d-mak.py` が別プロセスで起動します。
- OpenCVの画面で `q` を押して終了した場合も、GUI側で状態が追従します。

## EXE化（Windows, PyInstaller）
1. 依存をインストール

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

2. `opt` でGUIランチャーを `exe` 化

```powershell
cd opt
pyinstaller --noconfirm --onefile --windowed --name d-mak-launcher d_mak_gui.py
```

3. 監視本体を別 `exe` 化

```powershell
pyinstaller --noconfirm --onefile --name d-mak-monitor d_mak_monitor.py --add-data "d-mak.py;." --add-data "config.yaml;."
```

4. 出力先
- `opt\dist\d-mak-launcher.exe`
- `opt\dist\d-mak-monitor.exe`

注意:
- ランチャーは同一フォルダの `d-mak-monitor.exe` を優先して起動します。
- 配布時は2つの `exe` を同じフォルダに置いてください。

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
