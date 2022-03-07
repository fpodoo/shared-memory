# shared-memory

Python Shared Memory LRU - POC Test. Performance:

```
local
    0.000241 ms/opp
functools.lru_cache
    0.000266 ms/opp
shared memory_lru v1 - 3 lists: key, prev, next
    0.007839 ms/opp
shared memory_lru v2 - list of (key, prev, next)
    0.005929 ms/opp
shared memory_lru v3 - list of (key, prev, next) - no LRU touch on __get__
    0.002760 ms/opp
shared memory_lru v4 - lock - data in sm - 13% lru touch
    0.004553 ms/opp
current: numpy + root & length in shared memory
    0.004934 ms/opp
Manager().dict - no LRU
    0.030575 ms/opp
redis
    0.049428 ms/opp
```

# Todo:

- better conflict handling in _del_index
- put data in a single large shared memory block, instead of creating a sm per data

# Random notes

- 0.005ms to access a view is acceptable for the views cache of Odoo (~30 calls for a web page)
