"""Sugestões dos afiliados (painel > Sugerir melhoria): avisos por e-mail pra você a cada sugestão
nova e pra pessoa quando a sugestão dela fica pronta (você marca "Feita" no admin)."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from .models import Sugestao

logger = logging.getLogger(__name__)
POR_DIA = 10  # por conta: corta abuso


def avisar_voce(s: Sugestao) -> None:
    if not settings.APPFILIADO_EMAIL_SUPORTE:
        return
    linhas = [
        f"{s.conta.nome or s.conta.email} ({s.conta.email}) mandou uma sugestão.",
        "",
        f"Tipo: {s.get_tipo_display()}" + (f" · {s.get_ferramenta_display()}" if s.ferramenta else ""),
        f"Faria diferença: {s.get_importancia_display()}",
        f"Pode chamar pra conversar: {'sim' if s.pode_contatar else 'não'}",
        "",
        ("O que mudaria: " if s.tipo == Sugestao.MELHORIA else "Ferramenta: ") + s.descricao,
    ]
    if s.beneficio:
        linhas.append(("Como ajudaria: " if s.tipo == Sugestao.MELHORIA else "Problema que resolve: ") + s.beneficio)
    if s.como_hoje:
        linhas.append(f"Como faz hoje: {s.como_hoje}")
    linhas += ["", f"Ver no admin: {settings.APPFILIADO_ADMIN_URL.rstrip('/')}/painel/sugestao/{s.pk}/change/"]
    try:
        EmailMessage(subject=f"Sugestão nova: {s.descricao[:60]}", body="\n".join(linhas),
                     to=[settings.APPFILIADO_EMAIL_SUPORTE], from_email=settings.APPFILIADO_EMAIL_REMETENTE,
                     reply_to=[s.conta.email]).send()
    except Exception:  # noqa: BLE001 - a sugestão já está salva
        logger.exception("Sugestões: não deu pra avisar da sugestão %s", s.pk)


def avisar_que_ficou_pronta(s: Sugestao) -> bool:
    """E-mail pra pessoa: a ideia dela virou realidade. Uma vez só por sugestão."""
    if s.avisada_em or s.situacao != Sugestao.FEITA:
        return False
    from .emails import url_do_painel

    nome = (s.conta.nome or "").split(" ")[0]
    corpo = (
        f"Fala{', ' + nome if nome else ''}!\n\n"
        "Lembra da sugestão que você mandou pro Appfiliado?\n\n"
        f"\"{s.descricao[:400]}\"\n\n"
        "Ela já está no ar! Obrigado por ajudar a construir o Appfiliado. Pode conferir no painel:\n"
        f"{url_do_painel('painel_inicio')}\n\n"
        "Se tiver outra ideia, é só mandar em Sugerir melhoria, no menu do painel.\n\n"
        "Abraço,\nEduardo\nFundador do Appfiliado"
    )
    try:
        EmailMessage(subject="A sua sugestão virou realidade no Appfiliado", body=corpo, to=[s.conta.email],
                     from_email=settings.APPFILIADO_EMAIL_REMETENTE,
                     reply_to=[settings.APPFILIADO_EMAIL_SUPORTE] if settings.APPFILIADO_EMAIL_SUPORTE else None).send()
    except Exception:  # noqa: BLE001
        logger.exception("Sugestões: não deu pra avisar a pessoa da sugestão %s", s.pk)
        return False
    Sugestao.objects.filter(pk=s.pk).update(avisada_em=timezone.now())
    s.avisada_em = timezone.now()
    return True
