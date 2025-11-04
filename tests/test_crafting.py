import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bazaar_analysis.crafting import (
    CraftIngredient,
    CraftRecipe,
    CraftRepository,
    HypixelRecipeClient,
)
from bazaar_analysis import cli


@contextmanager
def recipe_server(payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # pragma: no cover - quiet test server
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/recipes"
    finally:
        server.shutdown()
        thread.join()


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


def test_cli_fetch_recipes_writes_filtered_file(tmp_path, hypixel_payload):
    output = tmp_path / "exports" / "recipes.json"
    payload = {"success": True, "recipes": {"A": hypixel_payload[0], "B": hypixel_payload[1]}}

    with recipe_server(payload) as url:
        exit_code = cli.main(
            [
                "fetch-recipes",
                "--output",
                str(output),
                "--include-all",
                "--recipes-api-url",
                url,
                "--recipes-fallback-url",
                url,
            ]
        )

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


def test_hypixel_recipe_client_extracts_from_recipes_payload(monkeypatch):
    payload = {
        "recipes": {
            "ENCHANTED_CARROT": {
                "output": {"itemId": "ENCHANTED_CARROT", "amount": 1},
                "input": [
                    {"itemId": "CARROT_ITEM", "amount": 160},
                ],
            },
            "ENCHANTED_PORK": {
                "output": {"item": "ENCHANTED_PORK", "count": 1},
                "ingredients": [
                    {"item": "PORK", "count": 160},
                ],
            },
        }
    }

    client = HypixelRecipeClient()
    monkeypatch.setattr(client, "fetch_raw", lambda: payload)

    repository = client.fetch_repository()
    assert list(repository) == [
        CraftRecipe("ENCHANTED_CARROT", 1, [CraftIngredient("CARROT_ITEM", 160)]),
        CraftRecipe("ENCHANTED_PORK", 1, [CraftIngredient("PORK", 160)]),
    ]


def test_hypixel_recipe_client_uses_fallback(hypixel_payload):
    payload = {"success": True, "recipes": {"A": hypixel_payload[0], "B": hypixel_payload[1]}}

    with recipe_server(payload) as url:
        client = HypixelRecipeClient(api_url="http://127.0.0.1:1/invalid", fallback_urls=[url])
        recipes = client.fetch_recipes()

    assert recipes == [
        CraftRecipe("ENCHANTED_CARROT", 1, [CraftIngredient("CARROT_ITEM", 160)]),
        CraftRecipe("ENCHANTED_PORK", 1, [CraftIngredient("PORK", 160)]),
    ]
