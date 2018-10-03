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
    return k == u'name' or \
        k.startswith(u'name:') or \
        k in _NAME_ALTERNATES


def summarise(features, kind_key):
    sizes = {}
    for feature in features:
        props = feature.properties
        kind = props.get(kind_key)

        props_size = feature.properties_size
        geom_cmds_size = feature.geom_cmds_size
        metadata_size = feature.size - (props_size + geom_cmds_size)
        names_count = sum(1 for k in props.keys() if _is_name(k))

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
    for k, v in node.iteritems():
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

    with open(mvt_file, 'r') as fh:
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
        print(json.dumps(d3_output(sizes, name=mvt_file)))
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

    from scoville.proxy import serve_http
    serve_http(url, port)


def scoville_main():
    cli()
