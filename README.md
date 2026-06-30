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

`setup.bat` requires Python 3.12 or newer. It accepts Python 3.13+ as well.

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
