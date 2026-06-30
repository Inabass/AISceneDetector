# Service Architecture

## TrainingService

TrainingService は学習動画登録、学習ジョブ作成、Feature 生成依頼、モデルバージョン作成を制御する。Video、Storage、Job、Model の各 Service に依存する。

## DetectionService

DetectionService は対象動画登録、検出ジョブ作成、推論結果保存、Segment 生成、Preview/Thumbnail 生成依頼を担う。ModelService から active version を取得する。

## ModelService

ModelService はモデル一覧、詳細、active version、rollback、削除、import/export を管理する。モデルファイルと DB メタデータの整合性を守る。

## ExportService

ExportService は Segment から Export Job を作成し、ffmpeg 実行計画、出力ファイル命名、成功失敗記録、ダウンロード情報を管理する。

## FeedbackService

FeedbackService は検出結果へのユーザーフィードバックを保存する。true positive、false positive、false negative、コメント、対象範囲を記録し、継続学習に渡す。

## JobService

JobService は Job 作成、状態更新、進捗更新、キャンセル要求、再試行、ログ取得を提供する。Worker は JobService を通じて状態を更新する。

## StorageService

StorageService は安全なパス生成、保存先ディレクトリ作成、一時ファイル確定、cleanup を担当する。ユーザー入力をそのままパスとして使わない。

## GpuService

GpuService は CUDA 利用可否、GPU 名、VRAM、PyTorch 情報、batch 推奨値、benchmark を提供する。AI Core とは情報取得の責務を分ける。

## 依存関係

Service 間の依存は一方向に保つ。Training/Detection/Export は JobService と StorageService に依存する。Repository は Service に依存しない。Core は Service から呼ばれるだけで、Service を呼び返さない。

