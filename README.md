# AI Scene Detector

Windows と NVIDIA GPU を前提にした、動画シーン検出アプリです。

FastAPI、SQLite、SQLAlchemy、Alembic、PyTorch CUDA、OpenCLIP、OpenCV、ffmpeg / ffprobe を使います。動画本体、特徴量、モデル、検出結果、出力、ログは `data/` 配下に保存します。SQLiteには大きなバイナリを保存せず、メタデータと storage root からの相対パスだけを保存します。

## 現在できること

- 学習動画の登録
- SHA256による重複動画判定
- ffmpeg / ffprobe の存在確認
- OpenCVで読めない動画の状態分離
- OpenCLIP / PyTorch CUDA による特徴量抽出
- 特徴量ファイルの保存とキャッシュ用メタデータ管理
- モデル作成、モデルバージョン生成、有効バージョン管理
- 検出対象動画のアップロード
- モデルを使ったフレーム単位の推論
- timeline JSON保存
- シーン区間生成
- ffmpegによるシーン区間の切り出し
- サムネイルと軽量プレビュー生成
- 検出シーンへのフィードバック記録
- ジョブ管理、進捗確認、キャンセル要求
- Web UIからの一連操作

## 前提環境

- Windows
- Python 3.12 以上
- NVIDIA GPU
- CUDA対応PyTorch
- ffmpeg / ffprobe
- OpenCVで読み取り可能な動画

GPUなしのCPU fallbackは優先していません。特徴量抽出、モデル生成、検出ではCUDAが使えない場合に明確なエラーになります。

## セットアップ

初回セットアップ:

```bat
setup.bat
```

起動:

```bat
run.bat
```

`setup.bat` は仮想環境を作成し、依存関係をインストールし、`data/` を準備して、Alembic migration を適用します。`run.bat` も起動前に未適用の migration を適用します。

起動後:

```text
http://127.0.0.1:8000/
```

## .env

通常は `.env` なしでも起動できます。設定を変えたい場合は `.env.example` をコピーして `.env` を作成してください。

```bat
copy .env.example .env
```

代表的な設定:

```text
AISD_FFMPEG_PATH=C:\ProgramData\chocolatey\bin\ffmpeg.exe
AISD_FFPROBE_PATH=C:\ProgramData\chocolatey\bin\ffprobe.exe
AISD_STORAGE_ROOT=data
AISD_DEFAULT_FRAME_INTERVAL_SEC=1.0
AISD_DEFAULT_DETECTION_BATCH_SIZE=64
```

## Python と PyTorch

`setup.bat` は Python 3.12 以上を要求します。`py -3.12` 固定ではなく、3.12以上のPythonを探します。

標準では CUDA 対応 PyTorch を次のindexからインストールします。

```text
https://download.pytorch.org/whl/cu128
```

必要に応じて変更できます。

```bat
set AISD_PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
setup.bat
```

GPU診断だけ行いたい場合は、PyTorchのインストールをスキップできます。

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

`Base.metadata.create_all()` には依存していません。DBスキーマは Alembic migration で管理します。既存DBを破壊しない方針で、追加カラムや追加テーブルは migration で反映します。

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

## Windowsで確認済みの状態

これまでにWindows環境で次の流れを確認済みです。

- CUDA利用可能
- GPU: NVIDIA GeForce RTX 5080
- PyTorch: `2.11.0+cu128`
- CUDA runtime: `12.8`
- ffmpeg / ffprobe 検出成功
- 学習動画アップロード成功
- OpenCLIP特徴量抽出ジョブ成功
- モデル作成と `v1` 生成成功
- 対象動画の検出ジョブ成功
- シーン区間生成成功
- `copy` mode のExportジョブ成功
- `data\outputs\exports\...` にmp4出力成功

Preview/ThumbnailはExport機能に後から追加したため、既存Exportには自動では付きません。確認する場合は、最新コードでmigration適用後にExportを再実行してください。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/exports" `
  -ContentType "application/json" `
  -Body '{"detection_id":3,"mode":"copy"}'
```

