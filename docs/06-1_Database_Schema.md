# Database Schema

## SQLite 設計

SQLite は単一ユーザー Windows アプリの永続化に利用する。WAL mode を有効化し、長時間処理中も UI の読み取りを可能にする。大きな Feature や動画本体は DB に保存せず、パスとメタデータだけを保持する。

## SQLAlchemy Model

SQLAlchemy 2.x style の typed declarative model を使う。日時は UTC で保存し、UI 表示時にローカル変換する。JSON 設定は SQLite JSON 互換の text/json column として扱う。

## ER 構成

Model は複数 ModelVersion を持つ。TrainingVideo と Feature は ModelVersion または FeatureSet に紐づく。DetectionResult は使用した ModelVersion、対象動画、生成 Segment を持つ。Export と Feedback は DetectionResult または Segment に紐づく。

## テーブル一覧

- `ai_models`
- `model_versions`
- `training_videos`
- `features`
- `jobs`
- `job_logs`
- `detection_results`
- `detection_segments`
- `exports`
- `feedbacks`
- `settings`

## ai_models

モデルの論理単位を保存する。主な列は `id`、`name`、`description`、`active_version_id`、`created_at`、`updated_at`、`deleted_at`。削除は論理削除を基本とする。

## model_versions

バージョンごとの immutable な情報を保存する。`model_id`、`version`、`parent_version_id`、`status`、`artifact_path`、`feature_set_path`、`thresholds_json`、`metrics_json`、`extractor_json`、`created_by_job_id` を持つ。

## training_videos

学習に使う動画を保存する。`label_type` は `positive` または `negative`。`sha256`、`path`、`duration`、`fps`、`width`、`height`、`codec`、`metadata_json`、`validation_status` を持つ。

## features

Feature ファイルの所在と生成条件を保存する。`source_video_id`、`model_version_id`、`kind`、`path`、`dtype`、`shape_json`、`frame_interval_sec`、`extractor_json`、`status` を持つ。

## jobs

Job は `type`、`status`、`progress`、`current_step`、`params_json`、`checkpoint_json`、`error_code`、`error_message`、`started_at`、`finished_at` を持つ。

## detection_results

検出実行単位を保存する。`source_video_path`、`source_sha256`、`model_version_id`、`settings_json`、`timeline_path`、`summary_json`、`job_id` を持つ。

## exports

Export は `detection_result_id`、`segment_id`、`mode`、`status`、`output_path`、`ffmpeg_args_json`、`error_message` を持つ。

## feedbacks

Feedback は `detection_result_id`、`segment_id`、`label`、`start_sec`、`end_sec`、`comment`、`model_version_id` を持つ。継続学習で参照できるよう、元バージョンを必ず保存する。

## settings

Settings は key-value と JSON value を持つ。UI から変更可能な設定と、環境変数でのみ変更すべき設定を区別する。

