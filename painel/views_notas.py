"""Emissor de notas fiscais no painel: cadastro da empresa, certificado A1, serviço, nota de
teste, importação do Relatório Mensal da Shopee (uma nota por loja) e nota da Shopee.
As regras ficam em notas/servicos.py; o envio de verdade é feito pelo worker (notas/fila.py)."""

import io
import zipfile

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from notas import certificado, danfse, servicos
from notas.models import AMBIENTE_PRODUCAO, AMBIENTE_TESTE, LoteNotas, NotaFiscal
from notas.relatorio import TAMANHO_MAXIMO as RELATORIO_MAXIMO

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto


def _bloqueio(request, conta):
    item = mod.POR_SLUG["notas"]
    situacao = mod.estado(item, conta.modulos_liberados())
    if situacao == "liberado":
        return None
    return render(request, "painel/modulo.html", _contexto(
        request, "notas", item={**item, "icone_path": mod.ICONES["notas"]}, situacao=situacao))


class CertificadoForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo do certificado (.pfx ou .p12)",
                              widget=forms.ClearableFileInput(attrs={"accept": ".pfx,.p12"}))
    senha = forms.CharField(label="Senha do certificado", strip=False,
                            widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))


HORARIOS_EMAIL = [("", "Logo depois que as notas saírem")] + [(str(h), f"Às {h:02d}:00") for h in range(6, 23)]


class HorarioEmailForm(forms.Form):
    horario = forms.ChoiceField(label="Quando mandar os e-mails", choices=HORARIOS_EMAIL, required=False,
                                help_text="Horário de Brasília. Com um horário, os e-mails de cada lote saem na "
                                          "próxima vez que der essa hora depois de você mandar emitir.")


class ServicoForm(forms.Form):
    codigo_tributacao = forms.CharField(label="Código de tributação nacional", max_length=8,
                                        help_text="6 números, como aparece na sua nota (ex: 17.06.01 → 170601).")
    codigo_municipal = forms.CharField(label="Código do município (se a prefeitura pedir)", max_length=20,
                                       required=False)
    codigo_nbs = forms.CharField(label="Código NBS", max_length=14, required=False,
                                 help_text="Vai junto com o IBS/CBS da reforma. Para 17.06: 1.1406.11.00 (campanhas "
                                           "publicitárias), 1.1406.12.00 (marketing direto) ou 1.1406.19.00 (outros "
                                           "serviços de propaganda).")
    inscricao_municipal = forms.CharField(label="Inscrição municipal (se tiver)", max_length=20, required=False)
    descricao_servico = forms.CharField(label="Descrição do serviço", max_length=2000,
                                        widget=forms.Textarea(attrs={"rows": 3}))


