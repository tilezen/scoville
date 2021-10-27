from enum import Enum
from struct import unpack_from


def _twoscomplement(x, bits):
    if x >= (1 << (bits - 1)):
        return x - (1 << bits)
    return x


def _zigzag(x):
    if x & 1:
        return -1 - (x >> 1)
    return x >> 1


class _Field(object):
    def __init__(self, tag):
        self.tag = tag


class _VarInt(_Field):
    def __init__(self, decoder, tag):
        _Field.__init__(self, tag)
        self.value = decoder.varint()

    def as_int32(self):
        return _twoscomplement(self.value, 32)

    def as_int64(self):
        return _twoscomplement(self.value, 64)

    def as_uint32(self):
        return self.value

    def as_uint64(self):
        return self.value

    def as_sint32(self):
        return _zigzag(self.value)

    def as_sint64(self):
        return _zigzag(self.value)


class _Bits64(_Field):
    def __init__(self, decoder, tag):
        _Field.__init__(self, tag)
        self.buf = decoder.get_bytes(8)

    def as_fixed64(self):
        return self._unpack('<Q')

    def as_sfixed64(self):
        return self._unpack('<q')

    def as_double(self):
        return self._unpack('<d')

    def _unpack(self, fmt):
        result = unpack_from(fmt, self.buf, 0)
        return result[0]


class _LengthDelimited(_Field):
    def __init__(self, decoder, tag):
        _Field.__init__(self, tag)
        self.num_bytes = decoder.varint()
        self.buf = decoder.get_bytes(self.num_bytes)

    def as_string(self):
        return self.buf.decode('utf-8')

    def as_memoryview(self):
        return self.buf

    def as_packed(self, wire_type):
        if wire_type is WireType.length_delimited:
            raise ValueError("Length delimited wire types cannot be packed.")

        return _LengthDelimited._iter(
            self.buf, self.tag, _WIRE_TYPES[wire_type])

    @staticmethod
    def _iter(buf, tag, cls):
        p = Decoder(buf)
        while p.pos < p.end:
            v = cls(p, tag)
            yield v


class _Bits32(_Field):
    def __init__(self, decoder, tag):
        _Field.__init__(self, tag)
        self.buf = decoder.get_bytes(4)

    def as_fixed32(self):
        return self._unpack('<L')

    def as_sfixed32(self):
        return self._unpack('<l')

    def as_float(self):
        return self._unpack('<f')

    def _unpack(self, fmt):
        result = unpack_from(fmt, self.buf, 0)
        return result[0]


class WireType(Enum):
    varint = 0
    bits64 = 1
    length_delimited = 2
    bits32 = 5


_WIRE_TYPES = {
    WireType.varint: _VarInt,
    WireType.bits64: _Bits64,
    WireType.length_delimited: _LengthDelimited,
    # 3 & 4 relate to groups, which we don't support
    WireType.bits32: _Bits32,
}


class Decoder(object):
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0
        self.end = len(buf)

    def varint(self):
        b = 128
        v = 0
        i = 0

        while b & 128 > 0:
            b = self.get_byte()
            v |= (b & 127) << (7 * i)
            i += 1

        return v

    def get_bytes(self, num_bytes):
        if self.pos + num_bytes > self.end:
            raise EOFError("Unexpected end of PBF data, attempting to read "
                           "%d bytes from position %d goes past end at %d"
                           % (num_bytes, self.pos, self.end))
        m = self.buf[self.pos:self.pos+num_bytes]
        self.pos += num_bytes
        return m

    def get_byte(self):
        if self.pos == self.end:
            raise EOFError("Unexpected end of PBF data at byte %d" % self.pos)

        v = self.buf[self.pos]
        self.pos += 1

        return v


class Message(object):
    def __init__(self, buf):
        self.decoder = Decoder(buf)

    def __iter__(self):
        return self

    def __next__(self):
        if self.decoder.pos >= self.decoder.end:
            raise StopIteration()

        start_pos = self.decoder.pos
        key = self.decoder.varint()
        tag = key >> 3
        typ = WireType(key & 7)

        # figure out how big the field was by comparing the position in the
        # PBF file before and after decoding it.
        field = _WIRE_TYPES[typ](self.decoder, tag)
        field.size = self.decoder.pos - start_pos

        return field

    __next__ = next
