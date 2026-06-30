# Backend Architecture

## FastAPI 設計

FastAPI は REST API、静的 Web UI 配信、ファイルダウンロードを担当する。API は `/api/v1` に集約し、UI ルーティングと分離する。

## API Layer

API Layer は Pydantic schema による入力検証、HTTP status の決定、Service 呼び出しを行う。DB セッションやファイル処理の詳細を API ハンドラに書かない。

## Service Layer

Service Layer は TrainingService、DetectionService、ModelService、ExportService、FeedbackService、JobService、StorageService、GpuService で構成する。ユースケースの流れと権限のない単一ユーザー前提の整合性を担保する。

## Core Layer

Core Layer は AI、動画、エクスポート、スコアリングなど純粋な処理を持つ。Core は FastAPI と SQLAlchemy に依存しない。

## Repository Layer

Repository は SQLAlchemy Model の CRUD と検索を担当する。Service は Repository を通じて DB にアクセスし、直接 query を散在させない。

## DI

DB session、Settings、Repository、Service は dependency injection で提供する。テスト時に fake service や temporary DB に差し替えられるようにする。

## Settings

`.env`、既定値、DB 保存設定を統合する。ffmpeg path、storage path、batch size、threshold、log level、CUDA 利用設定を管理する。

## Logging

アプリログとジョブログを分ける。アプリログは起動、API エラー、設定、Worker 例外を記録する。ジョブログは job_id に紐づく進捗、警告、失敗理由を記録する。

## Middleware

request id、処理時間、例外捕捉、静的ファイルキャッシュ制御を middleware で扱う。大容量アップロードは timeout とサイズ制限を設定する。

## Error Handling

独自例外を API error response に変換する。ユーザー向け message、機械処理用 code、詳細確認用 request_id/job_id を返す。内部 stack trace はレスポンスに含めない。

