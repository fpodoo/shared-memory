
from multiprocessing import Process, Manager
import sm_lru
import sm_lru_v1
import sm_lru_v2
import sm_lru_v3
import sm_lru_v4
import time
import functools
import redis

s = "a"*5000

def f():
    t = time.time()
    for i in range(500):
        d['a'*20+str(i)] = s
        for j in range(i):
            a = d['a'*20+str(j)]
    print('    %.6f ms/opp' % ((time.time() - t) * 1000.0 / (500*251),))

def lru_test():
    d = {}
    @functools.lru_cache(maxsize=2048)
    def getdata(key):
        return d[key]

    t = time.time()
    for i in range(500):
        d['a'*20+str(i)] = s
        for j in range(i):
            a = getdata('a'*20+str(j))
    print('    %.6f ms/opp' % ((time.time() - t) * 1000.0 / (500*251),))



if __name__ == '__main__':
    print('local')
    d = {}
    f()

    print('functools.lru_cache')
    d = {}
    lru_test()

    print('shared memory_lru v1 - 3 lists: key, prev, next')
    d = sm_lru_v1.lru_shared(4096)
    f()
    del d

    print('shared memory_lru v2 - list of (key, prev, next)')
    d = sm_lru_v2.lru_shared(4096)
    f()
    del d

    print('shared memory_lru v3 - list of (key, prev, next) - no LRU touch on __get__')
    d = sm_lru_v3.lru_shared(4096)
    f()
    del d

    print('shared memory_lru v4 - lock - data in sm - 13% lru touch')
    d = sm_lru_v4.lru_shared(4096)
    f()
    del d

    print('current: numpy + root & length in shared memory')
    d = sm_lru.lru_shared(4096)
    f()
    del d

    print('Manager().dict - no LRU')
    manager = Manager()
    d = manager.dict()
    p = Process(target=f)
    p.start()
    p.join()

    print('redis')
    d = redis.Redis()
    f()


