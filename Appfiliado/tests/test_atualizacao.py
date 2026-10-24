import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import atualizacao as at


class TestUrlDeDownloadESegura:
    def test_aceita_http_e_https(self):
        assert at.url_de_download_e_segura("https://exemplo.com/instalador.exe") is True
        assert at.url_de_download_e_segura("http://exemplo.com/instalador.exe") is True

    def test_rejeita_esquemas_perigosos_ou_vazios(self):
        assert at.url_de_download_e_segura("javascript:alert(1)") is False
        assert at.url_de_download_e_segura("file:///etc/passwd") is False
        assert at.url_de_download_e_segura("") is False
        assert at.url_de_download_e_segura(None) is False


class TestVersaoEMaior:
    def test_versao_maior_numerica_nao_lexicografica(self):
        # Comparacao por texto erraria isso ("1.10" < "1.9" alfabeticamente).
        assert at._versao_e_maior("1.10.0", "1.9.0") is True
        assert at._versao_e_maior("1.9.0", "1.10.0") is False

    def test_versao_igual_nao_e_maior(self):
        assert at._versao_e_maior("1.0.0", "1.0.0") is False

    def test_versao_menor_nao_e_maior(self):
        assert at._versao_e_maior("0.9.0", "1.0.0") is False

    def test_versao_malformada_nunca_e_considerada_maior(self):
        assert at._versao_e_maior("v1.1", "1.0.0") is False
        assert at._versao_e_maior("1.1.0-beta", "1.0.0") is False
        assert at._versao_e_maior("", "1.0.0") is False


class _ServidorFake:
    """Servidor HTTP local minimo pra testar verificar_atualizacao() contra
    respostas de verdade (nao mocks de biblioteca), incluindo os casos de
    erro que importam: JSON quebrado, campo faltando, HTTP 500 etc."""

    def __init__(self):
        self.rotas = {}

        rotas = self.rotas

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                status, corpo = rotas.get(self.path, (500, b"{}"))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(corpo)

        self._servidor = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self._servidor.server_port}"

    def definir_rota(self, caminho, status, dados_json):
        self.rotas[caminho] = (status, json.dumps(dados_json).encode("utf-8"))

    def definir_rota_bruta(self, caminho, status, corpo_bytes):
        self.rotas[caminho] = (status, corpo_bytes)

    def parar(self):
        self._servidor.shutdown()


@pytest.fixture(scope="module")
def servidor():
    srv = _ServidorFake()
    yield srv
    srv.parar()


class TestVerificarAtualizacaoSemServidorConfigurado:
    def test_url_vazia_nao_tenta_rede_e_retorna_ok_false(self):
        resultado = at.verificar_atualizacao("", "1.0.0")
        assert resultado == {"ok": False, "motivo": "Verificação de atualização não configurada."}


class TestVerificarAtualizacaoComServidor:
    def test_atualizacao_disponivel(self, servidor):
        servidor.definir_rota(
            "/ok",
            200,
            {
                "versao_disponivel": "1.2.0",
                "url_download": "https://exemplo.com/instalador.exe",
                "notas": "Corrige bug X",
                "obrigatoria": False,
            },
        )
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/ok", "1.0.0")
        assert resultado["ok"] is True
        assert resultado["atualizacao_disponivel"] is True
        assert resultado["versao_disponivel"] == "1.2.0"
        assert resultado["url_download"] == "https://exemplo.com/instalador.exe"

    def test_ja_na_versao_mais_recente(self, servidor):
        servidor.definir_rota("/mesma", 200, {"versao_disponivel": "1.0.0"})
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/mesma", "1.0.0")
        assert resultado["ok"] is True
        assert resultado["atualizacao_disponivel"] is False

    def test_json_quebrado(self, servidor):
        servidor.definir_rota_bruta("/quebrado", 200, b"isso nao e json")
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/quebrado", "1.0.0")
        assert resultado["ok"] is False

    def test_campo_de_versao_ausente(self, servidor):
        servidor.definir_rota("/sem-versao", 200, {"algumaCoisa": "valor"})
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/sem-versao", "1.0.0")
        assert resultado["ok"] is False

    def test_resposta_nao_e_objeto(self, servidor):
        servidor.definir_rota("/lista", 200, [1, 2, 3])
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/lista", "1.0.0")
        assert resultado["ok"] is False

    def test_erro_http(self, servidor):
        servidor.definir_rota("/erro", 500, {})
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/erro", "1.0.0")
        assert resultado["ok"] is False
        assert "500" in resultado["motivo"]

    def test_link_de_download_com_esquema_perigoso_fica_marcado_inseguro(self, servidor):
        # verificar_atualizacao nao precisa validar o esquema sozinho - quem
        # decide se abre o link e url_de_download_e_segura(), chamado por
        # quem exibe o aviso (ver app.py). Aqui so garantimos que o valor
        # cru chega intacto pra essa validação poder acontecer depois.
        servidor.definir_rota(
            "/malicioso",
            200,
            {"versao_disponivel": "2.0.0", "url_download": "javascript:alert(1)"},
        )
        resultado = at.verificar_atualizacao(f"{servidor.base_url}/malicioso", "1.0.0")
        assert resultado["ok"] is True
        assert at.url_de_download_e_segura(resultado["url_download"]) is False


class TestVerificarAtualizacaoServidorInalcancavel:
    def test_conexao_recusada(self):
        resultado = at.verificar_atualizacao("http://127.0.0.1:1", "1.0.0", timeout=2)
        assert resultado["ok"] is False
