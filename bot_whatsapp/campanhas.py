"""Modo campanha do bot: nas datas da Shopee marcadas (11.11, Black Friday...), o bot usa
a configuração da campanha no lugar da normal, do começo ao fim do dia. A configuração
normal nunca é alterada. O bot não liga sozinho: a campanha só vale com ele ligado.

As datas se repetem todo ano (a chave "11.11" vale para 2026, 2027...); as datas próprias
da pessoa têm dia certo."""

from datetime import date, timedelta

# (chave, nome, mês, dia). Black Friday e Dia do Consumidor ficam à parte.
DATAS_DUPLAS = [(f"{m}.{m}", f"{m}.{m}", m, m) for m in range(3, 13)]
LIGADAS_PADRAO = ["9.9", "10.10", "11.11", "black_friday", "12.12"]
DIAS_DO_AVISO = 7  # a tela Início avisa a partir de uma semana antes


def black_friday(ano: int) -> date:
    """A sexta depois da quarta quinta-feira de novembro."""
    primeiro = date(ano, 11, 1)
    primeira_quinta = primeiro + timedelta(days=(3 - primeiro.weekday()) % 7)
    return primeira_quinta + timedelta(days=21 + 1)


def datas_do_ano(ano: int) -> list[dict]:
    datas = [{"chave": "consumidor", "nome": "Dia do Consumidor", "data": date(ano, 3, 15)}]
    datas += [{"chave": chave, "nome": nome, "data": date(ano, m, d)} for chave, nome, m, d in DATAS_DUPLAS]
    datas.append({"chave": "black_friday", "nome": "Black Friday", "data": black_friday(ano)})
    return datas


def proximas_datas(campanha, hoje: date, meses: int = 12) -> list[dict]:
    """As datas da Shopee e as próprias dos próximos 12 meses (hoje incluído), em ordem,
    cada uma com "ligada", "propria" e "faltam" (dias)."""
    fim = hoje + timedelta(days=round(meses * 30.5))
    ligadas = set(campanha.datas_ligadas or [])
    datas = []
    for ano in (hoje.year, hoje.year + 1):
        for d in datas_do_ano(ano):
            if hoje <= d["data"] <= fim:
                datas.append({**d, "ligada": d["chave"] in ligadas, "propria": False})
    for p in campanha.datas_proprias or []:
        try:
            dia = date.fromisoformat(p.get("data", ""))
        except ValueError:
            continue
        if dia >= hoje:
            datas.append({"chave": f"propria:{dia.isoformat()}", "nome": p.get("nome") or "Data própria", "data": dia,
                          "ligada": True, "propria": True})
    for d in datas:
        d["faltam"] = (d["data"] - hoje).days
    return sorted(datas, key=lambda d: (d["data"], d["nome"]))


def campanha_do_dia(campanha, dia: date) -> dict | None:
    """A data ligada que cai neste dia (ou None). Com o modo campanha desligado, nunca."""
    if not campanha or not campanha.ativo:
        return None
    return next((d for d in proximas_datas(campanha, dia, meses=0) if d["ligada"] and d["data"] == dia), None)


def proxima_ligada(campanha, hoje: date) -> dict | None:
    return next((d for d in proximas_datas(campanha, hoje) if d["ligada"]), None) if campanha and campanha.ativo else None


def quando(faltam: int) -> str:
    return "hoje" if faltam == 0 else "amanhã" if faltam == 1 else f"em {faltam} dias"


def com_abertura(texto: str, frase: str) -> str:
    """A frase de abertura da campanha no começo da oferta."""
    frase = (frase or "").strip()
    return f"{frase}\n\n{texto}" if frase else texto


def aviso_da_inicio(conta, hoje: date) -> dict | None:
    """O aviso da tela Início: {"texto", "tipo"} de 7 dias antes até o dia da campanha."""
    from .models import CampanhaBot, ConfiguracaoOfertas

    campanha = CampanhaBot.objects.filter(conta=conta, ativo=True).first()
    proxima = proxima_ligada(campanha, hoje)
    if not proxima or proxima["faltam"] > DIAS_DO_AVISO:
        return None
    ligado = ConfiguracaoOfertas.objects.filter(conta=conta, ativo=True).exists()
    nome = proxima["nome"]
    if proxima["faltam"] == 0:
        texto = f"Hoje é {nome}: o modo campanha do bot está ativo." if ligado else (
            f"Hoje é {nome}, mas suas ofertas estão pausadas. Ligue o bot para a campanha valer.")
    elif not ligado and proxima["faltam"] <= 2:
        texto = f"O {nome} é {quando(proxima['faltam'])} e suas ofertas estão pausadas. Ligue o bot para a campanha valer."
    else:
        texto = f"Faltam {proxima['faltam']} dias para o {nome}. Confira o cupom e a frase da campanha no bot." if proxima["faltam"] > 1 else (
            f"O {nome} é amanhã. Confira o cupom e a frase da campanha no bot.")
    return {"texto": texto, "tipo": "success" if ligado and proxima["faltam"] == 0 else "warning" if not ligado else "info"}
