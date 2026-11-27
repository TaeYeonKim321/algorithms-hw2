"""A string-keyed hash table using linear probing."""

import math
from typing import Generic, TypeVar


_Value = TypeVar("_Value")
_TOMBSTONE = object()


class _Entry(Generic[_Value]):
    __slots__ = ("key", "value")

    def __init__(self, key: str, value: _Value):
        self.key = key
        self.value = value


class LinearProbingHashTable(Generic[_Value]):
    """A fixed-array hash table with Horner hashing and linear probing."""

    def __init__(self, bucket_count: int = 8, max_load: float | None = 0.75):
        if isinstance(bucket_count, bool) or not isinstance(bucket_count, int):
            raise TypeError("bucket_count must be an integer")
        if bucket_count <= 0:
            raise ValueError("bucket_count must be positive")
        if max_load is not None:
            if isinstance(max_load, bool) or not isinstance(max_load, (int, float)):
                raise TypeError("max_load must be a positive number or None")
            if not math.isfinite(max_load) or max_load <= 0 or max_load >= 1:
                raise ValueError("max_load must be greater than 0 and less than 1")

        self.bucket_count = bucket_count
        self.max_load = max_load
        self._slots: list[_Entry[_Value] | object | None] = [None] * bucket_count
        self._size = 0
        self.last_comparisons = 0
        self.last_probes = 0

    @staticmethod
    def _index(key: str, bucket_count: int) -> int:
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        value = 0
        for character in key:
            value = (value * 31 + ord(character)) % bucket_count
        return value

    def _locate(self, key: str) -> tuple[int | None, int | None]:
        start = self._index(key, self.bucket_count)
        first_tombstone = None
        for offset in range(self.bucket_count):
            index = (start + offset) % self.bucket_count
            slot = self._slots[index]
            if slot is None:
                return None, first_tombstone if first_tombstone is not None else index
            if slot is _TOMBSTONE:
                if first_tombstone is None:
                    first_tombstone = index
            elif isinstance(slot, _Entry) and slot.key == key:
                return index, index
        return None, first_tombstone

    def set(self, key: str, value: _Value) -> None:
        found, insertion = self._locate(key)
        if found is not None:
            slot = self._slots[found]
            if isinstance(slot, _Entry):
                slot.value = value
            return

        if self.max_load is not None and (self._size + 1) / self.bucket_count > self.max_load:
            self._resize()
            _, insertion = self._locate(key)
        if insertion is None:
            raise OverflowError("hash table is full")

        self._slots[insertion] = _Entry(key, value)
        self._size += 1

    def get(self, key: str) -> _Value:
        start = self._index(key, self.bucket_count)
        self.last_comparisons = 0
        self.last_probes = 0
        for offset in range(self.bucket_count):
            index = (start + offset) % self.bucket_count
            self.last_probes += 1
            slot = self._slots[index]
            if slot is None:
                break
            if slot is _TOMBSTONE:
                continue
            if isinstance(slot, _Entry):
                self.last_comparisons += 1
                if slot.key == key:
                    return slot.value
        raise KeyError(key)

    def delete(self, key: str) -> None:
        start = self._index(key, self.bucket_count)
        for offset in range(self.bucket_count):
            index = (start + offset) % self.bucket_count
            slot = self._slots[index]
            if slot is None:
                break
            if isinstance(slot, _Entry) and slot.key == key:
                self._slots[index] = _TOMBSTONE
                self._size -= 1
                return
        raise KeyError(key)

    def __len__(self) -> int:
        return self._size

    def _resize(self) -> None:
        old_slots = self._slots
        self.bucket_count *= 2
        self._slots = [None] * self.bucket_count
        for slot in old_slots:
            if isinstance(slot, _Entry):
                start = self._index(slot.key, self.bucket_count)
                for offset in range(self.bucket_count):
                    index = (start + offset) % self.bucket_count
                    if self._slots[index] is None:
                        self._slots[index] = slot
                        break
