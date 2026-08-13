from collections.abc import Sequence
from typing import Any

from litestar.connection.request import Request
from litestar.openapi.plugins import OpenAPIRenderPlugin

__all__ = ("ScalarRenderPlugin",)


class ScalarRenderPlugin(OpenAPIRenderPlugin):
    """Render OpenAPI schema using Scalar API Reference.

    Scalar provides a modern, feature-rich API documentation interface
    with built-in API client for making requests directly from the browser.
    """

    def __init__(
        self,
        path: str | Sequence[str] = "/docs",
        version: str = "latest",
        **kwargs: Any,
    ) -> None:
        self.scalar_url = (
            f"https://cdn.jsdelivr.net/npm/@scalar/api-reference@{version}"
            if version != "latest"
            else "https://cdn.jsdelivr.net/npm/@scalar/api-reference"
        )
        super().__init__(path=path, **kwargs)

    def render(self, request: Request, openapi_schema: dict[str, Any]) -> bytes:
        json_route = self.get_openapi_json_route(request)
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{openapi_schema["info"]["title"]}</title>
    {self.favicon}
    {self.style}
    <style>
        body {{ margin: 0; }}
        #api-reference {{
            height: 100vh;
        }}
    </style>
</head>
<body>
    <script
        id="api-reference"
        data-url="{json_route}"
        src="{self.scalar_url}"></script>
</body>
</html>"""
        return html.encode()
