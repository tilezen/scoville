import requests
from collections import defaultdict
from scoville.mvt import Tile


def _fetch_http(url):
    """
    Fetch a tile over HTTP.
    """

    res = requests.get(url)

    # TODO: retry? better error handling!
    if res.status_code != requests.codes.ok:
        print("Got tile response %d for %s" % (res.status_code, url))
        return None

    return res.content


def _fetch_cache(url):
    """
    If a tile is present on disk, then use it. Otherwise fetch over HTTP.
    """

    from base64 import urlsafe_b64encode
    from os.path import join, isfile, isdir
    from os import makedirs
    from hashlib import sha224

    # we use the non-query part to store on disk. (tile won't depend on API
    # key, right?) partly because the API key can be very long and overflow
    # the max 255 chars for a filename when base64 encoded.
    no_query = url[0].split('?', 1)[0].encode()
    encoded = urlsafe_b64encode(no_query).decode()
    assert len(encoded) < 256

    # we use a 2-level hash-based fanout to avoid having so many inodes in
    # a directory that file lookup slows to a crawl.
    hashed = sha224(no_query).hexdigest()
    dir_name = join('.cache', hashed[0:3], hashed[3:6])
    file_name = join(dir_name, encoded)

    data = None
    if isfile(file_name):
        with open(file_name, 'rb') as fh:
            data = fh.read()

    else:
        data = _fetch_http(url)
        if data:
            if not isdir(dir_name):
                makedirs(dir_name)
            with open(file_name, 'wb') as fh:
                fh.write(data)

    return data


def fetch(url, cache=False):
    """
    Fetch a tile from url, using cache if cache=True.
    """

    if cache:
        return _fetch_cache(url)
    return _fetch_http(url)


class Aggregator(object):
    """
    Core of the algorithm. Fetches tiles and aggregates their total and
    per-layer sizes into a set of lists.
    """

    def __init__(self, cache=False):
        self.fetch_fn = _fetch_http
        if cache:
            self.fetch_fn = _fetch_cache

        self.results = {'overall': defaultdict(list)}

    def add(self, tile_blob):
        data = self.fetch_fn(tile_blob[0])
        self.results['overall']['~total'].append(len(data))

        tile = Tile(data)
        for layer in tile:
            self.results['overall'][layer.name].append(layer.size)

        zoom = str(tile_blob[1][0])
        if not zoom in self.results:
            self.results[zoom] = defaultdict(list)

        self.results[zoom]['~total'].append(len(data))
        for layer in tile:
            self.results[zoom][layer.name].append(layer.size)

    # encode a message to be sent over the "wire" from a worker to the parent
    # process. we use msgpack encoding rather than pickle, as pickle was
    # producing some very large messages.
    def encode(self):
        from msgpack import packb
        return packb(self.results)

    def merge_decode(self, data):
        from msgpack import unpackb
        results = unpackb(data)
        for key1, by_zoom_map in results.items():
            print(key1)
            print(by_zoom_map)
            if key1 not in self.results:
                self.results[key1] = defaultdict(list)

            for key2, value in by_zoom_map.items():
                self.results[key1][key2].extend(value)


class FactoryFunctionHolder(object):
    def __init__(self, factory_fn):
        self.factory_fn = factory_fn

    def create(self):
        return self.factory_fn()


class LargestN(object):
    """
    Keeps a list of the largest N tiles for each layer.
    """

    def __init__(self, num, cache=False):
        self.num = num
        self.fetch_fn = _fetch_http
        if cache:
            self.fetch_fn = _fetch_cache

        self.results = defaultdict(list)

    def _insert(self, name, size, features_size, properties_size, url):
        largest = self.results.get(name, [])
        largest.append((size, features_size, properties_size, url))
        if len(largest) > self.num:
            largest.sort(reverse=True)
            del largest[self.num:]
        self.results[name] = largest

    def add(self, tile_url):
        data = self.fetch_fn(tile_url)
        if not data:
            return
        tile = Tile(data)
        for layer in tile:
            self._insert(layer.name, layer.size, layer.features_size, layer.properties_size, tile_url[0])

    def encode(self):
        from msgpack import packb
        return packb(self.results)

    def merge_decode(self, data):
        from msgpack import unpackb
        results = unpackb(data)
        for name, values in results.items():
            for size, features_size, properties_size, url in values:
                self._insert(name, size, features_size, properties_size, url)


