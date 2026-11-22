"""Single-catalog entry point used by the small quest connectivity check."""
import catalog_sources

PAGE = catalog_sources.WWW + '/forever/sitemap/quest?page='
NS = catalog_sources.NS
locations = catalog_sources.locations


def discover(fetcher, outcomes):
    return catalog_sources.discover(fetcher, outcomes, ('quest',))['quest']
