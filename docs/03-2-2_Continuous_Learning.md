# Continuous Learning

## 継続学習

継続学習は既存モデルバージョンを直接変更せず、新しいモデルバージョンを作成する。既存 Feature を再利用し、新規の正例、負例、フィードバック Feature を追加して再評価する。

## Feature 追加

同一 extractor、前処理、フレーム間隔の Feature は再利用できる。設定が異なる場合は Feature Set を分け、モデル生成時に混在させない。追加 Feature には由来を記録し、通常学習、フィードバック、Hard Negative を区別する。

## フィードバック学習

検出結果に対してユーザーが true positive、false positive、false negative を付与できる。フィードバックは元動画、タイムコード、モデルバージョン、スコアとともに保存し、次バージョンの学習材料にする。

## Hard Negative Mining

高スコアだがユーザーが不要と判断した区間を Hard Negative として保存する。Hard Negative は通常負例より重みを高く扱い、類似背景や構図による誤検出を抑制する。

## Active Learning

信頼度が中間の区間、クラスタ境界に近い区間、負例と正例の差が小さい区間を UI 上で確認候補として提示する。ユーザーがラベル付けした結果を次回学習に利用する。

## モデルバージョン管理

各追加学習は `model_versions` に新規レコードを作る。親バージョン、学習ジョブ、利用 Feature Set、しきい値、評価指標を保存する。バージョン削除は参照中の検出結果やエクスポートとの整合性を確認してから行う。

## ロールバック

モデルの active version を過去バージョンに戻せる。ロールバックはファイルをコピーせず、DB 上の active pointer を変更する。変更履歴は audit ログとして残す。

## 精度評価

評価指標はフィードバック付きデータに対する precision、recall、F1、false positive 件数、false negative 件数、平均 confidence を保存する。データが不足している場合は評価不能として扱い、数値を過信しない表示にする。

