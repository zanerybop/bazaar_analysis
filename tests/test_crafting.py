from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bazaar_analysis.crafting import (
    CraftIngredient,
    CraftRecipe,
    CraftRepository,
    HypixelRecipeClient,
)
from bazaar_analysis import cli


@pytest.fixture
def hypixel_payload():
    return [
        {
            "output": {"itemId": "ENCHANTED_CARROT", "amount": 1},
            "input": [
                {"itemId": "CARROT_ITEM", "amount": 160},
            ],
        },
        {
            "output": {"item": "ENCHANTED_PORK", "count": 1},
            "ingredients": [
                {"item": "PORK", "count": 160},
            ],
        },
    ]


def test_from_hypixel_payload_parses_basic_recipes(hypixel_payload):
    repository = CraftRepository.from_hypixel_payload(hypixel_payload)
    recipes = list(repository)
    assert recipes == [
        CraftRecipe("ENCHANTED_CARROT", 1, [CraftIngredient("CARROT_ITEM", 160)]),
        CraftRecipe("ENCHANTED_PORK", 1, [CraftIngredient("PORK", 160)]),
    ]


def test_from_hypixel_payload_handles_key_pattern():
    payload = [
        {
            "output": {"itemId": "ENCHANTED_STRING", "amount": 1},
            "pattern": ["XX", " X"],
            "key": {
                "X": {"itemId": "STRING", "amount": 5},
            },
        }
    ]
    repository = CraftRepository.from_hypixel_payload(payload)
    recipes = list(repository)
    assert recipes == [
        CraftRecipe("ENCHANTED_STRING", 1, [CraftIngredient("STRING", 15)]),
    ]


def test_cli_fetch_recipes_writes_filtered_file(tmp_path, monkeypatch, hypixel_payload):
    class DummyClient:
        def fetch_repository(self):
            return CraftRepository.from_hypixel_payload(hypixel_payload)

    monkeypatch.setattr(cli, "HypixelRecipeClient", lambda api_key=None: DummyClient())

    output = tmp_path / "exports" / "recipes.json"
    # include-all to avoid touching network for bazaar data
    exit_code = cli.main(["fetch-recipes", "--output", str(output), "--include-all"])
    assert exit_code == 0

    assert output.parent.is_dir()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data == {
        "recipes": [
            {
                "product_id": "ENCHANTED_CARROT",
                "output_amount": 1,
                "ingredients": [
                    {"product_id": "CARROT_ITEM", "amount": 160},
                ],
            },
            {
                "product_id": "ENCHANTED_PORK",
                "output_amount": 1,
                "ingredients": [
                    {"product_id": "PORK", "amount": 160},
                ],
            },
        ]
    }


def test_hypixel_recipe_client_extracts_from_items_payload(monkeypatch):
    payload = {
        "items": [
            {
                "id": "ENCHANTED_CARROT",
                "recipe": {
                    "inputs": [
                        {"itemId": "CARROT_ITEM", "amount": 160},
                    ]
                },
            },
            {
                "id": "ENCHANTED_PORK",
                "recipe": [
                    {"item": "PORK", "count": 160},
                ],
            },
        ]
    }

    client = HypixelRecipeClient()
    monkeypatch.setattr(client, "fetch_raw", lambda: payload)

    repository = client.fetch_repository()
    assert list(repository) == [
        CraftRecipe("ENCHANTED_CARROT", 1, [CraftIngredient("CARROT_ITEM", 160)]),
        CraftRecipe("ENCHANTED_PORK", 1, [CraftIngredient("PORK", 160)]),
    ]
