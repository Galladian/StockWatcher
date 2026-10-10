from app.ratelimit import FailureTracker, SlidingWindowLimiter


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def test_sliding_window_limits_then_recovers():
    clock = Clock()
    limiter = SlidingWindowLimiter(limit=3, window=10, clock=clock)
    assert [limiter.hit("a") for _ in range(3)] == [0, 0, 0]
    assert 9 < limiter.hit("a") <= 10          # the fourth is refused, with the time to wait
    assert limiter.hit("b") == 0               # other visitors are unaffected
    clock.t = 10.5
    assert limiter.hit("a") == 0               # the old hits have aged out


def test_failure_tracker_blocks_clears_and_expires():
    clock = Clock()
    tracker = FailureTracker(limit=3, window=100, clock=clock)
    for second in (0, 1, 2):
        clock.t = second
        assert tracker.blocked("x") == 0
        tracker.record("x")
    assert 97 < tracker.blocked("x") <= 98
    tracker.clear("x")
    assert tracker.blocked("x") == 0
    for _ in range(3):
        tracker.record("y")
    clock.t = 102.5                            # the first failures are older than the window now
    assert tracker.blocked("y") == 0


def test_memory_is_bounded_when_someone_sends_endless_new_keys():
    limiter = SlidingWindowLimiter(limit=5, window=60, max_keys=50)
    for i in range(500):
        limiter.hit(f"visitor-{i}")
    assert len(limiter._hits) <= 50
    limiter.hit("k" * 10_000)                   # huge keys are shortened rather than stored whole
    assert all(len(k) <= 200 for k in limiter._hits)


def test_endpoints_that_call_yahoo_are_limited_per_visitor(fresh_client, monkeypatch):
    monkeypatch.setattr("app.main.get_indices", lambda period: {"period": period, "regions": []})
    assert all(fresh_client.get("/api/markets/indices").status_code == 200 for _ in range(60))
    r = fresh_client.get("/api/markets/indices")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert fresh_client.get("/api/health").status_code == 200   # the health check is never limited


def test_everything_under_api_has_a_higher_overall_limit(fresh_client):
    assert all(fresh_client.get("/api/auth/me").status_code == 200 for _ in range(300))
    assert fresh_client.get("/api/auth/me").status_code == 429


def test_health_check_is_exempt(fresh_client):
    assert all(fresh_client.get("/api/health").status_code == 200 for _ in range(350))
