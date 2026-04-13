from main import _spa_index_response


def test_spa_index_response_disables_cache(tmp_path):
    index_path = tmp_path / "index.html"
    index_path.write_text("<html></html>", encoding="utf-8")

    response = _spa_index_response(index_path)

    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
