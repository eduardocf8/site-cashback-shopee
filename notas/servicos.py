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

from . import certificado, dps, endereco, receita
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
# NBS que a tabela oficial (Anexo VIII da reforma) liga ao 17.06 com cIndOp 100301/cClassTrib
# 000001: 1.1406.11.00 "Serviços de campanhas publicitárias".
SERVICO_PADRAO_NBS = "114061100"
VALOR_MAXIMO = Decimal("999999.99")


class ErroNotas(ValueError):
    pass


# ---------- Plano: notas de verdade por mês ----------

# Notas que ocupam o plano: as que foram para a fila, saíram ou podem ter saído. Prévias,
# recusadas e canceladas não contam (a recusada volta a contar se for reenviada).
SITUACOES_QUE_CONTAM = [NotaFiscal.FILA, NotaFiscal.ENVIANDO, NotaFiscal.AUTORIZADA, NotaFiscal.ERRO]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def uso_do_plano(empresa, hoje=None) -> dict:
    """Notas de verdade (ambiente de produção) com competência no mês atual e o limite do plano.
    As do ambiente de testes não contam."""
    from licencas import planos

    hoje = hoje or timezone.localdate()
    usadas = NotaFiscal.objects.filter(
        empresa=empresa, ambiente=AMBIENTE_PRODUCAO, situacao__in=SITUACOES_QUE_CONTAM,
        competencia__year=hoje.year, competencia__month=hoje.month,
    ).count()
    limite = planos.notas_por_mes(empresa.conta)
    restam = None if limite is None else max(0, limite - usadas)
    return {"limite": limite, "usadas": usadas, "restam": restam, "mes": MESES[hoje.month - 1],
            "progresso": 0 if not limite else min(100, round(usadas * 100 / limite))}


def conferir_plano(empresa, quantas: int, ambiente: str):
    """Barra antes de mandar notas de verdade além do que o plano ainda tem no mês.
    Tudo ou nada: nunca emite só uma parte do lote."""
    if ambiente != AMBIENTE_PRODUCAO or quantas <= 0:
        return
    uso = uso_do_plano(empresa)
    if uso["restam"] is None or quantas <= uso["restam"]:
        return
    if quantas == 1:
        pedido = "Esta nota passaria do limite."
    else:
        pedido = f"Para enviar estas {quantas} notas, faltam {quantas - uso['restam']}."
    raise ErroNotas(
        f"Seu plano emite até {uso['limite']} notas por mês e restam {uso['restam']} em {uso['mes']}. {pedido} "
        "Nenhuma nota foi enviada. Passe para um plano maior em Seu plano para emitir todas.")


def empresa_da_conta(conta):
    return EmpresaNotas.objects.filter(conta=conta).order_by("criada_em").first()


def atualizar_cadastro(empresa) -> str:
    """Confere na Receita se a empresa continua MEI/Simples (ex: passou do limite do MEI e
    virou ME) e atualiza o cadastro. Devolve um aviso para a tela, ou "" se nada mudou.
    Se a Receita estiver fora do ar, segue com o que já está salvo."""
    try:
        dados = receita.consultar(empresa.cnpj)
    except receita.ErroReceita as erro:
        logger.info("Notas: não deu para conferir o regime de %s na Receita (%s).", empresa.cnpj, erro)
        return ""
    if dados["regime"] not in ("mei", "simples"):
        raise ErroNotas("Pela Receita Federal, a empresa não está mais no MEI nem no Simples Nacional. "
                        "Por enquanto o emissor atende só esses dois regimes.")
    if dados["regime"] == empresa.regime:
        return ""
    antes = empresa.get_regime_display()
    empresa.regime = dados["regime"]
    empresa.save(update_fields=["regime", "atualizada_em"])
    return f"O regime da empresa mudou na Receita: de {antes} para {empresa.get_regime_display()}. Já atualizamos o cadastro."


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
    if not empresa.codigo_nbs and empresa.codigo_tributacao in ("", SERVICO_PADRAO_CODIGO):
        empresa.codigo_nbs = SERVICO_PADRAO_NBS
        empresa.save(update_fields=["codigo_nbs", "atualizada_em"])
    if empresa.codigo_tributacao or empresa.descricao_servico:
        return
    empresa.codigo_tributacao, empresa.descricao_servico = SERVICO_PADRAO_CODIGO, SERVICO_PADRAO_DESCRICAO
    empresa.save(update_fields=["codigo_tributacao", "descricao_servico", "atualizada_em"])


