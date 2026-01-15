"""Common collection utilities for the simulor package.

Provides reusable collection types and wrappers for internal use.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TypeVar, overload

T = TypeVar("T")


class ReadOnlySequence(Sequence[T]):
    """Read-only view of a list.

    Provides sequence protocol without allowing modification of underlying data.
    All operations are zero-copy views of the internal list.

    Examples:
        >>> data = [1, 2, 3, 4, 5]
        >>> view = ReadOnlySequence(data)
        >>> view[0]
        1
        >>> view[-1]
        5
        >>> view[1:3]
        ReadOnlySequence([2, 3])
        >>> len(view)
        5
        >>> list(view)
        [1, 2, 3, 4, 5]
    """

    __slots__ = ("_data",)

    def __init__(self, data: list[T]) -> None:
        self._data = data

    @overload
    def __getitem__(self, index: int) -> T:
        ...

    @overload
    def __getitem__(self, index: slice) -> ReadOnlySequence[T]:
        ...

    def __getitem__(self, index: int | slice) -> T | ReadOnlySequence[T]:
        if isinstance(index, slice):
            return ReadOnlySequence(self._data[index])
        return self._data[index]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[T]:
        return iter(self._data)

    def __reversed__(self) -> Iterator[T]:
        return reversed(self._data)

    def __contains__(self, value: object) -> bool:
        return value in self._data

    def count(self, value: T) -> int:
        return self._data.count(value)

    def index(self, value: T, start: int = 0, stop: int | None = None) -> int:
        if stop is None:
            return self._data.index(value, start)
        return self._data.index(value, start, stop)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReadOnlySequence):
            return self._data == other._data
        if isinstance(other, list):
            return self._data == other
        return False

    def __repr__(self) -> str:
        return f"ReadOnlySequence({self._data!r})"
