import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services import nonces


def test_challenge_generation():
    for _ in range(20):
        ch = nonces.generate_challenge()
        assert len(ch) == 2
        assert len(set(ch)) == 2
        for action in ch:
            assert action in nonces.CHALLENGE_ACTIONS


def test_issue_and_peek():
    async def _run():
        window_id = uuid4()
        student_id = uuid4()
        closes_at = datetime.now(UTC)

        storage = {}

        mock_redis = MagicMock()

        # pipeline mock
        pipe_mock = MagicMock()

        def mock_hsetnx(key, field, val):
            storage.setdefault(key, {})[field] = val

        pipe_mock.hsetnx.side_effect = mock_hsetnx
        pipe_mock.expireat.return_value = None
        pipe_mock.execute = AsyncMock(return_value=None)

        class PipeContext:
            async def __aenter__(self):
                return pipe_mock

            async def __aexit__(self, *args):
                pass

        mock_redis.pipeline.return_value = PipeContext()

        async def mock_hmget(key, *fields):
            data = storage.get(key, {})
            return [data.get(f) for f in fields]

        mock_redis.hmget = AsyncMock(side_effect=mock_hmget)

        # Issue
        await nonces.issue(mock_redis, window_id, [student_id], closes_at, challenges={student_id: ["blink", "smile"]})

        # Peek
        status, value, challenge = await nonces.peek(mock_redis, window_id, student_id)
        assert status == "ok"
        assert value is not None
        assert challenge == ["blink", "smile"]

    asyncio.run(_run())


if __name__ == "__main__":
    test_challenge_generation()
    test_issue_and_peek()
    print("Backend Phase 7 tests passed!")
