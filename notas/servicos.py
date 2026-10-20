"""Regras do emissor de notas: cadastro da empresa e envio de cada nota ao governo.

O envio é feito de um jeito que nunca gera nota duplicada: cada nota tem série e número
fixos (o "Id" da DPS) e, se a resposta se perder no meio do caminho, a próxima tentativa
pergunta primeiro ao governo se aquela DPS já virou nota."""

import logging
import re
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from lxml import etree

from . import certificado, dps, receita
from .models import AMBIENTE_PRODUCAO, AMBIENTE_TESTE, EmpresaNotas, LoteNotas, NotaFiscal
from .sefin import ClienteSefin, ErroSefin

logger = logging.getLogger(__name__)
FUSO = ZoneInfo("America/Sao_Paulo")

# Tomador da nota da comissão da Shopee, como sai hoje no Emissor Nacional (nome e
# endereço do cadastro da Receita).
SHOPEE_CNPJ = "35635824000112"
SHOPEE_NOME = "SHPS TECNOLOGIA E SERVICOS LTDA."
SHOPEE = dps.Tomador("cnpj", SHOPEE_CNPJ, SHOPEE_NOME, municipio_ibge="3550308", cep="04538132",
                     logradouro="BRIG FARIA LIMA", numero="3732", complemento="ANDAR 22 E 23", bairro="ITAIM BIBI")
VALOR_TESTE = Decimal("1.00")
# Serviço que já vem preenchido (o das notas de afiliado de hoje: 17.06.01, propaganda e
# publicidade, inclusive promoção de vendas). A pessoa pode trocar na tela.
SERVICO_PADRAO_CODIGO = "170601"
SERVICO_PADRAO_DESCRICAO = "Divulgação e venda de produtos"
VALOR_MAXIMO = Decimal("999999.99")


class ErroNotas(ValueError):
    pass


def empresa_da_conta(conta):
    return EmpresaNotas.objects.filter(conta=conta).order_by("criada_em").first()


def cadastrar_empresa(conta, cnpj_digitado: str) -> EmpresaNotas:
    try:
        dados = receita.consultar(cnpj_digitado)
    except receita.ErroReceita as erro:
        raise ErroNotas(str(erro))
    if not dados["ativa"]:
        raise ErroNotas("Esse CNPJ não está ativo na Receita Federal.")
    if dados["regime"] not in ("mei", "simples"):
        raise ErroNotas("Por enquanto o emissor atende empresas do MEI e do Simples Nacional.")
    if not dados["municipio_ibge"]:
        raise ErroNotas("Não achei o município desse CNPJ na Receita. Fale com a gente.")
    empresa, _ = EmpresaNotas.objects.update_or_create(
        conta=conta, cnpj=dados["cnpj"],
        defaults={k: dados[k] for k in ("razao_social", "municipio_ibge", "municipio_nome", "uf", "regime")},
    )
    aplicar_servico_padrao(empresa)
    return empresa


def aplicar_servico_padrao(empresa):
    """Preenche o serviço padrão se a empresa ainda não tem um (nunca troca o que a pessoa salvou)."""
    if empresa.codigo_tributacao or empresa.descricao_servico:
        return
    empresa.codigo_tributacao, empresa.descricao_servico = SERVICO_PADRAO_CODIGO, SERVICO_PADRAO_DESCRICAO
    empresa.save(update_fields=["codigo_tributacao", "descricao_servico", "atualizada_em"])


def salvar_servico(empresa, codigo: str, codigo_municipal: str, descricao: str, inscricao_municipal: str):
    codigo = re.sub(r"\D", "", codigo or "")
    if len(codigo) != 6:
        raise ErroNotas("O código de tributação nacional tem 6 números (ex: 170601).")
    descricao = " ".join((descricao or "").split())
    if len(descricao) < 10:
        raise ErroNotas("Escreva a descrição do serviço (ela aparece em todas as notas).")
    empresa.codigo_tributacao = codigo
    empresa.codigo_municipal = re.sub(r"\s", "", codigo_municipal or "")[:20]
    empresa.descricao_servico = descricao[:2000]
    empresa.inscricao_municipal = re.sub(r"\D", "", inscricao_municipal or "")[:20]
    empresa.save(update_fields=["codigo_tributacao", "codigo_municipal", "descricao_servico",
                                "inscricao_municipal", "atualizada_em"])


