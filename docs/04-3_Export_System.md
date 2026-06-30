# Export System

## ffmpeg 切り出し

検出 Segment は ffmpeg で個別ファイルに切り出す。開始時刻、終了時刻、padding 適用後の時刻、元動画パス、出力パスを Export Job に記録する。

## Export Job

Export は Background Job として実行する。複数 Segment の一括出力に対応し、Segment 単位の成功、失敗、スキップを記録する。失敗した Segment だけを再試行できるようにする。

## Copy Mode

copy mode は高速だがキーフレーム境界に依存する。正確な境界が不要な場合の既定候補とし、UI で「高速」と表示する。境界ずれが発生し得ることをログに残す。

## 再エンコード

正確な開始終了が必要な場合は再エンコードを使う。codec、crf、preset、audio handling を設定可能にする。GPU エンコードは将来拡張とし、MVP では CPU ffmpeg でもよい。

## サムネイル

Segment の代表時刻から jpeg または webp サムネイルを生成する。代表時刻は最大 score のフレームを優先し、なければ Segment 中央とする。

## プレビュー

Preview は短辺を小さくした軽量 mp4 として生成する。Web UI で即時確認できることを重視し、元品質の維持は Export 本体に任せる。

## ファイル命名

出力名は `{source_name}_{model_name}_scene_{index}_{start_ms}_{end_ms}.mp4` を基本とする。Windows 禁止文字を除去し、同名衝突時は連番を付与する。

## ダウンロード

API は個別ファイルと一括 zip ダウンロードを提供する。一括 zip は temp に生成し、有効期限または cleanup job で削除する。