def salvar_servico(empresa, codigo: str, codigo_municipal: str, descricao: str, inscricao_municipal: str, nbs: str = None):
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
    if nbs is not None:
        nbs = re.sub(r"\D", "", nbs)
        if nbs and len(nbs) != 9:
            raise ErroNotas("O código NBS tem 9 números (ex: 1.1406.11.00).")
        empresa.codigo_nbs = nbs
    empresa.save(update_fields=["codigo_tributacao", "codigo_municipal", "descricao_servico",
                                "inscricao_municipal", "codigo_nbs", "atualizada_em"])


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


# Campos novos da reforma que cada ambiente aceita (ver dps.CAMPOS_NOVOS). Começa assim e
# se ajusta sozinho quando o governo recusa pelo esquema (ver processar); o cache guarda.
CAMPOS_PADRAO = {AMBIENTE_PRODUCAO: frozenset(), AMBIENTE_TESTE: frozenset({"finNFSe", "IBSCBS", "IBSCBS.indDest"})}


def campos_novos(ambiente: str) -> frozenset:
    from django.core.cache import cache

    guardado = cache.get(f"notas:campos2:{ambiente}")
    return frozenset(guardado) if guardado is not None else CAMPOS_PADRAO[ambiente]


def _guardar_campos(ambiente: str, campos):
    from django.core.cache import cache

    cache.set(f"notas:campos2:{ambiente}", sorted(campos), 60 * 60 * 24 * 30)


_PADRAO = object()  # endereço do tomador: o de sempre (ver _endereco_do_tomador)


def _tomador(nota, campos, end=_PADRAO) -> dps.Tomador:
    if nota.tomador_documento == SHOPEE_CNPJ:
        return SHOPEE
    tomador = dps.Tomador(nota.tomador_tipo, nota.tomador_documento, nota.tomador_nome, nota.tomador_email,
                          nota.tomador_pais)
    if nota.tomador_tipo in ("cnpj", "cpf"):
        if end is _PADRAO:
            end = _endereco_do_tomador(nota, exigido="IBSCBS" in campos)
        if end:
            tomador.municipio_ibge, tomador.cep, tomador.logradouro = end["municipio_ibge"], end["cep"], end["logradouro"]
            tomador.numero = end.get("numero") or "S/N"
            tomador.complemento = end.get("complemento", "")
            tomador.bairro = end.get("bairro") or "-"
    return tomador


def _endereco_do_tomador(nota, exigido: bool) -> dict | None:
    """Endereço do vendedor: o do relatório da Shopee (município pela lista do IBGE). Se não der e a
    nota exigir endereço (com IBS/CBS, regra E0239), tenta o cadastro da Receita.
    Sem exigência, um endereço que não deu certo só fica de fora da nota."""
    try:
        end = endereco.do_relatorio(nota.tomador_endereco) if nota.tomador_endereco else None
        if end is None and exigido:
            end = _endereco_da_receita(nota)
    except receita.ReceitaFora:
        if exigido:
            raise
        return None
    if end is None and exigido:
        raise dps.ErroDPS("Não achei um endereço válido deste vendedor (nem no relatório da Shopee, nem na "
                          "Receita Federal), e a nota agora exige o endereço.")
    return end


def _endereco_da_receita(nota) -> dict | None:
    if nota.tomador_tipo != "cnpj":
        return None
    da_receita = receita.endereco(nota.tomador_documento)
    dados_cep = endereco.cep(da_receita.get("cep", "")) if endereco.completo(da_receita) else {}
    # O CEP da Receita às vezes é antigo e não existe mais (o governo recusaria com E0240).
    return {**da_receita, "municipio_ibge": dados_cep["municipio_ibge"]} if dados_cep else None


