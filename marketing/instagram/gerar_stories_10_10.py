"""Sequência de 4 stories da campanha 10.10 (50% a mais de cashback).

A sequência acompanha a contagem regressiva, do mais leve ao mais urgente:

1. TEASER ("vem aí"): só avisa que a data chegou. Sem números de cashback por pessoa; o
   gancho é "50% a mais" e o dia.
2. FALTAM 2 DIAS: aqui entram os números (1,6% -> 2,4% e 1% -> 1,5%), porque quem vai
   comprar precisa saber o que ganha para decidir esperar o dia.
3. HOJE: a campanha está no ar. Três passos e o horário limite.
4. ÚLTIMAS HORAS: urgência. O dia acaba à meia-noite, horário de Brasília.

Os números NÃO são digitados aqui: vêm de `marketing/gerar_banner_email.py`, que por sua vez
os documenta como cópia dos settings (pisos de cashback) e da campanha cadastrada no admin.
Arte que promete número diferente do que o sistema paga é o pior erro possível: se o
percentual da campanha mudar, muda numa constante só e o banner e os stories saem juntos.

IMPORTANTE ao postar:
- Só publicar com a campanha cadastrada no admin ("Campanhas de cashback": multiplicador
  1,5, 10/10 das 00:00 às 23:59:59). Os stories 3 e 4 afirmam que o cashback já está maior.
- A peça 2 diz "faltam 2 dias": só vale se postada na quinta, 8/10. Em outro dia a contagem
  fica errada. O teaser não cita contagem e serve de qualquer dia antes.
- Coloque a figurinha de CONTAGEM REGRESSIVA do Instagram no teaser e na peça 2: ela fica
  na faixa livre abaixo do texto (o texto não passa de ~65% da altura) e quem toca nela
  recebe o lembrete no dia.

Margens: 250px em cima e 300px embaixo ficam livres. É onde a interface do Instagram (foto
de perfil, nome, barra de resposta) cobre o story.

Como usar:
    python3 gerar_stories_10_10.py
"""
import base64
import sys
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import FAMILJEN_B64, HIGHLIGHT, MARCA

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "marketing"))

from gerar_banner_email import (  # noqa: E402
    DATA,
    DIA_MES,
    MINIMO_DIRETA,
    MINIMO_INDIRETA,
    MULTIPLICADOR,
    PERCENTUAL_EXTRA,
    _pct,
)

FUNDOS = REPO_ROOT / "marketing" / "fundos-marca"
OUT_DIR = Path(__file__).resolve().parent / "stories-10-10"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

# Verde da marca para dinheiro, mas um tom que lê sobre o roxo: o #059669 do banner (sobre
# papel claro) some em fundo escuro.
VERDE_SOBRE_ROXO = "#4ade80"
ROXO_CLARO = "#e9e1fb"

NOVO_DIRETA = _pct(MINIMO_DIRETA * MULTIPLICADOR)
NOVO_INDIRETA = _pct(MINIMO_INDIRETA * MULTIPLICADOR)
ANTES_DIRETA = _pct(MINIMO_DIRETA)
ANTES_INDIRETA = _pct(MINIMO_INDIRETA)
EXTRA = f"{PERCENTUAL_EXTRA}%"
MANCHETE = f"{EXTRA} a mais de cashback"


def _fundo(nome: str) -> str:
    return base64.b64encode((FUNDOS / nome).read_bytes()).decode()


