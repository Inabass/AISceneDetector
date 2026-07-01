# AI Scene Detector

Windows と NVIDIA GPU を前提にした、動画シーン検出アプリです。

FastAPI、SQLite、SQLAlchemy、Alembic、PyTorch CUDA、OpenCLIP、OpenCV、ffmpeg / ffprobe を使います。動画本体、特徴量、モデル、出力、ログは `data/` 配下に保存します。SQLiteには大きなバイナリを保存せず、メタデータと相対パスだけを保存します。

## 起動方法

初回セットアップ:

```bat
setup.bat
```

起動:

```bat
run.bat
```

`setup.bat` は仮想環境を作成し、依存関係をインストールし、`data/` を準備して、Alembic migration を適用します。`run.bat` も起動前に未適用の migration を適用します。

標準URL:

```text
http://127.0.0.1:8000
```

## Python と PyTorch

`setup.bat` は Python 3.12 以上を要求します。CUDA対応PyTorch wheelとの互換性を優先するため、Python 3.12 / 3.13 を想定しています。

標準では CUDA 対応 PyTorch を次のindexからインストールします。

```text
https://download.pytorch.org/whl/cu128
```

必要に応じて変更できます。

```bat
set AISD_PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
setup.bat
```

GPUを使わない診断目的でのみ、PyTorchのインストールをスキップできます。

```bat
set AISD_SKIP_TORCH_INSTALL=1
setup.bat
```

## マイグレーション

通常は `setup.bat` または `run.bat` が自動で実行します。

手動で適用する場合:

```bat
python -m app.db.migrate
```

スキーマ変更なしで開発用ディレクトリだけ初期化する場合:

```bat
python -m app.db.init_db
```

リポジトリ層は `commit` / `rollback` しません。トランザクション境界はサービス層または `UnitOfWork` が持ちます。

## 動作確認API

ヘルスチェック:

```text
http://127.0.0.1:8000/api/v1/health
```

GPU:

```text
http://127.0.0.1:8000/api/v1/gpu
```

ffmpeg / ffprobe:

```text
http://127.0.0.1:8000/api/v1/system/video-tools
```

## 学習動画の登録

PowerShellでは `curl` が `Invoke-WebRequest` の別名になるため、`curl.exe` または `Invoke-RestMethod` を使ってください。

```powershell
curl.exe -F label_type=positive -F file=@C:\videos\sample.mp4 http://127.0.0.1:8000/api/v1/training/videos
```

`label_type` は `positive` または `negative` です。

同じ動画を再登録した場合は、新規保存せず、既存動画のメタデータを `duplicated: true` 付きで返します。重複判定にはSHA256を使います。

## 特徴量抽出

登録済み学習動画からOpenCLIP特徴量を生成します。特徴量ファイルは `data/features/` 配下に保存され、DBにはメタデータのみ保存されます。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/training/videos/1/features" `
  -ContentType "application/json" `
  -Body '{"frame_interval_sec":1.0,"batch_size":16}'
```

返ってきた `data.id` がジョブIDです。

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs/1"
```

## モデル作成

論理モデルを作成します。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models" `
  -ContentType "application/json" `
  -Body '{"name":"sample-model","description":"first model"}'
```

## モデル学習

完了済みの学習用特徴量からモデルバージョンを作成します。モデル成果物は `data/models/` 配下に保存され、DBには相対パス、しきい値、評価指標、有効バージョンを指す値などのメタデータだけを保存します。

全ての完了済み学習用特徴量を使う場合:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models/1/train" `
  -ContentType "application/json" `
  -Body '{"threshold":null}'
```

使用する特徴量を明示する場合:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models/1/train" `
  -ContentType "application/json" `
  -Body '{"threshold":null,"feature_ids":[1]}'
```

モデルバージョンは作成後に変更しません。追加学習や再学習では新しい `v2`、`v3` を作成します。

## モデル確認

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/models/1"
dir data\models\model_1\v1
```

期待されるファイル:

```text
model.npz
feature_set.json
metadata.json
```

## 検出

対象動画をアップロードし、有効なモデルバージョンでフレーム単位の推論を実行します。timelineは `data/outputs/detections/` 配下にJSONとして保存されます。

```powershell
curl.exe -F model_id=1 -F frame_interval_sec=1.0 -F batch_size=16 -F file=@C:\videos\target.mp4 http://127.0.0.1:8000/api/v1/detections
```

返ってきた `data.id` がジョブIDです。

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs/3"
```

検出結果:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/detections/1"
```

timeline:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/detections/1/timeline"
```

## ロールバック

ロールバックはファイルをコピーせず、有効なモデルバージョンを指す値だけを変更します。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models/1/rollback" `
  -ContentType "application/json" `
  -Body '{"version_id":1}'
```

## ジョブ確認とキャンセル

ジョブ確認:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs/1"
```

キャンセル要求:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/jobs/1/cancel"
```

キャンセルは即時停止ではなく、処理の安全な境界で反映されます。

## 現在の実装範囲

- 学習動画アップロード
- SHA256重複判定
- ffmpeg / ffprobe存在確認
- OpenCV unreadable動画の状態分離
- OpenCLIP / PyTorch CUDAによる特徴量抽出
- 特徴量ストア初期実装
- 特徴量キャッシュ初期実装
- ジョブ管理、進捗、キャンセル入口
- 論理モデルとモデルバージョン管理
- 中心ベクトルベースの初期モデル生成
- 有効バージョンのロールバック
- 検出対象動画の登録
- モデルを使ったフレーム推論
- timeline JSON保存

## 未実装または今後の対象

- シーン区間生成
- プレビュー生成
- 動画出力ジョブ
- フィードバックと継続学習
- Web UIからの一連操作
