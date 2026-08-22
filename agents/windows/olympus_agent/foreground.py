import ctypes


def get_foreground_process_id() -> int | None:
    """Return the foreground window's process ID using the supported Win32 API."""
    try:
        user32 = ctypes.windll.user32
        window = user32.GetForegroundWindow()
        if not window:
            return None
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        return int(process_id.value) or None
    except (AttributeError, OSError):
        return None