@sensitive_post_parameters("senha")
@conta_requerida
def notas(request):
    conta = conta_logada(request)
    bloqueio = _bloqueio(request, conta)
    if bloqueio:
        return bloqueio
    empresa = servicos.empresa_da_conta(conta)
    if empresa:
        servicos.aplicar_servico_padrao(empresa)  # empresas cadastradas antes do padrão existir
    form_horario = HorarioEmailForm(initial={"horario": "" if getattr(empresa, "email_horario", None) is None
                                             else str(empresa.email_horario)})
    form_cert, form_servico = CertificadoForm(), ServicoForm(initial={
        "codigo_tributacao": getattr(empresa, "codigo_tributacao", ""),
        "codigo_municipal": getattr(empresa, "codigo_municipal", ""),
        "inscricao_municipal": getattr(empresa, "inscricao_municipal", ""),
        "codigo_nbs": _nbs_formatado(getattr(empresa, "codigo_nbs", "")),
        "descricao_servico": getattr(empresa, "descricao_servico", ""),
    })

    if request.method == "POST":
        acao = request.POST.get("acao")
        try:
            if acao == "empresa":
                empresa = servicos.cadastrar_empresa(conta, request.POST.get("cnpj", ""))
                messages.success(request, f"Empresa cadastrada: {empresa.razao_social}.")
                return redirect("painel_notas")
            if empresa is None:
                return redirect("painel_notas")
            if acao == "certificado":
                form_cert = CertificadoForm(request.POST, request.FILES)
                if form_cert.is_valid():
                    arquivo = form_cert.cleaned_data["arquivo"]
                    if arquivo.size > certificado.TAMANHO_MAXIMO:
                        raise certificado.ErroCertificado("Esse arquivo é grande demais para ser um certificado A1.")
                    cert = certificado.guardar(empresa, arquivo.read(), form_cert.cleaned_data["senha"])
                    messages.success(request, f"Certificado guardado. Vale até {cert.validade:%d/%m/%Y}.")
                    return redirect("painel_notas")
            elif acao == "retomar":
                empresa.emissao_pausada = ""
                empresa.save(update_fields=["emissao_pausada", "atualizada_em"])
                messages.info(request, "Emissão retomada.")
                return redirect(request.POST.get("voltar") or "painel_notas")
            elif acao == "remover_certificado":
                certificado.apagar(empresa)
                messages.info(request, "Certificado apagado do Appfiliado.")
                return redirect("painel_notas")
            elif acao == "servico":
                form_servico = ServicoForm(request.POST)
                if form_servico.is_valid():
                    d = form_servico.cleaned_data
                    servicos.salvar_servico(empresa, d["codigo_tributacao"], d["codigo_municipal"],
                                            d["descricao_servico"], d["inscricao_municipal"], d["codigo_nbs"])
                    messages.success(request, "Serviço salvo.")
                    return redirect("painel_notas")
            elif acao == "horario_email":
                form_horario = HorarioEmailForm(request.POST)
                if form_horario.is_valid():
                    valor = form_horario.cleaned_data["horario"]
                    hora = int(valor) if valor else None
                    reagendados = servicos.salvar_horario_dos_emails(empresa, hora)
                    texto = f"Os e-mails vão sair às {hora:02d}:00." if hora is not None else \
                        "Os e-mails vão sair logo depois que as notas saírem."
                    if reagendados:
                        texto += f" {reagendados} e-mail{'s' if reagendados > 1 else ''} que ainda não tinha{'m' if reagendados > 1 else ''} saído segue{'m' if reagendados > 1 else ''} o novo horário."
                    messages.success(request, texto)
                    return redirect("painel_notas")
            elif acao == "importar":
                arquivo = request.FILES.get("relatorio")
                if not arquivo:
                    raise servicos.ErroNotas("Escolha o arquivo do Relatório Mensal.")
                if arquivo.size > RELATORIO_MAXIMO:
                    raise servicos.ErroNotas("Arquivo grande demais (até 25 MB).")
                lote = servicos.importar_relatorio(empresa, arquivo.read(), arquivo.name, _ambiente(request))
                return redirect("painel_notas_lote", pk=lote.pk)
            elif acao == "shopee":
                _avisar_regime(request, empresa)
                nota = servicos.emitir_nota_shopee(empresa, request.POST.get("valor", ""), _ambiente(request))
                messages.success(request, f"Nota da Shopee de {_brl(nota.valor)} na fila. Ela sai em alguns minutos.")
                return redirect("painel_notas")
            elif acao == "testar":
                _avisar_regime(request, empresa)
                nota = servicos.emitir_teste(empresa)
                if nota.situacao == NotaFiscal.AUTORIZADA:
                    messages.success(request, "Deu certo! O governo gerou a nota de teste.")
                else:
                    messages.error(request, "A nota de teste não passou. Veja o motivo na lista abaixo.")
                return redirect("painel_notas")
        except (servicos.ErroNotas, certificado.ErroCertificado) as erro:
            messages.error(request, str(erro))
            if acao != "certificado":
                return redirect("painel_notas")

    contexto = {"empresa": empresa, "form_cert": form_cert, "form_servico": form_servico, "form_horario": form_horario}
    if empresa:
        contexto["falta"] = servicos.pronta_para_emitir(empresa)
        contexto["ultimas"] = empresa.notas.filter(lote__isnull=True)[:10]
        contexto["avulsas_na_fila"] = any(n.situacao in (NotaFiscal.FILA, NotaFiscal.ENVIANDO) for n in contexto["ultimas"])
        contexto["lotes"] = empresa.lotes.all()[:12]
        contexto["teste_ok"] = empresa.notas.filter(tipo=NotaFiscal.TIPO_TESTE, situacao=NotaFiscal.AUTORIZADA).exists()
    return render(request, "painel/notas.html", _contexto(request, "notas", **contexto))


def _nbs_formatado(nbs: str) -> str:
    return f"{nbs[0]}.{nbs[1:5]}.{nbs[5:7]}.{nbs[7:]}" if len(nbs or "") == 9 else (nbs or "")


def _avisar_regime(request, empresa):
    """Confere o regime (MEI/Simples) na Receita antes de emitir; avisa se mudou."""
    aviso = servicos.atualizar_cadastro(empresa)
    if aviso:
        messages.info(request, aviso)


