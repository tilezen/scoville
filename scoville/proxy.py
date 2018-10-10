import http.server
import socketserver
import pkg_resources
import re
import requests
import squarify
from scoville.mvt import Tile


TILE_PATTERN = re.compile('^/tiles/([0-9]+)/([0-9]+)/([0-9]+)\.png$')


class Treemap(object):
    """
    Draws a Treemap of layer sizes within the tile.
    """

    def tiles_for(self, z, x, y):
        return {0: (z, x, y)}

    def render(self, tiles):
        from PIL import Image, ImageDraw, ImageFont

        tile = tiles[0]
        sizes = []
        for layer in tile:
            sizes.append((layer.size, layer.name))
        sizes.sort(reverse=True)

        width = height = 256
        im = Image.new("RGB", (width, height), "black")

        values = squarify.normalize_sizes([r[0] for r in sizes], width, height)
        rects = squarify.squarify(values, 0, 0, width, height)
        names = [r[1] for r in sizes]

        draw = ImageDraw.Draw(im)
        font = ImageFont.load_default()

        for rect, name in reversed(zip(rects, names)):
            # hack to get 'water' => hue(240) = blue
            hue = (name.__hash__() + 192) % 360
            colour = 'hsl(%d, 100%%, 70%%)' % (hue,)
            outline_colour = 'hsl(%d, 100%%, 30%%)' % (hue,)
            x = rect['x']
            y = rect['y']
            dx = rect['dx']
            dy = rect['dy']
            draw.rectangle([x, y, x + dx, y + dy], fill=colour,
                           outline=outline_colour)

            text_w, text_h = font.getsize(name)
            if dx > text_w and dy > text_h:
                centre = (x + dx / 2, y + dy / 2)
                top_left = (centre[0] - text_w / 2,
                            centre[1] - text_h / 2)
                draw.text(top_left, name, fill='black', font=font)

        del draw
        return im


class Heatmap(object):
    """
    Renders each tile as a heatmap.
    """

    def __init__(self, sub_zooms, max_zoom, colour_map):
        self.sub_zooms = sub_zooms
        self.max_zoom = max_zoom
        self.colour_map = colour_map

    def tiles_for(self, z, x, y):
        sub_z = min(z + self.sub_zooms, self.max_zoom)
        dz = sub_z - z
        width = 1 << dz
        tiles = {}
        for dx in xrange(0, width):
            for dy in xrange(0, width):
                tiles[(dx, dy)] = (sub_z, (x << dz) + dx, (y << dz) + dy)
        return tiles

    def render(self, tiles):
        from PIL import Image, ImageDraw

        max_coord = max(tiles.keys())
        assert max_coord[0] == max_coord[1]
        ntiles = max_coord[0] + 1
        assert len(tiles) == ntiles ** 2

        width = height = 256
        im = Image.new("RGB", (width, height), "black")

        draw = ImageDraw.Draw(im)

        scale = width / ntiles
        assert width == scale * ntiles

        for x in xrange(0, ntiles):
            for y in xrange(0, ntiles):
                size = len(tiles[(x, y)].data)
                colour = self.colour_map(size)

                draw.rectangle(
                    [x * scale, y * scale, (x+1) * scale, (y+1) * scale],
                    fill=colour)

        del draw
        return im


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html", "/style.css", "/map.js"):
            template_name = self.path[1:]
            if not template_name:
                template_name = "index.html"

            self.send_template(template_name)
            return

        m = TILE_PATTERN.match(self.path)
        if m:
            z, x, y = map(int, m.groups())

            if 0 <= z < 16 and \
               0 <= x < (1 << z) and \
               0 <= y < (1 << z):
                self.send_tile(z, x, y)
                return

        self.error_not_found()

    def error_not_found(self):
        self.send_response(requests.codes.not_found)

    def send_tile(self, z, x, y):
        from requests_futures.sessions import FuturesSession

        session = FuturesSession()

        futures = {}
        tile_map = self.server.renderer.tiles_for(z, x, y)
        for name, coord in tile_map.iteritems():
            z, x, y = coord
            url = self.server.url_pattern \
                             .replace("{z}", str(z)) \
                             .replace("{x}", str(x)) \
                             .replace("{y}", str(y))

            futures[name] = session.get(url)

        tiles = {}
        for name, fut in futures.iteritems():
            res = fut.result()

            if res.status_code != requests.codes.ok:
                self.send_response(res.status_code)
                return

            tiles[name] = Tile(res.content)

        im = self.server.renderer.render(tiles)

        self.send_response(200)
        self.send_header('Cache-control', 'max-age=300')
        self.end_headers()

        im.save(self.wfile, 'PNG')
        del im

    def send_template(self, template_name):
        from jinja2 import Template

        template = Template(pkg_resources.resource_string(
            __name__, "proxy/" + template_name))

        data = template.render(port=self.server.server_port)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)
        return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    def __init__(self, server_address, handler_class, url_pattern, renderer):
        http.server.HTTPServer.__init__(self, server_address, handler_class)
        self.url_pattern = url_pattern
        self.renderer = renderer


def serve_http(url, port, renderer):
    httpd = ThreadedHTTPServer(("", port), Handler, url, renderer)
    print("Listening on port %d. Point your browser towards "
          "http://localhost:%d/" % (port, port))
    httpd.serve_forever()
