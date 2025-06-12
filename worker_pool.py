# worker_pool.py
import threading
import queue

stop_event = threading.Event()
_task_queue = queue.Queue()
_result_queue = queue.Queue()

_workers = []

def _worker_loop():
    while not stop_event.is_set():
        try:
            func, args, kwargs = _task_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            result = func(*args, **kwargs)
            # stick the result (and maybe some metadata) on the result queue
            _result_queue.put((func, args, result))
        except Exception as e:
            _result_queue.put((func, args, e))
        finally:
            _task_queue.task_done()


# start 3 workers as soon as this module is imported
for i in range(3):
    t = threading.Thread(target=_worker_loop,
                         name=f"Worker-{i+1}",
                         daemon=True)
    t.start()
    _workers.append(t)

def submit(func, *args, **kwargs):
    """Schedule func(*args, **kwargs) on a worker."""
    _task_queue.put((func, args, kwargs))

def shutdown(wait=True):
    """Stop workers after finishing outstanding tasks."""
    if wait:
        _task_queue.join()
    stop_event.set()
    for t in _workers:
        t.join()
