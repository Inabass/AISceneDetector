# Future Extensions

## LoRA

OpenCLIP または画像特徴抽出モデルに LoRA を適用し、特定シーンへの適応力を高める。MVP では採用せず、Feature Extractor 差し替え設計で受け入れる。

## Siamese Network

正例と対象フレームのペア類似度を学習する Siamese Network を追加できる。フィードバックデータが十分に蓄積した後の拡張候補とする。

## Video Transformer

単一フレームではなく時間方向の文脈を扱う Video Transformer を導入できる。処理負荷が高いため、MVP ではフレーム特徴量 + temporal smoothing とする。

## 音声特徴量

特定シーンが音声パターンを伴う場合、音声特徴量を補助スコアとして使える。映像特徴量とは別 Feature Store として管理する。

## OCR

画面内テキストが重要なシーンでは OCR 結果を特徴として利用できる。字幕やテロップ検出にも応用可能である。

## 顔認識

人物に強く依存するシーンでは顔特徴量を補助的に使える。プライバシーと利用目的に注意し、MVP には含めない。

## FAISS

Feature 数が増えた場合、類似検索に FAISS を導入する。Matcher インターフェースを維持すれば、cosine similarity 実装から差し替え可能である。

## React 化

初期 UI がシンプルなテンプレートで不足する場合、React SPA に移行できる。API 契約を維持すれば段階的に置き換えられる。

## Docker

Windows ローカル実行を主対象とするため MVP では Docker 必須にしない。将来、開発環境再現や Linux GPU 環境向けに Dockerfile を追加できる。

## マルチユーザー

認証、ユーザー別 storage、権限、Job 分離を追加すればマルチユーザー化できる。MVP では単一ユーザー前提とする。

