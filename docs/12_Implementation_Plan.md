# Implementation Plan

## Phase 分割

実装は常に起動可能な状態を維持しながら進める。各 Phase の完了時にテストまたは手動確認を行う。

## Phase 1: 基盤

FastAPI アプリ、Settings、Logging、SQLite、SQLAlchemy、Repository、静的 UI 配信、`setup.bat`、`run.bat` を作る。完了条件は health API、DB 初期化、アプリ起動が成功すること。

## Phase 2: Storage と Video I/O

StorageService、path 安全化、upload、ffprobe、OpenCV VideoReader、metadata 保存を実装する。完了条件は動画アップロードと検証結果表示ができること。

## Phase 3: Job 管理

JobService、Worker、Job 状態遷移、progress、cancel、job logs を実装する。完了条件はダミー長時間 Job を UI/API から開始、監視、キャンセルできること。

## Phase 4: AI Feature 抽出

OpenCLIP extractor、GPU info、batch 推論、auto batch reduction、Feature 保存を実装する。完了条件は学習動画から Feature を生成し、shape と metadata を保存できること。

## Phase 5: モデル生成

ModelService、Model Registry、Matcher、Cluster 初期実装、ModelVersion 保存を実装する。完了条件は正例動画から v1 モデルを作成できること。

## Phase 6: 検出

DetectionService、frame inference、score 計算、temporal smoothing、Segment 生成、timeline 保存を実装する。完了条件は対象動画から Segment 候補を生成できること。

## Phase 7: Preview / Thumbnail / Export

thumbnail、preview、ffmpeg export、copy mode、再エンコード、download を実装する。完了条件は検出 Segment を確認し、動画として出力できること。

## Phase 8: Feedback と継続学習

FeedbackService、Hard Negative、追加学習、新バージョン生成、rollback を実装する。完了条件は feedback を次バージョンへ反映できること。

## Phase 9: UI 仕上げ

Dashboard、Training、Detection、Model Management、Settings を一連の操作として整える。完了条件は UI だけで学習から出力まで完了できること。

## Phase 10: テストと安定化

Unit、Integration、API、ffmpeg、GPU、E2E テストを整備する。Windows 実機で setup/run、長時間動画、OOM 時 batch reduction を確認する。

## Codex への実装指示

実装依頼時は `MASTER_PROMPT.md` を使い、ユーザーが「実装開始」と言うまでコードを書かせない。実装開始後は Phase 単位で進め、各 Phase の前に対象ファイルと確認方法を提示させる。

## コード生成ルール

型ヒント、責務分離、設定集約、Repository 経由の DB 操作、Service 経由のユースケース制御を守る。大容量ファイル、GPU OOM、ffmpeg 失敗、キャンセル、再試行を必ず扱う。

## レビュー観点

- 仕様の削除や無断簡略化がないか
- Windows パスと ffmpeg path を安全に扱っているか
- 長時間処理が API request をブロックしていないか
- GPU OOM と batch reduction が機能するか
- DB とファイルの整合性が保たれるか
- モデルバージョンが immutable か

## 最終完成条件

Windows 上で `setup.bat` と `run.bat` により起動でき、Web UI から正例/負例動画登録、学習、検出、Timeline 確認、Preview、Export、Feedback、追加学習、Rollback が実行できること。

