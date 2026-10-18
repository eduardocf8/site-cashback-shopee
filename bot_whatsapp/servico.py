"""Lado do painel: registra pedidos para o worker e prepara o que as telas mostram.
Nada aqui fala com o WhatsApp (ver gerenciador.py)."""

from datetime import timedelta

from django.utils import timezone

from .models import ConexaoWhatsApp, EnvioWhatsApp, EventoWhatsApp

# Um QR Code do WhatsApp vale ~1 minuto; o worker vai mandando os próximos. Se
# nenhum chegar nesse tempo, o worker provavelmente está parado.
QR_SEM_RESPOSTA = timedelta(minutes=2)
MAXIMO_NA_FILA = 5


def conexao_da(conta) -> ConexaoWhatsApp:
    conexao, _ = ConexaoWhatsApp.objects.get_or_create(conta=conta)
    return conexao


def registrar_evento(conta_id: int, tipo: str, detalhe: str = "") -> None:
    EventoWhatsApp.objects.create(conta_id=conta_id, tipo=tipo, detalhe=detalhe[:300])


def pedir_conexao(conta) -> ConexaoWhatsApp:
    conexao = conexao_da(conta)
    conexao.estado = ConexaoWhatsApp.AGUARDANDO_QR
    conexao.qr_codigo = ""
    conexao.qr_em = timezone.now()
    conexao.erro = ""
    conexao.pedido_conectar = True
    conexao.pedido_desconectar = False
    conexao.save()
    return conexao


def pedir_desconexao(conta) -> ConexaoWhatsApp:
    conexao = conexao_da(conta)
    conexao.pedido_desconectar = True
    conexao.pedido_conectar = False
    conexao.save(update_fields=["pedido_desconectar", "pedido_conectar", "atualizado_em"])
    return conexao


def pedir_grupos(conta) -> ConexaoWhatsApp:
    conexao = conexao_da(conta)
    conexao.pedido_grupos = True
    conexao.save(update_fields=["pedido_grupos", "atualizado_em"])
    return conexao


def worker_sem_resposta(conexao: ConexaoWhatsApp) -> bool:
    """Pediu o QR e nada aconteceu em 2 minutos: o worker não está rodando."""
    return bool(
        conexao.estado == ConexaoWhatsApp.AGUARDANDO_QR and not conexao.qr_codigo
        and conexao.qr_em and timezone.now() - conexao.qr_em > QR_SEM_RESPOSTA
    )


def enfileirar_envio(conta, destino: str, texto: str, imagem_url: str = "") -> tuple[EnvioWhatsApp | None, str]:
    """(envio, "") ou (None, motivo)."""
    conexao = conexao_da(conta)
    if conexao.estado != ConexaoWhatsApp.CONECTADO:
        return None, "Conecte o WhatsApp antes de enviar."
    grupo = next((g for g in conexao.grupos if g.get("jid") == destino), None)
    if not grupo:
        return None, "Escolha um dos seus grupos."
    if not texto.strip() and not imagem_url:
        return None, "Escreva a mensagem."
    if EnvioWhatsApp.objects.filter(conta=conta, estado=EnvioWhatsApp.PENDENTE).count() >= MAXIMO_NA_FILA:
        return None, "Já tem mensagens na fila. Espere elas saírem."
    envio = EnvioWhatsApp.objects.create(
        conta=conta, destino=destino, destino_nome=grupo.get("nome", ""), texto=texto.strip(), imagem_url=imagem_url,
    )
    return envio, ""


def qr_svg(codigo: str) -> str:
    """O QR Code como <svg> para colocar direto na página."""
    if not codigo:
        return ""
    import segno

    # omitsize: sai com viewBox e sem largura fixa, para o CSS diminuir o desenho
    # inteiro (sem isso o navegador cortava o código, que é grande). border=4 é a
    # margem branca que os leitores de QR esperam.
    return segno.make_qr(codigo, error="l").svg_inline(border=4, omitsize=True, dark="#1F3A2E", light="#FFFFFF")


def estado_para_tela(conta) -> dict:
    conexao = conexao_da(conta)
    return {
        "estado": conexao.estado,
        "qr": qr_svg(conexao.qr_codigo) if conexao.estado == ConexaoWhatsApp.AGUARDANDO_QR else "",
        "pendentes": EnvioWhatsApp.objects.filter(conta=conta, estado=EnvioWhatsApp.PENDENTE).count(),
        "pedido_grupos": conexao.pedido_grupos,
        "sem_resposta": worker_sem_resposta(conexao),
    }
