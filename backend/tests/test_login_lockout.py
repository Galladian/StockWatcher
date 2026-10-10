from conftest import PASSWORD


def attempt(client, name, password):
    return client.post("/api/auth/login", json={"username": name, "password": password})


def test_five_wrong_passwords_lock_that_account_even_for_the_right_password(make_user, fresh_client):
    name = make_user("lock")
    assert [attempt(fresh_client, name, "wrong-password").status_code for _ in range(5)] == [401] * 5
    r = attempt(fresh_client, name, PASSWORD)
    assert r.status_code == 429 and "Too many failed login attempts" in r.json()["detail"] and int(r.headers["retry-after"]) > 0


def test_other_accounts_are_not_affected(make_user, fresh_client):
    locked, other = make_user("locked"), make_user("other")
    for _ in range(5):
        attempt(fresh_client, locked, "wrong-password")
    assert attempt(fresh_client, other, PASSWORD).status_code == 200


def test_a_successful_login_resets_the_count(make_user, fresh_client):
    name = make_user("reset")
    for _ in range(3):
        assert attempt(fresh_client, name, "wrong-password").status_code == 401
    assert attempt(fresh_client, name, PASSWORD).status_code == 200
    for _ in range(4):                          # would have locked the account if the earlier three still counted
        assert attempt(fresh_client, name, "wrong-password").status_code == 401
    assert attempt(fresh_client, name, PASSWORD).status_code == 200


def test_guessing_many_different_usernames_from_one_place_is_stopped(make_user, fresh_client):
    real = make_user("real")
    for i in range(20):
        assert attempt(fresh_client, f"ghost-{i}", "wrong-password").status_code == 401
    assert attempt(fresh_client, real, PASSWORD).status_code == 429


def test_unknown_and_wrong_password_look_identical(make_user, fresh_client):
    name = make_user("same")
    a, b = attempt(fresh_client, name, "wrong-password"), attempt(fresh_client, "no-such-user", "wrong-password")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_logout_ends_the_session(logged_in):
    client, name = logged_in("out")
    assert client.get("/api/auth/me").json() == {"username": name}
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json() == {"username": None}
    assert client.get("/api/portfolio/transactions").status_code == 401
