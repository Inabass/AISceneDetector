# Scene Detection

## Temporal Smoothing

フレーム単位スコアはノイズを含むため、移動平均、中央値フィルタ、または指数移動平均で時間方向に平滑化する。平滑化窓は秒単位で設定し、フレーム間隔からサンプル数へ変換する。

## Thresholding

平滑化後スコアが検出しきい値以上の連続範囲を positive range とする。しきい値はモデル既定値と検出ジョブごとの上書きを持つ。UI ではしきい値変更による候補区間の変化を再計算できる設計にする。

## Segment 生成

positive range を開始時刻、終了時刻、代表スコア、最大スコア、平均スコアを持つ Segment に変換する。サンプリング間隔により境界誤差が生じるため、境界は padding と近傍フレームで補正する。

## Merge

短い gap で分離した Segment は同一シーンとして結合する。merge gap は秒単位設定とし、結合後の score は長さ加重平均または最大値を保持する。

## Padding

検出区間の前後に padding を付与し、切り出し時に重要シーンが欠けないようにする。padding 後の開始時刻は 0 秒未満にしない。終了時刻は動画 duration を超えない。

## Min / Max Duration

min duration 未満の区間はノイズとして破棄するか、隣接区間と結合候補にする。max duration を超える区間はスコア谷を使って分割する。分割不能な場合は警告付きで保持する。

## Scene Score

Scene Score は区間内の平均 confidence、最大 confidence、連続性、負例距離を統合する。エクスポート優先順位、UI の並び替え、フィードバック対象選定に利用する。

## Timeline Data

Timeline はフレームスコア系列、しきい値線、Segment、サムネイル位置を含む JSON として API から返す。長時間動画では全点を返さず、表示幅に合わせてダウンサンプリングする。

## Preview / Thumbnail 連携

各 Segment には代表フレームからサムネイルを生成する。Preview は低解像度、短尺、軽量エンコードで作成し、UI で素早く確認できるようにする。