ジョブ完了後:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/exports"
dir data\outputs\exports /s
dir data\thumbnails /s
dir data\previews /s
```

`thumbnail_url` と `preview_url` が返っていれば、ブラウザUIからも確認できます。

## Web UIでの使い方

ブラウザで開きます。

```text
http://127.0.0.1:8000/
```

基本の流れ:

1. 学習動画を選ぶ
2. `positive` または `negative` を選んで登録する
3. 特徴量を生成する
4. モデルを作成する
5. モデルを学習する
6. 対象動画を選んで検出する
7. 判断用サムネイル付きでシーン区間を確認する
8. 正しい/誤検出/無視のフィードバックを記録する
9. Exportを実行する
10. サムネイル、プレビュー、出力動画を確認する

UIはローカル開発用です。長時間動画ではジョブ完了まで時間がかかるため、ジョブ状態を確認しながら待ってください。

## PowerShellの注意

PowerShellでは `curl` が `Invoke-WebRequest` の別名になるため、curl形式で送る場合は `curl.exe` を使ってください。

OK:

```powershell
curl.exe -F file=@C:\videos\sample.mp4 http://127.0.0.1:8000/api/v1/health
```

JSONを送る場合は `Invoke-RestMethod` が扱いやすいです。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models" `
  -ContentType "application/json" `
  -Body '{"name":"sample-model","description":"first model"}'
```

Markdownのリンク表記 `[http://...](http://...)` はコマンドに貼らないでください。URLはそのまま貼ります。

## APIでの使い方

### 1. 学習動画の登録

```powershell
curl.exe -F label_type=positive -F file=@C:\videos\sample.mp4 http://127.0.0.1:8000/api/v1/training/videos
```

`label_type` は `positive` または `negative` です。

同じ動画を再登録した場合は、新規保存せず、既存動画のメタデータを `duplicated: true` 付きで返します。重複判定にはSHA256を使います。

### 2. 特徴量抽出

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

### 3. モデル作成

論理モデルを作成します。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models" `
  -ContentType "application/json" `
  -Body '{"name":"sample-model","description":"first model"}'
```

### 4. モデル学習

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

保存済みフィードバックを再学習に含める場合:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models/1/train" `
  -ContentType "application/json" `
  -Body '{"threshold":null,"include_feedback":true}'
```

特定のフィードバックだけ使う場合:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models/1/train" `
  -ContentType "application/json" `
  -Body '{"threshold":null,"include_feedback":true,"feedback_ids":[1,2,3]}'
```

モデルバージョンは作成後に変更しません。追加学習や再学習では新しい `v2`、`v3` を作成します。

Web UIでは、`モデルを確認` を押すとモデルバージョン一覧が表示されます。有効バージョン以外の `ready` なバージョンには `このバージョンに戻す` ボタンが表示され、APIのrollbackを実行できます。

確認:

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

### 5. 検出

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

検出されたシーン区間:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/detections/1/segments"
```

シーン区間生成では、平滑化、しきい値判定、短いgapの結合、padding、最小/最大durationを適用します。既定値は環境変数で上書きできます。

```text
AISD_DEFAULT_SMOOTHING_WINDOW_SEC
AISD_DEFAULT_MERGE_GAP_SEC
AISD_DEFAULT_PADDING_SEC
AISD_DEFAULT_MIN_SEGMENT_DURATION_SEC
AISD_DEFAULT_MAX_SEGMENT_DURATION_SEC
```

### 6. 動画出力・プレビュー

検出済みシーン区間をffmpegで切り出します。既定は高速な `copy` modeです。正確な境界が必要な場合は `reencode` modeを使います。

Exportジョブは、切り出し動画に加えて確認用のサムネイルと軽量プレビューも生成します。

保存先:

```text
data\outputs\exports\...
data\thumbnails\detection_<ID>\...
data\previews\detection_<ID>\...
```

全シーン区間を出力:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/exports" `
  -ContentType "application/json" `
  -Body '{"detection_id":1,"mode":"copy"}'
```

特定のシーン区間だけ出力:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/exports" `
  -ContentType "application/json" `
  -Body '{"detection_id":1,"segment_ids":[1],"mode":"reencode"}'
```

ジョブ成功後、出力結果を確認します。

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/exports"
dir data\outputs\exports /s
dir data\thumbnails /s
dir data\previews /s
```

APIレスポンスには、保存先の相対パスとブラウザ確認用URLが含まれます。

```text
output_path / output_url
thumbnail_path / thumbnail_url
preview_path / preview_url
```

`copy` modeは高速ですが、キーフレーム都合で開始・終了位置が少しズレる場合があります。境界精度を優先する場合は `reencode` modeを使ってください。

### 7. フィードバック

検出されたシーン区間に、モデル改善用のフィードバックを記録できます。これはシーンデータベースではなく、検出結果に対する学習改善用の履歴です。動画本体や切り出し動画はDBに保存せず、検出結果、segment、モデルバージョン、ラベル、時刻スナップショットだけを保存します。

ラベル:

```text
positive  正しい検出
negative  誤検出
ignore    学習には使わない
```

シーン区間にフィードバックを付ける例:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/feedback" `
  -ContentType "application/json" `
  -Body '{"detection_id":3,"segment_id":1,"label":"negative","source":"manual","memo":"似ているが目的シーンではない"}'
```