def _outros_enderecos(nota):
    """Outras versões do endereço do vendedor, para tentar quando o governo recusa o CEP com o
    endereço obrigatório: o do relatório com o município tirado do CEP, depois o da Receita."""
    fontes = [lambda: endereco.do_relatorio(nota.tomador_endereco, conferir_cep=True) if nota.tomador_endereco else None,
              lambda: _endereco_da_receita(nota)]
    for fonte in fontes:
        try:
            end = fonte()
        except receita.ErroReceita:  # inclui ReceitaFora: fica com a recusa que já tem
            end = None
        if end:
            yield end


# Recusas por causa do endereço do tomador (CEP que não existe ou não é do município etc.).
REGRAS_ENDERECO_TOMADOR = {"E0239", "E0240"}


def _recusa_de_endereco(mensagens) -> bool:
    return any(m.get("codigo") in REGRAS_ENDERECO_TOMADOR
               or ("endereço" in (m.get("descricao") or "").lower() and "tomador" in (m.get("descricao") or "").lower())
               for m in mensagens)


def _montar_assinada(nota, cert, campos=None, end=_PADRAO) -> bytes:
    campos = campos_novos(nota.ambiente) if campos is None else campos
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
        tomador=_tomador(nota, campos, end),
        servico=dps.Servico(e.codigo_tributacao, e.descricao_servico, e.codigo_municipal,
                            e.codigo_nbs if "IBSCBS" in campos else ""),
        valor=nota.valor,
    )
    dps.validar(raiz)  # sempre confere no esquema oficial 1.01 antes
    dps.com_campos_novos(raiz, campos)
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


def _reenviar_com_outro_endereco(nota, cert, cliente, campos, resposta):
    """O governo recusou o endereço do vendedor (ex: E0240, CEP que a base dele não conhece).
    Sem IBS/CBS o endereço é opcional: vai sem. Com IBS/CBS ele é obrigatório: tenta as outras
    versões do endereço que sejam diferentes da recusada."""
    if "IBSCBS" not in campos:
        if not nota.tomador_endereco:
            return resposta  # não foi endereço nenhum: nada a tirar
        nova = cliente.emitir(_montar_assinada(nota, cert, campos, end=None))
        return nova if nova.ok else resposta
    enviado = _endereco_do_tomador(nota, exigido=True)
    tentados = {(enviado["cep"], enviado["municipio_ibge"])}
    for outro in _outros_enderecos(nota):
        if (outro["cep"], outro["municipio_ibge"]) in tentados:
            continue
        tentados.add((outro["cep"], outro["municipio_ibge"]))
        nova = cliente.emitir(_montar_assinada(nota, cert, campos, end=outro))
        if nova.ok or not _recusa_de_endereco(nova.mensagens):
            return nova
    return resposta


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
        campos = campos_novos(nota.ambiente)
        resposta = cliente.emitir(_montar_assinada(nota, cert, campos))
        for _ in range(8):  # o governo mudou o esquema: ajusta e reenvia na hora
            ajustados = dps.ajuste_de_campos(resposta.mensagens, campos) if not resposta.ok else None
            if ajustados is None:
                break
            logger.warning("Notas: ambiente %s recusou %s; tentando com os campos novos %s.", nota.ambiente,
                           [f"{m['codigo']} {m['descricao'][:300]}" for m in resposta.mensagens], sorted(ajustados))
            campos = ajustados
            _guardar_campos(nota.ambiente, campos)
            resposta = cliente.emitir(_montar_assinada(nota, cert, campos))
        if not resposta.ok and any(m["codigo"] == "E0160" for m in resposta.mensagens):
            # Regime errado para o governo (ex: virou ME e a base pública ainda dizia MEI):
            # tenta com o outro regime; se passar, o cadastro fica com ele.
            empresa = nota.empresa
            antes = empresa.regime
            empresa.regime = "simples" if antes == "mei" else "mei"
            nova = cliente.emitir(_montar_assinada(nota, cert, campos))
            if nova.ok:
                logger.info("Notas: regime de %s corrigido de %s para %s (E0160).", empresa.cnpj, antes, empresa.regime)
                empresa.save(update_fields=["regime", "atualizada_em"])
                resposta = nova
            else:
                empresa.regime = antes
        if not resposta.ok and _recusa_de_endereco(resposta.mensagens) and nota.tomador_tipo in ("cnpj", "cpf"):
            resposta = _reenviar_com_outro_endereco(nota, cert, cliente, campos, resposta)
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
    except receita.ReceitaFora as erro:  # consulta do endereço fora do ar: tenta de novo depois
        nota.situacao = NotaFiscal.ERRO
        nota.mensagens = [{"codigo": "", "descricao": str(erro)}]
    except (certificado.ErroCertificado, dps.ErroDPS, receita.ErroReceita) as erro:
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
    conferir_plano(empresa, 1, ambiente)
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
        ignoradas, notas, vistas, sem_endereco = [], [], set(), []
        for l in linhas:
            motivo = ""
            if l.problemas:
                motivo = ", ".join(l.problemas)
            elif l.estrangeira and (not l.pais or l.pais == "BR"):
                motivo = "loja do exterior sem o país no relatório"
            elif l.loja_id in ja:
                motivo = "já tem nota deste mês"
                if l.endereco:
                    sem_endereco.append((l.loja_id, l.endereco))
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
                tomador_endereco=l.endereco,
            ))
        NotaFiscal.objects.bulk_create(notas, batch_size=500)
        # Notas criadas antes de o endereço ser guardado: importar o relatório de novo completa
        # o endereço delas, para o "Tentar de novo" funcionar.
        for loja_id, texto in sem_endereco:
            NotaFiscal.objects.filter(
                empresa=empresa, ambiente=ambiente, tipo=NotaFiscal.TIPO_VENDEDOR, lote__mes_referencia=mes,
                loja_id=loja_id, tomador_endereco="").exclude(situacao=NotaFiscal.AUTORIZADA).update(
                tomador_endereco=texto)
        lote.ignoradas = ignoradas
        lote.save(update_fields=["ignoradas"])
    return lote


