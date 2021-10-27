from scoville.pbf import Message, WireType
from enum import Enum, IntEnum


class GeomType(Enum):
    """
    MVT uses an enumeration to indicate whether the commands in a geometry
    should be considered as points, linestrings or polygons. See the MVT spec
    for more information.
    """

    unknown = 0
    point = 1
    linestring = 2
    polygon = 3


class ValueTags(IntEnum):
    """
    MVT stores properties as string keys and compound value types. The value
    types are indicated by which one of the following tags are present in the
    value message.
    """

    STRING = 1
    FLOAT = 2
    DOUBLE = 3
    INT64 = 4
    UINT64 = 5
    SINT64 = 6
    BOOL = 7


def _decode_value(data):
    """
    Decode an MVT Value message, returning the Python type that represents it.
    """

    # since Value messages contain only one value, it didn't seem necessary to
    # represent it as a Python class.

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

    # the MVT spec says that there should be one and only one field in the
    # Value message, so check for that.
    if value is None:
        raise ValueError("Found no fields when decoding value")
    if count > 1:
        raise ValueError("Found multiple fields when decoding value")

    return value


class Feature(object):
    """
    A Feature is a geometry and set of key-value properties, plus an optional
    ID.

    The geometry and key-value properties are generated on-demand to reduce
    memory usage.
    """

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
        # unpack is called lazily, in case we don't need to decode this feature
        # at all (perhaps it's in a layer we're not interested in, or simply
        # want the overall size of the feature but not its details).

        self._fid = None
        self._properties = []
        self._geom_type = GeomType.unknown
        self._geom_cmds_data = []
        self._properties_size = 0
        self._geom_cmds_size = 0

        msg = Message(self.data)
        for field in msg:
            if field.tag == Feature.Tags.ID:
                self._fid = field.as_uint64()

            elif field.tag == Feature.Tags.TAGS:
                subfields = field.as_packed(WireType.varint)
                self._properties.extend(s.as_uint32() for s in subfields)
                self._properties_size += field.size

            elif field.tag == Feature.Tags.GEOM_TYPE:
                self._geom_type = GeomType(field.as_uint32())

            elif field.tag == Feature.Tags.GEOM_CMDS:
                # don't unpack this now - it's easy enough to iterate over
                # on-demand.
                self._geom_cmds_data.append(field)
                self._geom_cmds_size += field.size

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
    def properties(self):
        """
        The key-value properties of the Feature. Keys are always strings, but
        values can be any of the MVT value types (strings, integers, floats or
        bools).
        """

        if not self.unpacked:
            self.__unpack()

        # MVT encodes feature properties as a list of alternating key and
        # value indices. the keys and values themselves are deduplicated
        # in lists at the layer level (which were passed into the Feature
        # constructor).
        properties = {}
        for i in range(0, len(self._properties), 2):
            k = self.keys[self._properties[i]]
            v = self.values[self._properties[i+1]]
            properties[k] = _decode_value(v)
        return properties

    @property
    def properties_size(self):
        if not self.unpacked:
            self.__unpack()
        return self._properties_size

    @property
    def geom_cmds_size(self):
        if not self.unpacked:
            self.__unpack()
        return self._geom_cmds_size


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
    """
    TileIterator is an iterator over the layers in a tile.
    """

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
    r"""
    A tile is an iterable collection of layers in an MVT tile.

    It can be constructed from a string, buffer or memoryview and iterated
    over to yield each layer in turn.

    >>> from scoville.mvt import Tile
    >>> data = '\x1a\x2a\x0a\x07\x61\x20\x6c\x61\x79\x65\x72\x12\x0c\x12'
    >>> data += '\x02\x00\x00\x18\x01\x22\x04\x09\x00\x80\x40\x1a\x03\x6b'
    >>> data += '\x65\x79\x22\x07\x0a\x05\x76\x61\x6c\x75\x65\x28\x80\x20'
    >>> data += '\x78\x01'
    >>> t = Tile(data)
    >>> [layer.name for layer in t]
    [u'a layer']
    >>> [layer.features[0].properties for layer in t]
    [{u'key': u'value'}]
    """

    class Tags(IntEnum):
        LAYER = 3

    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return TileIterator(self.data)
