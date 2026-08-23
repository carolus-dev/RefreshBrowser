import queue

import pytest

from main import MIN_INTERVAL, RefreshBrowserApp


class FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def time(self):
        return self.t

    def advance(self, secs):
        self.t += secs


@pytest.fixture
def app_with_fake_time(tk_root, mocker):
    clock = FakeClock(start=1000.0)
    mocker.patch("main.time.time", clock.time)
    mocker.patch("main.time.sleep", lambda s: clock.advance(s))
    app = RefreshBrowserApp(tk_root)
    app.interval_var.set(str(MIN_INTERVAL))
    app.interval_seconds = MIN_INTERVAL
    app._show_notifier = lambda _s: None
    app._destroy_notifier = lambda: None
    return app, clock


def _drain_queue(q: queue.Queue):
    items = []
    while True:
        try:
            items.append(q.get_nowait())
        except queue.Empty:
            break
    return items


def test_worker_completes_cycle_and_refreshes(app_with_fake_time, mocker):
    app, _clock = app_with_fake_time
    mock_refresh = mocker.patch(
        "main.refresh_browsers",
        side_effect=lambda *_a, **_k: app.stop_event.set(),
    )

    app._run_loop()

    mock_refresh.assert_called_once()


def test_worker_cancel_during_warn_skips_refresh(app_with_fake_time, mocker):
    app, clock = app_with_fake_time
    mock_refresh = mocker.patch("main.refresh_browsers")
    sleeps = {"count": 0}

    def gated_sleep(s):
        clock.advance(s)
        sleeps["count"] += 1
        if sleeps["count"] == 3:
            app.cancel_event.set()
        if sleeps["count"] == 4:
            app.stop_event.set()

    mocker.patch("main.time.sleep", gated_sleep)

    app._run_loop()

    mock_refresh.assert_not_called()
    messages = [i[1] for i in _drain_queue(app.log_queue) if i[0] == "LOG"]
    assert any("cancelado" in msg.lower() for msg in messages)


def test_worker_postpone_waits_then_skips_refresh(app_with_fake_time, mocker):
    app, clock = app_with_fake_time
    mock_refresh = mocker.patch("main.refresh_browsers")
    sleeps = {"count": 0}

    def gated_sleep(s):
        clock.advance(s)
        sleeps["count"] += 1
        if sleeps["count"] == 3:
            app.postpone_event.set()
        # Fase 1 (2) + aviso hasta posponer (1) + postergación 300s (600) = 603
        if sleeps["count"] == 603:
            app.stop_event.set()

    mocker.patch("main.time.sleep", gated_sleep)

    app._run_loop()

    mock_refresh.assert_not_called()
    messages = [i[1] for i in _drain_queue(app.log_queue) if i[0] == "LOG"]
    assert any("pospuesto" in msg.lower() for msg in messages)
    assert any("postergación completada" in msg.lower() for msg in messages)


def test_worker_stop_during_countdown_exits(app_with_fake_time, mocker):
    app, _clock = app_with_fake_time
    mock_refresh = mocker.patch("main.refresh_browsers")
    app.stop_event.set()

    app._run_loop()

    mock_refresh.assert_not_called()


def test_worker_stop_during_warn_hides_notifier(app_with_fake_time, mocker):
    app, clock = app_with_fake_time
    mocker.patch("main.refresh_browsers")
    sleeps = {"count": 0}

    def gated_sleep(s):
        clock.advance(s)
        sleeps["count"] += 1
        if sleeps["count"] == 3:
            app.stop_event.set()

    mocker.patch("main.time.sleep", gated_sleep)

    app._run_loop()

    kinds = [item[0] for item in _drain_queue(app.log_queue)]
    assert "HIDE_NOTIFIER" in kinds