フィードバック一覧:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/feedback?detection_id=3"
```

Web UIでは、シーン一覧に表示される `正しい` / `誤検出` / `無視` ボタンから登録できます。

判断用サムネイルは、シーン一覧の取得時に不足分を自動生成します。保存先は次の通りです。

```text
data\thumbnails\detections\detection_<ID>\segment_001.jpg
```

フィードバックを再学習に含めると、対象シーン区間内から複数フレームを等間隔にサンプリングしてOpenCLIP特徴量を生成し、`data\features\feedback\...` に保存します。DBにはフィードバックID、ラベル、時刻、相対パスなどのメタデータだけを保持します。

フィードバック特徴量のサンプリングは環境変数で調整できます。

```text
AISD_FEEDBACK_MAX_FRAMES_PER_SEGMENT=5
AISD_FEEDBACK_MIN_FRAME_INTERVAL_SEC=0.5
```

## ジョブ確認とキャンセル

ジョブ一覧:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs"
```

ジョブ確認:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs/1"
```

ジョブログ:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs/1/logs"
```

失敗またはキャンセル済みジョブの再試行:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/jobs/1/retry"
```

キャンセル要求:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/jobs/1/cancel"
```

キャンセルは即時停止ではなく、処理の安全な境界で反映されます。

Web UIでは、`ジョブ` セクションから直近ジョブ、詳細、ログを確認できます。`failed` / `cancelled` のジョブには `再試行` ボタンが表示されます。

## ストレージ確認とcleanup

容量確認:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/system/storage"
```

cleanup見積もり:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/system/cleanup" `
  -ContentType "application/json" `
  -Body '{"dry_run":true,"targets":["temp","previews","thumbnails"],"older_than_hours":24}'
```

cleanup実行:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/system/cleanup" `
  -ContentType "application/json" `
  -Body '{"dry_run":false,"targets":["temp","previews","thumbnails"],"older_than_hours":24}'
```

cleanup対象は再生成可能な派生物と一時ファイルに限定しています。学習動画、特徴量、モデル、Export済み動画は削除しません。

Web UIでは、`ストレージ` セクションから容量確認、cleanup見積もり、cleanup実行ができます。

## モデルロールバック

ロールバックはファイルをコピーせず、有効なモデルバージョンを指す値だけを変更します。

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/models/1/rollback" `
  -ContentType "application/json" `
  -Body '{"version_id":1}'
```

## 保存先

主な保存先:

```text
data\uploads\                 アップロード動画
data\features\                OpenCLIP特徴量
data\models\                  モデル成果物
data\outputs\detections\      timeline JSON
data\outputs\exports\         切り出し動画
data\thumbnails\              サムネイル
data\previews\                軽量プレビュー
data\logs\                    ログ
data\app.db                   SQLite DB
```

DBには巨大バイナリを保存しません。動画、特徴量、モデル、出力ファイルはファイルシステムに保存し、DBにはメタデータと相対パスだけを保存します。

## APIエラー形式

APIエラーは統一形式で返します。stack traceはレスポンスに返しません。

```json
{
  "data": null,
  "error": {
    "error_code": "REQUEST_VALIDATION_ERROR",
    "message": "Request validation failed.",
    "detail": {},
    "recoverable": true,
    "suggested_action": "Check the request body, path, and query parameters.",
    "request_id": "..."
  },
  "request_id": "..."
}
```

## 現時点の制限

- 検出しきい値やシーン区間生成パラメータの細かいチューニングUIはまだ最小限です。
- フィードバック再学習はsegment内の少数フレームを使う初期実装です。重み付けや能動学習UIは次段階です。
- cleanupは `temp` / `previews` / `thumbnails` 対象です。モデルやExport済み動画の削除UIは未実装です。
- プレビューとサムネイルはExportジョブ成功時に生成されます。既存Exportに対する後追い生成APIは未実装です。
- Web UIはローカル開発用で、認証や複数ユーザー運用は対象外です。
- CPU fallbackは優先していません。