def _ambiente(request) -> str:
    return AMBIENTE_PRODUCAO if request.POST.get("ambiente") == AMBIENTE_PRODUCAO else AMBIENTE_TESTE


def _brl(valor) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _volta(request, nota):
    destino = request.POST.get("voltar", "")
    if nota.lote_id and destino == "lote":
        return redirect("painel_notas_lote", pk=nota.lote_id)
    return redirect("painel_notas")


FILTROS = {
    "todas": None, "autorizadas": [NotaFiscal.AUTORIZADA], "problemas": [NotaFiscal.RECUSADA, NotaFiscal.ERRO],
    "fila": [NotaFiscal.FILA, NotaFiscal.ENVIANDO, NotaFiscal.PREVIA],
}


@conta_requerida
def lote(request, pk):
    conta = conta_logada(request)
    bloqueio = _bloqueio(request, conta)
    if bloqueio:
        return bloqueio
    lote = get_object_or_404(LoteNotas, pk=pk, empresa__conta=conta)
    if request.method == "POST":
        acao = request.POST.get("acao")
        try:
            if acao == "confirmar":
                _avisar_regime(request, lote.empresa)
                quantas = servicos.confirmar_lote(lote)
                messages.success(request, f"{quantas} notas na fila. Pode fechar esta página: elas saem sozinhas.")
            elif acao == "descartar":
                servicos.descartar_lote(lote)
                messages.info(request, "Prévia descartada. Nenhuma nota foi emitida.")
                return redirect("painel_notas")
            elif acao == "reenviar_problemas":
                quantas = lote.notas.filter(situacao__in=[NotaFiscal.RECUSADA, NotaFiscal.ERRO]).update(
                    situacao=NotaFiscal.FILA)
                if quantas and lote.estado == LoteNotas.CONCLUIDO:
                    lote.estado = LoteNotas.EMITINDO
                    lote.save(update_fields=["estado"])
                messages.info(request, f"{quantas} nota(s) de volta para a fila.")
        except servicos.ErroNotas as erro:
            messages.error(request, str(erro))
        return redirect("painel_notas_lote", pk=lote.pk)

    filtro = request.GET.get("ver", "todas")
    notas = lote.notas.all().order_by("pk")
    if FILTROS.get(filtro):
        notas = notas.filter(situacao__in=FILTROS[filtro])
    busca = request.GET.get("busca", "").strip()
    if busca:
        from django.db.models import Q
        notas = notas.filter(Q(tomador_nome__icontains=busca) | Q(loja_nome__icontains=busca)
                             | Q(tomador_documento__icontains=busca.replace(".", "").replace("/", "").replace("-", "")))
    pagina = Paginator(notas, 50).get_page(request.GET.get("pagina"))
    email = servicos.andamento_emails(lote)
    return render(request, "painel/notas_lote.html", _contexto(
        request, "notas", lote=lote, empresa=lote.empresa, resumo=servicos.resumo(lote.notas.all()),
        pagina=pagina, filtro=filtro, busca=busca, falta=servicos.pronta_para_emitir(lote.empresa),
        email=email, atualizar=_acompanhar(lote, email),
    ))


def _acompanhar(lote, email) -> bool:
    """A tela continua se atualizando enquanto saem notas ou e-mails."""
    return lote.estado == LoteNotas.EMITINDO or bool(email and email["saindo"])


CLASSE_DA_SITUACAO = {NotaFiscal.AUTORIZADA: "selo-concluido", NotaFiscal.RECUSADA: "selo-cancelado",
                      NotaFiscal.ERRO: "selo-cancelado"}


