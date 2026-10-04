from __future__ import annotations


def chunked(items, batch_size: int):
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]
