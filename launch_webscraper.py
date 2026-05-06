from argparse import ArgumentParser
from types import SimpleNamespace

from utils.server_registration import get_cache_server
from crawler import Crawler


def build_config():
    return SimpleNamespace(
        user_agent="IR US26 48422630, 94776730, 50586359, 93806787",
        threads_count=1,
        save_file="frontier_webscraper.shelve",
        host="styx.ics.uci.edu",
        port=9000,
        seed_urls=["https://webscraper.io/test-sites"],
        time_delay=0.5,
        cache_server=None,
    )


def main(restart):
    config = build_config()
    config.cache_server = get_cache_server(config, restart)
    crawler = Crawler(config, restart)
    crawler.start()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--restart", action="store_true", default=False)
    args = parser.parse_args()
    main(args.restart)
