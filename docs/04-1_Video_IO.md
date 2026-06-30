# Video I/O

## 動画読込

動画入力はアップロード後に `data/uploads/` へ保存し、検証に成功したものだけを training または detection の処理対象にする。処理中は元ファイルを変更せず、派生物は temp、features、previews、outputs に分離する。

## ffprobe

ffprobe で duration、fps、width、height、codec、pixel format、bitrate、stream count、rotation、audio stream の有無を取得する。取得結果は DB に保存し、OpenCV で読めない場合の診断にも利用する。

## OpenCV

OpenCV はフレーム読込に利用する。フレームシークが不安定な形式では連続読みを優先し、必要に応じて ffmpeg で proxy video を生成する。OpenCV の BGR 出力は必ず RGB に変換する。

## Metadata 取得

Metadata は video table に保存する。duration、fps、フレーム数はツールにより差が出るため、ffprobe 値を主、OpenCV 値を補助として保持する。

## SHA256

アップロードファイルは SHA256 を計算し、重複検出、Feature 再利用、checkpoint 復旧に使う。大容量ファイルに対応するため、チャンク読みで計算する。

## Validation

拡張子、MIME らしき情報、ffprobe 成功、duration 正数、video stream 存在、サイズ上限、パス安全性を検証する。検証失敗時はユーザー向け理由と詳細ログを残す。

## 対応フォーマット

MVP は mp4、mov、mkv、avi、webm を対象とする。実際の対応可否は ffmpeg/ffprobe と OpenCV の結果に従う。可変フレームレート動画は ffprobe の time base を優先し、タイムコードずれをログに記録する。

## VideoReader 抽象化

`VideoReader` は `iter_frames(interval_sec)`, `get_metadata()`, `seek(time_sec)`, `close()` を持つ抽象とする。初期実装は OpenCV reader、将来 ffmpeg pipe reader を追加できる構成にする。

