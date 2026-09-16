"""Smoke test do app Streamlit (sem browser, via streamlit.testing)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(scope="module")
def at() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def test_primeira_tela_tem_aviso_e_achado(at):
    texto = " ".join(w.value for w in at.warning)
    assert "fila de atenção, não probabilidade" in texto
    # achado principal na primeira tela, sem escolher nada
    erro = " ".join(e.value for e in at.error)
    assert "a lista de decisão é maior que a fila de trabalho" in erro
    assert "1.291" in erro and "298" in erro
    # buraco de conta agregado, na faixa do topo
    m = next(m for m in at.metric if "sem conta" in m.label.lower())
    assert m.value == "1.425" and m.delta == "68% dos 2.089 abertos"


def test_vendedor_ve_cartoes_com_frases(at):
    at.selectbox(key="vendedor").select("Maureen Marcano").run()
    assert not at.exception, at.exception
    corpo = " ".join(m.value for m in at.markdown)
    assert "Bom dia, Maureen" in corpo
    assert "Você fecha GTX Plus Pro em 26 de 32 deals (81%)" in corpo
    assert "Última janela" in corpo
    assert "em jogo" in corpo


def test_filtro_por_produto(at):
    at.sidebar.multiselect[0].select("GTK 500").run()
    assert not at.exception, at.exception
    m = next(m for m in at.metric if "sem conta" in m.label.lower())
    assert m.delta.endswith("dos 15 abertos")  # 15 GTK 500 abertos
    at.sidebar.multiselect[0].unselect("GTK 500").run()


def test_filtro_por_regiao_reduz_escopo(at):
    at.sidebar.selectbox[0].select("West").run()
    assert not at.exception, at.exception
    labels = [m.label for m in at.metric]
    assert any("Agir" in lab for lab in labels)
    # Todos os vendedores oferecidos são da região West
    opcoes = at.selectbox(key="vendedor").options
    assert "Anna Snelling" not in opcoes and "Maureen Marcano" in opcoes
