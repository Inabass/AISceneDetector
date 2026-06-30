# Testing

## Unit Test

Service、Repository、Core の単体テストを作成する。パス安全化、threshold、segment merge、settings、状態遷移は小さな入力で網羅する。

## Integration Test

SQLite temporary database と temporary data directory を使い、動画登録、学習 Job 作成、検出 Job 作成、Export Job 作成までの流れを検証する。

## API Test

FastAPI TestClient で health、settings、models、jobs、detections、feedbacks を検証する。ファイルアップロードは小さなサンプル動画または fixture を使う。

## GPU Test

CUDA が利用可能な環境で OpenCLIP 推論、batch reduction、GPU info 取得を検証する。CI では GPU がない可能性があるため、GPU test は marker で分離する。

## ffmpeg Test

ffmpeg/ffprobe の path 検出、metadata 取得、copy mode、再エンコード、thumbnail 生成を検証する。ffmpeg がない場合は明確に skip する。

## Video Processing Test

OpenCV 読込、RGB 変換、frame sampling、timestamp 計算、proxy 生成を検証する。可変 fps や rotation metadata は追加 fixture で確認する。

## AI Feature Test

Feature shape、dtype、L2 normalization、metadata 保存、Feature reuse を検証する。OpenCLIP 本体が重い場合は fake extractor を使ったテストも用意する。

## E2E Test

短い動画を使い、学習、検出、Segment 生成、Preview、Export、Feedback 登録までを通す。Windows 実機で `setup.bat` と `run.bat` の起動確認も行う。

