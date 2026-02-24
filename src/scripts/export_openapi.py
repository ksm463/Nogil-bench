#!/usr/bin/env python3
"""OpenAPI 스펙 추출 스크립트.

FastAPI 앱에서 OpenAPI 스펙을 추출하여
/app/swagger/ 폴더에 JSON과 HTML 파일을 생성한다.

사용법 (Docker 컨테이너 내부):
    docker exec nogil-bench-compose uv run python src/scripts/export_openapi.py

생성 파일:
    - swagger/openapi.json     (OpenAPI 3.1 스펙)
    - swagger/index.html       (Swagger UI)
"""

import json
import sys
from pathlib import Path

src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from main import app  # noqa: E402

SWAGGER_UI_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" type="text/css"
          href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <link rel="icon" type="image/png"
          href="https://fastapi.tiangolo.com/img/favicon.png">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
        .swagger-ui .topbar {{
            display: none;
        }}
        .swagger-ui .information-container {{
            margin: 40px 0;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>

    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            window.ui = SwaggerUIBundle({{
                url: './openapi.json',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
                docExpansion: "list",
                filter: true,
                showRequestHeaders: true,
                tryItOutEnabled: true,
                persistAuthorization: true
            }});
        }};
    </script>
</body>
</html>
"""


def export_openapi():
    print("Generating OpenAPI schema from FastAPI app...")
    openapi_schema = app.openapi()

    swagger_dir = Path(__file__).resolve().parent.parent.parent / "swagger"
    swagger_dir.mkdir(parents=True, exist_ok=True)

    # 1. OpenAPI JSON
    openapi_json_path = swagger_dir / "openapi.json"
    with open(openapi_json_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    print(f"  OpenAPI JSON saved: {openapi_json_path}")

    # 2. Swagger UI HTML
    info = openapi_schema.get("info", {})
    title = info.get("title", "API Documentation")
    html_content = SWAGGER_UI_HTML_TEMPLATE.format(title=title)

    index_html_path = swagger_dir / "index.html"
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  Swagger UI HTML saved: {index_html_path}")

    # 통계
    paths_count = len(openapi_schema.get("paths", {}))
    schemas_count = len(
        openapi_schema.get("components", {}).get("schemas", {})
    )

    print(f"\n  Endpoints: {paths_count}")
    print(f"  Schemas:   {schemas_count}")
    print(f"  Version:   {info.get('version', 'N/A')}")
    print("\n  Open: swagger/index.html")


if __name__ == "__main__":
    export_openapi()
