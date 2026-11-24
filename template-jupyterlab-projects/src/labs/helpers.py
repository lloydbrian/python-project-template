"""Small, tested helpers that notebooks import instead of copying code between cells."""

from __future__ import annotations

from collections.abc import Iterable, Iterator


def batched_texts(texts: Iterable[str], size: int) -> Iterator[list[str]]:
    """Yield lists of at most `size` non-empty, stripped texts."""
    if size < 1:
        raise ValueError("size must be >= 1")
    batch: list[str] = []
    for text in texts:
        cleaned = text.strip()
        if not cleaned:
            continue
        batch.append(cleaned)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
