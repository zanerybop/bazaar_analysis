"""Command line entry point for the bazaar analysis tool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

from .analysis import BazaarAnalyzer
from .api import BazaarClient, BazaarProduct, load_products_from_json
from .crafting import CraftRepository, HypixelRecipeClient


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hypixel bazaar crafting toolkit")
    subcommands = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subcommands.add_parser("analyze", help="Analyse crafting profitability")
    analyze_parser.add_argument("recipes", type=Path, help="Path to the recipes JSON file")
    analyze_parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of results to show",
    )
    analyze_parser.add_argument(
        "--min-profit",
        type=float,
        default=0.0,
        help="Only include crafts with at least this much profit",
    )
    analyze_parser.add_argument(
        "--min-popularity",
        type=int,
        default=0,
        help="Only include crafts that have at least this popularity score",
    )
    analyze_parser.add_argument(
        "--sort-by",
        choices=["profit", "roi", "popularity"],
        default="profit",
        help="Sort criterion",
    )
    analyze_parser.add_argument(
        "--bazaar-cache",
        type=Path,
        help="Optional path to a cached bazaar snapshot (JSON)",
    )
    analyze_parser.add_argument(
        "--dump-results",
        type=Path,
        help="If provided, dump the ranked flips to this JSON file",
    )

    fetch_parser = subcommands.add_parser(
        "fetch-recipes", help="Download recipes from the Hypixel API"
    )
    fetch_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to save the recipes JSON file",
    )
    fetch_parser.add_argument(
        "--api-key",
        type=str,
        help="Optional Hypixel API key for authorised requests",
    )
    fetch_parser.add_argument(
        "--bazaar-cache",
        type=Path,
        help="Optional path to a cached bazaar snapshot (JSON)",
    )
    fetch_parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include all recipes even if the product is not sold on the bazaar",
    )
    fetch_parser.add_argument(
        "--recipes-api-url",
        type=str,
        help="Override the primary recipes API endpoint",
    )
    fetch_parser.add_argument(
        "--recipes-fallback-url",
        action="append",
        default=None,
        help="Additional fallback URLs to try if the primary endpoint fails",
    )

    return parser.parse_args(argv)


def load_products(args: argparse.Namespace) -> dict[str, BazaarProduct]:
    if args.bazaar_cache:
        data = json.loads(args.bazaar_cache.read_text(encoding="utf-8"))
        return load_products_from_json(data)

    client = BazaarClient()
    return client.fetch_products()


def handle_analyze(args: argparse.Namespace) -> int:
    recipes = CraftRepository.from_json_file(args.recipes)
    products = load_products(args)

    analyzer = BazaarAnalyzer(products)
    results = analyzer.rank_recipes(
        recipes,
        min_profit=args.min_profit,
        min_popularity=args.min_popularity,
        limit=args.top,
        sort_by=args.sort_by,
    )

    if args.dump_results:
        args.dump_results.write_text(
            json.dumps([item.as_dict() for item in results], indent=2),
            encoding="utf-8",
        )

    for index, result in enumerate(results, start=1):
        print(
            f"{index:>2}. {result.product_id:<20} profit={result.profit:,.1f} "
            f"roi={result.roi:.2%} popularity={result.popularity:,}"
        )

    return 0


def handle_fetch_recipes(args: argparse.Namespace) -> int:
    client = HypixelRecipeClient(
        api_url=args.recipes_api_url,
        api_key=args.api_key,
        fallback_urls=args.recipes_fallback_url,
    )
    try:
        repository = client.fetch_repository()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    recipes = list(repository)

    if not args.include_all:
        products = load_products(args)
        allowed_ids = set(products.keys())
        recipes = [recipe for recipe in recipes if recipe.product_id in allowed_ids]
        repository = CraftRepository(recipes)
    else:
        repository = CraftRepository(recipes)

    if args.output.parent and not args.output.parent.exists():
        args.output.parent.mkdir(parents=True, exist_ok=True)

    args.output.write_text(
        json.dumps(repository.to_payload(), indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(repository)} recipes to {args.output}")
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "analyze":
        return handle_analyze(args)
    if args.command == "fetch-recipes":
        return handle_fetch_recipes(args)
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
