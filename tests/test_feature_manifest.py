from pathlib import Path

import numpy as np

from app.core.features.manifest import FeatureManifest, dump_feature_manifest, load_feature_manifest


def test_feature_manifest_roundtrip(tmp_path: Path) -> None:
    chunk_path = tmp_path / "chunk_000000.npz"
    vectors = np.zeros((2, 4), dtype=np.float16)
    np.savez_compressed(chunk_path, features=vectors)

    manifest = FeatureManifest(
        chunks=[
            {
                "path": "features/training_video_1/cache/chunks/chunk_000000.npz",
                "sha256": "0" * 64,
                "size": chunk_path.stat().st_size,
                "shape": [2, 4],
                "dtype": "float16",
                "first_frame_index": 0,
                "last_frame_index": 10,
                "first_timestamp_sec": 0.0,
                "last_timestamp_sec": 1.0,
            }
        ],
        frame_count=2,
        shape=[2, 4],
        dtype="float16",
        cache_key="cache",
        source_video_id=1,
        extractor={"extractor": "openclip"},
    )

    manifest_path = tmp_path / "manifest.json"
    dump_feature_manifest(manifest_path, manifest)

    loaded = load_feature_manifest(manifest_path)
    assert loaded.schema_version == 1
    assert loaded.storage == "chunked_npz"
    assert loaded.frame_count == 2
    assert loaded.shape == [2, 4]
    assert loaded.chunks[0].dtype == "float16"
