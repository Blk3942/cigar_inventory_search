from __future__ import annotations

from typing import Any, Iterator

from cigar_inventory.config_loader import SiteConfig

from cigar_inventory.adapters import magento2_adapter
from cigar_inventory.adapters import oscommerce_adapter
from cigar_inventory.adapters import prestashop_adapter
from cigar_inventory.adapters import shopify_adapter
from cigar_inventory.adapters import woocommerce_adapter
from cigar_inventory.adapters import xtcommerce_adapter
from cigar_inventory.adapters import custom_shop_adapter


def iter_normalized_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    """
    产出与 Shopify products.json 兼容的 dict（含 title, handle, tags, product_type, variants）。
    """
    name = site.adapter.lower().strip()
    if name == "shopify":
        yield from shopify_adapter.iter_products(site)
    elif name == "woocommerce":
        yield from woocommerce_adapter.iter_products(site)
    elif name == "magento2":
        yield from magento2_adapter.iter_products(site)
    elif name == "prestashop":
        yield from prestashop_adapter.iter_products(site)
    elif name == "oscommerce":
        yield from oscommerce_adapter.iter_products(site)
    elif name == "xtcommerce":
        yield from xtcommerce_adapter.iter_products(site)
    elif name in ("custom", "custom_shop", "jimdo"):
        yield from custom_shop_adapter.iter_products(site)
    else:
        raise ValueError(f"未知 adapter: {site.adapter!r} (站点 {site.id})")
