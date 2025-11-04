"""Core bazaar flip analysis logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .api import BazaarProduct
from .crafting import CraftRecipe


@dataclass(frozen=True)
class CraftProfit:
    """Result of evaluating a craft recipe against bazaar prices."""

    product_id: str
    output_amount: int
    total_sell_price: float
    total_buy_cost: float
    profit: float
    roi: float
    popularity: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "product_id": self.product_id,
            "output_amount": self.output_amount,
            "total_sell_price": self.total_sell_price,
            "total_buy_cost": self.total_buy_cost,
            "profit": self.profit,
            "roi": self.roi,
            "popularity": self.popularity,
        }


class BazaarAnalyzer:
    """Combines bazaar data with craft recipes to locate profitable flips."""

    def __init__(self, products: Dict[str, BazaarProduct]):
        self.products = products

    def evaluate_recipe(self, recipe: CraftRecipe) -> Optional[CraftProfit]:
        product = self.products.get(recipe.product_id)
        if not product:
            return None

        total_cost = 0.0
        popularity = product.popularity
        for ingredient in recipe.ingredients:
            ingredient_product = self.products.get(ingredient.product_id)
            if not ingredient_product:
                return None
            total_cost += ingredient_product.buy_price * ingredient.amount
            popularity = min(popularity, ingredient_product.popularity)

        total_sell_price = product.sell_price * recipe.output_amount
        profit = total_sell_price - total_cost
        if total_cost <= 0:
            roi = 0.0
        else:
            roi = profit / total_cost

        return CraftProfit(
            product_id=recipe.product_id,
            output_amount=recipe.output_amount,
            total_sell_price=total_sell_price,
            total_buy_cost=total_cost,
            profit=profit,
            roi=roi,
            popularity=popularity,
        )

    def rank_recipes(
        self,
        recipes: Iterable[CraftRecipe],
        *,
        min_profit: float = 0.0,
        min_popularity: int = 0,
        limit: Optional[int] = 10,
        sort_by: str = "profit",
    ) -> List[CraftProfit]:
        """Filter and rank recipes by profitability."""

        evaluated: List[CraftProfit] = []
        for recipe in recipes:
            result = self.evaluate_recipe(recipe)
            if not result:
                continue
            if result.profit < min_profit:
                continue
            if result.popularity < min_popularity:
                continue
            evaluated.append(result)

        key = {
            "profit": lambda item: item.profit,
            "roi": lambda item: item.roi,
            "popularity": lambda item: item.popularity,
        }.get(sort_by, lambda item: item.profit)

        evaluated.sort(key=key, reverse=True)
        if limit is None:
            return evaluated
        return evaluated[:limit]
