"""A string-keyed hash table using separate chaining."""

import math
from typing import Generic, TypeVar


_Value = TypeVar("_Value")


class _Node(Generic[_Value]):
    __slots__ = ("key", "value", "next")

    def __init__(
        self,
        key: str,
        value: _Value,
        next_node: "_Node[_Value] | None" = None,
    ):
        self.key = key
        self.value = value
        self.next = next_node


class HashTable(Generic[_Value]):
    """A hash table with Horner hashing and linked-list buckets."""

    def __init__(self, bucket_count: int = 8, max_load: float | None = 0.75):
        if isinstance(bucket_count, bool) or not isinstance(bucket_count, int):
            raise TypeError("bucket_count must be an integer")
        if bucket_count <= 0:
            raise ValueError("bucket_count must be positive")
        if max_load is not None:
            if isinstance(max_load, bool) or not isinstance(max_load, (int, float)):
                raise TypeError("max_load must be a positive number or None")
            if not math.isfinite(max_load) or max_load <= 0:
                raise ValueError("max_load must be a positive finite number or None")

        self.bucket_count = bucket_count
        self.max_load = max_load
        self._buckets: list[_Node[_Value] | None] = [None] * bucket_count
        self._size = 0
        self.last_comparisons = 0

    @staticmethod
    def _index(key: str, bucket_count: int) -> int:
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        value = 0
        for character in key:
            value = (value * 31 + ord(character)) % bucket_count
        return value

    def set(self, key: str, value: _Value) -> None:
        index = self._index(key, self.bucket_count)
        node = self._buckets[index]
        while node is not None:
            if node.key == key:
                node.value = value
                return
            node = node.next

        self._buckets[index] = _Node(key, value, self._buckets[index])
        self._size += 1
        if self.max_load is not None and self._size / self.bucket_count > self.max_load:
            self._resize()

    def get(self, key: str) -> _Value:
        index = self._index(key, self.bucket_count)
        self.last_comparisons = 0
        node = self._buckets[index]
        while node is not None:
            self.last_comparisons += 1
            if node.key == key:
                return node.value
            node = node.next
        raise KeyError(key)

    def delete(self, key: str) -> None:
        index = self._index(key, self.bucket_count)
        previous = None
        node = self._buckets[index]
        while node is not None:
            if node.key == key:
                if previous is None:
                    self._buckets[index] = node.next
                else:
                    previous.next = node.next
                self._size -= 1
                return
            previous = node
            node = node.next
        raise KeyError(key)

    def __len__(self) -> int:
        return self._size

    def _resize(self) -> None:
        self.bucket_count *= 2
        buckets: list[_Node[_Value] | None] = [None] * self.bucket_count
        for head in self._buckets:
            node = head
            while node is not None:
                next_node = node.next
                index = self._index(node.key, self.bucket_count)
                node.next = buckets[index]
                buckets[index] = node
                node = next_node
        self._buckets = buckets
