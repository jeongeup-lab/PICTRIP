"""MAP must not import spots ORM models directly — cross-module reads go through the spots.services seam (#22)."""

from __future__ import annotations

import inspect

from app.modules.map import routes as map_routes
from app.modules.map import services as map_services


def test_map_services_does_not_import_spots_models() -> None:
    src = inspect.getsource(map_services)
    assert "spots.models" not in src
    assert "import Spot" not in src


def test_map_routes_does_not_import_spots_models() -> None:
    src = inspect.getsource(map_routes)
    assert "spots.models" not in src


def test_map_categories_module_is_gone() -> None:
    # taxonomy moved to spots — the old location must no longer exist.
    import importlib.util

    assert importlib.util.find_spec("app.modules.map.categories") is None
