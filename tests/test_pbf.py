import unittest


class PBFTest(unittest.TestCase):

    def test_int32(self):
        from scoville.pbf import Message, _VarInt

        msg = '\x08\x96\x01'
        p = Message(msg)

        field = p.next()
        self.assertEqual(field.tag, 1)
        self.assertIsInstance(field, _VarInt)

        val = field.as_uint32()
        self.assertEqual(val, 150)

    def test_string(self):
        from scoville.pbf import Message, _LengthDelimited

        msg = '\x12\x07\x74\x65\x73\x74\x69\x6e\x67'
        p = Message(msg)

        field = p.next()
        self.assertEqual(field.tag, 2)
        self.assertIsInstance(field, _LengthDelimited)

        val = field.as_string()
        self.assertEqual(val, 'testing')

    def test_packed_int(self):
        from scoville.pbf import Message, _LengthDelimited, WireType

        msg = '\x22\x06\x03\x8e\x02\x9e\xa7\x05'
        p = Message(msg)

        field = p.next()
        self.assertEqual(field.tag, 4)
        self.assertIsInstance(field, _LengthDelimited)

        packed_fields = list(field.as_packed(WireType.varint))
        values = [f.as_uint32() for f in packed_fields]
        self.assertEqual(values, [3, 270, 86942])

    def test_zigzag_int(self):
        from scoville.pbf import Message

        msg = '\x08\x03'
        p = Message(msg)

        fields = list(p)
        val = fields[0].as_sint32()
        self.assertEqual(val, -2)

    def test_zigzag(self):
        from scoville.pbf import _zigzag

        def expect(original, encoded):
            decoded = _zigzag(encoded)
            self.assertEqual(original, decoded)

        expect(0, 0)
        expect(-1, 1)
        expect(1, 2)
        expect(-2, 3)
        expect(2147483647, 4294967294)
        expect(-2147483648, 4294967295)

    def test_twoscomplement(self):
        from scoville.pbf import _twoscomplement

        def expect(original, encoded, bits):
            decoded = _twoscomplement(encoded, bits)
            self.assertEqual(original, decoded)

        expect(0, 0, 32)
        expect(1, 1, 32)
        expect(2, 2, 32)
        expect(-1, 4294967295, 32)
        expect(-2, 4294967294, 32)

    def test_double(self):
        from scoville.pbf import Message, _Bits64
        from math import pi

        msg = '\x09\x18\x2d\x44\x54\xfb\x21\x09\x40'
        p = Message(msg)

        field = p.next()
        self.assertEqual(field.tag, 1)
        self.assertIsInstance(field, _Bits64)

        val = field.as_double()
        self.assertAlmostEqual(val, pi)

    def test_float(self):
        from scoville.pbf import Message, _Bits32
        from math import pi

        msg = '\x0d\xdb\x0f\x49\x40'
        p = Message(msg)

        field = p.next()
        self.assertEqual(field.tag, 1)
        self.assertIsInstance(field, _Bits32)

        val = field.as_float()
        self.assertAlmostEqual(val, pi, 5)
