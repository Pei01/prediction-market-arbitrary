import time


def get_current_window_timestamp():
    now = time.time()

    INTERVAL = 900  # 15 * 60 sec

    window_start = int((now // INTERVAL) * INTERVAL)

    return window_start 
