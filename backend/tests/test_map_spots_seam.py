"""MAP는 spots의 ORM 모델을 직접 import하지 않는다 — cross-module read는 spots.services seam으로(#22)."""

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
    # taxonomy는 spots로 이동했다 — 옛 위치는 더 이상 존재하지 않아야 한다.
    import importlib.util

    assert importlib.util.find_spec("app.modules.map.categories") is None
