import pycurl
import gzip
import os
from cStringIO import StringIO
from contextlib2 import contextmanager
import mapbox_vector_tile as mvt
import shapely.geometry
import psycopg2
import yaml
import time
import datetime
import uuid
import random
import traceback


@contextmanager
def fetch(stats, url):
    buf = StringIO()
    headers = {}

    def header_function(header_line):
        header_line = header_line.decode('iso-8859-1')
        if ':' not in header_line:
            return
        name, value = header_line.split(':', 1)
        name = name.strip()
        value = value.strip()
        name = name.lower()
        headers[name] = value

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buf)
    c.setopt(c.HEADERFUNCTION, header_function)
    c.setopt(c.HTTPHEADER, ["Accept-Encoding: gzip, deflate"])

    try:
        c.perform()

        status = c.getinfo(c.RESPONSE_CODE)

    except pycurl.error as e:
        # set a fake status if pycurl failed.
        status = 599

        logger = logging.getLogger('scoville')
        logger.warning("Failed to fetch tile %r: %s" %
                       (url, "".join(traceback.format_exception(
                           *sys.exc_info()))))

    stats['http_status'] = status
    tile = None

    if status == 200:
        stats['http_namelookup_time'] = c.getinfo(c.NAMELOOKUP_TIME)
        stats['http_connect_time'] = c.getinfo(c.CONNECT_TIME)
        stats['http_appconnect_time'] = c.getinfo(c.APPCONNECT_TIME)
        stats['http_pretransfer_time'] = c.getinfo(c.PRETRANSFER_TIME)
        stats['http_starttransfer_time'] = c.getinfo(c.STARTTRANSFER_TIME)
        stats['http_total_time'] = c.getinfo(c.TOTAL_TIME)

        tile = buf.getvalue()
        stats['http_bytes_received'] = len(tile)

        content_encoding = headers.get('content-encoding', 'identity')
        stats['http_content_encoding'] = content_encoding

        if content_encoding == 'gzip':
            buf.seek(0, os.SEEK_SET)
            gz = gzip.GzipFile('tile.gz', 'rb', 9, buf)
            tile = gz.read()
            stats['http_bytes_uncompressed'] = len(tile)

    yield (headers, tile)


def polygon_num_coords(p):
    count = len(p.exterior.coords)
    for inner in p.interiors:
        count += len(inner.coords)
    return count


def mk_point(geom):
    try:
        shape = shapely.geometry.Point(*geom)

    except:
        exc_class, exc, tb = sys.exc_info()
        new_exc = ValueError("When making point from geom = %r" % geom)
        raise new_exc.__class__, new_exc, tb

    return shape


def mk_linestring(geom):
    try:
        shape = shapely.geometry.LineString(geom)

    except:
        exc_class, exc, tb = sys.exc_info()
        new_exc = ValueError("When making linestring from geom = %r" % geom)
        raise new_exc.__class__, new_exc, tb

    return shape


def mk_polygon(geom):
    try:
        if len(geom) > 0 and len(geom[0]) > 0 and isinstance(geom[0][0], list):
            shape = shapely.geometry.Polygon(geom[0], geom[1:])
        else:
            shape = shapely.geometry.Polygon(geom)

    except:
        exc_class, exc, tb = sys.exc_info()
        new_exc = ValueError("When making polygon from geom = %r" % geom)
        raise new_exc.__class__, new_exc, tb

    return shape


def make_shapely_geom(feature):
    typ = feature['type']
    geom = feature['geometry']

    if len(geom) == 0:
        return shapely.geometry.GeometryCollection()

    if typ == 1:
        if len(geom) > 0 and isinstance(geom[0], list):
            parts = []
            for g in geom:
                parts.append(mk_point(g))
            shape = shapely.geometry.MultiPoint(parts)
        else:
            shape = mk_point(geom)

    elif typ == 2:
        if len(geom) > 0 and len(geom[0]) > 0 and isinstance(geom[0][0], list):
            parts = []
            for g in geom:
                parts.append(mk_linestring(g))
            shape = shapely.geometry.MultiLineString(parts)
        else:
            shape = mk_linestring(geom)

    elif typ == 3:
        if len(geom) > 0 and len(geom[0]) > 0 and isinstance(geom[0][0], list):
            parts = []
            for g in geom:
                parts.append(mk_polygon(g))
            shape = shapely.geometry.MultiPolygon(parts)
        else:
            shape = mk_polygon(geom)

    else:
        raise ValueError, "Geometry type %d not understood." % typ

    return shape


