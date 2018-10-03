import http.server
import socketserver
import pkg_resources
import re
import requests
import squarify
from scoville.mvt import Tile


TILE_PATTERN = re.compile('^/tiles/([0-9]+)/([0-9]+)/([0-9]+)\.png$')


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
                self.send_tile_breakdown(z, x, y)
                return

        self.error_not_found()

    def error_not_found(self):
        self.send_response(requests.codes.not_found)

    def send_tile_breakdown(self, z, x, y):
        url = self.server.url_pattern \
                         .replace("{z}", str(z)) \
                         .replace("{x}", str(x)) \
                         .replace("{y}", str(y))

        res = requests.get(url)
        if res.status_code != requests.codes.ok:
            self.send_response(res.status_code)
            return

        tile = Tile(res.content)
        sizes = []
        for layer in tile:
            sizes.append((layer.size, layer.name))
        sizes.sort(reverse=True)

        self.send_png(sizes)

    def send_png(self, sizes):
        from PIL import Image, ImageDraw, ImageFont

        width = height = 256

        values = squarify.normalize_sizes([r[0] for r in sizes], width, height)
        rects = squarify.squarify(values, 0, 0, width, height)
        names = [r[1] for r in sizes]

        im = Image.new("RGB", (width, height), "black")
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

        self.send_response(200)
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
    def __init__(self, server_address, handler_class, url_pattern):
        http.server.HTTPServer.__init__(self, server_address, handler_class)
        self.url_pattern = url_pattern


def serve_http(url, port):
    httpd = ThreadedHTTPServer(("", port), Handler, url)
    print("Listening on port %d. Point your browser towards "
          "http://localhost:%d/" % (port, port))
    httpd.serve_forever()
