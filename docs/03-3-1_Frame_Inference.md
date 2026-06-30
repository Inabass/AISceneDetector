# Frame Inference

## フレーム単位推論

対象動画から指定間隔でフレームを抽出し、OpenCLIP 特徴量を生成してモデルバージョンと照合する。推論結果はフレーム番号、タイムコード、各スコア、最終 confidence として保存する。

## Batch 推論

フレームはチャンク単位で読み込み、GPU バッチで特徴量化する。バッチサイズは設定値から開始し、GPU メモリ状況と OOM に応じて自動調整する。動画全体の Feature を保持せず、必要に応じてチャンクごとに保存する。

## 類似度計算

cosine similarity を基本とし、正例クラスタ中心との最大類似度、上位 k 近傍平均、負例中心との距離を計算する。スコアは 0.0 から 1.0 に正規化し、モデルメタデータに計算式を記録する。

## Positive / Negative 判定

正例スコアがしきい値以上、かつ負例スコアとの差分が margin 以上の場合に positive 候補とする。負例なしモデルでは margin 判定を省略するが、誤検出リスクを UI に表示する。

## Cluster 判定

各フレームは最も近い正例クラスタ ID を持つ。クラスタごとのしきい値を持てるようにし、特定クラスタだけ誤検出が多い場合に継続学習で調整可能にする。

## Classifier 推論

Classifier が存在するモデルバージョンでは、特徴量を分類器に入力して classifier score を得る。最終 confidence は Matcher score、Cluster score、Classifier score の重み付き統合とする。

## Confidence Score

confidence は UI、シーン生成、エクスポート判断に利用するため安定した意味を持たせる。モデルバージョンごとに score schema を保存し、後から結果を解釈できるようにする。

## GPU 最適化

推論は `torch.no_grad()`、可能なら autocast、pin memory、非同期転送を利用する。メモリ断片化に備え、チャンク終了時に不要 tensor を解放する。ただし頻繁な `empty_cache()` は性能低下を招くため、OOM 後や大きなフェーズ境界に限定する。

