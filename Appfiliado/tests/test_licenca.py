import json

import licenca


class _Resposta:
    def __init__(self, dados):
        self._corpo = json.dumps(dados).encode("utf-8")

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _servidor(monkeypatch, dados):
    monkeypatch.setattr(licenca.urllib.request, "urlopen", lambda *a, **k: _Resposta(dados))


def _sem_internet(monkeypatch):
    def falha(*a, **k):
        raise licenca.urllib.error.URLError("sem rede")
    monkeypatch.setattr(licenca.urllib.request, "urlopen", falha)


def test_servidor_novo_devolve_modulos(monkeypatch, tmp_path):
    _servidor(monkeypatch, {"valido": True, "conta_ativa": True, "modulos": ["whatsapp", "site"], "plano": "Mensal"})
    liberado, _, detalhes = licenca.verificar_licenca("AF-1", "https://x", tmp_path / "estado.json")
    assert liberado
    assert detalhes["modulos"] == ["whatsapp", "site"]


def test_conta_sem_bot_ainda_abre_o_app(monkeypatch, tmp_path):
    _servidor(monkeypatch, {"valido": False, "conta_ativa": True, "modulos": ["site"],
                            "motivo": "Seu plano não inclui o bot de WhatsApp."})
    liberado, _, detalhes = licenca.verificar_licenca("AF-1", "https://x", tmp_path / "estado.json")
    assert liberado
    assert detalhes["modulos"] == ["site"]


def test_servidor_antigo_sem_modulos_vale_como_bot(monkeypatch, tmp_path):
    _servidor(monkeypatch, {"valido": True, "motivo": "", "plano": "", "expira_em": ""})
    liberado, _, detalhes = licenca.verificar_licenca("AF-1", "https://x", tmp_path / "estado.json")
    assert liberado
    assert detalhes["modulos"] == ["whatsapp"]


def test_conta_inativa_bloqueia_e_limpa_cache(monkeypatch, tmp_path):
    caminho = tmp_path / "estado.json"
    _servidor(monkeypatch, {"valido": True, "conta_ativa": True, "modulos": ["whatsapp"]})
    licenca.verificar_licenca("AF-1", "https://x", caminho)
    _servidor(monkeypatch, {"valido": False, "conta_ativa": False, "modulos": [], "motivo": "Assinatura cancelada."})
    liberado, motivo, _ = licenca.verificar_licenca("AF-1", "https://x", caminho)
    assert not liberado
    assert "cancelada" in motivo
    assert licenca.LicencaEstado(caminho).dados == {}


def test_offline_usa_modulos_do_cache(monkeypatch, tmp_path):
    caminho = tmp_path / "estado.json"
    _servidor(monkeypatch, {"valido": True, "conta_ativa": True, "modulos": ["whatsapp", "videos"]})
    licenca.verificar_licenca("AF-1", "https://x", caminho)
    _sem_internet(monkeypatch)
    liberado, _, detalhes = licenca.verificar_licenca("AF-1", "https://x", caminho)
    assert liberado
    assert detalhes["modulos"] == ["whatsapp", "videos"]


def test_cache_antigo_sem_modulos_vale_como_bot(monkeypatch, tmp_path):
    caminho = tmp_path / "estado.json"
    estado = licenca.LicencaEstado(caminho)
    estado.dados = {"chave": "AF-1", "plano": "", "expira_em": "",
                    "verificado_em": licenca.datetime.now(licenca.timezone.utc).isoformat()}
    estado.salvar()
    _sem_internet(monkeypatch)
    liberado, _, detalhes = licenca.verificar_licenca("AF-1", "https://x", caminho)
    assert liberado
    assert detalhes["modulos"] == ["whatsapp"]