def pronta_para_emitir(empresa) -> list[str]:
    """O que ainda falta para emitir (vazio = pode)."""
    falta = []
    if not empresa.tem_certificado:
        falta.append("o certificado digital A1")
    elif empresa.certificado_validade and empresa.certificado_validade <= timezone.now():
        falta.append("um certificado dentro da validade")
    if not (empresa.codigo_tributacao and empresa.descricao_servico):
        falta.append("o código e a descrição do serviço")
    return falta


def _proximo_numero(empresa_id: int, ambiente: str) -> tuple[str, int]:
    """Série e próximo número da DPS, sem dois envios pegarem o mesmo."""
    campo = "ultimo_numero_producao" if ambiente == AMBIENTE_PRODUCAO else "ultimo_numero_teste"
    with transaction.atomic():
        empresa = EmpresaNotas.objects.select_for_update().get(pk=empresa_id)
        numero = getattr(empresa, campo) + 1
        setattr(empresa, campo, numero)
        empresa.save(update_fields=[campo])
    return empresa.serie, numero


def criar_nota(empresa, *, ambiente, tipo, competencia, tomador: dps.Tomador, valor, situacao=NotaFiscal.FILA,
               **extra) -> NotaFiscal:
    return NotaFiscal.objects.create(
        empresa=empresa, ambiente=ambiente, tipo=tipo, competencia=competencia, situacao=situacao,
        tomador_tipo=tomador.tipo, tomador_documento=tomador.documento, tomador_nome=tomador.nome[:300],
        tomador_email=tomador.email, tomador_pais=tomador.pais, valor=valor, **extra,
    )


def _garantir_numero(nota):
    if nota.numero:
        return
    nota.serie, nota.numero = _proximo_numero(nota.empresa_id, nota.ambiente)
    nota.dps_id = dps.id_dps(nota.empresa.municipio_ibge, nota.empresa.cnpj, nota.serie, nota.numero)
    nota.save(update_fields=["serie", "numero", "dps_id"])


# Leiaute de cada ambiente. Começa assim (produção ainda no 1.01, testes já no novo) e
# troca sozinho se o governo recusar pelo leiaute (ver processar). O cache guarda a troca.
LEIAUTE_PADRAO = {AMBIENTE_PRODUCAO: dps.LEIAUTE_ATUAL, AMBIENTE_TESTE: dps.LEIAUTE_NOVO}


def leiaute(ambiente: str) -> str:
    from django.core.cache import cache

    return cache.get(f"notas:leiaute:{ambiente}") or LEIAUTE_PADRAO[ambiente]


def _guardar_leiaute(ambiente: str, valor: str):
    from django.core.cache import cache

    cache.set(f"notas:leiaute:{ambiente}", valor, 60 * 60 * 24 * 30)


def _montar_assinada(nota, cert, versao=None) -> bytes:
    e = nota.empresa
    agora = timezone.now().astimezone(FUSO)
    # Um minuto para trás: o governo recusa emissão "no futuro" se o relógio dele atrasar.
    # Logo depois da meia-noite isso cairia no dia anterior à competência: aí vai a hora certa.
    emitida_em = agora - timedelta(minutes=1)
    if emitida_em.date() < nota.competencia:
        emitida_em = agora
    raiz = dps.montar(
        ambiente=nota.ambiente,
        emitida_em=emitida_em,
        serie=nota.serie, numero=nota.numero, competencia=nota.competencia,
        prestador=dps.Prestador(e.cnpj, e.municipio_ibge, e.regime, e.inscricao_municipal),
        tomador=SHOPEE if nota.tomador_documento == SHOPEE_CNPJ else dps.Tomador(
            nota.tomador_tipo, nota.tomador_documento, nota.tomador_nome, nota.tomador_email, nota.tomador_pais),
        servico=dps.Servico(e.codigo_tributacao, e.descricao_servico, e.codigo_municipal),
        valor=nota.valor,
    )
    dps.validar(raiz)  # sempre confere no esquema oficial 1.01 antes
    if (versao or leiaute(nota.ambiente)) == dps.LEIAUTE_NOVO:
        dps.para_leiaute_novo(raiz)
    dps.assinar(raiz, cert.chave, cert.certificado)
    return dps.para_bytes(raiz)


