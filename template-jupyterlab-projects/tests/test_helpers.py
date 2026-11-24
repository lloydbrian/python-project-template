import pytest

from labs.helpers import batched_texts


def test_batches_and_skips_blanks() -> None:
    assert list(batched_texts(["a", " ", "b ", "c"], 2)) == [["a", "b"], ["c"]]


def test_rejects_bad_size() -> None:
    with pytest.raises(ValueError):
        list(batched_texts(["a"], 0))
