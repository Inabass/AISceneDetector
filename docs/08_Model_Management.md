# Model Management

## モデル構造

モデルは論理モデル `ai_models` と immutable な `model_versions` に分ける。各バージョンは Feature Set、Matcher 設定、Cluster、Classifier、threshold、metadata を持つ。

## Version 管理

バージョン番号は `v1`、`v2` のような連番を基本とする。追加学習、再学習、threshold 再調整は新しいバージョンを作成する。既存バージョンの artifact は変更しない。

## Metadata

Metadata には extractor 名、重み、前処理、Feature 次元、学習動画数、正例/負例件数、学習日時、作成 Job、評価指標を保存する。

## Feature Set

Feature Set はモデルバージョンが参照する特徴量群である。同一 Feature を複数バージョンで共有できるが、削除時は参照数を確認する。

## Cluster

Cluster artifact はクラスタ中心、クラスタ件数、各クラスタのサンプル数、クラスタ別 threshold を持つ。クラスタが未使用でも schema は保持し、将来拡張に備える。

## Classifier

Classifier artifact は重み、入力次元、label mapping、score calibration 情報を持つ。分類器がないバージョンでは `classifier_type = none` として明示する。

## Export / Import

Model Export は metadata、artifact、必要 Feature schema、互換性情報を zip にまとめる。Import 時は extractor 互換性と artifact 完全性を検証し、既存 ID と衝突しない新 ID を割り当てる。

## Rollback

Rollback は active version pointer を変更する操作である。検出結果や過去 Job の参照バージョンは変更しない。Rollback 操作は job log または audit log に残す。

## Deletion Policy

active version は削除不可とする。DetectionResult、Export、Feedback から参照されるバージョンは、強制削除ではなく非表示または archive を優先する。Artifact 削除は DB 更新と同一操作として扱い、失敗時に不整合が残らないようにする。

