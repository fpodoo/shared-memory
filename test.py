
from multiprocessing import Process, Manager, Pool
import sm_lru
import time
import functools
import redis
from pymemcache.client import base


s = "a"*5000

def f():
    t = time.time()
    for i in range(500):
        d['a'*20+str(i)] = s
        for j in range(i):
            a = d['a'*20+str(j)]
    print('    %.6f ms/opp' % ((time.time() - t) * 1000.0 / (500*251),))
    return True

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

    print('shared memory: 1 process')
    d = sm_lru.lru_shared(4096)
    f()
    del d

    print('shared memory: 8 processes')
    d = sm_lru.lru_shared(4096)
    with Pool(8) as p:
        p.starmap(f, [()]*8)
        p.close()
        p.join()
    del d

    print('Manager().dict - no LRU')
    manager = Manager()
    d = manager.dict()
    p = Process(target=f)
    p.start()
    p.join()

    print('redis: 1 process')
    d = redis.Redis()
    f()

    print('redis: 8 processes')
    with Pool(8) as p:
        p.starmap(f, [()]*8)
        p.close()
        p.join()

    print('memcache')
    d = base.Client('/tmp/sock')
    with Pool(8) as p:
        p.starmap(f, [()]*8)
        p.close()
        p.join()

