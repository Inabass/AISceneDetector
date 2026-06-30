# File Storage

## data ディレクトリ構成

`data/` はユーザーデータと生成物のルートである。アプリコードとは分離し、バックアップ、削除、移行を行いやすくする。

```text
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
```

## uploads

アップロード直後の原本を保存する。ファイル名はユーザー名をそのまま使わず、ID と安全化した元名を組み合わせる。

## training

学習用に登録された動画を保存または参照する。正例、負例の区分は DB に保存し、ディレクトリ名だけに依存しない。

## features

Feature は model/version/extractor ごとに分ける。大きなファイルになるため、削除ポリシーと参照チェックを実装する。

## models

Model artifact、cluster、classifier、metadata snapshot を保存する。DB とファイルの整合性を保つため、作成中は temp に保存し、成功後に確定パスへ移動する。

## outputs

切り出し済み動画を保存する。ユーザーが削除するまで保持するが、設定により古い export を cleanup 対象にできる。

## previews

UI 確認用の軽量動画を保存する。再生成可能な派生物のため、容量不足時は優先的に削除できる。

## thumbnails

Segment と動画一覧のサムネイルを保存する。サイズ別に生成する場合は設定をファイル名または DB に保存する。

## logs

アプリログ、ジョブログ、ffmpeg stderr を保存する。ログローテーションを行い、巨大化を防ぐ。

## temp

処理中ファイル、一括 zip、途中生成物を保存する。アプリ起動時に古い temp を cleanup するが、running job のものは削除しない。

## path 安全化

ユーザー入力由来の名前は Windows 禁止文字、制御文字、予約名、末尾スペース/ドットを除去する。パス結合後は必ず storage root 配下であることを検証する。

## cleanup

cleanup は preview、thumbnail、temp、古い failed job artifact を対象にする。モデル、学習動画、出力動画は明示操作なしに削除しない。