class FeatureStats(object):
    def __init__(self):
        self.num_points = 0
        self.num_lines = 0
        self.num_polygons = 0
        self.num_empty = 0

        self.num_line_coords = 0
        self.num_polygon_coords = 0

        self.line_length = 0.0
        self.polygon_area = 0.0

    def update(self, shape, props):
        geom_type = shape.geom_type

        if geom_type == 'Point' or geom_type == 'MultiPoint':
            self.num_points += 1

        elif geom_type == 'MultiLineString':
            for g in shape.geoms:
                self.num_line_coords += len(g.coords)
            self.num_lines += 1
            self.line_length += shape.length

        elif geom_type == 'LineString':
            self.num_line_coords += len(shape.coords)
            self.num_lines += 1
            self.line_length += shape.length

        elif geom_type == 'MultiPolygon':
            for g in shape.geoms:
                self.num_polygon_coords += polygon_num_coords(g)
            self.num_polygons += 1
            self.polygon_area += shape.area

        elif geom_type == 'Polygon':
            self.num_polygon_coords += polygon_num_coords(shape)
            self.num_polygons += 1
            self.polygon_area += shape.area

        elif geom_type == 'GeometryCollection':
            self.num_empty += 1

        else:
            raise ValueError, "Geometry type %r not understood." % geom_type

    def output_to(self, stats, layer_prefix):
        stats[layer_prefix + 'points'] = self.num_points
        stats[layer_prefix + 'lines'] = self.num_lines
        stats[layer_prefix + 'line_coords'] = self.num_line_coords
        stats[layer_prefix + 'line_length'] = self.line_length
        stats[layer_prefix + 'polygons'] = self.num_polygons
        stats[layer_prefix + 'polygon_coords'] = self.num_polygon_coords
        stats[layer_prefix + 'polygon_area'] = self.polygon_area
        stats[layer_prefix + 'empty'] = self.num_empty


class PropertyStats(object):
    def __init__(self):
        self.num_features = 0
        self.num_props = 0
        self.prop_bytes = 0
        self.uniq_props = dict()

    def update(self, shape, props):
        self.num_features += 1

        for k, v in props.items():
            self.num_props += 1
            self.prop_bytes += len(k) + len(v)

            if k in self.uniq_props:
                self.uniq_props[k].add(v)

            else:
                self.uniq_props[k] = set([v])

    def output_to(self, stats, layer_prefix):
        stats[layer_prefix + 'features'] = self.num_features
        stats[layer_prefix + 'num_props'] = self.num_props
        stats[layer_prefix + 'prop_bytes'] = self.prop_bytes

        uniq_num_props = 0
        uniq_prop_bytes = 0
        for k, s in self.uniq_props:
            for v in s:
                uniq_num_props += 1
                uniq_prop_bytes += len(k) + len(v)

        stats[layer_prefix + 'uniq_num_props'] = uniq_num_props
        stats[layer_prefix + 'uniq_prop_bytes'] = uniq_prop_bytes


class KindHistogram(object):
    def __init__(self):
        self.counts = {}

    def update(self, shape, props):
        kind = props.get('kind')
        if kind:
            self.counts[kind] = self.counts.get(kind, 0) + 1

    def output_to(self, stats, layer_prefix):
        stats['kinds'] = dict()
        for kind, count in self.counts.items():
            if len(kind) > 20:
                logger = logging.getLogger('scoville')
                logger.warning("Kind %r is too long, truncating." % kind)
                kind = kind[:20]
            stats['kinds'][kind] = count


class MapzenProvider(object):
    def __init__(self, hostname, api_key=None):
        self.hostname = hostname
        self.api_key = api_key

    def tile_url(self, coords):
        url = 'http://%s/osm/all/%d/%d/%d.mvt' % (self.hostname, coords[0], coords[1], coords[2])
        if self.api_key:
            url += '?api_key=%s' % self.api_key
        return url

    def stats_counters(self):
        return [FeatureStats(), PropertyStats(), KindHistogram()]

    def source(self):
        return 'mapzen'


