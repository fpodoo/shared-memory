# shared-memory

Python Shared Memory LRU - POC Test. Performance:

```
local
    0.000242 ms/opp
functools.lru_cache
    0.000268 ms/opp
shared memory_lru v1 - 3 lists: key, prev, next
    0.008065 ms/opp
shared memory_lru v2 - list of (key, prev, next)
    0.005850 ms/opp
shared memory_lru v3 - list of (key, prev, next) - no LRU touch on __get__
    0.002774 ms/opp
shared memory_lru v4 - lock - data in sm - 13% lru touch
    0.004620 ms/opp
current: numpy + single large shared memory
    0.004500 ms/opp
Manager().dict - no LRU
    0.031983 ms/opp
redis
    0.048989 ms/opp
```

# Todo:

- better conflict handling in _del_index

# Random notes

- 0.005ms to access a view is acceptable for the views cache of Odoo (~30 calls for a web page)
