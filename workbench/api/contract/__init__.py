"""Camada do contrato genérico da interface (docs/planning/2026-10-27-workbench-generic-contract.md).

Cada módulo de rotas do contrato expõe `router(datasets) -> APIRouter`; `include` registra os que
já existem, para que as tarefas do plano não precisem editar `app.py`.
"""
from importlib import import_module

AXES = [("texture", "Texture"), ("brightness", "Brightness"), ("noise", "Noise")]
DATASET_LABEL = {"same anatomy": "Same anatomy", "mask only": "Mask only"}
ROUTER_MODULES = ("schema", "items", "versions", "inspect", "bench", "runs", "experiments")


def include(app, datasets: dict) -> None:
    for name in ROUTER_MODULES:
        try:
            module = import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as error:
            if error.name != f"{__name__}.{name}":
                raise
            continue
        app.include_router(module.router(datasets))
