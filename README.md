Scoville - A simple little script to collect tile statistics.

Scoville generates a stream of random tile coordinates according to a given distribution and then downloads the [mapbox vector tile](https://github.com/mapbox/vector-tile-spec), recording information about the tile size, latency and contents. Aggregating this data over a long period can help decide what changes to make to tile contents, and quantify the effect of changes to the tile production.

## Install on Ubuntu:

```
sudo apt-get install libgeos-dev libcurl4-openssl-dev libpq-dev python-dev
pip install -r requirements.txt
```
