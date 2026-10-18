"""
Testa que ComboBoxMultiplaSelecao (o combo de múltipla escolha usado pelo
filtro "Categoria/nicho" do Modo Shopee) realmente para de responder a
clique quando desabilitado via setEnabled(False).

Bug que isso cobre: o widget guarda o popup de seleção como uma janela
separada (Qt.Popup) e intercepta cliques nele via eventFilter - o
bloqueio automático de eventos que o Qt aplica a um widget desabilitado
não alcançava essa janela separada, então dava pra continuar marcando/
desmarcando itens mesmo com o campo "cinza".
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from app import ComboBoxMultiplaSelecao


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def combo(qapp):
    widget = ComboBoxMultiplaSelecao(texto_vazio="Todas as categorias")
    widget.adicionar_opcao("Moda", "moda")
    widget.adicionar_opcao("Beleza", "beleza")
    return widget


def _evento_clique(tipo):
    """QEvent de verdade (não um duplo Python) - o código de produção passa
    isso pra super().eventFilter() quando o widget está desabilitado, que
    exige um QEvent real."""
    return QMouseEvent(
        tipo,
        QPointF(5, 5),
        QPointF(5, 5),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )


class TestClickAbrePopupQuandoHabilitado:
    def test_clique_no_lineedit_abre_popup(self, combo, monkeypatch):
        chamadas = []
        monkeypatch.setattr(combo, "showPopup", lambda: chamadas.append("show"))
        monkeypatch.setattr(combo, "hidePopup", lambda: chamadas.append("hide"))
        monkeypatch.setattr(combo.view(), "isVisible", lambda: False)

        evento = _evento_clique(QEvent.MouseButtonPress)
        resultado = combo.eventFilter(combo.lineEdit(), evento)

        assert resultado is True
        assert chamadas == ["show"]

    def test_clique_no_item_marca_desmarca(self, combo, monkeypatch):
        item = combo._modelo.item(0)
        assert item.checkState() == Qt.Unchecked

        monkeypatch.setattr(combo.view(), "indexAt", lambda pos: combo._modelo.indexFromItem(item))
        sinais = []
        combo.selecaoAlterada.connect(lambda: sinais.append(True))

        evento = _evento_clique(QEvent.MouseButtonRelease)
        resultado = combo.eventFilter(combo.view().viewport(), evento)

        assert resultado is True
        assert item.checkState() == Qt.Checked
        assert sinais == [True]


class TestClickNaoFazNadaQuandoDesabilitado:
    def test_clique_no_lineedit_nao_abre_popup(self, combo, monkeypatch):
        combo.setEnabled(False)
        chamadas = []
        monkeypatch.setattr(combo, "showPopup", lambda: chamadas.append("show"))
        monkeypatch.setattr(combo, "hidePopup", lambda: chamadas.append("hide"))

        evento = _evento_clique(QEvent.MouseButtonPress)
        combo.eventFilter(combo.lineEdit(), evento)

        assert chamadas == []

    def test_clique_no_item_nao_marca_nada(self, combo, monkeypatch):
        combo.setEnabled(False)
        item = combo._modelo.item(0)
        assert item.checkState() == Qt.Unchecked

        monkeypatch.setattr(combo.view(), "indexAt", lambda pos: combo._modelo.indexFromItem(item))
        sinais = []
        combo.selecaoAlterada.connect(lambda: sinais.append(True))

        evento = _evento_clique(QEvent.MouseButtonRelease)
        combo.eventFilter(combo.view().viewport(), evento)

        assert item.checkState() == Qt.Unchecked
        assert sinais == []
