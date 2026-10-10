from conftest import PASSWORD


def test_api_responses_carry_security_headers(fresh_client):
    r = fresh_client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"ok": True}
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "script-src 'self'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["cache-control"] == "no-store"  # private data is never cached


def test_frontend_is_served_and_react_routes_fall_back_to_the_index(fresh_client):
    for path in ("/", "/portfolio", "/overview", "/screener"):
        r = fresh_client.get(path)
        assert r.status_code == 200 and "test app" in r.text, path
        assert r.headers["cache-control"] == "no-cache" and "content-security-policy" in r.headers
    assert fresh_client.get("/theme-init.js").text == "// theme"


def test_hashed_assets_are_cached_for_a_year(fresh_client):
    r = fresh_client.get("/assets/app.js")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"] and "max-age=31536000" in r.headers["cache-control"]


def test_unknown_api_paths_are_a_json_404_not_the_homepage(fresh_client):
    r = fresh_client.get("/api/nope")
    assert r.status_code == 404 and r.json()["detail"] == "Not found"


def test_files_outside_the_site_folder_cannot_be_read(fresh_client):
    for attack in ("/..%2f..%2f..%2fetc%2fpasswd", "/%2e%2e/%2e%2e/etc/passwd", "/../../../../etc/passwd"):
        r = fresh_client.get(attack)
        assert "root:" not in r.text, attack


def test_api_docs_are_off_in_production(fresh_client):
    assert "swagger" not in fresh_client.get("/docs").text.lower()
    assert "openapi" not in fresh_client.get("/openapi.json").text.lower()[:200]


def test_login_cookie_is_locked_down(make_user, fresh_client):
    name = make_user("cookie")
    r = fresh_client.post("/api/auth/login", json={"username": name, "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert cookie.startswith("__host-sw_session=")
    for flag in ("secure", "httponly", "samesite=lax", "path=/"):
        assert flag in cookie, flag
    assert "domain" not in cookie  # a __Host- cookie can't be shared with subdomains


def test_other_sites_get_no_cors_permission(fresh_client):
    r = fresh_client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cross_site_posts_are_refused_but_same_site_and_tools_still_work(fresh_client):
    body = {"username": "nobody", "password": "wrong-password"}
    assert fresh_client.post("/api/auth/login", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert fresh_client.post("/api/auth/login", json=body, headers={"Origin": "https://testserver"}).status_code == 401
    assert fresh_client.post("/api/auth/login", json=body).status_code == 401  # no Origin header: curl, scripts


def test_oversized_login_input_is_rejected_before_hashing(fresh_client):
    r = fresh_client.post("/api/auth/login", json={"username": "a", "password": "x" * 5000})
    assert r.status_code == 422
