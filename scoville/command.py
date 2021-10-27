import click
import json
from scoville.mvt import Tile


def print_tree(node, prefix=''):
    for key in sorted(node.keys()):
        obj = node[key]
        label = '.'.join([prefix, key])
        if isinstance(obj, dict):
            print_tree(obj, label)
        else:
            click.echo('%s => %r' % (label, obj))


_NAME_ALTERNATES = (
    'int_name',
    'loc_name',
    'nat_name',
    'official_name',
    'old_name',
    'reg_name',
    'short_name',
    'name_left',
    'name_right',
)


def _is_name(k):
    # return true if the key looks like a name
    return k == 'name' or \
        k.startswith('name:') or \
        k in _NAME_ALTERNATES


def summarise(features, kind_key):
    sizes = {}
    for feature in features:
        props = feature.properties
        kind = props.get(kind_key)

        props_size = feature.properties_size
        geom_cmds_size = feature.geom_cmds_size
        metadata_size = feature.size - (props_size + geom_cmds_size)
        names_count = sum(1 for k in list(props.keys()) if _is_name(k))

        if kind not in sizes:
            sizes[kind] = dict(count=0, properties=0, geom_cmds=0, metadata=0,
                               names=dict(count=0))

        sizes[kind]['count'] += 1
        sizes[kind]['properties'] += props_size
        sizes[kind]['geom_cmds'] += geom_cmds_size
        sizes[kind]['metadata'] += metadata_size
        sizes[kind]['names']['count'] += names_count

    return sizes


def d3_output(node, name=''):
    children = []
    for k, v in list(node.items()):
        if isinstance(v, dict):
            subtree = d3_output(v, name=k)
            if subtree:
                children.append(subtree)
        elif k != 'count':
            children.append({
                'name': k,
                'size': v,
            })
    if children:
        return dict(name=name, children=children)
    else:
        return None


@click.group()
def cli():
    pass


@cli.command()
@click.argument('mvt_file', required=1)
@click.option('--kind', help='Primary property key to segment features '
              'within a layer. By default, features will not be segmented.')
@click.option('--d3-json/--no-d3-json', default=False,
              help='Output D3 JSON to use with the Treemap visualisation.')
def info(mvt_file, kind, d3_json):
    """
    Prints the detailed breakdown of bytes in MVT_FILE. If KIND is provided,
    then this property is used to further break down features into categories.

    Alternatively, set --d3-json to dump a file suitable for using in D3's
    treemap visualisation.
    """

    if mvt_file.startswith('http://') or \
       mvt_file.startswith('https://'):
        import requests

        res = requests.get(mvt_file)
        if res.status_code == 200:
            tile = Tile(res.content)
        else:
            click.echo("Failed to fetch tile, status was %r" %
                       (res.status_code,))
            return

    else:
        with open(mvt_file, 'rb') as fh:
            tile = Tile(fh.read())

    sizes = {}
    for layer in tile:
        feat_and_prop_size = layer.properties_size + layer.features_size

        layer_sizes = {}
        layer_sizes['properties'] = {
            'size': layer.properties_size,
            'keys': dict(count=len(layer.keys)),
            'values': dict(count=len(layer.values)),
        }
        layer_sizes['metadata'] = layer.size - feat_and_prop_size

        if kind is None:
            layer_sizes['features'] = layer.features_size
        else:
            layer_sizes['features'] = summarise(
                layer.features, kind)

        sizes[layer.name] = layer_sizes

    if d3_json:
        print((json.dumps(d3_output(sizes, name=mvt_file))))
    else:
        print_tree(sizes)


@cli.command()
@click.argument('url', required=1)
@click.option('--port', default=8000, help='Port to serve tiles on.')
def proxy(url, port):
    """
    Proxies vector tiles available from URL to a local server on PORT, serving
    tiles showing the breakdown of size by layer.

    URL should contain {z}, {x} and {y} replacements.
    """

    from scoville.proxy import serve_http, Treemap
    serve_http(url, port, Treemap())


def read_urls(file_name, url_pattern):
    with open(file_name, 'r') as fh:
        for line in fh:
            zxy = line.split(' ', 1)[0]
            z, x, y = list(map(int, zxy.split('/', 2)))

            u = url_pattern \
                .replace('{z}', str(z)) \
                .replace('{x}', str(x)) \
                .replace('{y}', str(y))

            yield u


