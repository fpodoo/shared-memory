# shared-memory

Python Shared Memory LRU - POC Test. Performance:

```
local
    0.000044 ms/opp
functools.lru_cache
    0.000301 ms/opp
shared memory_lru v1 - 3 lists: key, prev, next
    0.007454 ms/opp
shared memory_lru v2 - list of (key, prev, next)
    0.005607 ms/opp
shared memory_lru v3 - list of (key, prev, next) - no LRU touch on __get__
    0.002878 ms/opp
shared memory_lru v4 - data in sm - 10% lru touch
    0.004500 ms/opp
Manager().dict - no LRU
    0.030116 ms/opp
redis
    0.048077 ms/opp
```

# Todo:

- locks
- self.root in shared memory
- better conflict handling in _del_index

# Random notes

- `marshal.dumps((a, b, b))` is 2x faster than `a.to_bytes(...) + b.to_bytes() + c.to_bytes()`
  but I still use `to_bytes` to write one value of the tuple, without reading
- 0.004ms to access a view is acceptable for the views cache of Odoo (~30 calls for a web page)
