import time


def retry(fn, attempts=3, delay=0.1):
    """Call fn up to `attempts` times, re-raising the last error.

    The final failure propagates: a retry helper that swallows the
    error it could not survive hides the reason it gave up.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if i + 1 < attempts:
                time.sleep(delay)
    raise last
