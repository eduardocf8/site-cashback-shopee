# -*- coding: utf-8 -*-
"""
Checagem de licenca (assinatura) do bot.

O bot e um arquivo baixado que roda offline no computador de quem compra -
diferente de um curso hospedado numa plataforma tipo Hotmart/Kiwify, a
propria plataforma de pagamento nao tem como "desligar" o bot sozinha
quando alguem cancela a assinatura ou o pagamento falha. Por isso esse
modulo consulta um servidor proprio (o endpoint configurado em
settings.licenca_servidor_url) que sabe, atraves dos webhooks recebidos da
plataforma de pagamento, se aquela chave ainda esta com a assinatura em dia.

Contrato esperado do servidor:
    POST {licenca_servidor_url}
    body: {"chave": "<chave da licenca>"}
    resposta (200): {
        "valido": true/false,
        "motivo": "texto explicando por que nao e valido, se for o caso",
        "plano": "nome do plano (opcional)",
        "expira_em": "data ISO da proxima cobranca/expiracao (opcional)"
    }

Como o bot pode ficar sem internet por um tempo sem travar: guardamos a
ultima validacao BEM-SUCEDIDA num arquivo local (licenca_estado.json, ao
lado do config_usuario.json) e aceitamos rodar offline por alguns dias
usando esse cache - so quando o servidor responde ativamente "invalido"
(assinatura cancelada, pagamento atrasado etc.) e que bloqueamos na hora,
mesmo com cache dizendo que era valido antes.
"""

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIAS_TOLERANCIA_OFFLINE = 5
TIMEOUT_PADRAO_SEGUNDOS = 10


class LicencaEstado:
    """Guarda em disco o resultado da ultima validacao bem-sucedida."""

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.dados = self._carregar()

    def _carregar(self):
        if not self.caminho.exists():
            return {}
        try:
            return json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def salvar(self):
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.caminho.write_text(
                json.dumps(self.dados, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def registrar_validacao_ok(self, chave, plano="", expira_em=""):
        self.dados = {
            "chave": chave,
            "plano": plano,
            "expira_em": expira_em,
            "verificado_em": datetime.now(timezone.utc).isoformat(),
        }
        self.salvar()

    def limpar(self):
        self.dados = {}
        self.salvar()

    def chave_corresponde(self, chave):
        return bool(self.dados) and self.dados.get("chave") == chave

    def dentro_da_tolerancia_offline(self, dias_tolerancia=DIAS_TOLERANCIA_OFFLINE):
        verificado_em = self.dados.get("verificado_em")
        if not verificado_em:
            return False
        try:
            momento = datetime.fromisoformat(verificado_em)
        except ValueError:
            return False
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - momento <= timedelta(days=dias_tolerancia)


def validar_licenca_online(servidor_url, chave, timeout=TIMEOUT_PADRAO_SEGUNDOS):
    """Consulta o servidor de licencas.

    Retorna sempre um dict com "ok" (True se conseguiu conversar com o
    servidor, mesmo que a resposta seja "invalido"; False se nem deu pra
    consultar - sem internet, servidor fora do ar, timeout etc.):
        {"ok": True,  "valido": bool, "motivo": str, "plano": str, "expira_em": str}
        {"ok": False, "motivo": str}
    """
    if not servidor_url:
        return {"ok": False, "motivo": "Servidor de licenças não configurado."}
    if not chave:
        return {"ok": True, "valido": False, "motivo": "Preencha a chave de licença."}

    payload = json.dumps({"chave": chave}).encode("utf-8")
    request = urllib.request.Request(
        servidor_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return {
            "ok": True,
            "valido": bool(dados.get("valido")),
            "motivo": str(dados.get("motivo") or ""),
            "plano": str(dados.get("plano") or ""),
            "expira_em": str(dados.get("expira_em") or ""),
        }
    except urllib.error.HTTPError as erro:
        try:
            dados = json.loads(erro.read().decode("utf-8"))
            motivo = str(dados.get("motivo") or f"Erro HTTP {erro.code} ao validar a licença.")
        except (OSError, ValueError):
            motivo = f"Erro HTTP {erro.code} ao validar a licença."
        # HTTPError significa que o servidor respondeu (mesmo que com erro),
        # entao trata como resposta valida do tipo "invalido", nao como
        # falha de conexao - nao deve cair na tolerancia offline.
        return {"ok": True, "valido": False, "motivo": motivo}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
        return {"ok": False, "motivo": f"Não consegui conectar ao servidor de licenças: {erro}"}


def verificar_licenca(chave, servidor_url, caminho_estado):
    """Retorna (liberado: bool, motivo: str, detalhes: dict).

    Tenta validar online primeiro; se nao conseguir conectar, cai para o
    cache local (tolerancia de alguns dias), desde que seja a mesma chave.
    """
    chave = str(chave or "").strip()
    servidor_url = str(servidor_url or "").strip()
    estado = LicencaEstado(caminho_estado)

    if not chave:
        return False, "Nenhuma chave de licença configurada.", {}

    resultado = validar_licenca_online(servidor_url, chave)

    if resultado["ok"]:
        if resultado["valido"]:
            estado.registrar_validacao_ok(chave, resultado.get("plano", ""), resultado.get("expira_em", ""))
            return True, "Licença ativa.", resultado
        estado.limpar()
        return False, resultado.get("motivo") or "Licença inválida ou assinatura cancelada.", resultado

    if estado.chave_corresponde(chave) and estado.dentro_da_tolerancia_offline():
        return True, "Licença validada offline (última verificação recente ainda dentro do prazo).", resultado

    motivo = resultado.get("motivo") or "Não foi possível validar a licença."
    return False, motivo, resultado
