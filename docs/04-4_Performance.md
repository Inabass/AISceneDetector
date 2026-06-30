# Performance

## RTX 5090 活用

RTX 5090 を主対象とし、OpenCLIP 特徴量抽出と類似度計算を GPU で実行する。設定画面には CUDA 利用可否、GPU 名、VRAM、使用量、推奨 batch size を表示する。

## Batch Size

既定 batch size は環境検出で決める。ユーザー設定で上書きできるが、OOM 時は Job 内で自動縮小する。縮小履歴はジョブログに残し、次回推奨値に反映する。

## Auto Batch Reduction

CUDA OOM 発生時は batch size を半減し、同じチャンクを再試行する。最小 batch size でも失敗する場合は Job を failed にし、GPU メモリ状況、対象解像度、推奨対処を表示する。

## GPU Memory Monitoring

PyTorch の memory allocated/reserved と、可能なら NVML の使用量を取得する。NVML が利用できない場合でもアプリは動作し、取得不可として表示する。

## 長時間動画対応

長時間動画では chunk 処理、checkpoint、feature reuse、timeline downsampling を必須とする。UI は全処理完了を待たず、進捗と部分ログを取得できる。

## Checkpoint

training、detection、export は checkpoint を保存する。checkpoint は処理済み動画、処理済み timestamp、生成済み feature file、segment export 状態を含む。

## Cache

同一動画、同一抽出設定、同一 extractor の Feature は再利用できる。Cache hit/miss はログに残し、ユーザーが storage cleanup で削除できるようにする。

## Proxy

UI preview と timeline には proxy を使い、AI 推論とは分離する。Proxy 作成は任意ジョブだが、長時間動画では自動作成を推奨する。

## Benchmark

設定画面から短い benchmark を実行し、Feature 抽出 fps、推論 fps、VRAM 使用量、推奨 batch size を計測する。結果は settings に保存し、初期値決定に使う。

