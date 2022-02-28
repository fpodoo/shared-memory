from multiprocessing.managers import SharedMemoryManager
import marshal
import pudb
import timeit

HASHSIZE = 4           # hash: 8 bytes, prev: 4 bytes, next: 4 bytes = 16 bytes

class lru_shared(object):
    def __init__(self, size=4096):
        assert size>0 and (size & (size-1) == 0), "LRU size must be an exponantiel of 2"
        self.mask = size-1
        self.size = size
        self.smm = SharedMemoryManager()
        self.smm.start()

        self.htm = self.smm.SharedMemory(size=size << HASHSIZE)
        self.ht = self.htm.buf
        self.ht[:size << HASHSIZE] = b'\x00' * (size << HASHSIZE)

        self.root = None
        self.data = [None] * size
        self.length = 0

    def __del__(self):
        self.smm.shutdown()

    def mset(self, index, key, prev, nxt):
        key.to_bytes
        data = key.to_bytes(8, 'little', signed=True) + prev.to_bytes(4, 'little', signed=False) + nxt.to_bytes(4, 'little', signed=False)
        self.ht[index << HASHSIZE:(index+1) << HASHSIZE] = data

    def mget(self, index):
        data = bytes(self.ht[index << HASHSIZE:(index+1) << HASHSIZE])
        key =  int.from_bytes(data[:8], 'little', signed=True)
        prev = int.from_bytes(data[8:12], 'little', signed=False)
        nxt =  int.from_bytes(data[12:16], 'little', signed=False)
        return (key, prev, nxt)

    def index_get(self, hash_):
        for i in range(self.size):
            yield (hash_ + i) & self.mask

    def lookup(self, key_, hash_):
        for index in self.index_get(hash_):
            key, prev, nxt = self.mget(index)
            if not key:
                return (index, key, prev, nxt, None)
            if key == hash_:
                (key_full, val) = marshal.loads(self.data[index])
                if key_full == key_:
                    return (index, key, prev, nxt, val)
        raise "memory full means bug"

    def __getitem__(self, key_):
        index, key, prev, nxt, val = self.lookup(key_, hash(key_))
        if val is None:
            return None
        # self.lru_touch(index, key, prev, nxt)
        return val

    def __setitem__(self, key, value):
        hash_ = hash(key)
        index, key_, prev, nxt, val = self.lookup(key, hash_)
        if val is None:
            self.length += 1
        self.lru_touch(index, hash_, None, None)
        self.data[index] = marshal.dumps((key, value))
        while self.length > (self.size >> 1):
            self.lru_pop()

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

        if prev:
            self.ht[(nxt << HASHSIZE)+8:(nxt << HASHSIZE)+12] = prev.to_bytes(4, 'little', signed=False)
            self.ht[(prev << HASHSIZE)+12:(prev << HASHSIZE)+16] = nxt.to_bytes(4, 'little', signed=False)
        rkey, rprev, rnxt = self.mget(self.root)
        self.mset(index, key, rprev, self.root)
        bindex = index.to_bytes(4, 'little', signed=False)
        self.ht[(self.root << HASHSIZE)+8:(self.root << HASHSIZE)+12] = bindex
        self.ht[(rprev << HASHSIZE)+12:(rprev << HASHSIZE)+16] = bindex
        self.root = index

    # NOTE: for a perfect dict, we should reallocate the hash that are after this element
    #       because of a conflict, but should be before. Instead of managing that, it's
    #       less costly to drop more keys, because it's an LRU.
    def _del_index(self, index, key, prev, nxt):
        if prev == index:
            self.root = None
        else:
            self.ht[(nxt << HASHSIZE)+8:(nxt << HASHSIZE)+12] = prev.to_bytes(4, 'little', signed=False)
            self.ht[(prev << HASHSIZE)+12:(prev << HASHSIZE)+16] = nxt.to_bytes(4, 'little', signed=False)
            if self.root == index:
                self.root = nxt
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
            result.append(str(node)+': '+marshal.loads(self.data[node])[1])
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
