from multiprocessing.managers import SharedMemoryManager
import marshal
import pudb
import timeit

HASHSIZE = 3         # Python hash are 64 bits = 1 << 3 bytes
HASHNONE = b'\xff' * (1 << HASHSIZE)

class lbuf(object):
    def __init__(self, buf, size, bsize, signed=False):
        self.bsize = bsize
        self.buf = buf
        self.signed = signed
        buf[:size << bsize] = b'\xff' * ((1 << bsize) * size)

    def __getitem__(self, index):
        return int.from_bytes(self.buf[index << self.bsize:(index+1) << self.bsize], 'little', signed=self.signed)

    def __setitem__(self, index, value):
        self.buf[index << self.bsize:(index+1) << self.bsize] = value.to_bytes(1 << self.bsize, 'little', signed=self.signed)
        return value

class lru_shared(object):
    def __init__(self, size=4096):
        assert size>0 and (size & (size-1) == 0), "LRU size must be an exponantiel of 2"
        self.mask = size-1
        self.size = size
        self.smm = SharedMemoryManager()
        self.smm.start()

        self.htm = self.smm.SharedMemory(size=size << HASHSIZE)
        self.ht = self.htm.buf
        self.ht[:size << HASHSIZE] = HASHNONE * size

        empty = [None] * self.size

        index_size = (size <= 65536) and 2 or 4
        self.prevm = self.smm.SharedMemory(size=size << index_size)
        self.prev = lbuf(self.prevm.buf, size, index_size)
        self.nextm = self.smm.SharedMemory(size=size << index_size)
        self.next = lbuf(self.nextm.buf, size, index_size)
        self.root = None
        self.data = empty
        self.length = 0

    def __del__(self):
        self.smm.shutdown()

    def index_get(self, hash_):
        for i in range(self.size):
            yield (hash_ + i) & self.mask

    def lookup(self, key_, hash_):
        for index in self.index_get(hash_):
            data = self.ht[index << HASHSIZE:(index+1) << HASHSIZE]
            if data == HASHNONE:
                return (index, None)
            key = int.from_bytes(data, 'little', signed=True)
            if key == hash_:
                (key, val) = marshal.loads(self.data[index])
                if key == key_:
                    return (index, val)
        raise "memory full"

    def __getitem__(self, key):
        index, val = self.lookup(key, hash(key))
        if val is None:
            return None
        self.lru_touch(index)
        return val

    def __setitem__(self, key, value):
        hash_ = hash(key)
        index, val = self.lookup(key, hash_)
        if val is None:
            self.length += 1
        self.ht[index << HASHSIZE:(index+1) << HASHSIZE] = (hash_).to_bytes(1 << HASHSIZE, 'little', signed=True)
        self.data[index] = marshal.dumps((key, value))
        self.lru_touch(index, bool(val))
        while self.length > (self.size >> 1):
            self.lru_pop()

    def lru_pop(self):
        if self.root is None:
            return False
        self._del_index( self.prev[self.root] )

    def lru_touch(self, index, exist=True):
        if self.root is None:
            self.root = index
            self.prev[index] = index
            self.next[index] = index
            return True
        if exist:
            self.next[self.prev[index]] = self.next[index]
            self.prev[self.next[index]] = self.prev[index]
        self.prev[index] = self.prev[self.root]
        self.next[index] = self.root
        self.next[self.prev[self.root]] = index
        self.prev[self.root] = index
        self.root = index

    # NOTE: for a perfect dict, we should reallocate the hash that are after this element
    #       because of a conflict, but should be before. Instead of managing that, it's
    #       less costly to drop more keys, because it's an LRU.
    def _del_index(self, index):
        prev = self.prev[index]
        after = self.next[index]
        if prev == index:
            self.root = None
        else:
            self.next[prev] = after
            self.prev[after] = prev
            if self.root == index:
                self.root = after
        self.ht[index << HASHSIZE:(index+1) << HASHSIZE] = HASHNONE
        self.length -= 1

    def __delitem__(self, key):
        hash_ = hash(key)
        index, val = self.lookup(key, hash_)
        self._del_index(index)

    def __str__(self):
        if self.root is None:
            return '[]'

        node = self.root
        result = []
        while True:
            result.append(str(node)+': '+marshal.loads(self.data[node])[1])
            node = self.next[node]
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
