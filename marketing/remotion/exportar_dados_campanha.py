"""Exporta para o Remotion os números da campanha 10.10.

O Remotion roda em Node e não lê o Python, e os números do reel não podem ser digitados
de novo: banner do e-mail, stories, cards, carrossel e reel precisam dizer a mesma coisa.
Este script lê as mesmas constantes que os outros (`marketing/gerar_banner_email.py`, que
as documenta como cópia dos settings e da campanha do admin, e os cards antes/agora, que
fazem a conta do produto de exemplo do jeito que o site faz) e grava
`src/campanha/dados.json`, que o vídeo importa.

Rode de novo sempre que a campanha, o piso de cashback ou o produto de exemplo mudarem:

    python3 marketing/remotion/exportar_dados_campanha.py
"""
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "marketing"))
sys.path.insert(0, str(REPO_ROOT / "marketing" / "instagram"))

import gerar_cards_antes_agora as cards  # noqa: E402
import gerar_cards_vitrine as vitrine  # noqa: E402
from gerar_banner_email import (  # noqa: E402
    DATA,
    DIA_MES,
    MINIMO_DIRETA,
    MINIMO_INDIRETA,
    MULTIPLICADOR,
    PERCENTUAL_EXTRA,
    _pct,
    _reais,
)

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "src" / "campanha" / "dados.json"
# O Remotion só serve arquivos de public/. Os cards antes/agora (gerar_cards_antes_agora.py)
# entram no reel B copiados para lá; a pasta é ignorada pelo git porque é cópia.
CARDS = REPO_ROOT / "marketing" / "instagram" / "cards-antes-agora"
PUBLICO = AQUI / "public" / "campanha"


def exportar():
    dados = {
        "data": DATA,
        "diaMes": DIA_MES,
        "percentualExtra": PERCENTUAL_EXTRA,
        "direta": {"antes": _pct(MINIMO_DIRETA), "agora": _pct(MINIMO_DIRETA * MULTIPLICADOR)},
        "indireta": {"antes": _pct(MINIMO_INDIRETA), "agora": _pct(MINIMO_INDIRETA * MULTIPLICADOR)},
        "produto": {
            "nome": vitrine.PRODUTO["nome"].split(" com ")[0],
            "preco": vitrine._reais(Decimal(str(vitrine.PRODUTO["preco_base"]))),
            "percentualAntes": cards.PCT_ANTES,
            "percentualAgora": cards.PCT_AGORA,
            "valorAntes": cards.VALOR_ANTES,
            "valorAgora": cards.VALOR_AGORA,
        },
    }
    # Decimal vira texto no formato do site ("5,8%", "R$ 4,05").
    dados["produto"]["percentualAntes"] = vitrine._percentual(dados["produto"]["percentualAntes"])
    dados["produto"]["percentualAgora"] = vitrine._percentual(dados["produto"]["percentualAgora"])
    dados["produto"]["valorAntes"] = vitrine._reais(dados["produto"]["valorAntes"])
    dados["produto"]["valorAgora"] = vitrine._reais(dados["produto"]["valorAgora"])
    PUBLICO.mkdir(parents=True, exist_ok=True)
    for nome in ("card-antes.png", "card-agora.png"):
        shutil.copy(CARDS / nome, PUBLICO / nome)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("gerado:", SAIDA.relative_to(REPO_ROOT))
    print(json.dumps(dados, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    exportar()
