Scoville - A tool to attribute size information in MVT tiles.

Current scoville commands:

* `info`: Prints size and item count information about an MVT tile.
* `percentiles`: Calculate the percentile tile sizes for a set of MVT tiles.

### Info command ###

Running `scoville info --kind kind foo.mvt` on a [Nextzen](https://nextzen.org) tile might output something like:

```
...
.water.features.bay.count => 2
.water.features.bay.geom_cmds => 14
.water.features.bay.metadata => 8
.water.features.bay.names.count => 2
.water.features.bay.properties => 50
.water.features.riverbank.count => 169
.water.features.riverbank.geom_cmds => 61962
.water.features.riverbank.metadata => 774
.water.features.riverbank.names.count => 176
.water.features.riverbank.properties => 3419
.water.features.water.count => 261
.water.features.water.geom_cmds => 54333
.water.features.water.metadata => 1155
.water.features.water.names.count => 363
.water.features.water.properties => 5770
.water.metadata => 16
.water.properties.keys.count => 40
.water.properties.size => 9184
.water.properties.values.count => 823
```

This is showing that in the `water` layer, there were 2 `kind: bay` features, totalling 14 bytes for the commands to draw their geometry, 50 bytes to represent their property indexes, and 8 bytes to represent their metadata. The count, across all features, of properties that look like a name is given by the `.names.count`.

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

### Percentiles command ###

Downloads a set of tiles and calculates percentile tile sizes, both total for the tile and per-layer within the tile. This can be useful for measuring the changes in tile size across different versions of tiles, and indicating which layers are contributing the most to outlier sizes.

For example:

```
echo "0/0/0" > tiles.txt
scoville percentiles --cache tiles.txt https://tile.nextzen.org/tilezen/vector/v1/512/all/{z}/{x}/{y}.mvt?api_key=YOUR_API_KEY
```

Will output something like:

```
               TOTAL      p50      p90      p99    p99.9
          boundaries    68731    68731    68731    68731
           buildings       19       19       19       19
               earth   110378   110378   110378   110378
             landuse       17       17       17       17
              places   471086   471086   471086   471086
                pois       14       14       14       14
               roads       15       15       15       15
             transit       17       17       17       17
               water   404996   404996   404996   404996
              ~total  1055273  1055273  1055273  1055273
```

Note that the `~total` entry is **not** the total of the column above it; it's the percentile of total tile size. In other words, if we had three tiles with three layers, and each tile had a single, different layer taking up 1000 bytes and two layers taking up 10 bytes, then each tile is 1020 bytes and that would be the p50 `~total`. However, the p50 on each individual layer would only be 10 bytes.

## Install on Ubuntu:

```
pip install -r requirements.txt
```
