from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bazaar_analysis.analysis import BazaarAnalyzer
from bazaar_analysis.api import BazaarProduct
from bazaar_analysis.crafting import CraftIngredient, CraftRecipe


def build_product(product_id: str, *, sell_price: float, buy_price: float, sell_volume: int, buy_volume: int) -> BazaarProduct:
    return BazaarProduct(
        product_id=product_id,
        sell_price=sell_price,
        buy_price=buy_price,
        sell_volume=sell_volume,
        buy_volume=buy_volume,
    )


def test_rank_recipes_filters_and_sorts():
    products = {
        "A": build_product("A", sell_price=600, buy_price=90, sell_volume=1000, buy_volume=900),
        "B": build_product("B", sell_price=500, buy_price=400, sell_volume=2000, buy_volume=1500),
        "C": build_product("C", sell_price=250, buy_price=100, sell_volume=1000, buy_volume=1000),
    }
    analyzer = BazaarAnalyzer(products)
    recipes = [
        CraftRecipe("A", 1, [CraftIngredient("B", 1)]),
        CraftRecipe("C", 1, [CraftIngredient("A", 1)]),
        CraftRecipe("B", 1, [CraftIngredient("C", 1)]),
    ]

    ranked = analyzer.rank_recipes(recipes, min_profit=0, min_popularity=500, limit=2)

    assert [item.product_id for item in ranked] == ["B", "A"]
    profits = {item.product_id: item.profit for item in ranked}
    assert profits["B"] == 400
    assert profits["A"] == 200


def test_evaluate_recipe_handles_missing_data():
    products = {"A": build_product("A", sell_price=100, buy_price=90, sell_volume=100, buy_volume=100)}
    analyzer = BazaarAnalyzer(products)

    missing_product = CraftRecipe("B", 1, [CraftIngredient("A", 1)])
    missing_ingredient = CraftRecipe("A", 1, [CraftIngredient("B", 1)])

    assert analyzer.evaluate_recipe(missing_product) is None
    assert analyzer.evaluate_recipe(missing_ingredient) is None
