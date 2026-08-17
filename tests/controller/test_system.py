import pytest
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient


class TestSystemController:
    app: Litestar

    @pytest.fixture(autouse=True)
    def set_up(self, app: Litestar) -> None:
        self.app = app

    async def test_health_returns_ok_response(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            response = await client.get("/system/health")

        assert response.status_code == HTTP_200_OK
        assert response.json()["message"] == "ok"