def proximo_envio_de_email(empresa, a_partir=None):
    """Quando os e-mails podem sair, conforme o horário escolhido pela empresa: a próxima vez que
    der aquela hora (horário de Brasília) a partir de agora. None = logo que der."""
    if empresa.email_horario is None:
        return None
    local = (a_partir or timezone.now()).astimezone(FUSO)
    horario = local.replace(hour=empresa.email_horario, minute=0, second=0, microsecond=0)
    return horario if horario >= local else horario + timedelta(days=1)


def salvar_horario_dos_emails(empresa, hora) -> int:
    """Guarda o horário (None = logo depois das notas) e reagenda os e-mails que ainda não saíram.
    Devolve quantos e-mails foram reagendados."""
    empresa.email_horario = hora
    empresa.save(update_fields=["email_horario", "atualizada_em"])
    return NotaFiscal.objects.filter(empresa=empresa, email_situacao=NotaFiscal.EMAIL_PENDENTE).update(
        email_enviar_em=proximo_envio_de_email(empresa))


def confirmar_lote(lote) -> int:
    falta = pronta_para_emitir(lote.empresa)
    if falta:
        raise ErroNotas("Antes de emitir, falta: " + " e ".join(falta) + ".")
    if lote.estado != LoteNotas.PREVIA:
        return 0
    conferir_plano(lote.empresa, lote.notas.filter(situacao=NotaFiscal.PREVIA).count(), lote.ambiente)
    hoje = timezone.localdate()
    envia_email = lote.ambiente == AMBIENTE_PRODUCAO
    with transaction.atomic():
        notas = lote.notas.filter(situacao=NotaFiscal.PREVIA)
        # Competência = dia em que a pessoa mandou emitir (não pode ser depois da emissão).
        com_email = notas.exclude(tomador_email="").update(
            situacao=NotaFiscal.FILA, competencia=hoje,
            email_situacao=NotaFiscal.EMAIL_PENDENTE if envia_email else NotaFiscal.EMAIL_NAO,
            email_enviar_em=proximo_envio_de_email(lote.empresa) if envia_email else None)
        sem_email = notas.update(situacao=NotaFiscal.FILA, competencia=hoje,
                                 email_situacao=NotaFiscal.EMAIL_SEM if envia_email else NotaFiscal.EMAIL_NAO)
        lote.estado, lote.competencia, lote.confirmado_em = LoteNotas.EMITINDO, hoje, timezone.now()
        lote.save(update_fields=["estado", "competencia", "confirmado_em"])
    return com_email + sem_email


