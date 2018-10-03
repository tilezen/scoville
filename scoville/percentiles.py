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
        raise IOError("Got tile response %d" % (res.status_code,))

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
    no_query = url.split('?', 1)[0]
    encoded = urlsafe_b64encode(no_query)
    assert len(encoded) < 256

    # we use a 2-level hash-based fanout to avoid having so many inodes in
    # a directory that file lookup slows to a crawl.
    hashed = sha224(no_query).hexdigest()
    dir_name = join('.cache', hashed[0:3], hashed[3:6])
    file_name = join(dir_name, encoded)

    data = None
    if isfile(file_name):
        with open(file_name, 'r') as fh:
            data = fh.read()

    else:
        data = _fetch_http(url)
        if not isdir(dir_name):
            makedirs(dir_name)
        with open(file_name, 'w') as fh:
            fh.write(data)

    return data


class Aggregator(object):
    """
    Core of the algorithm. Fetches tiles and aggregates their total and
    per-layer sizes into a set of lists.
    """

    def __init__(self, cache=False):
        self.fetch_fn = _fetch_http
        if cache:
            self.fetch_fn = _fetch_cache

        self.results = defaultdict(list)

    def add(self, tile_url):
        data = self.fetch_fn(tile_url)
        self.results['~total'].append(len(data))

        tile = Tile(data)
        for layer in tile:
            self.results[layer.name].append(layer.size)


# special object to tell worker threads to exit
class Sentinel(object):
    pass


# encode a message to be sent over the "wire" from a worker to the parent
# process. we use msgpack encoding rather than pickle, as pickle was producing
# some very large messages.
def mp_encode(data):
    from msgpack import packb
    return packb(data)


def mp_decode(data):
    from msgpack import unpackb
    return unpackb(data)


def worker(input_queue, output_queue, cache):
    """
    Worker for multi-processing. Reads tasks from a queue and feeds them into
    the Aggregator. When all tasks are done it reads a Sentinel and sends the
    aggregated result back on the output queue.
    """

    agg = Aggregator(cache)

    while True:
        obj = input_queue.get()
        if isinstance(obj, Sentinel):
            break

        assert(isinstance(obj, (str, unicode)))
        agg.add(obj)
        input_queue.task_done()

    output_queue.put(mp_encode(agg.results))


def parallel(tile_urls, cache, nprocs):
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
    for i in xrange(0, nprocs):
        w = Process(target=worker, args=(input_queue, output_queue, cache))
        w.start()
        workers.append(w)

    for tile_url in tile_urls:
        input_queue.put(tile_url)

    # join waits for all the tasks to be marked as done. this way we know that
    # enqueuing the Sentinel isn't going to "jump the queue" in front of a task
    # and mean we don't get the full result set back.
    input_queue.join()
    for i in xrange(0, nprocs):
        input_queue.put(Sentinel())

    # after we've queued the Sentinels, each worker should output an aggregated
    # result on the output queue.
    result = defaultdict(list)
    for i in xrange(0, nprocs):
        worker_result = mp_decode(output_queue.get())
        for k, v in worker_result.iteritems():
            result[k].extend(v)

    # and the worker should have exited, so we can clean up the processes.
    for w in workers:
        w.join()

    return result


def sequential(tile_urls, cache):
    agg = Aggregator(cache)
    for tile_url in tile_urls:
        agg.add(tile_url)
    return agg.results


def calculate_percentiles(tile_urls, percentiles, cache, nprocs):
    """
    Fetch tiles and calculate the percentile sizes in total and per-layer.

    Percentiles should be given as a list of decimal numbers out of 100,
    i.e: [50, 90, 99].

    Cache, if true, uses a local disk cache for the tiles. This can be very
    useful if re-running percentile calculations.

    Nprocs is the number of processes to use for both fetching and aggregation.
    Even on a system with a single CPU, it can be worth setting this to a
    larger number to make concurrent nework requests for tiles.
    """

    if nprocs > 1:
        results = parallel(tile_urls, cache, nprocs)
    else:
        results = sequential(tile_urls, cache)

    pct = {}
    for label, values in results.iteritems():
        values.sort()
        pcts = []
        for p in percentiles:
            i = int(len(values) * p / 100.0)
            pcts.append(values[i])

        pct[label] = pcts

    return pct
