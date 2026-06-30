# Detection UI

## 検出画面

Detection UI は対象動画をアップロードし、モデルを選択して検出 Job を開始する画面である。完了後は Timeline、Preview、Export、Feedback を同じ流れで扱う。

## 動画アップロード

対象動画をアップロードし、ffprobe 検証結果を表示する。長時間動画では proxy 作成の有無を選択できる。

## モデル選択

モデルとバージョンを選択する。既定では active version を使う。モデルの学習日時、しきい値、評価指標を表示する。

## 検出設定

frame interval、threshold、smoothing window、merge gap、padding、min/max duration、export mode の初期値を設定する。

## 検出結果

検出結果は Segment 一覧として表示する。各行にはサムネイル、開始終了時刻、duration、score、export 状態、feedback 状態を表示する。

## Timeline

Timeline はスコア曲線、threshold、Segment 範囲、現在 preview 位置を表示する。長時間動画ではデータを間引いて描画し、選択範囲だけ詳細取得する。

## Preview

Segment の preview を再生できる。元動画全体を読み込まず、軽量 preview または proxy を使う。

## Export

選択 Segment または全 Segment を Export Job に送る。copy mode と再エンコードを選べる。Export 完了後に個別ダウンロードと一括ダウンロードを提供する。

## Feedback

Segment に対して correct、incorrect、missed を付与できる。missed は Timeline 上で範囲選択して登録する。Feedback は次回継続学習に使う。