def run_provider(provider, coords):
    stats = dict(
        coord_z=coords[0],
        coord_x=coords[1],
        coord_y=coords[2],
        source=provider.source())
    url = provider.tile_url(coords)

    with fetch(stats, url) as (headers, tile):
        if tile is None:
            return stats

        content_type = headers.get('content-type')
        if content_type:
            stats['http_content_type'] = content_type
        server_source = headers.get('server')
        if server_source:
            if len(server_source) > 20:
                logger = logging.getLogger('scoville')
                logger.warning("Truncating server_source %r" % server_source)
                server_source = server_source[:20]
            stats['http_server'] = server_source

        data = mvt.decode(tile)
        stats['layers'] = dict()

        for name, layer_data in data.items():
            features = []
            stats_counters = provider.stats_counters()

            if len(name) > 20:
                logger = logging.getLogger('scoville')
                logger.warning("Truncating layer name %r, as it is too long." %
                               name)
                name = name[:20]

            for feature in layer_data['features']:
                fid = feature['id']
                props = feature['properties']

                shape = make_shapely_geom(feature)
                for counter in stats_counters:
                    counter.update(shape, props)

                features.append(dict(geometry=shape, id=fid, properties=props))

            layer_size = len(mvt.encode(
                dict(features=features, name=name)))
            layer = dict()
            layer['bytes'] = layer_size
            for counter in stats_counters:
                counter.output_to(layer, '')
            stats['layers'][name] = layer

    return stats


class RedshiftExporter(object):
    def __init__(self, db_params):
        self.db_params = db_params
        self.conn = None

    def upload(self, stats):
        try:
            if self.conn is None:
                self.conn = psycopg2.connect(self.db_params)

            self.upload_(stats)

        except:
            self.conn = None
            exc_class, exc, tb = sys.exc_info()
            new_exc = ValueError("While uploading stats to redshift, resetting connection.")
            raise new_exc.__class__, new_exc, tb

    def upload_(self, stats):
        measurement_id = uuid.uuid4().int & ((1 << 63) - 1)

        cur = self.conn.cursor()
        cur.execute("""
INSERT INTO scoville_measurements(
  id, "timestamp", region, source, coord_z, coord_x, coord_y,
  status_code)
VALUES
  (%(measurement_id)s, %(timestamp)s, %(region)s, %(source)s, %(coord_z)s,
   %(coord_x)s, %(coord_y)s, %(status_code)s)""",
                    dict(measurement_id=measurement_id,
                         timestamp=datetime.datetime.now(),
                         region=stats['region'],
                         source=stats['source'],
                         coord_z=stats['coord_z'],
                         coord_x=stats['coord_x'],
                         coord_y=stats['coord_y'],
                         status_code=stats['http_status']
                    ))

        if stats['http_status'] == 200:
            cur.execute("""
INSERT INTO scoville_tile_info (
            measurement_id, bytes_received, bytes_uncompressed,
            content_encoding, content_type, namelookup_time_ms,
            connect_time_ms, appconnect_time_ms, pretransfer_time_ms,
            starttransfer_time_ms, total_time_ms, server_source)
VALUES (
            %(measurement_id)s, %(bytes_received)s, %(bytes_uncompressed)s,
            %(content_encoding)s, %(content_type)s, %(namelookup_time_ms)s,
            %(connect_time_ms)s, %(appconnect_time_ms)s,
            %(pretransfer_time_ms)s, %(starttransfer_time_ms)s,
            %(total_time_ms)s, %(server_source)s)""",
                        dict(measurement_id=measurement_id,
                             bytes_received=stats['http_bytes_received'],
                             bytes_uncompressed=stats.get('http_bytes_uncompressed', stats['http_bytes_received']),
                             content_encoding=stats['http_content_encoding'],
                             content_type=stats.get('http_content_type'),
                             namelookup_time_ms=int(1000 * stats['http_namelookup_time']),
                             connect_time_ms=int(1000 * stats['http_connect_time']),
                             appconnect_time_ms=int(1000 * stats['http_appconnect_time']),
                             pretransfer_time_ms=int(1000 * stats['http_pretransfer_time']),
                             starttransfer_time_ms=int(1000 * stats['http_starttransfer_time']),
                             total_time_ms=int(1000 * stats['http_total_time']),
                             server_source=stats.get('http_server')))

            for name, layer in stats['layers'].items():
                cap_line_length = min(int(100 * layer['line_length']), (1 << 31) - 1)
                cap_polygon_area = min(int(100 * layer['polygon_area']), (1 << 31) - 1)

                cur.execute("""
INSERT INTO scoville_layer_info (
  measurement_id, name, bytes, num_points, num_lines, num_polygons,
  num_empty, line_coords, polygon_coords, line_length_cpx, polygon_area_cpx)
VALUES
  (%(measurement_id)s, %(name)s, %(bytes)s, %(num_points)s, %(num_lines)s,
   %(num_polygons)s, %(num_empty)s, %(line_coords)s, %(polygon_coords)s,
   %(line_length_cpx)s, %(polygon_area_cpx)s, %(features)s, %(num_props)s,
   %(prop_bytes)s, %(uniq_num_props)s, %(uniq_prop_bytes)s)""",
                            dict(measurement_id=measurement_id,
                                 name=name,
                                 bytes=layer['bytes'],
                                 num_points=layer['points'],
                                 num_lines=layer['lines'],
                                 num_polygons=layer['polygons'],
                                 num_empty=layer['empty'],
                                 line_coords=layer['line_coords'],
                                 polygon_coords=layer['polygon_coords'],
                                 line_length_cpx=cap_line_length,
                                 polygon_area_cpx=cap_polygon_area,
                                 features=layer['features'],
                                 num_props=layer['num_props'],
                                 prop_bytes=layer['prop_bytes'],
                                 uniq_num_props=layer['uniq_num_props'],
                                 uniq_prop_bytes=layer['uniq_prop_bytes']))

                for kind, num in layer['kinds'].items():
                    cur.execute("""
INSERT INTO scoville_layer_kind_info (
  measurement_id, name, kind, "count")
VALUES (
  %(measurement_id)s, %(name)s, %(kind)s, %(count)s)""",
                                dict(
                                    measurement_id=measurement_id,
                                    name=name,
                                    kind=kind,
                                    count=num))

        cur.close()
        self.conn.commit()