@conta_requerida
def andamento(request):
    """Situação atual das notas pedidas (ids=1,2,3) e, com lote=<id>, o resumo do lote.
    A tela pergunta isso a cada poucos segundos para a barra e a lista andarem sozinhas."""
    conta = conta_logada(request)
    ids = [int(i) for i in request.GET.get("ids", "").split(",") if i.isdigit()][:200]
    notas = {}
    for n in NotaFiscal.objects.filter(empresa__conta=conta, pk__in=ids):
        rotulo = n.get_situacao_display() + (f" nº {n.numero_nfse}" if n.numero_nfse else "")
        notas[n.pk] = {"situacao": n.situacao, "rotulo": rotulo,
                       "classe": CLASSE_DA_SITUACAO.get(n.situacao, "selo-pendente")}
    resposta = {"notas": notas}
    if request.GET.get("lote", "").isdigit():
        lote = LoteNotas.objects.filter(pk=int(request.GET["lote"]), empresa__conta=conta).first()
        if lote:
            r = servicos.resumo(lote.notas.all())
            resposta["lote"] = {
                "estado": lote.estado, "total": r["total"], "progresso": r["progresso"],
                "autorizadas": r["por"][NotaFiscal.AUTORIZADA]["qtd"],
                "feitas": sum(r["por"][s]["qtd"] for s in (NotaFiscal.AUTORIZADA, NotaFiscal.RECUSADA, NotaFiscal.CANCELADA)),
                "problemas": r["por"][NotaFiscal.RECUSADA]["qtd"] + r["por"][NotaFiscal.ERRO]["qtd"],
                "fila": r["por"][NotaFiscal.FILA]["qtd"] + r["por"][NotaFiscal.ENVIANDO]["qtd"],
                "emails": r["emails"].get(NotaFiscal.EMAIL_ENVIADO, 0),
            }
            email = servicos.andamento_emails(lote)
            resposta["lote"]["email"] = email
            resposta["lote"]["acompanhar"] = _acompanhar(lote, email)
    return JsonResponse(resposta)


@conta_requerida
def lote_zip(request, pk):
    """XML de todas as notas autorizadas do lote, mais uma planilha-resumo (CSV)."""
    import csv

    lote = get_object_or_404(LoteNotas, pk=pk, empresa__conta=conta_logada(request))
    memoria = io.BytesIO()
    resumo = io.StringIO()
    planilha = csv.writer(resumo, delimiter=";")
    planilha.writerow(["Loja", "ID da loja", "Tomador", "Documento", "Valor", "Situação", "Número NFS-e",
                       "Chave de acesso", "E-mail", "Situação do e-mail"])
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for nota in lote.notas.all().order_by("pk").iterator():
            planilha.writerow([nota.loja_nome, nota.loja_id, nota.tomador_nome, nota.tomador_documento,
                               str(nota.valor).replace(".", ","), nota.get_situacao_display(), nota.numero_nfse,
                               nota.chave, nota.tomador_email, nota.get_email_situacao_display()])
            if nota.xml_nfse:
                arquivo.writestr(f"xml/{danfse.nome_arquivo(nota, 'xml')}", nota.xml_nfse)
        arquivo.writestr("resumo.csv", "\ufeff" + resumo.getvalue())
    resposta = HttpResponse(memoria.getvalue(), content_type="application/zip")
    resposta["Content-Disposition"] = f'attachment; filename="notas-{lote.mes_referencia:%Y-%m}-{lote.pk}.zip"'
    return resposta


@require_POST
@conta_requerida
def reenviar(request, pk):
    nota = get_object_or_404(NotaFiscal, pk=pk, empresa__conta=conta_logada(request))
    if nota.situacao in (NotaFiscal.RECUSADA, NotaFiscal.ERRO):
        servicos.processar(nota)
    return _volta(request, nota)


@require_POST
@conta_requerida
def reenviar_email(request, pk):
    nota = get_object_or_404(NotaFiscal, pk=pk, empresa__conta=conta_logada(request))
    if nota.situacao == NotaFiscal.AUTORIZADA and nota.tomador_email and nota.ambiente == AMBIENTE_PRODUCAO:
        nota.email_situacao, nota.email_enviar_em = NotaFiscal.EMAIL_PENDENTE, None  # reenvio pedido: sai já
        nota.save(update_fields=["email_situacao", "email_enviar_em", "atualizada_em"])
        messages.info(request, "O e-mail vai sair de novo em alguns minutos.")
    return _volta(request, nota)


@conta_requerida
def pdf(request, pk):
    nota = get_object_or_404(NotaFiscal, pk=pk, empresa__conta=conta_logada(request))
    if not nota.xml_nfse:
        return HttpResponse(status=404)
    resposta = HttpResponse(danfse.pdf(nota.xml_nfse), content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{danfse.nome_arquivo(nota, "pdf")}"'
    return resposta


@conta_requerida
def xml(request, pk):
    nota = get_object_or_404(NotaFiscal, pk=pk, empresa__conta=conta_logada(request))
    if not nota.xml_nfse:
        return HttpResponse(status=404)
    resposta = HttpResponse(nota.xml_nfse, content_type="application/xml; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{danfse.nome_arquivo(nota, "xml")}"'
    return resposta
