# shared-memory

Python Shared Memory LRU - POC Test. Performance:

```
local
    0.000252 ms/opp
functools.lru_cache
    0.000275 ms/opp
shared memory_lru v1 - 3 lists: key, prev, next
    0.007828 ms/opp
shared memory_lru v2 - list of (key, prev, next)
    0.005785 ms/opp
shared memory_lru v2 - list of (key, prev, next) - no LRU touch on __get__
    0.002724 ms/opp
shared memory_lru v3 - data in sm
    0.033305 ms/opp
Manager().dict - no LRU
    0.031112 ms/opp
redis
    0.049201 ms/opp

```

# Todo:

- locks
- self.root in shared memory
- better conflict handling in _del_index

# Random notes

- `marshal.dumps((a, b, b))` is 2x faster than `a.to_bytes(...) + b.to_bytes() + c.to_bytes()`
  but I still use `to_bytes` to write one value of the tuple, without reading
- reading / writing to the shared memory is surprisingly slow: to investigate
- 0.03ms to access a view is acceptable for the cache of views of Odoo
- we could speed up by `lru_touch` only 10% of the `__get__` (to test on a prod DB, it should work)

