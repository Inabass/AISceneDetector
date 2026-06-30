# Frame Processing

## Frame Sampling

Frame Sampling は学習と検出で共通化する。設定は interval seconds、max frames、start/end range、scene padding 用追加取得を持つ。サンプリング結果には frame index と timestamp を必ず付与する。

## Resize

OpenCLIP 入力サイズに合わせるため、短辺基準または固定サイズへリサイズする。モデルの前処理設定は Feature と Model Version に保存し、後から同じ設定で再現できるようにする。

## Letterbox

アスペクト比維持が必要な場合は letterbox を使う。背景色、配置、出力サイズを設定値として保存する。OpenCLIP 標準前処理を使う場合は、その挙動を優先する。

## RGB 変換

OpenCV 由来の BGR フレームは RGB に変換する。alpha channel がある場合は破棄または背景合成し、処理方針をログに残す。

## Batch 生成

Frame Batch は tensor、timestamps、frame_indices、source metadata をまとめて扱う。メモリ使用量を抑えるため、画像配列はバッチ処理後に破棄する。

## Frame Cache

頻繁に参照するサムネイル候補や preview 用フレームは `data/temp/` または `data/thumbnails/` にキャッシュする。キャッシュキーは動画 SHA256、timestamp、サイズ、処理設定から作る。

## Proxy Video

長時間動画や読込が不安定な動画では、低解像度 proxy video を作成して UI preview と timeline 操作に利用する。AI 推論は原則として元動画または統一前処理のフレームを使う。

## Streaming 処理

長時間動画を扱うため、フレーム列は generator として処理する。読み込み、前処理、GPU 推論、保存をチャンク単位で接続し、全フレームを一括保持しない。