def _numero_da_nfse(xml: str) -> str:
    try:
        achado = etree.fromstring(xml.encode("utf-8")).find(f".//{{{dps.NS}}}nNFSe")
        return achado.text if achado is not None else ""
    except etree.XMLSyntaxError:
        return ""


def _autorizar(nota, chave: str, xml: str, mensagens=None):
    nota.situacao = NotaFiscal.AUTORIZADA
    nota.chave = str(chave)[:50]
    nota.xml_nfse = xml
    nota.numero_nfse = _numero_da_nfse(xml)[:20] if xml else ""
    nota.mensagens = mensagens or []
    nota.autorizada_em = timezone.now()


def processar(nota: NotaFiscal, cert=None, cliente=None) -> NotaFiscal:
    """Envia uma nota (ou confere uma que ficou sem resposta). Nunca levanta exceção:
    o resultado fica na própria nota."""
    if nota.situacao in (NotaFiscal.AUTORIZADA, NotaFiscal.CANCELADA, NotaFiscal.PREVIA):
        return nota
    _garantir_numero(nota)
    nota.tentativas += 1
    nota.enviada_em = timezone.now()
    try:
        cert = cert or certificado.da_empresa(nota.empresa)
        cliente = cliente or ClienteSefin(nota.ambiente, cert)
        if nota.tentativas > 1:  # pode já ter virado nota numa tentativa que perdeu a resposta
            conferida = cliente.consultar_dps(nota.dps_id)
            chave = conferida.campo("chaveAcesso") if conferida.ok else ""
            if chave:
                consulta = cliente.consultar_nfse(chave)
                _autorizar(nota, chave, consulta.xml_nfse() if consulta.ok else "")
                nota.save()
                return nota
        resposta = cliente.emitir(_montar_assinada(nota, cert))
        outro = dps.leiaute_errado(resposta.mensagens) if not resposta.ok else ""
        if outro and outro != leiaute(nota.ambiente):
            # O governo mudou (ou está num) outro leiaute: troca e reenvia na hora.
            logger.info("Notas: ambiente %s passou a usar o leiaute %s.", nota.ambiente, outro)
            _guardar_leiaute(nota.ambiente, outro)
            resposta = cliente.emitir(_montar_assinada(nota, cert, outro))
        if resposta.ok and resposta.campo("chaveAcesso"):
            _autorizar(nota, resposta.campo("chaveAcesso"), resposta.xml_nfse(), resposta.mensagens)
        elif any(m["codigo"] == "E0014" for m in resposta.mensagens):
            # "Essa DPS já virou nota": a resposta anterior se perdeu. Busca a nota que já existe.
            conferida = cliente.consultar_dps(nota.dps_id)
            chave = conferida.campo("chaveAcesso") if conferida.ok else ""
            consulta = cliente.consultar_nfse(chave) if chave else None
            if chave and consulta.ok:
                _autorizar(nota, chave, consulta.xml_nfse())
            else:
                nota.situacao = NotaFiscal.ERRO
                nota.mensagens = resposta.mensagens
        else:
            nota.situacao = NotaFiscal.RECUSADA
            nota.mensagens = resposta.mensagens
    except (certificado.ErroCertificado, dps.ErroDPS) as erro:
        nota.situacao = NotaFiscal.RECUSADA
        nota.mensagens = [{"codigo": "", "descricao": str(erro)}]
    except ErroSefin as erro:
        nota.situacao = NotaFiscal.ERRO
        nota.mensagens = [{"codigo": "", "descricao": str(erro)}]
    except Exception:  # noqa: BLE001 - uma nota com problema não pode derrubar o lote
        logger.exception("Notas: erro inesperado ao processar a nota %s", nota.pk)
        nota.situacao = NotaFiscal.ERRO
        nota.mensagens = [{"codigo": "", "descricao": "Erro inesperado do nosso lado. Já estamos olhando."}]
    nota.save()
    return nota


