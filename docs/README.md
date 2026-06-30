# AI Scene Detector 仕様書

このディレクトリは、Windows 向け GPU 対応 AI 動画シーン抽出アプリケーション「AI Scene Detector」の仕様書・基本設計書一式である。今回はコード実装ではなく、実装者が迷わず開発に入れる粒度の設計を定義する。

## アプリケーション概要

AI Scene Detector は、ユーザーが用意した「抽出したい特定シーンのみを含む動画」を正例として学習し、必要に応じて負例動画も利用しながら、別の動画から同一または類似したシーン区間を自動検出して切り出す Windows 向け Web UI アプリケーションである。

## 技術前提

- Backend: FastAPI
- Runtime: Python 3.12+
- Database: SQLite
- ORM: SQLAlchemy
- AI: PyTorch + CUDA、OpenCLIP
- Video: OpenCV、ffmpeg、ffprobe
- Hardware: RTX 5090 を主対象
- UI: 初期実装は FastAPI 配信の Web UI を想定
- OS: Windows 11 を主対象

## 文書構成

各文書は独立して読めるようにしつつ、全体として次の順序で理解できる構成にしている。

1. プロジェクト目的と完成条件
2. システム全体アーキテクチャ
3. AI 学習、推論、シーン検出
4. 動画 I/O とエクスポート
5. Backend、Service、API、Job
6. Database と File Storage
7. Web UI
8. Model Management
9. Testing
10. Deployment
11. Future Extensions
12. Implementation Plan

## 実装時の読み方

実装者は `MASTER_PROMPT.md` を最初に読み、次に `01_Project_Overview.md` から番号順に読む。個別機能を実装する場合でも、関連する AI、動画、ジョブ、DB、UI の仕様を横断的に確認すること。