def reenviar_problemas(lote) -> int:
    """Põe de volta na fila as notas do lote que deram problema. As recusadas voltam a ocupar o
    plano; as sem resposta já ocupavam."""
    problemas = lote.notas.filter(situacao__in=[NotaFiscal.RECUSADA, NotaFiscal.ERRO])
    conferir_plano(lote.empresa, problemas.filter(situacao=NotaFiscal.RECUSADA).count(), lote.ambiente)
    quantas = problemas.update(situacao=NotaFiscal.FILA)
    if quantas and lote.estado == LoteNotas.CONCLUIDO:
        lote.estado = LoteNotas.EMITINDO
        lote.save(update_fields=["estado"])
    return quantas


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


def andamento_emails(lote) -> dict | None:
    """Envio dos e-mails do lote para os vendedores (só produção): quantos já foram, quantos
    faltam e em que fase está. None quando não há e-mail a mandar (testes ou prévia)."""
    from django.db.models import Count

    if lote.ambiente != AMBIENTE_PRODUCAO or lote.estado == LoteNotas.PREVIA:
        return None
    autorizadas = lote.notas.filter(situacao=NotaFiscal.AUTORIZADA)
    qtd = dict(autorizadas.values_list("email_situacao").annotate(qtd=Count("id")))
    enviados, falharam = qtd.get(NotaFiscal.EMAIL_ENVIADO, 0), qtd.get(NotaFiscal.EMAIL_FALHOU, 0)
    # Sem o XML da nota não há o que mandar (fica de fora para a barra não esperar para sempre).
    a_enviar = autorizadas.filter(email_situacao=NotaFiscal.EMAIL_PENDENTE).exclude(xml_nfse="")
    pendentes = a_enviar.count()
    alvo = enviados + falharam + pendentes
    agora = timezone.now()
    agendado = a_enviar.filter(email_enviar_em__gt=agora).order_by("email_enviar_em").values_list(
        "email_enviar_em", flat=True).first()
    if agendado is None and lote.estado == LoteNotas.EMITINDO:
        agendado = proximo_envio_de_email(lote.empresa, lote.confirmado_em)
        agendado = agendado if agendado and agendado > agora else None
    # E-mails que já podem sair agora (os agendados para mais tarde não contam).
    saindo = pendentes - a_enviar.filter(email_enviar_em__gt=agora).count()
    quando = _quando(agendado) if agendado else ""
    if lote.estado == LoteNotas.EMITINDO:
        fase = f"Os e-mails estão agendados para {quando}." if quando else \
            "Os e-mails saem assim que todas as notas terminarem de sair."
        situacao = "agendado" if quando else "aguardando"
    elif saindo:
        fase, situacao = "Enviando os e-mails…", "enviando"
    elif pendentes and quando:
        fase, situacao = f"Agendados para {quando}.", "agendado"
    else:
        fase, situacao = "Concluído.", "concluido"
    return {"enviados": enviados, "falharam": falharam, "sem_email": qtd.get(NotaFiscal.EMAIL_SEM, 0),
            "pendentes": pendentes, "saindo": saindo, "alvo": alvo,
            "progresso": round(100 * (enviados + falharam) / alvo) if alvo else 0, "fase": fase, "situacao": situacao}


def _quando(momento) -> str:
    local = momento.astimezone(FUSO)
    hoje = timezone.now().astimezone(FUSO).date()
    dia = "hoje" if local.date() == hoje else ("amanhã" if local.date() == hoje + timedelta(days=1)
                                               else local.strftime("%d/%m"))
    return f"{dia} às {local:%H:%M}"
