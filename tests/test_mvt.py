from unittest import TestCase


class TestMVT(TestCase):

    def test_empty(self):
        from scoville.mvt import Tile

        t = Tile('')

        self.assertEqual(list(t), [])

    def test_encode_unicode_property(self):
        from scoville.mvt import Tile

        t = Tile('\x1a\x3a\x0a\x05\x77\x61\x74\x65\x72\x12\x14\x12\x04'
                 '\x00\x00\x01\x01\x18\x02\x22\x0a\x09\x8d\x01\xac\x3f'
                 '\x12\x00\x01\x00\x02\x1a\x03\x66\x6f\x6f\x1a\x03\x62'
                 '\x61\x7a\x22\x05\x0a\x03\x62\x61\x72\x22\x05\x0a\x03'
                 '\x66\x6f\x6f\x28\x80\x20\x78\x01')

        layers = list(t)
        self.assertEqual(len(layers), 1)
        water_layer = layers[0]
        self.assertEqual(water_layer.name, "water")
        features = list(water_layer)
        self.assertEqual(len(features), 1)
        feature = features[0]
        self.assertEqual(feature.properties, {
            u'foo': u'bar',
            u'baz': u'foo',
        })
