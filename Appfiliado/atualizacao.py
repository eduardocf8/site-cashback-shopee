# -*- coding: utf-8 -*-
"""
Checagem de nova versao disponivel do Appfiliado.

Assim como em licenca.py, o app e um executavel baixado que roda no
computador de quem usa - nao ha como "empurrar" uma atualizacao sozinho.
Este modulo so consulta um endpoint proprio (settings.atualizacao_servidor_url)
que informa a versao mais recente publicada, pra o app poder avisar o
usuario e levar ele ate o link de download; a instalacao em si continua
manual (baixar o novo instalador e rodar por cima do atual).

Contrato esperado do servidor (GET, sem corpo):
    resposta (200): {
        "versao_disponivel": "1.1.0",
        "url_download": "https://.../appfiliado-instalador.exe",
        "notas": "texto curto sobre o que mudou (opcional)",
        "obrigatoria": false
    }

Se atualizacao_servidor_url estiver vazio, a checagem e simplesmente
ignorada (recurso desligado ate alguem configurar um endpoint) - nao gera
erro nem tentativa de rede.
"""

import json
import urllib.error
import urllib.request

TIMEOUT_PADRAO_SEGUNDOS = 10


def url_de_download_e_segura(url):
    """So permite abrir links http/https - evita seguir um esquema
    inesperado (javascript:, file: etc.) caso a resposta do servidor de
    atualizacao venha corrompida ou adulterada."""
    return str(url or "").strip().lower().startswith(("http://", "https://"))


def _parseia_versao(versao):
    """Converte "1.2.10" em (1, 2, 10) pra comparar numericamente (sem
    isso, "1.9" pareceria "maior" que "1.10" numa comparacao de texto).
    Retorna None se a string nao parecer uma versao valida - quem chama
    deve tratar isso como "nao ha atualizacao" por seguranca, nunca travar
    o app por causa de uma resposta mal formada."""
    partes = str(versao or "").strip().split(".")
    if not partes or not all(parte.isdigit() for parte in partes):
        return None
    return tuple(int(parte) for parte in partes)


def _versao_e_maior(versao_remota, versao_atual):
    remota = _parseia_versao(versao_remota)
    atual = _parseia_versao(versao_atual)
    if remota is None or atual is None:
        return False
    return remota > atual


def verificar_atualizacao(servidor_url, versao_atual, timeout=TIMEOUT_PADRAO_SEGUNDOS):
    """Consulta o servidor de atualizacoes.

    Retorna sempre um dict com "ok" (True se conseguiu consultar o
    servidor e entender a resposta; False se nao deu - sem internet,
    servidor fora do ar, resposta invalida etc. - quem chama deve tratar
    "ok": False como "nao sei se tem atualizacao", nunca como erro fatal):
        {"ok": True, "atualizacao_disponivel": bool, "versao_disponivel": str,
         "url_download": str, "notas": str, "obrigatoria": bool}
        {"ok": False, "motivo": str}
    """
    servidor_url = str(servidor_url or "").strip()
    if not servidor_url:
        return {"ok": False, "motivo": "Verificação de atualização não configurada."}

    request = urllib.request.Request(servidor_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return {"ok": False, "motivo": f"Erro HTTP {erro.code} ao verificar atualizações."}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
        return {"ok": False, "motivo": f"Não consegui conectar ao servidor de atualizações: {erro}"}

    if not isinstance(dados, dict):
        return {"ok": False, "motivo": "Resposta inesperada do servidor de atualizações."}

    versao_disponivel = str(dados.get("versao_disponivel") or "").strip()
    if not versao_disponivel:
        return {"ok": False, "motivo": "O servidor de atualizações não informou uma versão."}

    return {
        "ok": True,
        "atualizacao_disponivel": _versao_e_maior(versao_disponivel, versao_atual),
        "versao_disponivel": versao_disponivel,
        "url_download": str(dados.get("url_download") or "").strip(),
        "notas": str(dados.get("notas") or "").strip(),
        "obrigatoria": bool(dados.get("obrigatoria")),
    }
