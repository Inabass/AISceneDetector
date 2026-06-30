# Settings UI

## GPU 設定

CUDA 使用、CPU 診断実行、GPU 同時 Job 数、benchmark 実行を設定する。GPU 情報取得結果も同じ画面に表示する。

## Batch Size

Training と Detection の既定 batch size を分けて設定する。auto reduction を有効にした場合、OOM 時に自動調整する。

## Frame Interval

学習、検出それぞれの既定 frame interval を設定する。短い間隔は精度と処理時間、長い間隔は速度と見落としのトレードオフがある。

## Threshold

モデル作成時と検出時の既定 threshold、merge gap、padding、min/max duration を設定する。モデルごとの値が優先される場合は UI に表示する。

## ffmpeg path

ffmpeg、ffprobe の path を設定し、検証ボタンで version 取得を行う。未設定時は PATH から探索する。

## storage path

`data/` root を設定する。変更時は既存データ移行を自動では行わず、再起動と手動移行が必要であることを表示する。

## log level

アプリログとジョブログの log level を設定する。debug は容量増加に注意する。

## cleanup

temp、preview、thumbnail、古い failed job artifact の削除を実行できる。削除前に対象件数と容量を表示する。

