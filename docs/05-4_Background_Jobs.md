# Background Jobs

## Job Queue

MVP では単一プロセス内の永続化 Job Queue を SQLite で管理する。Worker は pending job を取得し、排他状態に更新して実行する。将来は外部 queue に差し替えられるよう、JobService 経由にする。

## Worker

Worker は training、detection、export、preview、cleanup を実行する。GPU を使う job は同時実行数を制限し、VRAM 競合を避ける。

## Job Status

状態は `queued`、`running`、`cancel_requested`、`cancelled`、`failed`、`succeeded`、`retrying` とする。状態遷移は JobService に集約し、不正遷移を防ぐ。

## Progress

Progress は percent、current_step、processed_items、total_items、message を持つ。長時間動画ではフレーム数または duration ベースで進捗を計算する。

## Cancel

キャンセルは DB に cancel request を記録する。Worker はチャンク境界で確認し、安全に中断する。ffmpeg 実行中はプロセス停止と一時ファイル削除を行う。

## Retry

Retry は失敗理由と checkpoint に基づく。GPU OOM のように設定変更で回復可能な失敗は batch size を下げて再試行できる。動画破損など入力依存の失敗は自動再試行しない。

## Checkpoint

Checkpoint は job type ごとに JSON として保存する。Detection では処理済み timestamp、Training では生成済み Feature、Export では Segment 単位の状態を持つ。

## Job Logs

Job Log は時刻、level、step、message、details を持つ。UI は tail 表示と全件ダウンロードに対応する。内部例外の詳細はファイルログに残し、UI では要点を表示する。

## 長時間処理

長時間処理では DB session を長く保持しない。チャンクごとに状態更新し、ファイルは temp に書いてから確定する。アプリ再起動時は running job を interrupted として扱い、再試行可能にする。

