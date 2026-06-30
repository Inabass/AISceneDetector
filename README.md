# AI Scene Detector

Windows 向け GPU 対応の動画シーン抽出アプリケーションです。FastAPI、SQLite、SQLAlchemy、PyTorch CUDA、OpenCLIP、OpenCV、ffmpeg/ffprobe を使い、学習動画から特徴量を作成して対象動画の類似シーン検出へつなげます。

## セットアップと起動

```bat
setup.bat
run.bat
```

`setup.bat` は Python 仮想環境を作成し、依存関係をインストールし、`data/` 配下の保存先を準備して Alembic migration を適用します。`run.bat` も起動前に未適用 migration を適用してから FastAPI を起動します。

Python は 3.12 以上が必要です。

## CUDA 対応 PyTorch

RTX 5090 を前提に、`setup.bat` は通常の依存関係より先に CUDA 対応 PyTorch wheel を明示的にインストールします。

```bat
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

これにより、CPU-only 版 PyTorch が誤って入ることを避けます。PyTorch 公式の推奨 CUDA wheel index が変わった場合は、公式インストールページのコマンドに合わせて `setup.bat` を更新してください。

インストール後は次のコマンドで CUDA 認識を確認できます。

```bat
.venv\Scripts\python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

OpenCLIP まで含めた実 GPU 成功パスは次で確認します。

```bat
.venv\Scripts\python scripts\check_cuda_openclip.py
```

## DB migration

手動で migration を適用する場合:

```bat
python -m app.db.migrate
```

開発用の初期化のみ行う場合:

```bat
python -m app.db.init_db
```

Repository は commit / rollback を直接行いません。Service 層が `UnitOfWork` または明示的なトランザクション境界を持ちます。

## 既定 URL

```text
http://127.0.0.1:8000
```

## Health API

```text
http://127.0.0.1:8000/api/v1/health
```

## 学習動画アップロード

```bat
curl -F label_type=positive -F file=@sample.mp4 http://127.0.0.1:8000/api/v1/training/videos
```

重複アップロード時は既存動画 metadata を返し、`duplicated: true` を付与します。

## Feature 抽出 Job

Feature 抽出は永続 Worker が DB 上の queued job を取得して実行します。API リクエスト内では長時間処理を直接実行しません。

```bat
curl -X POST -H "Content-Type: application/json" -d "{}" http://127.0.0.1:8000/api/v1/training/videos/1/features
```

Job 状態、キャンセル、再試行、ログ確認:

```text
GET  /api/v1/jobs
GET  /api/v1/jobs/{job_id}
POST /api/v1/jobs/{job_id}/cancel
POST /api/v1/jobs/{job_id}/retry
GET  /api/v1/jobs/{job_id}/logs
```

Feature manifest 確認:

```text
GET /api/v1/features/{feature_id}/manifest
```

Feature は `data/features/` 配下に chunked `.npz` と manifest として保存されます。動画本体や Feature の巨大バイナリは DB に保存しません。

## ffmpeg / ffprobe 確認

```text
http://127.0.0.1:8000/api/v1/system/video-tools
```