class RandomTile(object):
    def __init__(self, tiles_file):
        if tiles_file.startswith('http'):
            buf = StringIO()
            c = pycurl.Curl()
            c.setopt(c.URL, tiles_file)
            c.setopt(c.WRITEDATA, buf)
            c.setopt(c.ENCODING, 'gzip')
            c.perform()

            status = c.getinfo(c.RESPONSE_CODE)
            if status != 200:
                raise RuntimeError, "Failed to get %r: HTTP status %r" % \
                    (tiles_file, status)

            data, sum = RandomTile.parse_config(buf)

        else:
            with open(tiles_file, 'r') as fh:
                data, sum = RandomTile.parse_config(fh)

        self.sum = sum
        self.data = data

    @staticmethod
    def parse_config(io):
        data = []
        sum = 0

        for line in io:
            z, x, y, num = line.split('|')
            z = int(z)
            x = int(x)
            y = int(y)
            num = int(num)

            sum += num
            data.append((z, x, y, sum))

        return data, sum

    def get_tile(self):
        idx = random.randrange(self.sum)
        for d in self.data:
            if d[3] >= idx:
                return (d[0], d[1], d[2])

        raise ValueError, "Could not find index %d with sum %d" % \
            (idx, self.sum)


if __name__ == '__main__':
    import sys
    import logging
    import logging.config

    if len(sys.argv) < 2:
        print>>sys.stderr, "Usage: python scoville/__init__.py config.yaml"
        sys.exit(1)

    config_file = sys.argv[1]
    with open(config_file) as fh:
        config = yaml.load(fh)

    logging_config = config.get('logging_config')
    if logging_config:
        logging.config.fileConfig(logging_config)

    logger = logging.getLogger('scoville')

    rs = RedshiftExporter(config['database'])
    mz = MapzenProvider(config['mapzen']['host'], config['mapzen']['api_key'])
    rand = RandomTile(config['tiles'])

    next_run = time.time()
    run_interval = int(config['run_interval'])
    tiles = config['tiles']

    while True:
        try:
            tile = rand.get_tile()
            stats = run_provider(mz, tile)
            stats['region'] = config['region']
            rs.upload(stats)

            logger.info("Fetched tile %r" % (tile,))

        except (StandardError, pycurl.error) as e:
            logger.warning("While fetching tile %r, got exception but carrying "
                           "on regardless: %s" %
                           (tile, "".join(traceback.format_exception(
                               *sys.exc_info()))))

        # python sleep can be interrupted and won't resume, so to try and make
        # sure that we sleep the full interval, we loop on it.
        next_run += run_interval
        while True:
            now = time.time()
            if now >= next_run:
                break
            time.sleep(next_run - now)
