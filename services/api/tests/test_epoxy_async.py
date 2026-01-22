import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport
import sys
import os

# Ensure app is importable
# services/api/tests/test_epoxy_async.py -> services/api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from main import app  # noqa: E402
from app.api import deps  # noqa: E402

# UUIDs for testing
TEST_STYLE_ID = "00000000-0000-0000-0000-000000000001"
TEST_IMAGE_ID = "test-image"


@pytest.fixture
def mock_db():
    mock_session = AsyncMock()
    mock_result = MagicMock()

    # Mock Style
    mock_style = MagicMock()
    mock_style.parameters = {"color": "#ffffff"}
    mock_result.scalar_one_or_none.return_value = mock_style

    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.fixture
def app_with_overrides(mock_db):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[deps.get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preview_concurrency(app_with_overrides):
    # Mock process_image to be slow
    with patch("app.api.endpoints.epoxy.process_image") as mock_process:
        # Simulate blocking work
        def slow_process(*args, **kwargs):
            time.sleep(1)
            return {"success": True, "mask_filename": None}

        mock_process.side_effect = slow_process

        # Mock filesystem
        with patch("os.path.exists", return_value=True), patch(
            "os.listdir", return_value=["test-image.jpg"]
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                print("\nStarting concurrent requests...")
                start_time = time.time()

                # Launch two requests
                task1 = asyncio.create_task(
                    ac.post(
                        "/api/v1/epoxy/preview",
                        data={
                            "image_id": TEST_IMAGE_ID,
                            "style_id": TEST_STYLE_ID,
                            "debug": False,
                        },
                    )
                )

                task2 = asyncio.create_task(
                    ac.post(
                        "/api/v1/epoxy/preview",
                        data={
                            "image_id": TEST_IMAGE_ID,
                            "style_id": TEST_STYLE_ID,
                            "debug": False,
                        },
                    )
                )

                responses = await asyncio.gather(task1, task2)

                duration = time.time() - start_time

                print(f"Test Duration: {duration:.2f}s")

                for r in responses:
                    assert r.status_code == 200, f"Request failed: {r.text}"

                # If fixed, it should be around 1s. If not, around 2s.
                # We assert < 1.5 to pass only when fixed.
                assert (
                    duration < 1.5
                ), f"Expected < 1.5s, got {duration:.2f}s. Requests are blocking."
