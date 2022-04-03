
from multiprocessing import Process, Manager
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

    print('current: numpy + single large shared memory')
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

    print('memcache')
    d = base.Client('/tmp/sock')
    f()

