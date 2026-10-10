"""Supabase Storage and Database operations for the Face Worker."""

from __future__ import annotations

import hashlib
import json
import logging
from uuid import UUID

import httpx
import numpy as np

from worker.config import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """Manages secure access to the Supabase private 'frames' bucket and 'face_embeddings' table."""

    def __init__(self) -> None:
        self.url = settings.SUPABASE_URL.rstrip("/")
        self.key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.bucket = settings.FRAMES_BUCKET

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": content_type,
        }

    # --- Frame Hash Verification ---

    @staticmethod
    def verify_frame_hash(frame_bytes: bytes, expected_hash: str) -> bool:
        """Check SHA-256 of frame bytes against the hash passed by the backend."""
        actual_hash = hashlib.sha256(frame_bytes).hexdigest().lower()
        return actual_hash == expected_hash.strip().lower()

    # --- Frame Storage (Private Bucket) ---

    async def upload_frame(self, path: str, frame_bytes: bytes) -> bool:
        """Upload a single JPEG frame to the private Supabase storage bucket."""
        if not self.url or not self.key:
            logger.warning("Supabase credentials not configured, skipping storage upload")
            return True

        upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{path}"
        headers = self._headers(content_type="image/jpeg")
        headers["x-upsert"] = "true"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(upload_url, headers=headers, content=frame_bytes)
                if resp.status_code not in (200, 201):
                    logger.error(f"Failed to upload frame to {path}: HTTP {resp.status_code} {resp.text}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Error uploading frame to {path}: {e}")
                return False

    async def save_verified_frames(
        self,
        window_id: UUID,
        mark_id: UUID,
        frames: list[tuple[int, bytes]],
    ) -> str:
        """Upload nightly frames to frames/{window_id}/{mark_id}/{index}.jpg.

        Returns folder path: frames/{window_id}/{mark_id}/
        """
        folder_path = f"frames/{window_id}/{mark_id}"
        for idx, frame_bytes in frames:
            file_path = f"{folder_path}/{idx}.jpg"
            await self.upload_frame(file_path, frame_bytes)

        return f"{folder_path}/"

    # --- Database Operations (face_embeddings table only) ---

    async def save_embedding(
        self,
        student_id: UUID,
        embedding: np.ndarray,
        model_version: str,
    ) -> bool:
        """Upsert 512-dimension vector into face_embeddings table."""
        if not self.url or not self.key:
            logger.warning("Supabase credentials missing; embedding not persisted")
            return True

        endpoint = f"{self.url}/rest/v1/face_embeddings"
        headers = self._headers()
        headers["Prefer"] = "resolution=merge-duplicates"

        # Format embedding as vector literal or float list
        emb_list = [float(v) for v in embedding]
        payload = {
            "student_id": str(student_id),
            "embedding": emb_list,
            "model_version": model_version,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(endpoint, headers=headers, json=payload)
                if resp.status_code not in (200, 201):
                    logger.error(f"Failed to save embedding for student {student_id}: {resp.status_code} {resp.text}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Database error saving embedding: {e}")
                return False

    async def get_embedding(self, student_id: UUID) -> np.ndarray | None:
        """Read enrolled embedding vector for student from face_embeddings table."""
        if not self.url or not self.key:
            return None

        endpoint = f"{self.url}/rest/v1/face_embeddings?student_id=eq.{student_id}&select=embedding,model_version"
        headers = self._headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(endpoint, headers=headers)
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch embedding for student {student_id}: HTTP {resp.status_code}")
                    return None

                data = resp.json()
                if not data:
                    return None

                raw_emb = data[0].get("embedding")
                if isinstance(raw_emb, str):
                    # pgvector string format: "[0.123, -0.456, ...]"
                    raw_emb = json.loads(raw_emb)

                arr = np.array(raw_emb, dtype=np.float32)
                return arr
            except Exception as e:
                logger.error(f"Database error fetching embedding: {e}")
                return None

    async def delete_embedding(self, student_id: UUID) -> bool:
        """Delete embedding for student from face_embeddings table upon consent withdrawal."""
        if not self.url or not self.key:
            return True

        endpoint = f"{self.url}/rest/v1/face_embeddings?student_id=eq.{student_id}"
        headers = self._headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.delete(endpoint, headers=headers)
                return resp.status_code in (200, 204)
            except Exception as e:
                logger.error(f"Database error deleting embedding: {e}")
                return False


storage = StorageClient()
