import threading
from unittest.mock import MagicMock

import pytest

import main
from main import MIN_INTERVAL, RefreshBrowserApp, _fmt


@pytest.mark.parametrize(
    "secs, expected",
    [
        (0, "00:00"),
        (45, "00:45"),
        (60, "01:00"),
        (-5, "00:00"),
        (3661, "61:01"),
    ],
)
def test_fmt(secs, expected):
    assert _fmt(secs) == expected


def test_read_interval_seconds(tk_root):
    app = RefreshBrowserApp(tk_root)
    app.interval_var.set("100")
    app.unit_var.set("segundos")
    assert app._read_interval() == 100


def test_read_interval_minutes(tk_root):
    app = RefreshBrowserApp(tk_root)
    app.interval_var.set("5")
    app.unit_var.set("minutos")
    assert app._read_interval() == 300


def test_read_interval_hours(tk_root):
    app = RefreshBrowserApp(tk_root)
    app.interval_var.set("2")
    app.unit_var.set("horas")
    assert app._read_interval() == 7200


def test_read_interval_invalid_text(tk_root):
    app = RefreshBrowserApp(tk_root)
    app.interval_var.set("abc")
    assert app._read_interval() is None


def test_read_interval_zero(tk_root):
    app = RefreshBrowserApp(tk_root)
    app.interval_var.set("0")
    assert app._read_interval() is None


def test_start_without_browsers_shows_warning(tk_root, mocker):
    app = RefreshBrowserApp(tk_root)
    mock_warn = mocker.patch("main.messagebox.showwarning")
    for var in app.browser_vars.values():
        var.set(False)

    app._start()

    mock_warn.assert_called_once()
    assert app.worker is None or not app.worker.is_alive()


def test_start_invalid_interval_shows_warning(tk_root, mocker):
    app = RefreshBrowserApp(tk_root)
    mock_warn = mocker.patch("main.messagebox.showwarning")
    app.interval_var.set(str(MIN_INTERVAL - 1))

    app._start()

    mock_warn.assert_called_once()
    assert app.worker is None or not app.worker.is_alive()


def test_start_valid_starts_worker(tk_root, mocker):
    app = RefreshBrowserApp(tk_root)
    started = threading.Event()

    def fake_loop():
        started.set()
        app.stop_event.wait(timeout=2)

    mocker.patch.object(app, "_run_loop", side_effect=fake_loop)
    app.interval_var.set(str(MIN_INTERVAL))

    app._start()

    assert started.wait(timeout=2)
    assert app.toggle_btn.cget("text") == "Detener"
    app._stop()
    if app.worker:
        app.worker.join(timeout=2)


def test_stop_sets_state(tk_root, mocker):
    app = RefreshBrowserApp(tk_root)
    mocker.patch.object(app, "_run_loop")
    app.interval_var.set(str(MIN_INTERVAL))
    app._start()

    app._stop()

    assert app.status_var.get() == "Detenido"
    assert app.countdown_var.get() == ""
    assert app.toggle_btn.cget("text") == "Iniciar"
