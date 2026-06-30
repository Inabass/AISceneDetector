# System Architecture

## 全体構成

システムは Web UI、FastAPI Backend、Service Layer、AI/Core Layer、Repository Layer、File Storage、SQLite Database で構成する。長時間処理は API リクエスト内で直接実行せず、Job Queue に登録して Worker が実行する。

## レイヤー設計

- API Layer: HTTP 入出力、バリデーション、レスポンス整形
- Service Layer: ユースケース制御、トランザクション境界、ジョブ生成
- Core Layer: AI 推論、動画処理、スコアリング、エクスポート
- Repository Layer: SQLAlchemy による DB 永続化
- Storage Layer: `data/` 配下のファイル保存、パス安全化

## ディレクトリ構成

```text
app/
  api/
  services/
  core/
    ai/
    video/
    export/
  repositories/
  models/
  schemas/
  workers/
  web/
data/
  uploads/
  training/
  features/
  models/
  outputs/
  previews/
  thumbnails/
  logs/
  temp/
docs/
```

## データフロー

学習では、動画アップロード、ffprobe 検証、フレームサンプリング、OpenCLIP 特徴量生成、Feature Store 保存、モデルバージョン作成の順に処理する。検出では、対象動画からフレーム特徴量を生成し、モデルと照合し、フレームスコアをシーン区間へ変換し、プレビューとエクスポートへ接続する。

## 採用技術

FastAPI は API と Web UI 配信を担当する。SQLite は単一 PC アプリとして十分であり、SQLAlchemy で将来の DB 差し替え余地を残す。OpenCLIP は視覚特徴量抽出に使い、PyTorch CUDA で GPU 推論を行う。ffmpeg/ffprobe は動画メタデータ取得と切り出しの標準手段とする。

## 責務分離

AI Core は DB を直接触らない。動画処理 Core は HTTP を知らない。Repository は業務判断を持たない。Service は複数 Core と Repository を組み合わせるが、重い処理は Worker に委譲する。

## 禁止事項

- API ハンドラ内で長時間動画処理を直接実行しない。
- ファイルパスをユーザー入力から直接組み立てない。
- モデルファイルを DB BLOB として保存しない。
- GPU OOM を握りつぶさない。
- 仕様外のシーンデータベース機能を追加しない。

