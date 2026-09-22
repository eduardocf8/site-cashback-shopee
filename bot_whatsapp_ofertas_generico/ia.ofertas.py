import json
import os
import urllib.error
import urllib.request

try:
    from config import MODELO_IA, TIMEOUT_IA_SEGUNDOS, USAR_IA_REESCRITA
except Exception:
    MODELO_IA = "gpt-5.5"
    TIMEOUT_IA_SEGUNDOS = 25
    USAR_IA_REESCRITA = False


def _extrair_output_text(resposta_json):
    if not isinstance(resposta_json, dict):
        return None

    if resposta_json.get("output_text"):
        return resposta_json["output_text"]

    partes = []
    for item in resposta_json.get("output", []) or []:
        for conteudo in item.get("content", []) or []:
            if isinstance(conteudo, dict):
                texto = conteudo.get("text")
                if texto:
                    partes.append(texto)

    if partes:
        return "\n".join(partes)

    return None


def _limpar_resposta_ia(texto):
    if not texto:
        return None

    texto = texto.strip()

    # Remove cercas de markdown se o modelo responder com ```.
    if texto.startswith("```"):
        texto = texto.strip("`").strip()

    # Segurança: a IA não deve devolver link nem aviso final, porque o bot monta isso.
    linhas = []
    for linha in texto.splitlines():
        linha_limpa = linha.strip()
        if not linha_limpa:
            linhas.append("")
            continue
        if "http://" in linha_limpa.lower() or "https://" in linha_limpa.lower():
            continue
        if "preço sujeito" in linha_limpa.lower():
            continue
        if "compre aqui" in linha_limpa.lower():
            continue
        linhas.append(linha_limpa)

    texto = "\n".join(linhas).strip()
    return texto or None


def reescrever_oferta_com_ia(dados_oferta, texto_base):
    """Reescreve apenas o miolo da oferta.

    Nunca deve ser indispensável: se faltar chave, internet, crédito, modelo ou
    qualquer outra coisa, retorna None e o formatador usa fallback manual.
    """
    if not USAR_IA_REESCRITA:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("IA desativada: OPENAI_API_KEY não encontrada. Usando texto manual.")
        return None

    prompt = f"""
Você é um copywriter de ofertas para WhatsApp/Telegram.
Reescreva APENAS o miolo da oferta em português do Brasil.

REGRAS IMPORTANTES:
- Não invente preço, desconto, quantidade de pedidos, frete ou benefício.
- Use somente informações presentes nos dados ou no texto original.
- Não inclua link.
- Não inclua título como OFERTA ENCONTRADA.
- Não inclua aviso de preço mudar.
- Frases curtas, naturais, com urgência moderada.
- Pode usar poucos emojis, sem exagerar.
- Se houver preço antigo e preço atual, destaque "de X por Y".
- Se houver apenas preço atual, destaque apenas esse preço.
- Não diga que é original/oficial se isso não estiver explícito.
- Retorne de 3 a 7 linhas no máximo.

DADOS ESTRUTURADOS:
{json.dumps(dados_oferta, ensure_ascii=False, indent=2)}

TEXTO ORIGINAL LIMPO:
{texto_base}
""".strip()

    payload = {
        "model": MODELO_IA,
        "input": prompt,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_IA_SEGUNDOS) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        texto = _extrair_output_text(data)
        return _limpar_resposta_ia(texto)

    except urllib.error.HTTPError as e:
        try:
            detalhe = e.read().decode("utf-8")[:500]
        except Exception:
            detalhe = str(e)
        print(f"IA falhou HTTP {e.code}. Usando texto manual. Detalhe: {detalhe}")
        return None

    except Exception as e:
        print(f"IA falhou. Usando texto manual. Erro: {e}")
        return None
