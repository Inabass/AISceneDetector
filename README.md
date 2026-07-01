# AI Scene Detector

Windows-first GPU video scene extraction app.

## Phase 1 Run

```bat
setup.bat
run.bat
```

`setup.bat` creates the virtual environment, installs dependencies, prepares
`data/`, and applies Alembic migrations. `run.bat` also applies pending
migrations before starting FastAPI.

`setup.bat` requires Python 3.12 or 3.13. Newer Python versions may not have
compatible CUDA PyTorch wheels yet, so the setup script avoids them.
By default it installs CUDA-enabled PyTorch from:

```text
https://download.pytorch.org/whl/cu128
```

Override this when needed:

```bat
set AISD_PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
setup.bat
```

Skip PyTorch installation only for non-GPU diagnostics:

```bat
set AISD_SKIP_TORCH_INSTALL=1
setup.bat
```

Manual migration command:

```bat
python -m app.db.migrate
```

Development initialization without schema migration:

```bat
python -m app.db.init_db
```

Repository classes do not commit or rollback transactions. Services use
`UnitOfWork` or an explicit service-level transaction boundary.

Default URL:

```text
http://127.0.0.1:8000
```

Health API:

```text
http://127.0.0.1:8000/api/v1/health
```

Upload a training video:

```bat
curl -F label_type=positive -F file=@sample.mp4 http://127.0.0.1:8000/api/v1/training/videos
```

Duplicate uploads return the existing video metadata with `duplicated: true`.

Check ffmpeg and ffprobe:

```text
http://127.0.0.1:8000/api/v1/system/video-tools
```

GPU status:

```text
http://127.0.0.1:8000/api/v1/gpu
```

Start training feature extraction:

```bat
curl -X POST http://127.0.0.1:8000/api/v1/training/videos/1/features -H "Content-Type: application/json" -d "{\"frame_interval_sec\":1.0}"
```

Create a model and start model training from completed training features:

```bat
curl -X POST http://127.0.0.1:8000/api/v1/models -H "Content-Type: application/json" -d "{\"name\":\"sample-model\",\"description\":\"first model\"}"
curl -X POST http://127.0.0.1:8000/api/v1/models/1/train -H "Content-Type: application/json" -d "{\"threshold\":null}"
```

Model artifacts are stored under `data/models/`. SQLite stores only model
metadata, active version pointers, thresholds, metrics, and relative artifact
paths. Model versions are immutable; rollback changes only the active version:

```bat
curl -X POST http://127.0.0.1:8000/api/v1/models/1/rollback -H "Content-Type: application/json" -d "{\"version_id\":1}"
```

Check or cancel a job:

```text
http://127.0.0.1:8000/api/v1/jobs/1
http://127.0.0.1:8000/api/v1/jobs/1/cancel
```
