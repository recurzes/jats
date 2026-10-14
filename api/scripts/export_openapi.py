"""Write the API's OpenAPI document to contracts/openapi.json, which the web app generates its
types from. Run from api/ after changing a route or a response model:

    python -m scripts.export_openapi

A test fails while the committed file is out of date.
"""

import json
from pathlib import Path

from app.main import app

CONTRACT = Path(__file__).resolve().parent.parent.parent / "contracts" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2) + "\n"


def main() -> None:
    CONTRACT.parent.mkdir(exist_ok=True)
    CONTRACT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"Wrote {CONTRACT}")


if __name__ == "__main__":
    main()
