# WebUI Dashboard

## Dashboard 画面

Dashboard はアプリ起動後の最初の作業画面である。学習、検出、モデル管理、設定へ移動でき、現在の処理状況を一覧できる。

## GPU 情報

GPU 名、CUDA 利用可否、VRAM 使用量、PyTorch CUDA version、現在の推奨 batch size を表示する。取得失敗時はエラーではなく「取得不可」とし、詳細はログに誘導する。

## Job 状況

queued、running、failed、succeeded の Job 件数と、実行中 Job の進捗を表示する。Job 詳細ではログ tail、キャンセル、再試行を操作できる。

## モデル数

登録モデル数、active version、最終学習日時、評価指標の概要を表示する。モデルがない場合は学習画面への導線を出す。

## 最近の検出

最近の detection result、使用モデル、検出 Segment 数、平均 score、Export 状態を表示する。結果詳細へ遷移できる。

## ストレージ使用量

uploads、features、models、outputs、previews、logs の使用量を表示する。cleanup 対象の容量も表示し、設定画面へ誘導する。

