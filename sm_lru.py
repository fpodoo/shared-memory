#from multiprocessing.managers import SharedMemoryManager
from multiprocessing.shared_memory import SharedMemory
from multiprocessing import Lock
import marshal
import pudb
import struct
import timeit
import random

HASHSIZE = 4           # hash: 8 bytes, prev: 4 bytes, next: 4 bytes = 16 bytes

write_lock  = Lock()

class lru_shared(object):
    def __init__(self, size=4096):
        assert size>0 and (size & (size-1) == 0), "LRU size must be an exponantiel of 2"
        self.mask = size-1
        self.size = size

        self.htm = SharedMemory(size=size << HASHSIZE, name="odoo_sm_cache", create=True)
        self.ht = self.htm.buf
        self.ht[:size << HASHSIZE] = b'\x00' * (size << HASHSIZE)

        self.root = None
        self.data = {}      # cache of shared memories
        self.length = 0
        self.touch = 1

    def __del__(self):
        if self.root is not None:
            node = self.root
            self.data_del(node)
            _, _, node = self.mget(node)
            while node != self.root:
                self.data_del(node)
                _, _, node = self.mget(node)

        self.htm.close()
        self.htm.unlink()

    def mset(self, index, key, prev, nxt):
        data = struct.pack('<qII', key, prev, nxt)
        self.ht[index << HASHSIZE:(index+1) << HASHSIZE] = data

    def mget(self, index):
        data = bytes(self.ht[index << HASHSIZE:(index+1) << HASHSIZE])
        return struct.unpack('<qII', data)

    def index_get(self, hash_):
        for i in range(self.size):
            yield (hash_ + i) & self.mask

    def data_del(self, index):
        name = 'odoo_sm_%x' % (index,)
        mem = SharedMemory(name=name)
        mem.close()
        mem.unlink()
        if name in self.data:
            del self.data[name]

    def data_get(self, index):
        name='odoo_sm_%x' % (index,)
        if name in self.data:
            mem = self.data[name]
        else:
            mem = SharedMemory(name=name)
            self.data[name] = mem
        return marshal.loads(mem.buf)

    def data_set(self, index, key, data):
        d = marshal.dumps((key, data))
        ld = len(d)
        name = 'odoo_sm_%x' % (index,)
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
        if not self.touch:
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
        self.lru_touch(index, hash_, None, None)
        self.data_set(index, key, value)
        while self.length > (self.size >> 1):
            self.lru_pop()
        write_lock.release()

    def lru_pop(self):
        if self.root is None:
            return False
        _, index, _ = self.mget(self.root)
        self._del_index(index, *self.mget(index))

    def lru_touch(self, index, key, prev, nxt):
        if self.root is None:
            self.root = index
            self.mset(index, key, index, index)
            return True

        if prev is not None:
            self.ht[(nxt << HASHSIZE)+8:(nxt << HASHSIZE)+12] = struct.pack('<I', prev)
            self.ht[(prev << HASHSIZE)+12:(prev << HASHSIZE)+16] = struct.pack('<I', nxt)
        rkey, rprev, rnxt = self.mget(self.root)
        self.mset(index, key, rprev, self.root)
        bindex = struct.pack('<I', index)
        self.ht[(self.root << HASHSIZE)+8:(self.root << HASHSIZE)+12] = bindex
        self.ht[(rprev << HASHSIZE)+12:(rprev << HASHSIZE)+16] = bindex
        self.root = index

    # NOTE: delete the keys that are between this element, and the next free spot, having
    #       an index lower or equal to the position we delete. (conflicts handling) or
    #       move them by 1 position left
    def _del_index(self, index, key, prev, nxt):
        if prev == index:
            self.root = None
        else:
            self.ht[(nxt << HASHSIZE)+8:(nxt << HASHSIZE)+12] = struct.pack('<I', prev)
            self.ht[(prev << HASHSIZE)+12:(prev << HASHSIZE)+16] = struct.pack('<I', nxt)
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
        if self.root is None:
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
