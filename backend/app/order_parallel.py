"""Parallel Delta order placement (requests.Session is not thread-safe)."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar

from app.delta_service import DeltaService

T = TypeVar("T")

_order_lock = threading.Lock()


def place_order_safe(delta: DeltaService, **kwargs: Any) -> dict[str, Any]:
    with _order_lock:
        return delta.place_order(**kwargs)


def run_parallel(
    tasks: list[Callable[[], T]],
    *,
    max_workers: int = 4,
) -> list[T]:
    if not tasks:
        return []
    if len(tasks) == 1:
        return [tasks[0]()]

    workers = min(len(tasks), max_workers)
    results: list[T] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn) for fn in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results
