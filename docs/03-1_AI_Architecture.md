# AI Architecture

## AI 全体設計

AI 部分は Feature Extractor、Feature Store、Matcher、Cluster、Classifier、Model Registry に分ける。MVP では OpenCLIP 特徴量と類似度ベースの判定を中心にし、負例、クラスタ、軽量分類器を段階的に組み合わせる。

## OpenCLIP 特徴量抽出

動画フレームを RGB に変換し、OpenCLIP の前処理に合わせてリサイズ、正規化する。推論は `torch.no_grad()` と mixed precision を利用し、GPU バッチ推論を標準とする。出力特徴量は L2 正規化して保存する。

## Feature Store

Feature Store は `.npy` または `.npz` 形式のベクトルファイルと、DB 上のメタデータで構成する。メタデータには動画 ID、フレーム番号、タイムコード、正例/負例、モデルバージョン、抽出設定、特徴量次元、ハッシュを保存する。

## Matcher

Matcher は対象フレーム特徴量と正例特徴量の cosine similarity を計算する。負例がある場合は、正例類似度から負例類似度を差し引く、または margin を使う。しきい値はモデルバージョンごとに保持する。

## Cluster

正例特徴量をクラスタリングし、シーン内の見た目の揺らぎを表現する。クラスタ中心との最大類似度、平均類似度、近傍数をスコアに利用する。初期実装は scikit-learn なしでも実装可能な簡易 k-means 方針とし、将来 FAISS に差し替え可能にする。

## Classifier

負例やフィードバックが十分に集まった段階で、特徴量を入力とする軽量分類器を利用する。MVP では logistic regression 相当の線形分類器、または PyTorch の小さな MLP を想定する。Classifier は Matcher を置き換えるのではなく、スコア統合要素として扱う。

## Model Registry

Model Registry はモデル、バージョン、特徴量セット、しきい値、クラスタ、分類器、評価指標、作成ジョブを関連付ける。バージョンは immutable とし、追加学習時は新しいバージョンを作る。

## GPU 利用方針

OpenCLIP 推論、バッチ類似度計算、分類器推論を GPU 優先で実行する。GPU メモリ使用量を監視し、OOM 発生時はバッチサイズを段階的に下げる。GPU 不可時は処理を中断するか、明示設定時のみ CPU で診断実行する。

## 将来モデル差し替え設計

Feature Extractor はインターフェース化し、OpenCLIP 以外の Video Transformer、Siamese Network、LoRA 適用モデルに差し替えられるようにする。Feature の extractor 名、重みバージョン、前処理設定を必ず保存する。

