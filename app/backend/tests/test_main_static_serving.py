from static_serving import spa_index_response
from static_serving import mount_frontend_static_dirs

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_spa_index_response_disables_cache(tmp_path):
    index_path = tmp_path / "index.html"
    index_path.write_text("<html></html>", encoding="utf-8")

    response = spa_index_response(index_path)

    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


def test_mount_frontend_static_dirs_supports_vite_assets_without_static_dir(tmp_path):
    build_path = tmp_path / "frontend_build"
    assets_path = build_path / "assets"
    assets_path.mkdir(parents=True)
    (assets_path / "app.js").write_text("console.log('ok');", encoding="utf-8")

    app = FastAPI()

    mount_frontend_static_dirs(app, build_path)

    response = TestClient(app).get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log('ok');" in response.text
