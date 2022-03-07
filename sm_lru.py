#from multiprocessing.managers import SharedMemoryManager
from multiprocessing.shared_memory import SharedMemory
from multiprocessing import Lock
import numpy
import marshal
import pudb
import timeit
import random

write_lock  = Lock()

class lru_shared(object):
    def __init__(self, size=4096):
        assert size>0 and (size & (size-1) == 0), "LRU size must be an exponantiel of 2"
        self.mask = size-1
        self.size = size

        self.salt = '%x' % (random.randint(0, 2**32-1),)
        self.htm = SharedMemory(size=size << 3, name="odoo_hash_"+self.salt, create=True)
        self.ht = numpy.ndarray((size,), dtype=numpy.float64, buffer=self.htm.buf)
        self.ht.fill(0)

        self.prevm = SharedMemory(size=(size+1) << 2, name="odoo_prev_"+self.salt, create=True)
        self.prev = numpy.ndarray((size+1,), dtype=numpy.int32, buffer=self.prevm.buf)
        self.prev.fill(0)

        self.nxtm = SharedMemory(size=(size+1) << 2, name="odoo_nxt_"+self.salt, create=True)
        self.nxt = numpy.ndarray((size+1,), dtype=numpy.int32, buffer=self.nxtm.buf)
        self.nxt.fill(0)

        self.data = {}      # local cache of shared memories index
        self.touch = 1

        self.root = -1
        self.length = 0

    root = property(lambda self: self.prev[-1], lambda self, x: self.prev.__setitem__(-1, x))
    length = property(lambda self: self.nxt[-1], lambda self, x: self.nxt.__setitem__(-1, x))

    def __del__(self):
        if self.root >= 0:
            node = self.root
            self.data_del(node)
            _, _, node = self.mget(node)
            while node != self.root:
                self.data_del(node)
                _, _, node = self.mget(node)

        self.htm.close()
        self.htm.unlink()
        self.prevm.close()
        self.prevm.unlink()
        self.nxtm.close()
        self.nxtm.unlink()

    def mset(self, index, key, prev, nxt):
        self.prev[index] = prev
        self.nxt[index] = nxt
        self.ht[index] = key

    def mget(self, index):
        return (self.ht[index], self.prev[index], self.nxt[index])

    def index_get(self, hash_):
        for i in range(self.size):
            yield (hash_ + i) & self.mask

    def data_del(self, index):
        name = 'odoo_sm_%s_%x' % (self.salt, index)
        mem = SharedMemory(name=name)
        mem.close()
        mem.unlink()
        if name in self.data:
            del self.data[name]

    def data_get(self, index):
        name='odoo_sm_%s_%x' % (self.salt, index)
        if name in self.data:
            mem = self.data[name]
        else:
            mem = SharedMemory(name=name)
            self.data[name] = mem
        return marshal.loads(mem.buf)

    def data_set(self, index, key, data):
        d = marshal.dumps((key, data))
        ld = len(d)
        name = 'odoo_sm_%s_%x' % (self.salt, index)
        mem = SharedMemory(create=True, name=name, size=ld)
        self.data[name] = mem
        mem.buf[:ld] = d

    def lookup(self, key_, hash_):
        for index in self.index_get(hash_):
            key, prev, nxt = self.mget(index)
            if not key:
                return (index, key, prev, nxt, None)
            if key == hash_:
                (key_full, val) = self.data_get(index)
                if key_full == key_:
                    return (index, key, prev, nxt, val)
        raise "memory full means bug"

    def __getitem__(self, key_):
        write_lock.acquire(block=False)
        index, key, prev, nxt, val = self.lookup(key_, hash(key_))
        if val is None:
            return None
        write_lock.release()
        self.touch = (self.touch + 1) & 7
        if not self.touch:   # lru touch every 8th reads: not sure about this optim?
            if write_lock.acquire(block=False):
                self.lru_touch(index, key, prev, nxt)
            write_lock.release()
        return val

    def __setitem__(self, key, value):
        hash_ = hash(key)
        write_lock.acquire()
        index, key_, prev, nxt, val = self.lookup(key, hash_)
        if val is None:
            self.length += 1
        else:
            self.data_del(index)
        self.ht[index] = hash_
        self.lru_touch(index, hash_, None, None)
        self.data_set(index, key, value)
        while self.length > (self.size >> 1):
            self.lru_pop()
        write_lock.release()

    def lru_pop(self):
        root = self.root
        if root == -1:
            return False
        _, index, _ = self.mget(root)
        self._del_index(index, *self.mget(index))

    def lru_touch(self, index, key, prev, nxt):
        root = self.root
        if root == -1:
            self.root = index
            self.mset(index, key, index, index)
            return True

        if prev is not None:
            self.prev[nxt] = prev
            self.nxt[prev] = nxt

        rprev = self.prev[root]
        self.prev[index] = rprev
        self.nxt[index] = root

        self.prev[root] = index
        self.nxt[rprev] = index
        self.root = index

    # NOTE: delete the keys that are between this element, and the next free spot, having
    #       an index lower or equal to the position we delete. (conflicts handling) or
    #       move them by 1 position left
    def _del_index(self, index, key, prev, nxt):
        if prev == index:
            self.root = None
        else:
            self.prev[nxt] = prev
            self.nxt[prev] = nxt
            if self.root == index:
                self.root = nxt
        self.data_del(index)
        self.mset(index, 0, 0, 0)
        self.length -= 1

    def __delitem__(self, key):
        hash_ = hash(key)
        index, key, prev, nxt, val = self.lookup(key, hash_)
        self._del_index(index, key, prev, nxt)

    def __str__(self):
        if self.root == -1:
            return '[]'

        node = self.root
        result = []
        while True:
            key, prev, nxt = self.mget(node)
            result.append(str(node)+': '+self.data_get(node)[1])
            node = nxt
            if node == self.root:
                return ' > '.join(result) + ', len: ' + str(self.length)


if __name__=="__main__":
    data = {"a"*20+str(i): "0123456789"*100 for i in range(10000)}
    lru = lru_shared(4)
    lru["hello"] = "Bonjour!"
    print(lru)
    lru["bye"] = "Au revoir!"
    print(lru)
    lru["hello"]
    print(lru)
    lru["I"] = "Je"
    print(lru)
    lru["you"] = "Tu"
    print(lru)
    lru["have"] = "as"
    print(lru)
    del lru