# special object to tell worker threads to exit
class Sentinel(object):
    pass


def worker(input_queue, output_queue, aggregator):
    """
    Worker for multi-processing. Reads tasks from a queue and feeds them into
    the Aggregator. When all tasks are done it reads a Sentinel and sends the
    aggregated result back on the output queue.
    """

    while True:
        obj = input_queue.get()
        if isinstance(obj, Sentinel):
            break

        #assert(isinstance(obj, str))
        aggregator.add(obj)
        input_queue.task_done()

    output_queue.put(aggregator.encode())


def parallel(tiles, factory, nprocs):
    """
    Fetch percentile data in parallel, using nprocs processes.

    This uses two queues; one for input to the workers and one for output from
    the workers. A pool of workers of size nprocs is started, fed with jobs
    from tile_urls, and the results are aggregated at the end and returned.
    """

    from multiprocessing import Queue, JoinableQueue, Process

    input_queue = JoinableQueue(nprocs)
    output_queue = Queue(nprocs)

    workers = []
    for i in range(0, nprocs):
        w = Process(target=worker, args=(input_queue, output_queue, factory.create()))
        w.start()
        workers.append(w)

    for tile in tiles:
        input_queue.put(tile)

    # join waits for all the tasks to be marked as done. this way we know that
    # enqueuing the Sentinel isn't going to "jump the queue" in front of a task
    # and mean we don't get the full result set back.
    input_queue.join()
    for i in range(0, nprocs):
        input_queue.put(Sentinel())

    # after we've queued the Sentinels, each worker should output an aggregated
    # result on the output queue.
    agg = factory.create()
    for i in range(0, nprocs):
        agg.merge_decode(output_queue.get())

    # and the worker should have exited, so we can clean up the processes.
    for w in workers:
        w.join()

    return agg.results


def sequential(tiles, factory_fn):
    agg = factory_fn()
    for tile in tiles:
        agg.add(tile)
    return (agg.results, agg.results_by_zoom)


def calculate_percentiles(tiles, percentiles, cache, nprocs):
    """
    Fetch tiles and calculate the percentile sizes in total and per-layer.

    Percentiles should be given as a list of decimal numbers between 0 and 100,
    i.e: [50, 90, 99].

    Cache, if true, uses a local disk cache for the tiles. This can be very
    useful if re-running percentile calculations.

    Nprocs is the number of processes to use for both fetching and aggregation.
    Even on a system with a single CPU, it can be worth setting this to a
    larger number to make concurrent nework requests for tiles.
    """

    # check that the input values are in the range we need
    for p in percentiles:
        assert 0 <= p <= 100

    def factory_fn():
        return Aggregator(cache)

    if nprocs > 1:
        results = parallel(tiles, FactoryFunctionHolder(factory_fn), nprocs)
    else:
        results = sequential(tiles, factory_fn)

    pct = {}
    for zoom, result in results.items():
        pct[zoom] = {}
        for label, values in result.items():
            values.sort()
            pcts = []
            for p in percentiles:
                i = min(len(values) - 1, int(len(values) * p / 100.0))
                pcts.append(values[i])

            pct[zoom][label] = pcts

    return pct


def calculate_outliers(tile_urls, num_outliers, cache, nprocs):
    """
    Fetch tiles and calculate the outlier tiles per layer.

    The number of outliers is per layer - the largest N.

    Cache, if true, uses a local disk cache for the tiles. This can be very
    useful if re-running percentile calculations.

    Nprocs is the number of processes to use for both fetching and aggregation.
    Even on a system with a single CPU, it can be worth setting this to a
    larger number to make concurrent nework requests for tiles.
    """

    def factory_fn():
        return LargestN(num_outliers, cache)

    if nprocs > 1:
        results = parallel(tile_urls, FactoryFunctionHolder(factory_fn), nprocs)
    else:
        results = sequential(tile_urls, factory_fn)

    return results