def emitir_teste(empresa) -> NotaFiscal:
    """Uma nota de R$ 1,00 para a Shopee no ambiente de testes do governo (sem valor fiscal)."""
    falta = pronta_para_emitir(empresa)
    if falta:
        raise ErroNotas("Antes do teste, falta: " + " e ".join(falta) + ".")
    hoje = timezone.localdate()
    nota = criar_nota(empresa, ambiente=AMBIENTE_TESTE, tipo=NotaFiscal.TIPO_TESTE, competencia=hoje,
                      tomador=SHOPEE, valor=VALOR_TESTE)
    return processar(nota)


def emitir_nota_shopee(empresa, valor_digitado: str, ambiente=AMBIENTE_PRODUCAO) -> NotaFiscal:
    """A nota da comissão da própria Shopee (uma por mês). Vai para a fila do worker."""
    from .relatorio import ler_valor

    falta = pronta_para_emitir(empresa)
    if falta:
        raise ErroNotas("Antes de emitir, falta: " + " e ".join(falta) + ".")
    valor = ler_valor(valor_digitado)
    if valor is None or valor <= 0 or valor > VALOR_MAXIMO:
        raise ErroNotas("Digite o valor da comissão da Shopee (ex: 11.712,09).")
    return criar_nota(empresa, ambiente=ambiente, tipo=NotaFiscal.TIPO_SHOPEE, competencia=timezone.localdate(),
                      tomador=SHOPEE, valor=valor)


# ---------- Relatório Mensal da Shopee (uma nota por loja) ----------

def _ja_emitidas(empresa, ambiente, mes) -> set:
    """IDs de loja desse mês que já têm nota (ou estão na fila) em outro lote."""
    return set(NotaFiscal.objects.filter(
        empresa=empresa, ambiente=ambiente, tipo=NotaFiscal.TIPO_VENDEDOR, lote__mes_referencia=mes,
    ).exclude(situacao__in=[NotaFiscal.PREVIA, NotaFiscal.CANCELADA]).values_list("loja_id", flat=True))


