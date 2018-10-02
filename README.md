Scoville - A tool to attribute size information in MVT tiles.

Current scoville commands:

* `info`: Prints size and item count information about an MVT tile.

### Info command ###

Running `scoville info --kind kind foo.mvt` on a [Nextzen](https://nextzen.org) tile might output something like:

```
...
.water.features.bay.count => 2
.water.features.bay.geom_cmds => 14
.water.features.bay.metadata => 8
.water.features.bay.properties => 50
.water.features.riverbank.count => 169
.water.features.riverbank.geom_cmds => 61962
.water.features.riverbank.metadata => 774
.water.features.riverbank.properties => 3419
.water.features.water.count => 261
.water.features.water.geom_cmds => 54333
.water.features.water.metadata => 1155
.water.features.water.properties => 5770
.water.metadata => 16
.water.properties.keys.count => 40
.water.properties.size => 9184
.water.properties.values.count => 823
```

This is showing that in the `water` layer, there were 2 `kind: bay` features, totalling 14 bytes for the commands to draw their geometry, 50 bytes to represent their property indexes, and 8 bytes to represent their metadata.

Similar breakdowns are given for the other two observed `kind`s; `riverbank` and `water`.

`.water.metadata` gives the size of the metadata overhead for the `water` layer itself.

The size for property indexes is given in the kind breakdown, rather than the sum of the strings making up their key-value properties, because MVT de-duplicates property keys and values and stores them at the top level in the layer. This is given by the `.water.properties.size` entry, and counts given for the keys and values.

#### D3 output ####

The option `--d3-json` will instead output a JSON file suitable for use with [D3's treemap](https://bl.ocks.org/mbostock/4063582) visualisation. See the example code in the `examples/` directory. To get started:

```
scoville info --d3-json <YOUR FILE>.mvt > examples/treemap.json
cd examples
python -m SimpleHTTPServer
```

And visit [localhost:8000](http://localhost:8000) in a browser.

## Install on Ubuntu:

```
pip install -r requirements.txt
```
