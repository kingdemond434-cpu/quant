from unittest.mock import patch

from scripts import memory_guard as guard


def test_windows_uses_median_native_readings_without_proc():
    with patch.object(guard.sys, "platform", "win32"), \
         patch.object(guard, "_windows_available_mb", side_effect=[1500, 800, 1200]), \
         patch.object(guard.time, "sleep"), patch("builtins.open") as open_file:
        assert guard.available_mb() == 1200
    open_file.assert_not_called()


def test_windows_failure_does_not_grant_memory_admission():
    with patch.object(guard.sys, "platform", "win32"), \
         patch.object(guard, "_windows_available_mb", return_value=0), \
         patch.object(guard.time, "sleep"):
        assert guard.wait_for_headroom(700, 0)[0] is False


def test_native_api_error_is_fail_closed():
    with patch.object(guard.ctypes, "WinDLL", side_effect=OSError("unavailable"), create=True):
        assert guard._windows_available_mb() == 0
