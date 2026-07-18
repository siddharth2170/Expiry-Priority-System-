from itertools import count
from typing import Any


class PriorityQueue:
    """A binary min-heap implemented from scratch (no heapq).

    Entries are stored as (priority, seq, item) tuples where ``seq`` is a
    monotonically increasing counter. The counter keeps ordering stable for
    equal priorities (insertion order) and ensures items themselves are never
    compared, so items need not be orderable.

    The entry with the smallest priority is always at the root and returned
    first by ``peek`` / ``pop``.
    """

    def __init__(self) -> None:
        self._heap: list[tuple[Any, int, Any]] = []
        self._counter = count()

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return not self._heap

    def push(self, item: Any, priority: Any) -> None:
        entry = (priority, next(self._counter), item)
        self._heap.append(entry)
        self._sift_up(len(self._heap) - 1)

    def peek(self) -> Any:
        if not self._heap:
            raise IndexError("peek from an empty PriorityQueue")
        return self._heap[0][2]

    def pop(self) -> Any:
        if not self._heap:
            raise IndexError("pop from an empty PriorityQueue")

        root = self._heap[0]
        last = self._heap.pop()
        if self._heap:
            self._heap[0] = last
            self._sift_down(0)
        return root[2]

    def _sift_up(self, i: int) -> None:
        """Restore the heap after an insertion at index ``i``.

        Moves the new entry toward the root, swapping with its parent while it
        is smaller, until the parent is no longer larger or the root is reached.
        """
        heap = self._heap
        while i > 0:
            parent = (i - 1) // 2
            # Compare on (priority, seq) only, never the item, so unorderable
            # items are safe and equal priorities keep insertion order.
            if heap[i][:2] < heap[parent][:2]:
                heap[i], heap[parent] = heap[parent], heap[i]
                i = parent
            else:
                break

    def _sift_down(self, i: int) -> None:
        """Restore the heap after the root is replaced, starting at index ``i``.

        Moves the entry toward the leaves, repeatedly swapping it with its
        smaller child until it is no larger than both children (or has no
        children), which re-establishes the min-heap property.
        """
        heap = self._heap
        n = len(heap)
        while True:
            left = 2 * i + 1
            right = 2 * i + 2
            smallest = i

            # Pick the smallest of the node and its two children; swapping with
            # the smaller child is what keeps every parent <= its children.
            if left < n and heap[left][:2] < heap[smallest][:2]:
                smallest = left
            if right < n and heap[right][:2] < heap[smallest][:2]:
                smallest = right

            if smallest == i:
                break

            heap[i], heap[smallest] = heap[smallest], heap[i]
            i = smallest
