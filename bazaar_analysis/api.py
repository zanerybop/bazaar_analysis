"""Client helpers for interacting with the Hypixel bazaar API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping

BAZAAR_URL = "https://api.hypixel.net/skyblock/bazaar"


@dataclass(frozen=True)
class BazaarProduct:
    """A projection of the fields we need from the bazaar API."""

    product_id: str
    sell_price: float
    buy_price: float
    sell_volume: int
    buy_volume: int

    @property
    def spread(self) -> float:
        """Absolute price spread between instant buy and sell."""

        return self.sell_price - self.buy_price

    @property
    def popularity(self) -> int:
        """Simple popularity score based on total traded volume."""

        return self.sell_volume + self.buy_volume


class BazaarClient:
    """Small wrapper around the Hypixel bazaar REST API."""

    def __init__(self, api_url: str = BAZAAR_URL, *, timeout: int = 30) -> None:
        self.api_url = api_url
        self.timeout = timeout

    def fetch_products(self) -> Dict[str, BazaarProduct]:
        """Fetch the bazaar snapshot and return simplified product objects.

        The Hypixel API limits the request rate, so callers should cache the
        results if they need to perform multiple analyses.
        """

        request = urllib.request.Request(self.api_url, headers={"User-Agent": "bazaar-analysis/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(f"Failed to fetch bazaar data: {exc}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(f"Unable to contact bazaar API: {exc}") from exc

        products_payload = payload.get("products") or {}
        result: Dict[str, BazaarProduct] = {}
        for product_id, data in products_payload.items():
            quick_status = data.get("quick_status") or {}
            try:
                result[product_id] = BazaarProduct(
                    product_id=product_id,
                    sell_price=float(quick_status.get("sellPrice") or 0.0),
                    buy_price=float(quick_status.get("buyPrice") or 0.0),
                    sell_volume=int(quick_status.get("sellVolume") or 0),
                    buy_volume=int(quick_status.get("buyVolume") or 0),
                )
            except (TypeError, ValueError):
                # Skip malformed entries gracefully.
                continue
        return result

    def wait_for_rate_limit(self, seconds: float) -> None:
        """Helper that can be used to sleep between API calls."""

        time.sleep(seconds)


def merge_snapshots(snapshots: Iterable[Mapping[str, BazaarProduct]]) -> Dict[str, BazaarProduct]:
    """Merge multiple bazaar snapshots by averaging price and volume fields."""

    aggregate: Dict[str, BazaarProduct] = {}
    counts: Dict[str, int] = {}

    for snapshot in snapshots:
        for product_id, product in snapshot.items():
            if product_id not in aggregate:
                aggregate[product_id] = product
                counts[product_id] = 1
                continue

            count = counts[product_id] + 1
            baseline = aggregate[product_id]
            aggregate[product_id] = BazaarProduct(
                product_id=product.product_id,
                sell_price=(baseline.sell_price * counts[product_id] + product.sell_price) / count,
                buy_price=(baseline.buy_price * counts[product_id] + product.buy_price) / count,
                sell_volume=(baseline.sell_volume * counts[product_id] + product.sell_volume) // count,
                buy_volume=(baseline.buy_volume * counts[product_id] + product.buy_volume) // count,
            )
            counts[product_id] = count
    return aggregate


def load_products_from_json(raw: Mapping[str, Mapping[str, object]]) -> Dict[str, BazaarProduct]:
    """Convert a JSON blob into :class:`BazaarProduct` instances.

    This helper is primarily useful for tests or for working with cached API
    responses stored on disk.
    """

    result: Dict[str, BazaarProduct] = {}
    for product_id, data in raw.items():
        result[product_id] = BazaarProduct(
            product_id=product_id,
            sell_price=float(data.get("sell_price", 0.0)),
            buy_price=float(data.get("buy_price", 0.0)),
            sell_volume=int(data.get("sell_volume", 0)),
            buy_volume=int(data.get("buy_volume", 0)),
        )
    return result
