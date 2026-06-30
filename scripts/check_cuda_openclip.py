"""CUDA/OpenCLIP smoke check for Windows RTX environments.

This script intentionally performs a tiny real OpenCLIP image encode on CUDA.
Run after setup from the repository root:

    .venv\\Scripts\\python scripts\\check_cuda_openclip.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from app.core.ai.openclip_extractor import OpenCLIPFeatureExtractor
from app.core.config import get_settings


def main() -> int:
    try:
        import torch
    except ImportError as exc:
        print(f"NG: PyTorch is not installed: {exc}")
        return 2

    print(f"torch={torch.__version__}")
    print(f"torch_cuda={torch.version.cuda}")
    print(f"cuda_available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"gpu={torch.cuda.get_device_name(0)}")
    else:
        print("NG: CUDA is not available. Install CUDA-enabled PyTorch and check NVIDIA driver.")
        return 3

    extractor = OpenCLIPFeatureExtractor(get_settings())
    frame = np.zeros((224, 224, 3), dtype=np.uint8)
    result = extractor.encode_frames([frame])
    extractor.release()
    print(f"feature_shape={result.shape}")
    print(f"feature_dtype={result.dtype}")
    print("OK: CUDA/OpenCLIP encode succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
