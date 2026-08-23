from freezegun import freeze_time

import main


@freeze_time("2026-08-23")
def test_check_expiry_allows_before_expiry(mocker):
    mocker.patch.object(main, "sys")
    main._check_expiry()
    main.sys.exit.assert_not_called()


@freeze_time("2027-08-23")
def test_check_expiry_allows_on_expiry_date(mocker):
    mocker.patch.object(main, "sys")
    main._check_expiry()
    main.sys.exit.assert_not_called()


@freeze_time("2027-08-24")
def test_check_expiry_blocks_after_expiry(mocker):
    mock_exit = mocker.patch.object(main.sys, "exit")
    mock_msg = mocker.patch("main.messagebox.showerror")
    mock_root = mocker.MagicMock()
    mocker.patch("main.tk.Tk", return_value=mock_root)

    main._check_expiry()

    mock_msg.assert_called_once()
    assert "23/08/2027" in mock_msg.call_args[0][1]
    mock_root.withdraw.assert_called_once()
    mock_root.destroy.assert_called_once()
    mock_exit.assert_called_once_with(0)
