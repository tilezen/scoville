from scoville.pbf import Message, WireType
from enum import Enum


LAYER_TAG = 3


class GeomType(Enum):
    unknown = 0
    point = 1
    linestring = 2
    polygon = 3


def _decode_value(data):
    msg = Message(data)
    value = None
    count = 0

    for field in msg:
        count += 1
        if field.tag == 1:
            value = field.as_string()

        elif field.tag == 2:
            value = field.as_float()

        elif field.tag == 3:
            value = field.as_double()

        elif field.tag == 4:
            value = field.as_int64()

        elif field.tag == 5:
            value = field.as_uint64()

        elif field.tag == 6:
            value = field.as_sint64()

        elif field.tag == 7:
            value = field.as_int32() != 0

        else:
            raise ValueError("Unexpected tag %d while decoding value"
                             % (field.tag,))

    if value is None:
        raise ValueError("Found no fields when decoding value")
    if count > 1:
        raise ValueError("Found multiple fields when decoding value")

    return value


class Feature(object):

    def __init__(self, field, keys, values):
        self.keys = keys
        self.values = values
        self.data = field.as_memoryview()
        self.unpacked = False
        self.size = field.size

    def __unpack(self):
        self._fid = None
        self._tags = []
        self._geom_type = GeomType.unknown
        self._cmds_data = []
        self._tags_size = 0
        self._cmds_size = 0

        msg = Message(self.data)
        for field in msg:
            if field.tag == 1:
                self._fid = field.as_uint64()

            elif field.tag == 2:
                subfields = field.as_packed(WireType.varint)
                self._tags.extend(s.as_uint32() for s in subfields)
                self._tags_size += field.size

            elif field.tag == 3:
                self._geom_type = GeomType(field.as_uint32())

            elif field.tag == 4:
                # don't unpack this now - it's easy enough to iterate over
                # on-demand.
                self._cmds_data.append(field)
                self._cmds_size += field.size

            else:
                raise ValueError("Unknown Feature tag %d" % field.tag)

        self.unpacked = True

    @property
    def fid(self):
        if not self.unpacked:
            self.__unpack()
        return self._fid

    @property
    def geom_type(self):
        if not self.unpacked:
            self.__unpack()
        return self._geom_type

    @property
    def tags(self):
        if not self.unpacked:
            self.__unpack()
        tags = {}
        for i in xrange(0, len(self._tags), 2):
            k = self.keys[self._tags[i]]
            v = self.values[self._tags[i+1]]
            tags[k] = _decode_value(v)
        return tags

    @property
    def tags_size(self):
        if not self.unpacked:
            self.__unpack()
        return self._tags_size

    @property
    def cmds_size(self):
        if not self.unpacked:
            self.__unpack()
        return self._cmds_size


class Layer(object):
    """
    A layer is a container of features, plus some metadata.
    """

    def __init__(self, field):
        data = field.as_memoryview()

        self.version = 1
        self.name = None
        self.features = []
        self.keys = []
        self.values = []
        self.extent = 4096
        self.size = field.size
        self.features_size = 0
        self.properties_size = 0

        msg = Message(data)
        for field in msg:
            if field.tag == 15:
                self.version = field.as_uint32()

            elif field.tag == 1:
                self.name = field.as_string()

            elif field.tag == 2:
                feature = Feature(field, self.keys, self.values)
                self.features.append(feature)
                self.features_size += field.size

            elif field.tag == 3:
                self.keys.append(field.as_string())
                self.properties_size += field.size

            elif field.tag == 4:
                self.values.append(field.as_memoryview())
                self.properties_size += field.size

            elif field.tag == 5:
                self.extent = field.as_uint32()

            else:
                raise ValueError("Unknown Layer tag %d" % field.tag)

        if self.name is None:
            raise ValueError("Layer missing name, but name is required")

    def __iter__(self):
        return iter(self.features)


class TileIterator(object):

    def __init__(self, data):
        self.msg = Message(data)

    def next(self):
        field = self.msg.next()

        if field.tag != LAYER_TAG:
            raise ValueError(
                "Expecting layer with tag %d, got tag %d instead."
                % (LAYER_TAG, field.tag))

        return Layer(field)

    __next__ = next


class Tile(object):
    """
    A tile is an iterator over the layers in the tile.
    """

    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return TileIterator(self.data)
