"""Craft recipe loading and fetching utilities."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence, Set


@dataclass(frozen=True)
class CraftIngredient:
    """Representation of an ingredient within a craft recipe."""

    product_id: str
    amount: int


@dataclass(frozen=True)
class CraftRecipe:
    """Definition of a recipe that can be crafted via bazaar items."""

    product_id: str
    output_amount: int
    ingredients: List[CraftIngredient]


class CraftRepository:
    """Loads craft recipes from JSON files."""

    def __init__(self, recipes: Iterable[CraftRecipe]):
        self._recipes = list(recipes)

    def __iter__(self):
        return iter(self._recipes)

    def __len__(self) -> int:
        return len(self._recipes)

    @classmethod
    def from_json_file(cls, path: Path) -> "CraftRepository":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(cls._parse_payload(data))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "CraftRepository":
        return cls(cls._parse_payload(data))

    @classmethod
    def from_hypixel_payload(cls, data: object) -> "CraftRepository":
        """Build a repository from the Hypixel recipes API payload."""

        return cls(list(cls._parse_hypixel_payload(data)))

    @staticmethod
    def _parse_payload(data: Mapping[str, object]) -> List[CraftRecipe]:
        recipes: List[CraftRecipe] = []
        for entry in data.get("recipes", []):
            product_id = str(entry.get("product_id"))
            if not product_id:
                continue
            output_amount = int(entry.get("output_amount", 1))
            ingredients: List[CraftIngredient] = []
            for ingredient in entry.get("ingredients", []):
                ingredient_id = ingredient.get("product_id")
                amount = ingredient.get("amount")
                if not ingredient_id or amount is None:
                    continue
                ingredients.append(CraftIngredient(str(ingredient_id), int(amount)))
            if ingredients:
                recipes.append(CraftRecipe(product_id, output_amount, ingredients))
        return recipes

    def to_payload(self) -> Dict[str, object]:
        """Return the recipes in a JSON-serialisable structure."""

        return {
            "recipes": [
                {
                    "product_id": recipe.product_id,
                    "output_amount": recipe.output_amount,
                    "ingredients": [
                        {"product_id": ingredient.product_id, "amount": ingredient.amount}
                        for ingredient in recipe.ingredients
                    ],
                }
                for recipe in self._recipes
            ]
        }

    @staticmethod
    def _parse_hypixel_payload(data: object) -> Iterator[CraftRecipe]:
        """Parse the ``/resources/skyblock/recipes`` payload into recipes.

        The Hypixel API contains a variety of recipe formats (shaped, shapeless,
        forge, etc.) with subtly different schemas.  This parser aims to
        normalise the common pieces that we need for bazaar crafting analysis and
        skips entries that do not contain the expected fields.
        """

        if isinstance(data, Mapping):
            entries = data.values()
        elif isinstance(data, Sequence):
            entries = data
        else:
            return iter(())

        recipes: List[CraftRecipe] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue

            product_id, output_amount = CraftRepository._extract_output(entry)
            if not product_id:
                continue

            ingredients = CraftRepository._extract_ingredients(entry)
            if not ingredients:
                continue

            recipes.append(CraftRecipe(product_id, output_amount, ingredients))

        return iter(recipes)

    @staticmethod
    def _extract_output(entry: Mapping[str, object]) -> tuple[str, int]:
        product_id = None
        output_amount = 1

        output_candidates = [
            entry.get("output"),
            entry.get("result"),
            entry.get("output_item"),
            entry.get("outputItem"),
        ]
        for candidate in output_candidates:
            product_id, output_amount = CraftRepository._decode_output(candidate)
            if product_id:
                break

        if not product_id:
            product_id = CraftRepository._coerce_product_id(
                entry.get("output_item_id")
                or entry.get("outputItemId")
                or entry.get("name")
                or entry.get("id")
            )
            if product_id:
                output_amount = CraftRepository._coerce_int(
                    entry.get("output_amount")
                    or entry.get("amount")
                    or entry.get("count")
                    or entry.get("quantity")
                    or 1,
                    default=1,
                )

        return product_id or "", output_amount

    @staticmethod
    def _decode_output(candidate: object) -> tuple[str, int]:
        if not isinstance(candidate, Mapping):
            if isinstance(candidate, str) and candidate:
                return candidate, 1
            return "", 1

        product_id = CraftRepository._coerce_product_id(
            candidate.get("product_id")
            or candidate.get("item_id")
            or candidate.get("itemId")
            or candidate.get("id")
            or candidate.get("item")
            or candidate.get("name")
        )
        amount = CraftRepository._coerce_int(
            candidate.get("output_amount")
            or candidate.get("amount")
            or candidate.get("count")
            or candidate.get("qty")
            or 1,
            default=1,
        )

        return product_id or "", amount

    @staticmethod
    def _extract_ingredients(entry: Mapping[str, object]) -> List[CraftIngredient]:
        containers = [
            entry.get("ingredients"),
            entry.get("input"),
            entry.get("inputs"),
            entry.get("items"),
            entry.get("materials"),
            entry.get("slots"),
            entry.get("recipe"),
            entry.get("components"),
        ]

        ingredient_amounts: Dict[str, int] = {}
        for container in containers:
            if container is None:
                continue
            for product_id, amount in CraftRepository._extract_ingredient_container(container):
                if not product_id or amount <= 0:
                    continue
                ingredient_amounts[product_id] = ingredient_amounts.get(product_id, 0) + amount

        # Some shaped recipes expose a "key" mapping and a "pattern" matrix.
        key = entry.get("key")
        pattern = entry.get("pattern")
        if isinstance(key, Mapping) and isinstance(pattern, Sequence):
            char_counts: Counter[str] = Counter()
            for row in pattern:
                if isinstance(row, str):
                    char_counts.update(ch for ch in row if ch.strip())
            for symbol, ingredient in key.items():
                if not symbol or symbol not in char_counts:
                    continue
                if not isinstance(ingredient, Mapping):
                    continue
                product_id = CraftRepository._coerce_product_id(
                    ingredient.get("product_id")
                    or ingredient.get("item_id")
                    or ingredient.get("itemId")
                    or ingredient.get("id")
                    or ingredient.get("item")
                    or ingredient.get("name")
                )
                amount = CraftRepository._coerce_int(
                    ingredient.get("amount")
                    or ingredient.get("count")
                    or ingredient.get("qty"),
                )
                if product_id and amount > 0:
                    total_amount = amount * char_counts[symbol]
                    ingredient_amounts[product_id] = ingredient_amounts.get(product_id, 0) + total_amount

        return [CraftIngredient(product_id, amount) for product_id, amount in ingredient_amounts.items()]

    @staticmethod
    def _extract_ingredient_container(container: object) -> Iterator[tuple[str, int]]:
        seen: set[int] = set()
        yield from CraftRepository._extract_ingredient_container_inner(container, seen)

    @staticmethod
    def _extract_ingredient_container_inner(
        container: object, seen: Set[int]
    ) -> Iterator[tuple[str, int]]:
        if not isinstance(container, (Mapping, Sequence)) or isinstance(container, (str, bytes)):
            return

        obj_id = id(container)
        if obj_id in seen:
            return
        seen.add(obj_id)

        if isinstance(container, Mapping):
            product_id = CraftRepository._coerce_product_id(
                container.get("product_id")
                or container.get("item_id")
                or container.get("itemId")
                or container.get("id")
                or container.get("item")
                or container.get("name")
            )
            amount = CraftRepository._coerce_int(
                container.get("amount")
                or container.get("count")
                or container.get("qty")
                or container.get("quantity")
                or container.get("value"),
            )
            if product_id and amount > 0:
                yield product_id, amount
                return

            for value in container.values():
                yield from CraftRepository._extract_ingredient_container_inner(value, seen)
            return

        # Sequence of ingredients.
        for value in container:
            yield from CraftRepository._extract_ingredient_container_inner(value, seen)

    @staticmethod
    def _coerce_product_id(value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""

    @staticmethod
    def _coerce_int(value: object, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


class HypixelRecipeClient:
    """Fetcher for Hypixel SkyBlock recipe data."""

    RECIPES_URL = "https://api.hypixel.net/resources/skyblock/collections"

    def __init__(self, api_url: str | None = None, *, timeout: int = 30, api_key: str | None = None) -> None:
        self.api_url = api_url or self.RECIPES_URL
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("HYPIXEL_API_KEY")

    def fetch_raw(self) -> Mapping[str, object]:
        """Fetch the raw collections payload from the API."""

        headers = {"User-Agent": "bazaar-analysis/1.0"}
        if self.api_key:
            headers["API-Key"] = self.api_key

        request = urllib.request.Request(self.api_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(f"Failed to fetch recipes data: {exc}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(f"Unable to contact recipes API: {exc}") from exc

        if isinstance(payload, Mapping):
            return payload
        return {"collections": payload}

    def fetch_repository(self) -> CraftRepository:
        """Fetch recipes and return them as a :class:`CraftRepository`."""

        payload = self.fetch_raw()
        collections = payload.get("collections") if isinstance(payload, Mapping) else None

        recipes: List[Mapping[str, object]] = []
        if isinstance(collections, Mapping):
            for category in collections.values():
                if not isinstance(category, Mapping):
                    continue
                for entry in category.values():
                    if not isinstance(entry, Mapping):
                        continue
                    raw_recipes = entry.get("recipes")
                    if not isinstance(raw_recipes, Sequence):
                        continue
                    for recipe in raw_recipes:
                        if isinstance(recipe, Mapping):
                            recipes.append(recipe)

        if not recipes and isinstance(payload, Mapping):
            fallback = payload.get("recipes", payload)
            if isinstance(fallback, Sequence):
                recipes.extend(entry for entry in fallback if isinstance(entry, Mapping))
            elif isinstance(fallback, Mapping):
                recipes.extend(
                    entry for entry in fallback.values() if isinstance(entry, Mapping)
                )

        return CraftRepository.from_hypixel_payload(recipes)

    def fetch_recipes(self) -> List[CraftRecipe]:
        """Fetch recipes and return them as a list."""

        return list(self.fetch_repository())
