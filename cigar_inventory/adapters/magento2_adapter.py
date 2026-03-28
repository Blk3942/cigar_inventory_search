from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Iterator

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.http_util import post_json


def _url_for(site: SiteConfig, url_key: str) -> str:
    b = site.base_url.rstrip("/")
    key = url_key.strip()
    custom = site.adapter_options.get("product_url_template")
    if isinstance(custom, str) and "{url_key}" in custom:
        return custom.replace("{url_key}", key)
    builders: dict[str, Callable[[str, str], str]] = {
        "falkum": lambda base, k: f"https://www.falkum.de/de/{k}.html",
        "selected-cigars": lambda base, k: f"https://selected-cigars.com/de/{k}",
    }
    fn = builders.get(site.id)
    if fn:
        return fn(b, key)
    return f"{b}/{key}"


def _map_item(raw: dict[str, Any], site: SiteConfig) -> dict[str, Any]:
    url_key = str(raw.get("url_key") or raw.get("sku") or "item")
    price_info = (
        (raw.get("price_range") or {})
        .get("minimum_price", {})
        .get("final_price", {})
    )
    val = price_info.get("value")
    try:
        price_s = format(Decimal(str(val)).quantize(Decimal("0.01")), "f")
    except Exception:
        price_s = "0"
    st = str(raw.get("stock_status") or "")
    available = st.upper() == "IN_STOCK"
    title = str(raw.get("name") or url_key)
    variant = {
        "id": None,
        "title": "Default Title",
        "option1": "默认",
        "option2": None,
        "option3": None,
        "sku": str(raw.get("sku") or ""),
        "price": price_s,
        "available": available,
        "inventory_quantity": None,
    }
    return {
        "title": title,
        "handle": url_key,
        "body_html": "",
        "vendor": "",
        "product_type": "Magento2",
        "tags": [],
        "variants": [variant],
        "__product_url__": _url_for(site, url_key),
    }


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    gql_path = str(site.adapter_options.get("graphql_path") or "/graphql")
    b = site.base_url.rstrip("/")
    url = f"{b}{gql_path}" if gql_path.startswith("/") else gql_path
    page_size = int(site.adapter_options.get("page_size") or 48)
    page = 1
    cap = site.max_pages if site.max_pages is not None else 35
    search = site.adapter_options.get("magento_graphql_search")
    if search:
        q = """query($ps:Int!,$p:Int!,$s:String!){
          products(search:$s, pageSize:$ps, currentPage:$p) {
            items{ sku name url_key stock_status
              price_range{ minimum_price{ final_price{ value currency } } }
            }
          }
        }"""
    else:
        q = """query($ps:Int!,$p:Int!){
          products(
            filter: { price: { from: "0", to: "99999999" } },
            pageSize: $ps,
            currentPage: $p
          ) {
            items{ sku name url_key stock_status
              price_range{ minimum_price{ final_price{ value currency } } }
            }
          }
        }"""
    while page <= cap:
        if search:
            body = {
                "query": q,
                "variables": {"ps": page_size, "p": page, "s": str(search)},
            }
        else:
            body = {"query": q, "variables": {"ps": page_size, "p": page}}
        resp = post_json(url, body, timeout=90.0)
        if resp.get("errors"):
            raise ValueError(f"Magento GraphQL: {resp.get('errors')}")
        items = (resp.get("data") or {}).get("products", {}).get("items") or []
        if not items:
            break
        for it in items:
            if isinstance(it, dict):
                yield _map_item(it, site)
        if len(items) < page_size:
            break
        page += 1
