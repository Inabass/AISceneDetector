# REST API

## API 一覧

API は `/api/v1` 配下に配置する。

- `GET /health`
- `GET /gpu`
- `POST /training/videos`
- `POST /models`
- `GET /models`
- `GET /models/{model_id}`
- `POST /models/{model_id}/train`
- `POST /models/{model_id}/rollback`
- `POST /detections`
- `GET /detections/{detection_id}`
- `GET /detections/{detection_id}/timeline`
- `POST /exports`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`
- `POST /feedbacks`
- `GET /settings`
- `PUT /settings`

## Request / Response

Request は Pydantic schema で定義する。Response は `data`、`error`、`request_id` を基本形とする。Job を作成する API は即時に `job_id` を返し、処理完了を待たない。

## Error Response

```json
{
  "error": {
    "code": "VIDEO_VALIDATION_FAILED",
    "message": "動画を読み込めませんでした。",
    "details": {"filename": "sample.mp4"}
  },
  "request_id": "..."
}
```

## HTTP Status

成功は 200 または 201、ジョブ受付は 202 を使う。入力不正は 400、存在しないリソースは 404、競合は 409、処理不能な動画は 422、内部エラーは 500 とする。

## ファイルアップロード

動画アップロードは multipart/form-data を使う。アップロード中に拡張子とサイズを確認し、保存後に SHA256 と ffprobe 検証を行う。

## ジョブ API

Job API は状態、進捗率、現在ステップ、ログ tail、開始終了時刻、エラーを返す。キャンセルは即時停止ではなく cancel request として受け付ける。

## モデル API

モデル API はモデル、バージョン、active version、評価指標、Feature Set、設定値を返す。削除は参照中リソースがある場合 409 を返す。

## 検出 API

検出 API は対象動画、モデルバージョン、しきい値、frame interval、padding、min/max duration を受け取り、Detection Job を作成する。

## フィードバック API

Feedback API は detection result、segment、label、範囲、コメントを受け取る。保存後、次回継続学習で利用可能な状態にする。