def _percentiles_output_text(percentiles, result):
    """
    Output results to the console as columns of text, using ANSI colours where
    available.
    """

    fmt = '%20s' + ' %8d' * len(percentiles)
    header = '%20s' % ('TOTAL',)
    for percentile in percentiles:
        pct_header = 'p%r' % (percentile,)
        header += ' %8s' % (pct_header,)
    click.secho(header, fg='green', bold=True)
    for name in sorted(result.keys()):
        percentiles = result[name]
        line = fmt % tuple([name] + percentiles)
        click.secho(line, bold=name.startswith('~'))


def _percentiles_output_csv(percentiles, result):
    """
    Output text to the console as a CSV file.
    """

    import csv
    from sys import stdout

    writer = csv.writer(stdout)

    headers = ['Layer']
    for percentile in percentiles:
        headers.append('p%r' % (percentile,))
    writer.writerow(headers)

    for name in sorted(result.keys()):
        line = [name]
        for pct in result[name]:
            line.append(str(pct))
        writer.writerow(line)


@cli.command()
@click.argument('tiles_file', required=1)
@click.argument('url', required=1)
@click.option('--percentiles', '-p', multiple=True, type=float,
              help='Percentiles to display. Use decimal floats, i.e: 99.9, '
              'not 99_9. Can be used multiple times.')
@click.option('--cache/--no-cache', default=False, help='Use a cache for '
              'tiles. Can speed up multiple runs considerably.')
@click.option('--nprocs', '-j', default=1, type=int, help='Number of '
              'processes to use to download and do tile size aggregation.')
@click.option('--output-format', '-f', type=click.Choice(['text', 'csv']),
              default='text', help='Format to use when writing results to '
              'the console.')
def percentiles(tiles_file, url, percentiles, cache, nprocs, output_format):
    """
    Download a bunch of tiles and display the percentiles of size, breakdown by
    layer, and so forth.

    The tiles to download should be listed in TILES_FILE, one per line as
    'z/x/y'. The URL to fetch them from should contain {z}, {x} and {y}
    replacements.
    """

    from scoville.percentiles import calculate_percentiles

    if not percentiles:
        percentiles = [50, 90, 99, 99.9]

    tiles = read_urls(tiles_file, url)
    result = calculate_percentiles(tiles, percentiles, cache, nprocs)

    if output_format == 'text':
        _percentiles_output_text(percentiles, result)

    elif output_format == 'csv':
        _percentiles_output_csv(percentiles, result)

    else:
        raise ValueError('Unknown output format %r' % (output_format,))


@cli.command()
@click.argument('url', required=1)
@click.option('--port', default=8000, help='Port to serve tiles on.')
def heatmap(url, port):
    """
    Serves a heatmap of tile sizes on localhost:PORT.

    URL should contain {z}, {x} and {y} replacements.
    """

    from scoville.proxy import serve_http, Heatmap

    def colour_map(size):
        kb = size / 1024

        if kb < 6:
            return '#ffffff'
        elif kb < 12:
            return '#fff7ec'
        elif kb < 25:
            return '#fee8c8'
        elif kb < 50:
            return '#fdd49e'
        elif kb < 75:
            return '#fdbb84'
        elif kb < 125:
            return '#fc8d59'
        elif kb < 250:
            return '#ef6548'
        elif kb < 500:
            return '#d7301f'
        elif kb < 750:
            return '#990000'
        else:
            return '#000000'

    heatmap = Heatmap(3, 16, colour_map)
    serve_http(url, port, heatmap)


@cli.command()
@click.argument('tiles_file', required=1)
@click.argument('url', required=1)
@click.option('--cache/--no-cache', default=False, help='Use a cache for '
              'tiles. Can speed up multiple runs considerably.')
@click.option('--nprocs', '-j', default=1, type=int, help='Number of '
              'processes to use to download and do tile size aggregation.')
@click.option('--num-outliers-per-layer', '-n', type=int, default=3,
              help='Number of outliers for each layer to report on.')
def outliers(tiles_file, url, cache, nprocs, num_outliers_per_layer):
    """
    From the distribution of tile coordinates given in TILES_FILE and fetched
    from the URL pattern, pull out some of the outlier tiles which have the
    largest sizes in each layer.
    """

    from scoville.percentiles import calculate_outliers

    tiles = read_urls(tiles_file, url)
    result = calculate_outliers(tiles, num_outliers_per_layer, cache, nprocs)

    for name in sorted(result.keys()):
        click.secho("Layer %r" % name, fg='green', bold=True)
        for size, url in sorted(result[name]):
            click.echo("%8d %s" % (size, url))


def scoville_main():
    cli()


if __name__ == '__main__':
    scoville_main()
