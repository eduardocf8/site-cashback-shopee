"""
Testa só a lógica de detecção/cache do tipo de origem (grupo vs canal) em
WhatsApp._abrir_origem() - não usa navegador de verdade (Playwright), só
monkeypatcha _abrir_origem_por_tipo() pra simular sucesso/falha, do mesmo
jeito que o WhatsApp Web reagiria a uma origem que é grupo ou canal.
"""

import pytest

from whatsapp import WhatsApp


@pytest.fixture
def zap():
    instancia = WhatsApp.__new__(WhatsApp)
    instancia._tipo_origem_detectado = None
    return instancia


class TestDeteccaoDeTipoDeOrigem:
    def test_detecta_grupo_quando_grupo_funciona_de_primeira(self, zap, monkeypatch):
        chamadas = []

        def fake_abrir(nome, tipo, timeout_ms=20000):
            chamadas.append(tipo)
            if tipo == "canal":
                raise AssertionError("não deveria tentar canal se grupo já funcionou")
            return True

        monkeypatch.setattr(zap, "_abrir_origem_por_tipo", fake_abrir)
        zap._abrir_origem("Grupo Ofertas")

        assert chamadas == ["grupo"]
        assert zap._tipo_origem_detectado == "grupo"

    def test_cai_para_canal_quando_grupo_nao_e_encontrado(self, zap, monkeypatch):
        chamadas = []

        def fake_abrir(nome, tipo, timeout_ms=20000):
            chamadas.append(tipo)
            if tipo == "grupo":
                raise Exception(f"Não encontrei a origem '{nome}' como grupo.")
            return True

        monkeypatch.setattr(zap, "_abrir_origem_por_tipo", fake_abrir)
        zap._abrir_origem("Canal de Ofertas")

        assert chamadas == ["grupo", "canal"]
        assert zap._tipo_origem_detectado == "canal"

    def test_propaga_erro_quando_nem_grupo_nem_canal_encontrados(self, zap, monkeypatch):
        def fake_abrir(nome, tipo, timeout_ms=20000):
            raise Exception(f"Não encontrei a origem '{nome}' como {tipo}.")

        monkeypatch.setattr(zap, "_abrir_origem_por_tipo", fake_abrir)

        with pytest.raises(Exception, match="canal"):
            zap._abrir_origem("Nome Que Não Existe")

        # Sem sucesso nenhum, não deve ter guardado nenhum tipo em cache.
        assert zap._tipo_origem_detectado is None

    def test_reaproveita_tipo_ja_detectado_sem_tentar_de_novo(self, zap, monkeypatch):
        zap._tipo_origem_detectado = "canal"
        chamadas = []

        def fake_abrir(nome, tipo, timeout_ms=20000):
            chamadas.append(tipo)
            return True

        monkeypatch.setattr(zap, "_abrir_origem_por_tipo", fake_abrir)
        zap._abrir_origem("Canal de Ofertas")

        # Já sabia que é canal - não deve tentar "grupo" primeiro de novo.
        assert chamadas == ["canal"]

    def test_reaproveita_tipo_grupo_ja_detectado(self, zap, monkeypatch):
        zap._tipo_origem_detectado = "grupo"
        chamadas = []

        def fake_abrir(nome, tipo, timeout_ms=20000):
            chamadas.append(tipo)
            return True

        monkeypatch.setattr(zap, "_abrir_origem_por_tipo", fake_abrir)
        zap._abrir_origem("Grupo Ofertas")

        assert chamadas == ["grupo"]
