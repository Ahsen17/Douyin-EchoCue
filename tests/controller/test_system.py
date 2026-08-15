from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient


class TestSystemController:
    async def test_health_returns_ok_response(self, app: Litestar) -> None:
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/system/health")

        assert response.status_code == HTTP_200_OK
        assert response.json()["message"] == "ok"
