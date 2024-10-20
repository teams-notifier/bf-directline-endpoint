#!/usr/bin/env python3

from collections import OrderedDict
from threading import Lock
from typing import Hashable


class LeastRecentlySeen:
    def __init__(self, maxsize: int = 0) -> None:
        self._maxsize: int = maxsize
        self._lock = Lock()
        self._seen: OrderedDict = OrderedDict()

    def look_and_remember(self, key: Hashable) -> bool:
        res = False
        if key in self._seen:
            with self._lock:
                self._seen.move_to_end(key)
                res = True
        else:
            with self._lock:
                self._seen[key] = None
                if self._maxsize and len(self._seen) > self._maxsize:
                    self._seen.popitem(last=False)
        return res
