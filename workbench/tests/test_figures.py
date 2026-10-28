"""Figuras do framework desenhadas pelos inspetores de imagem: subconjunto de versões, figura de NPS/ar e o
dataset Dgen. As rotas `/api/inspect/{key}.png` estão em test_inspect.py; aqui ficam os desenhos de `board`.

Só leitura do histórico real de outputs/placar; o histórico do Dgen é uma cópia temporária.
"""
import io

import pytest
from fastapi import HTTPException
from PIL import Image

from frameworks.texture_evaluator.placar import load_history
from workbench.api import board, datasets as ds
from workbench.api.data import NotFound
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, workbench_of

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def real_names():
    return [item["name"] for item in load_history(HISTORY_DIR)["versions"]]


def width(content: bytes) -> int:
    assert content[:8] == PNG_MAGIC
    return Image.open(io.BytesIO(content)).size[0]


def test_technique_versions_subset_is_honoured():
    wb, names = workbench_of(), real_names()
    full = width(board.technique_png(wb, CID, "delta_mu", names))
    one = width(board.technique_png(wb, CID, "delta_mu", names[:1]))
    two = width(board.technique_png(wb, CID, "delta_mu", names[:2]))
    # cada versão a mais é uma coluna a mais: a figura cresce com a seleção
    assert one < two < full


def test_map_versions_subset_is_honoured():
    wb, names = workbench_of(), real_names()
    full = width(board.map_png(wb, CID, "fina", True, names))
    one = width(board.map_png(wb, CID, "fina", True, names[:1]))
    assert one < full


def test_nps_versions_unknown_is_not_found():
    with pytest.raises(NotFound):
        board.nps_png(workbench_of(), CID, ["Dsr", "bogus"])


def test_nps_figure_real_case_png():
    assert width(board.nps_png(workbench_of(), CID, [])) >= 200


def test_nps_figure_explicit_versions():
    wb, names = workbench_of(), real_names()
    assert width(board.nps_png(wb, CID, [names[0], names[-1]])) >= 200
    assert width(board.nps_png(wb, CID, [names[-1]])) >= 200


def test_nps_figure_rejects_more_than_two_versions():
    names = real_names()
    if len(names) < 3:
        pytest.skip("precisa de três versões no histórico real")
    with pytest.raises(HTTPException) as error:
        board.nps_png(workbench_of(), CID, names[:3])
    assert error.value.status_code == 400


def test_nps_figure_unknown_case_is_not_found():
    with pytest.raises(NotFound):
        board.nps_png(workbench_of(), "nope", [])


def test_figures_dgen_dataset_path(tmp_history):
    """Dgen com histórico próprio: as três figuras saem do histórico do dataset pedido."""
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": HISTORY_DIR},
                "Dgen": {**ds.DATASETS["Dgen"], "history": tmp_history}}
    wb = workbench_of(datasets, "Dgen")
    assert width(board.technique_png(wb, CID, "delta_mu", ["Dsr"])) > 0
    assert width(board.map_png(wb, CID, "fina", True, ["Dsr"])) > 0
    assert width(board.nps_png(wb, CID, ["Dsr"])) > 0


def test_figures_dgen_without_history_is_not_found(tmp_path):
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": HISTORY_DIR},
                "Dgen": {**ds.DATASETS["Dgen"], "history": tmp_path / "placar_dgen"}}
    with pytest.raises(NotFound):
        workbench_of(datasets, "Dgen")


def test_nps_figure_unloadable_case_is_404(monkeypatch):
    from frameworks.texture_evaluator.placar import PlacarError
    from workbench.api import nps_figure

    def broken(entry, case_id):
        raise PlacarError("arquivo corrompido")

    monkeypatch.setattr(nps_figure, "load_case", broken)
    with pytest.raises(HTTPException) as error:
        board.nps_png(workbench_of(), CID, [])
    assert error.value.status_code == 404 and error.value.detail == f"slice could not be loaded: {CID}"


def test_nps_figure_closes_figure_on_any_error(monkeypatch):
    import matplotlib.pyplot as plt
    from workbench.api import nps_figure

    names = real_names()
    history = load_history(HISTORY_DIR)

    def boom(*args, **kwargs):
        raise RuntimeError("falha no desenho")

    monkeypatch.setattr(nps_figure.plt, "Rectangle", boom)
    before = set(plt.get_fignums())
    with pytest.raises(RuntimeError):
        nps_figure.nps_case_png(history, CID, names[0], names[-1])
    assert set(plt.get_fignums()) == before
