import sys
import logging
import logging.config
import time
import pycurl
import yaml
import os.path
import traceback
from scoville import RedshiftExporter, MapzenProvider, MapboxProvider, \
    RandomTile, run_provider


def scoville_main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 1:
        print>>sys.stderr, "Usage: scoville config.yaml"
        sys.exit(1)

    config_file = argv[0]
    with open(config_file) as fh:
        config = yaml.load(fh)

    logging_config = config.get('logging_config')
    if logging_config:
        config_dir = os.path.dirname(config_file)
        logging.config.fileConfig(os.path.join(config_dir, logging_config))

    logger = logging.getLogger('scoville')

    rs = RedshiftExporter(config['database'])
    providers = []

    mz_conf = config.get('mapzen')
    if mz_conf:
        mz = MapzenProvider(mz_conf['host'], mz_conf.get('api_key'),
                            mz_conf.get('old_tile_format'))
        providers.append(mz)

    mb_conf = config.get('mapbox')
    if mb_conf:
        mb = MapboxProvider(mb_conf['style'], mb_conf['api_key'])
        providers.append(mb)

    rand = RandomTile(config['tiles'])

    next_run = time.time()
    run_interval = int(config['run_interval'])
    tiles = config['tiles']

    while True:
        try:
            tile = rand.get_tile()
            for p in providers:
                stats = run_provider(p, tile)
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