def _pagina(fundo_png: str, corpo: str) -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; color:#fff;
        background:#5b21b6 url(data:image/png;base64,{_fundo(fundo_png)}) center/cover no-repeat;
        font-family:"Familjen", Arial, sans-serif;
    }}
    body {{ display:flex; flex-direction:column; padding:250px 90px 300px; }}
    .marca {{ font-size:46px; font-weight:700; letter-spacing:-0.03em; }}
    .miolo {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
    .selo {{
        align-self:flex-start; background:{HIGHLIGHT}; color:#111827; border-radius:999px;
        padding:16px 36px; font-size:34px; font-weight:700; letter-spacing:6px; text-transform:uppercase;
    }}
    .data {{ font-size:360px; font-weight:700; line-height:0.9; letter-spacing:-0.05em; margin-top:46px; white-space:nowrap; }}
    .manchete {{ font-size:78px; font-weight:700; line-height:1.05; letter-spacing:-0.02em; color:{HIGHLIGHT}; text-transform:uppercase; margin-top:30px; }}
    .texto {{ font-size:46px; line-height:1.3; color:{ROXO_CLARO}; margin-top:44px; }}
    .texto b {{ color:#fff; }}
    .nota {{ font-size:34px; line-height:1.35; color:{ROXO_CLARO}; opacity:.85; margin-top:36px; }}
    .cartao {{
        margin-top:52px; background:rgba(255,255,255,0.13); border:2px solid rgba(255,255,255,0.28);
        border-radius:44px; padding:14px 50px;
    }}
    .linha {{ display:flex; align-items:center; justify-content:space-between; padding:40px 0; gap:24px; }}
    .linha + .linha {{ border-top:2px solid rgba(255,255,255,0.22); }}
    .linha .rotulo {{ font-size:44px; font-weight:700; line-height:1.15; }}
    .linha .rotulo small {{ display:block; font-size:30px; font-weight:400; color:{ROXO_CLARO}; margin-top:8px; }}
    .valores {{ display:flex; align-items:center; gap:22px; white-space:nowrap; }}
    .antes {{ font-size:42px; color:{ROXO_CLARO}; text-decoration:line-through; opacity:.8; }}
    .seta {{ font-size:40px; opacity:.7; }}
    .depois {{ font-size:84px; font-weight:700; color:{VERDE_SOBRE_ROXO}; letter-spacing:-0.03em; }}
    .passos {{ margin-top:48px; display:flex; flex-direction:column; gap:36px; }}
    .passo {{ display:flex; align-items:center; gap:34px; font-size:48px; font-weight:700; line-height:1.15; }}
    .passo i {{
        flex:none; width:88px; height:88px; border-radius:50%; background:#fff; color:#6d28d9;
        font-style:normal; font-size:46px; display:flex; align-items:center; justify-content:center;
    }}
    .rodape {{ font-size:36px; font-weight:700; letter-spacing:1px; color:{ROXO_CLARO}; }}
    </style></head><body>
        <div class="marca">cash-b</div>
        <div class="miolo">{corpo}</div>
        {{rodape}}
    </body></html>""".replace("{rodape}", '<div class="rodape">cash-b.com</div>')


def _teaser() -> str:
    return f"""
        <div class="selo">vem aí</div>
        <div class="data">{DATA}</div>
        <div class="manchete">{MANCHETE}</div>
        <div class="texto">No sábado, todo pedido feito pela {MARCA} rende <b>mais dinheiro de volta</b>.</div>
    """


def _faltam_2_dias() -> str:
    return f"""
        <div class="selo">faltam 2 dias</div>
        <div class="manchete" style="font-size:96px; margin-top:44px; text-transform:none; color:#fff;">
            No {DIA_MES}, o seu cashback sobe <span style="color:{HIGHLIGHT};">{EXTRA}</span>.
        </div>
        <div class="cartao">
            <div class="linha">
                <div class="rotulo">Por link ou vitrine<small>cashback mínimo</small></div>
                <div class="valores"><span class="antes">{ANTES_DIRETA}</span><span class="seta">&rarr;</span><span class="depois">{NOVO_DIRETA}</span></div>
            </div>
            <div class="linha">
                <div class="rotulo">Botão “Ir pra Shopee”<small>cashback mínimo</small></div>
                <div class="valores"><span class="antes">{ANTES_INDIRETA}</span><span class="seta">&rarr;</span><span class="depois">{NOVO_INDIRETA}</span></div>
            </div>
        </div>
        <div class="nota">Muitas vezes, bem mais: o valor de cada produto aparece no card da vitrine.</div>
    """


def _hoje() -> str:
    return f"""
        <div class="selo">hoje</div>
        <div class="data" style="font-size:330px;">{DATA}</div>
        <div class="manchete" style="font-size:70px;">{MANCHETE}</div>
        <div class="passos">
            <div class="passo"><i>1</i><span>Entre na {MARCA} e escolha o produto</span></div>
            <div class="passo"><i>2</i><span>Compre na Shopee até 23h59</span></div>
            <div class="passo"><i>3</i><span>Receba {EXTRA} a mais de cashback</span></div>
        </div>
    """


def _ultimas_horas() -> str:
    return f"""
        <div class="selo">últimas horas</div>
        <div class="manchete" style="font-size:132px; line-height:1.0; margin-top:60px; text-transform:none; color:#fff;">
            O {DATA} acaba hoje à <span style="color:{HIGHLIGHT}; white-space:nowrap;">meia-noite</span>.
        </div>
        <div class="texto">Pedido feito até 23h59 vale <b>{EXTRA} a mais de cashback</b>. Depois disso, volta ao normal.</div>
        <div class="nota">Horário de Brasília.</div>
    """


STORIES = [
    ("01-teaser", "fundo-03-canto-roxo-9x16.png", _teaser),
    ("02-faltam-2-dias", "fundo-03-canto-roxo-9x16.png", _faltam_2_dias),
    ("03-hoje", "fundo-03-canto-roxo-9x16.png", _hoje),
    ("04-ultimas-horas", "fundo-06-halo-roxo-9x16.png", _ultimas_horas),
]


def gerar():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        for nome, fundo, corpo in STORIES:
            pagina.set_content(_pagina(fundo, corpo()))
            pagina.wait_for_timeout(250)
            destino = OUT_DIR / f"story-{nome}.png"
            pagina.screenshot(path=str(destino))
            print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA * ESCALA}x{ALTURA * ESCALA})")
        navegador.close()


if __name__ == "__main__":
    gerar()
