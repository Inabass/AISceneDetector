# Model Management UI

## モデル一覧

モデル一覧には名前、active version、作成日、最終学習日、正例数、負例数、評価概要を表示する。検索と並び替えに対応する。

## モデル詳細

詳細ではバージョン履歴、学習動画、Feature Set、しきい値、評価指標、作成 Job、関連 Detection を表示する。

## バージョン管理

各バージョンは immutable として表示する。active version 切り替え、rollback、削除可否確認を提供する。

## 追加学習

既存モデルに正例、負例、Feedback を追加して新しいバージョンを作成できる。親バージョンと利用データを明示する。

## 再学習

再学習は既存 Feature を使うか再抽出するかを選択できる。抽出設定が変わる場合は Feature 再生成が必要であることを表示する。

## 削除

モデル削除は論理削除を基本とする。関連する outputs や detection results がある場合は警告し、削除対象を明示する。

## Export / Import

モデル artifact、metadata、Feature schema を zip として export できる。Import 時は extractor 互換性、ファイル存在、バージョン衝突を検証する。

