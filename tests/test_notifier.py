from unittest.mock import MagicMock

import pytest

from notifier import NotifierWindow, corner_to_coords


@pytest.mark.parametrize(
    "corner, expected",
    [
        ("Inferior derecha", (1920 - 300 - 20, 1080 - 200 - 20 - 48)),
        ("Inferior izquierda", (20, 1080 - 200 - 20 - 48)),
        ("Superior derecha", (1920 - 300 - 20, 20)),
        ("Superior izquierda", (20, 20)),
    ],
)
def test_corner_to_coords(corner, expected):
    assert corner_to_coords(corner, 300, 200, 1920, 1080) == expected


def test_corner_unknown_falls_back_to_inferior_derecha():
    fallback = corner_to_coords("Inferior derecha", 300, 200, 1920, 1080)
    assert corner_to_coords("desconocida", 300, 200, 1920, 1080) == fallback


def test_cancel_calls_on_cancel_once(tk_root, mocker):
    mocker.patch.object(NotifierWindow, "_beep")
    on_cancel = MagicMock()
    notifier = NotifierWindow(
        parent=tk_root,
        seconds=5,
        on_cancel=on_cancel,
        on_postpone=MagicMock(),
    )

    notifier._cancel()
    notifier._cancel()

    on_cancel.assert_called_once()


def test_postpone_calls_on_postpone_once(tk_root, mocker):
    mocker.patch.object(NotifierWindow, "_beep")
    on_postpone = MagicMock()
    notifier = NotifierWindow(
        parent=tk_root,
        seconds=5,
        on_cancel=MagicMock(),
        on_postpone=on_postpone,
    )

    notifier._postpone()
    notifier._postpone()

    on_postpone.assert_called_once()


def test_destroy_idempotent(tk_root, mocker):
    mocker.patch.object(NotifierWindow, "_beep")
    notifier = NotifierWindow(
        parent=tk_root,
        seconds=5,
        on_cancel=MagicMock(),
        on_postpone=MagicMock(),
    )

    notifier.destroy()
    notifier.destroy()

    assert notifier._active is False
