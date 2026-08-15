import random
import re


FECHAMENTOS = [
    "⚠️ Preço sujeito a alteração a qualquer momento.",
    "⏳ Oferta pode acabar ou mudar de preço a qualquer momento.",
    "⚠️ Valores e disponibilidade podem mudar sem aviso.",
    "🛒 Aproveite enquanto a oferta estiver ativa.",
]

PADRAO_PRECO = r"R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?|R\$\s*\d+(?:,\d{2})?"

TRECHOS_REMOVER = (
    "preço sujeito",
    "sujeito a alteração",
    "valores e disponibilidade",
    "compre aqui",
    "link aqui",
    "clique aqui",
    "garanta já",
    "garanta ja",
    "aproveite agora",
    "aproveite já",
    "aproveite ja",
    "corre antes",
    "antes que acabe",
)


def limpar_linhas(texto):
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    linhas = [linha.strip() for linha in texto.split("\n")]
    linhas = [linha for linha in linhas if linha]

    filtradas = []
    for linha in linhas:
        if filtradas and filtradas[-1].lower() == linha.lower():
            continue
        filtradas.append(linha)

    return "\n".join(filtradas).strip()


def remover_links(texto):
    return re.sub(r"https?://[^\s]+", "", texto or "").strip()


def extrair_precos(texto):
    precos = re.findall(PADRAO_PRECO, texto or "", flags=re.IGNORECASE)
    return [re.sub(r"\s+", " ", p).strip() for p in precos]


def preco_para_numero(preco):
    if not preco:
        return None

    valor = re.sub(r"[^\d,.]", "", preco)

    if not valor:
        return None

    valor = valor.replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        return None


def corrigir_precos_invertidos(preco_antigo, preco_atual):
    valor_antigo = preco_para_numero(preco_antigo)
    valor_atual = preco_para_numero(preco_atual)

    if valor_antigo is None or valor_atual is None:
        return preco_antigo, preco_atual

    if valor_atual > valor_antigo:
        return preco_atual, preco_antigo

    return preco_antigo, preco_atual


def extrair_percentual(texto):
    m = re.search(r"(\d{1,3})\s*%", texto or "")
    return f"{m.group(1)}%" if m else None


def linha_tem_apenas_preco_ou_preco_com_rotulo(linha):
    l = (linha or "").strip().lower()
    if not l:
        return False

    l_limpa = re.sub(r"[✅❌🔥💰💸⚡➡️:;\-–—()\[\]]", " ", l)
    l_limpa = re.sub(r"\s+", " ", l_limpa).strip()

    tem_preco = bool(re.search(PADRAO_PRECO, linha or "", flags=re.IGNORECASE))
    if not tem_preco:
        return False

    palavras_preco = (
        "de", "por", "agora", "antes", "preço", "preco", "r$",
        "apenas", "somente", "à vista", "avista", "pix"
    )

    palavras = l_limpa.split()

    if len(palavras) <= 8:
        return True

    if any(p in l_limpa for p in palavras_preco) and len(palavras) <= 14:
        return True

    return False


def linha_e_chamada_antiga(linha):
    l = (linha or "").lower().strip()

    if not l:
        return True

    if any(trecho in l for trecho in TRECHOS_REMOVER):
        return True

    if re.fullmatch(r"[\W_]+", l):
        return True

    return False


def extrair_chamada_original(texto):
    texto_sem_link = remover_links(texto)
    linhas = limpar_linhas(texto_sem_link).split("\n")

    for linha in linhas:
        linha = linha.strip()

        if not linha:
            continue

        if linha_tem_apenas_preco_ou_preco_com_rotulo(linha):
            continue

        if re.fullmatch(r"[\W_]+", linha.lower()):
            continue

        return linha

    return ""


def preparar_descricao_original(texto):
    texto_sem_link = remover_links(texto)
    linhas = limpar_linhas(texto_sem_link).split("\n")

    chamada_original = extrair_chamada_original(texto)

    descricao = []

    for linha in linhas:
        linha = linha.strip()

        if not linha:
            continue

        if chamada_original and linha.lower() == chamada_original.lower():
            continue

        if linha_e_chamada_antiga(linha):
            continue

        if linha_tem_apenas_preco_ou_preco_com_rotulo(linha):
            continue

        descricao.append(linha)

    return limpar_linhas("\n\n".join(descricao))


def montar_bloco_preco(texto_original):
    precos = extrair_precos(texto_original)
    percentual = extrair_percentual(texto_original)

    if len(precos) >= 2:
        preco_antigo = precos[0]
        preco_atual = precos[-1]
        preco_antigo, preco_atual = corrigir_precos_invertidos(preco_antigo, preco_atual)

        if preco_antigo != preco_atual:
            return f"💸 De: {preco_antigo}\n✅ Por: {preco_atual}"

        return f"✅ Por: {preco_atual}"

    if len(precos) == 1:
        return f"✅ Por: {precos[0]}"

    if percentual:
        return f"💥 Desconto: {percentual}"

    return ""


def formatar_texto_oferta(texto, link_final):
    chamada_original = extrair_chamada_original(texto)
    descricao_original = preparar_descricao_original(texto)
    bloco_preco = montar_bloco_preco(texto)

    partes = []

    if chamada_original:
        partes.append(chamada_original)

    if descricao_original:
        partes.append(descricao_original)

    if bloco_preco:
        partes.append(bloco_preco)

    if link_final:
        partes.append(f"🛒 Compre aqui:\n{link_final}")

    partes.append(random.choice(FECHAMENTOS))

    return "\n\n".join(
        p.strip()
        for p in partes
        if p and p.strip()
    ).strip()