def importar_relatorio(empresa, dados: bytes, nome_arquivo: str, ambiente=AMBIENTE_PRODUCAO) -> LoteNotas:
    """Lê o relatório e monta a prévia: uma nota por linha, sem enviar nada ainda."""
    from .relatorio import ErroRelatorio, ler

    try:
        linhas = ler(dados, nome_arquivo)
    except ErroRelatorio as erro:
        raise ErroNotas(str(erro))
    meses = {l.mes for l in linhas if l.mes}
    if not linhas or not meses:
        raise ErroNotas("Não achei nenhuma loja nesse relatório.")
    if len(meses) > 1:
        raise ErroNotas("Esse relatório tem mais de um mês de conclusão. Exporte um mês por vez.")
    mes = meses.pop()
    # Prévias antigas do mesmo mês saem (a pessoa está importando de novo).
    LoteNotas.objects.filter(empresa=empresa, ambiente=ambiente, mes_referencia=mes, estado=LoteNotas.PREVIA).delete()
    ja = _ja_emitidas(empresa, ambiente, mes)
    hoje = timezone.localdate()
    with transaction.atomic():
        lote = LoteNotas.objects.create(empresa=empresa, ambiente=ambiente, mes_referencia=mes, competencia=hoje,
                                        nome_arquivo=(nome_arquivo or "")[:200])
        ignoradas, notas, vistas = [], [], set()
        for l in linhas:
            motivo = ""
            if l.problemas:
                motivo = ", ".join(l.problemas)
            elif l.estrangeira and (not l.pais or l.pais == "BR"):
                motivo = "loja do exterior sem o país no relatório"
            elif l.loja_id in ja:
                motivo = "já tem nota deste mês"
            elif l.loja_id in vistas:
                motivo = "linha repetida no arquivo"
            elif l.valor > VALOR_MAXIMO:
                motivo = "valor acima do limite"
            if motivo:
                ignoradas.append({"linha": l.numero, "loja": l.loja_nome or l.loja_id, "nome": l.nome[:120],
                                  "valor": str(l.valor or ""), "motivo": motivo})
                continue
            vistas.add(l.loja_id)
            notas.append(NotaFiscal(
                empresa=empresa, lote=lote, ambiente=ambiente, tipo=NotaFiscal.TIPO_VENDEDOR, competencia=hoje,
                situacao=NotaFiscal.PREVIA, loja_id=l.loja_id, loja_nome=l.loja_nome,
                tomador_tipo=l.tipo_documento, tomador_documento=l.documento, tomador_nome=l.nome,
                tomador_email=l.email[:254], tomador_pais=l.pais if l.estrangeira else "", valor=l.valor,
            ))
        NotaFiscal.objects.bulk_create(notas, batch_size=500)
        lote.ignoradas = ignoradas
        lote.save(update_fields=["ignoradas"])
    return lote


def confirmar_lote(lote) -> int:
    falta = pronta_para_emitir(lote.empresa)
    if falta:
        raise ErroNotas("Antes de emitir, falta: " + " e ".join(falta) + ".")
    if lote.estado != LoteNotas.PREVIA:
        return 0
    hoje = timezone.localdate()
    envia_email = lote.ambiente == AMBIENTE_PRODUCAO
    with transaction.atomic():
        notas = lote.notas.filter(situacao=NotaFiscal.PREVIA)
        # Competência = dia em que a pessoa mandou emitir (não pode ser depois da emissão).
        com_email = notas.exclude(tomador_email="").update(
            situacao=NotaFiscal.FILA, competencia=hoje,
            email_situacao=NotaFiscal.EMAIL_PENDENTE if envia_email else NotaFiscal.EMAIL_NAO)
        sem_email = notas.update(situacao=NotaFiscal.FILA, competencia=hoje,
                                 email_situacao=NotaFiscal.EMAIL_SEM if envia_email else NotaFiscal.EMAIL_NAO)
        lote.estado, lote.competencia, lote.confirmado_em = LoteNotas.EMITINDO, hoje, timezone.now()
        lote.save(update_fields=["estado", "competencia", "confirmado_em"])
    return com_email + sem_email


def descartar_lote(lote):
    if lote.estado == LoteNotas.PREVIA:
        lote.delete()


def resumo(notas) -> dict:
    """Quantas notas em cada situação e o valor total (para a tela do lote)."""
    from django.db.models import Count, Sum

    por = {s: {"qtd": 0, "valor": Decimal("0")} for s, _ in NotaFiscal.SITUACOES}
    for linha in notas.values("situacao").annotate(qtd=Count("id"), valor=Sum("valor")):
        por[linha["situacao"]] = {"qtd": linha["qtd"], "valor": linha["valor"] or Decimal("0")}
    total = sum(v["qtd"] for v in por.values())
    emails = dict(notas.values_list("email_situacao").annotate(qtd=Count("id")))
    feitas = por[NotaFiscal.AUTORIZADA]["qtd"] + por[NotaFiscal.RECUSADA]["qtd"] + por[NotaFiscal.CANCELADA]["qtd"]
    return {"por": por, "total": total, "valor": sum((v["valor"] for v in por.values()), Decimal("0")),
            "emails": emails, "progresso": round(100 * feitas / total) if total else 0}
