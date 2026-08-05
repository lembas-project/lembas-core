"""Native sync client for case data.

Simple protocol:
1. Walk case_dir, hash each file → manifest {path: hash}
2. Check which hashes server already has
3. Upload only missing blobs
4. Store manifest on server

No DVC, no .dvc files, no complex cache structures.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

log = logging.getLogger(__name__)

CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks for hashing


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(case_dir: Path) -> dict[str, str]:
    """Build a manifest of all files in a case directory.

    Skips .lembas internal directory (status, metadata).

    Returns:
        Dict mapping relative path → SHA-256 hash
    """
    manifest = {}
    for path in case_dir.rglob("*"):
        if path.is_file():
            rel_path = str(path.relative_to(case_dir))
            # Skip internal .lembas directory
            if rel_path.startswith(".lembas/") or rel_path.startswith(".lembas\\"):
                continue
            manifest[rel_path] = hash_file(path)
    return manifest


def push_case(
    client: httpx.Client,
    study_id: str,
    case_id: str,
    case_dir: Path,
) -> dict:
    """Push a case directory to the platform.

    Args:
        client: HTTP client with auth configured
        study_id: Study ID
        case_id: Case ID
        case_dir: Local case directory path

    Returns:
        Dict with upload stats
    """
    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory not found: {case_dir}")

    # Build manifest
    manifest = build_manifest(case_dir)
    if not manifest:
        return {"files": 0, "uploaded": 0, "bytes": 0}

    # Check which blobs server already has
    hashes = list(set(manifest.values()))
    response = client.post(
        "/api/storage/check-hashes",
        json={"hashes": hashes},
    )
    response.raise_for_status()
    missing = set(response.json()["missing"])

    # Upload missing blobs
    uploaded_count = 0
    uploaded_bytes = 0
    for rel_path, file_hash in manifest.items():
        if file_hash in missing:
            file_path = case_dir / rel_path
            data = file_path.read_bytes()
            response = client.put(
                f"/api/storage/blobs/{file_hash}",
                content=data,
            )
            response.raise_for_status()
            uploaded_count += 1
            uploaded_bytes += len(data)
            missing.discard(file_hash)  # Don't upload same hash twice

    # Store manifest
    response = client.put(
        f"/api/storage/manifests/{study_id}/{case_id}",
        json={"files": manifest},
    )
    response.raise_for_status()

    return {
        "files": len(manifest),
        "uploaded": uploaded_count,
        "bytes": uploaded_bytes,
    }


def pull_case(
    client: httpx.Client,
    study_id: str,
    case_id: str,
    case_dir: Path,
) -> dict:
    """Pull a case directory from the platform.

    Args:
        client: HTTP client with auth configured
        study_id: Study ID
        case_id: Case ID
        case_dir: Local case directory path (will be created)

    Returns:
        Dict with download stats
    """
    # Get manifest
    response = client.get(f"/api/storage/manifests/{study_id}/{case_id}")
    if response.status_code == 404:
        return {"files": 0, "downloaded": 0, "bytes": 0}
    response.raise_for_status()
    manifest = response.json()["files"]

    if not manifest:
        return {"files": 0, "downloaded": 0, "bytes": 0}

    case_dir.mkdir(parents=True, exist_ok=True)

    # Check what we already have locally
    downloaded_count = 0
    downloaded_bytes = 0
    for rel_path, file_hash in manifest.items():
        file_path = case_dir / rel_path

        # Skip if file exists and hash matches
        if file_path.exists():
            local_hash = hash_file(file_path)
            if local_hash == file_hash:
                continue

        # Download blob
        response = client.get(f"/api/storage/blobs/{file_hash}")
        response.raise_for_status()
        data = response.content

        # Write to file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        downloaded_count += 1
        downloaded_bytes += len(data)

    return {
        "files": len(manifest),
        "downloaded": downloaded_count,
        "bytes": downloaded_bytes,
    }


def get_case_manifest(
    client: httpx.Client,
    study_id: str,
    case_id: str,
) -> dict[str, str] | None:
    """Get the manifest for a case from the server.

    Returns:
        Dict mapping path → hash, or None if not found
    """
    response = client.get(f"/api/storage/manifests/{study_id}/{case_id}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()["files"]
