from scoville.pbf import Message, WireType
from enum import Enum, IntEnum


class GeomType(Enum):
    unknown = 0
    point = 1
    linestring = 2
    polygon = 3


class ValueTags(IntEnum):
    STRING = 1
    FLOAT = 2
    DOUBLE = 3
    INT64 = 4
    UINT64 = 5
    SINT64 = 6
    BOOL = 7


def _decode_value(data):
    msg = Message(data)
    value = None
    count = 0

    for field in msg:
        count += 1
        if field.tag == ValueTags.STRING:
            value = field.as_string()

        elif field.tag == ValueTags.FLOAT:
            value = field.as_float()

        elif field.tag == ValueTags.DOUBLE:
            value = field.as_double()

        elif field.tag == ValueTags.INT64:
            value = field.as_int64()

        elif field.tag == ValueTags.UINT64:
            value = field.as_uint64()

        elif field.tag == ValueTags.SINT64:
            value = field.as_sint64()

        elif field.tag == ValueTags.BOOL:
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

    class Tags(IntEnum):
        ID = 1
        TAGS = 2
        GEOM_TYPE = 3
        GEOM_CMDS = 4

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
            if field.tag == Feature.Tags.ID:
                self._fid = field.as_uint64()

            elif field.tag == Feature.Tags.TAGS:
                subfields = field.as_packed(WireType.varint)
                self._tags.extend(s.as_uint32() for s in subfields)
                self._tags_size += field.size

            elif field.tag == Feature.Tags.GEOM_TYPE:
                self._geom_type = GeomType(field.as_uint32())

            elif field.tag == Feature.Tags.GEOM_CMDS:
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

    DEFAULT_VERSION = 1
    DEFAULT_EXTENT = 4096

    class Tags(IntEnum):
        VERSION = 15
        NAME = 1
        FEATURES = 2
        KEYS = 3
        VALUES = 4
        EXTENT = 5

    def __init__(self, field):
        data = field.as_memoryview()

        self.version = Layer.DEFAULT_VERSION
        self.name = None
        self.features = []
        self.keys = []
        self.values = []
        self.extent = Layer.DEFAULT_EXTENT
        self.size = field.size
        self.features_size = 0
        self.properties_size = 0

        msg = Message(data)
        for field in msg:
            if field.tag == Layer.Tags.VERSION:
                self.version = field.as_uint32()

            elif field.tag == Layer.Tags.NAME:
                self.name = field.as_string()

            elif field.tag == Layer.Tags.FEATURES:
                feature = Feature(field, self.keys, self.values)
                self.features.append(feature)
                self.features_size += field.size

            elif field.tag == Layer.Tags.KEYS:
                self.keys.append(field.as_string())
                self.properties_size += field.size

            elif field.tag == Layer.Tags.VALUES:
                self.values.append(field.as_memoryview())
                self.properties_size += field.size

            elif field.tag == Layer.Tags.EXTENT:
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

        if field.tag != Tile.Tags.LAYER:
            raise ValueError(
                "Expecting layer with tag %d, got tag %d instead."
                % (Tile.Tags.LAYER, field.tag))

        return Layer(field)

    __next__ = next


class Tile(object):
    """
    A tile is an iterator over the layers in the tile.
    """

    class Tags(IntEnum):
        LAYER = 3

    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return TileIterator(self.data)
