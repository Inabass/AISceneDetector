# Deployment

## Windows setup

主対象は Windows 11、NVIDIA Driver、CUDA 対応 PyTorch が利用できる環境である。インストール手順は `setup.bat` に集約し、ユーザーがコマンドを最小限で済ませられるようにする。

## Python venv

`setup.bat` は Python 3.12+ を確認し、`.venv` を作成し、pip を更新して依存関係をインストールする。Python が見つからない場合は終了し、インストール案内を表示する。

## CUDA 対応 PyTorch

PyTorch は CUDA 対応 wheel を明示的にインストールする。実装時点の公式指定に従う必要があるため、`requirements.txt` と setup 手順でバージョンを固定する。

## ffmpeg

ffmpeg/ffprobe は PATH から探索し、見つからない場合は設定画面で path を指定できるようにする。`setup.bat` は自動ダウンロードを必須にせず、手動配置にも対応する。

## setup.bat

`setup.bat` は venv 作成、依存関係インストール、data directory 作成、DB 初期化、ffmpeg 確認を行う。失敗時はエラーコードと対処を表示する。

## run.bat

`run.bat` は venv を有効化し、FastAPI アプリを起動する。既定 URL は `http://127.0.0.1:8000` とする。起動時にブラウザを開くかは設定可能にする。

## .env.example

`.env.example` には storage path、database URL、log level、ffmpeg path、default batch size、CUDA 設定を記載する。秘密情報は扱わない前提だが、将来拡張に備えて `.env` は gitignore する。

## トラブルシューティング

- CUDA が見つからない: NVIDIA Driver、PyTorch CUDA wheel、`torch.cuda.is_available()` を確認する。
- ffmpeg が見つからない: PATH または Settings の ffmpeg path を確認する。
- GPU OOM: batch size を下げる、他アプリを終了する、proxy/interval を調整する。
- 動画が読めない: ffprobe 結果、codec、破損、ファイルパスを確認する。
- DB locked: 長時間トランザクションを避け、WAL mode を確認する。

