from __future__ import annotations

from typing import Any, Iterator

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.shopify import iter_products as shopify_iter_products


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    yield from shopify_iter_products(site.base_url, max_pages=site.max_pages)
