from unittest.mock import MagicMock

import pytest

import refresher


def _fake_process(pid, name):
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name}
    return proc


def test_get_target_pids_matches_case_insensitive(mocker):
    processes = [
        _fake_process(100, "chrome.exe"),
        _fake_process(200, "CHROME.EXE"),
        _fake_process(300, "notepad.exe"),
    ]
    mocker.patch(
        "refresher.psutil.process_iter",
        return_value=iter(processes),
    )

    pids = refresher.get_target_pids({"chrome.exe"})

    assert pids == {100, 200}


def test_get_target_pids_handles_access_denied(mocker):
    ok = _fake_process(100, "chrome.exe")
    bad = MagicMock()
    bad.info = MagicMock(side_effect=refresher.psutil.AccessDenied())
    mocker.patch("refresher.psutil.process_iter", return_value=iter([ok, bad]))

    pids = refresher.get_target_pids({"chrome.exe"})

    assert pids == {100}


def test_get_target_pids_empty_input_returns_empty():
    assert refresher.get_target_pids(set()) == set()


def test_get_windows_skips_invisible_and_empty_title(mocker):
    visible = 101
    invisible = 102
    no_title = 103

    def fake_enum(callback, _):
        for hwnd in (visible, invisible, no_title):
            callback(hwnd, None)

    mocker.patch("refresher.win32gui.EnumWindows", side_effect=fake_enum)
    mocker.patch(
        "refresher.win32gui.IsWindowVisible",
        side_effect=lambda h: h == visible,
    )
    mocker.patch(
        "refresher.win32gui.GetWindowText",
        side_effect=lambda h: "Tab" if h == visible else "",
    )
    mocker.patch(
        "refresher.win32process.GetWindowThreadProcessId",
        side_effect=lambda h: (0, 1000 if h == visible else 9999),
    )

    handles = refresher.get_windows_for_pids({1000})

    assert handles == [visible]


def test_refresh_no_process_names_logs_message():
    logs = []
    refresher.refresh_browsers(set(), logs.append)
    assert logs == ["Sin navegadores seleccionados."]


def test_refresh_no_pids_logs_no_windows(mocker):
    mocker.patch("refresher.get_target_pids", return_value=set())
    logs = []

    refresher.refresh_browsers({"chrome.exe"}, logs.append)

    assert logs == ["Sin ventanas abiertas de los navegadores seleccionados."]


def test_refresh_calls_f5_per_window(mocker):
    mocker.patch("refresher.get_target_pids", return_value={100})
    mocker.patch("refresher.get_windows_for_pids", return_value=[1, 2])
    mocker.patch("refresher.win32gui.IsIconic", return_value=False)
    mock_fg = mocker.patch("refresher._force_foreground")
    mock_f5 = mocker.patch("refresher._press_f5")
    mock_sleep = mocker.patch("refresher.time.sleep")
    logs = []

    refresher.refresh_browsers({"chrome.exe"}, logs.append)

    assert mock_fg.call_count == 2
    assert mock_f5.call_count == 2
    assert logs == ["Refrescadas 2 ventana(s)."]
    mock_sleep.assert_called()


def test_refresh_restores_minimized_window(mocker):
    mocker.patch("refresher.get_target_pids", return_value={100})
    mocker.patch("refresher.get_windows_for_pids", return_value=[1])
    mocker.patch("refresher.win32gui.IsIconic", return_value=True)
    mock_show = mocker.patch("refresher.win32gui.ShowWindow")
    mocker.patch("refresher._force_foreground")
    mocker.patch("refresher._press_f5")
    mocker.patch("refresher.time.sleep")

    refresher.refresh_browsers({"chrome.exe"}, lambda _m: None)

    mock_show.assert_called_once_with(1, refresher.win32con.SW_RESTORE)


def test_refresh_continues_on_single_window_error(mocker):
    mocker.patch("refresher.get_target_pids", return_value={100})
    mocker.patch("refresher.get_windows_for_pids", return_value=[1, 2])
    mocker.patch("refresher.win32gui.IsIconic", return_value=False)
    mocker.patch(
        "refresher._force_foreground",
        side_effect=[RuntimeError("fail"), None],
    )
    mock_f5 = mocker.patch("refresher._press_f5")
    mocker.patch("refresher.time.sleep")
    logs = []

    refresher.refresh_browsers({"chrome.exe"}, logs.append)

    assert mock_f5.call_count == 1
    assert logs == ["Refrescadas 1 ventana(s)."]
