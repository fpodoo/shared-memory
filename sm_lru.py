#from multiprocessing.managers import SharedMemoryManager
from multiprocessing.shared_memory import SharedMemory
import numpy
import marshal
import functools
from read_write_lock import RWLock


class lru_shared(object):
    def __init__(self, size=4096):
        assert size>0 and (size & (size-1) == 0), "LRU size must be an exponantiel of 2"
        self.mask = size-1
        self.size = size

        self.sm = SharedMemory(size=size << 12, create=True)
        self.sm.buf[:] = b'\x00' * (size << 12)
        data = [
            ('head', numpy.int32, (3,)), ('ht', numpy.float64, (size,)),
            ('prev', numpy.int32, (size,)), ('nxt', numpy.int32, (size,)),
            ('data_idx', numpy.uint64, (size,2)), ('data_free', numpy.uint64, (size + 9,2))
        ]
        start = 0
        for (name, dtype, sz) in data:
            end = start + dtype().nbytes * functools.reduce(lambda x,y: x*y, sz, 1)
            setattr(self, name, numpy.ndarray(sz, dtype=dtype, buffer=self.sm.buf[start:end]))
            start = end

        self.data = self.sm.buf[end: size<<12]
        self.data_free[0] = [0, (size<<12) - end]
        self.lock = RWLock()

        self.touch = 1        # used to touch the lru periodically, not 100% of the time
        self.root = -1        # stored at end of self.prev
        self.length = 0       # stored at end of self.nxt
        self.free_len = 1     # size of self.data_free

    root = property(lambda self: self.head[0], lambda self, x: self.head.__setitem__(0, x))
    length = property(lambda self: self.head[1], lambda self, x: self.head.__setitem__(1, x))
    free_len = property(lambda self: self.head[2], lambda self, x: self.head.__setitem__(2, x))

    def _malloc(self, index, data):
        data = marshal.dumps(data)
        size = len(data)
        for pos in range(self.free_len):
            if self.data_free[pos,1] >= size:
                break
        else:
            raise "no memory"

        mem_pos = int(self.data_free[pos,0])
        self.data[mem_pos:(mem_pos+size)] = data
        self.data_idx[index] = (mem_pos, size)
        self.data_free[pos, 1] -= size
        self.data_free[pos, 0] += size
        return True

    def _mprint(self):
        print('free: ', self.data_free[:self.free_len])

    def _free(self, index):
        last = self.free_len
        self.data_free[last] = self.data_idx[index]
        size = last + 1
        self.free_len = size

        if size>=self.size or not self.touch:
            # TODO: optimize this code
            mems = self.data_free[self.data_free[:size, 0].argsort()]
            pos = 0
            while pos < len(mems)-1:
                if mems[pos][0] + mems[pos][1] == mems[pos+1][0]:
                    mems[pos][1] += mems[pos+1][1]
                    mems = numpy.delete(mems, pos+1, 0)
                else:
                    pos += 1
            self.free_len = len(mems)
            mems = self.data_free[:len(mems)] = mems[mems[:, 1].argsort()[::-1]]

    def __del__(self):
        del self.head
        del self.ht
        del self.prev
        del self.nxt
        del self.data_idx
        del self.data_free
        del self.data
        self.sm.close()
        self.sm.unlink()

    def mset(self, index, key, prev, nxt):
        self.prev[index] = prev
        self.nxt[index] = nxt
        self.ht[index] = key

    def mget(self, index):
        return (self.ht[index], self.prev[index], self.nxt[index])

    def index_get(self, hash_):
        for i in range(self.size):
            yield (hash_ + i) & self.mask

    def data_get(self, index):
        return marshal.loads(self.data[self.data_idx[index,0]:])

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
        with self.lock.r_locked():
            index, key, prev, nxt, val = self.lookup(key_, hash(key_))
        if val is None:
            return None
        self.touch = (self.touch + 1) & 7
        if not self.touch:   # lru touch every 8th reads: not sure about this optim?
            with self.lock.w_locked():
                self.lru_touch(index, key, prev, nxt)
        return val

    def __setitem__(self, key, value):
        hash_ = hash(key)
        with self.lock.w_locked():
            index, key_, prev, nxt, val = self.lookup(key, hash_)
            if val is None:
                self.length += 1
            else:
                self._free(index)
            self.ht[index] = hash_
            self.lru_touch(index, hash_, None, None)
            self._malloc(index, (key, value))
            while self.length > (self.size >> 1):
                self.lru_pop()

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
        self._free(index)
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
