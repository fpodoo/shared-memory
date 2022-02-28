# shared-memory

Python Shared Memory LRU - POC Test. Performance:

```
local
    0.000253 ms/opp
functools.lru_cache
    0.000282 ms/opp
shared memory_lru v1 - 3 lists: key, prev, next
    0.007842 ms/opp
shared memory_lru v2 - list of (key, prev, next)
    0.005867 ms/opp
shared memory_lru v2 - list of (key, prev, next) - no LRU touch on __get__
    0.002732 ms/opp
Manager().dict - no LRU
    0.030400 ms/opp
```
