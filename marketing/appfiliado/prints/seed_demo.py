import os
AQUI = os.path.dirname(os.path.abspath(__file__))
import datetime as dt, random, io
from decimal import Decimal as D
from django.utils import timezone
from licencas.models import ContaAppfiliado
from painel import cripto
from painel.models import MetaMensal, RegraSubId, ResultadoDiario, ResultadoSubIdDiario, SincronizacaoResultados, VendaItem
from ofertas.models import Oferta, SincronizacaoCatalogo
from bot_whatsapp.models import (AlertaDisparado, AlertaPreco, CampanhaBot, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp,
                                 EventoWhatsApp, ProdutoAcompanhado)
from meusite.models import BotaoSite, ProdutoSite, SiteAfiliado
from carrosseis.models import Carrossel
from carrosseis import ia, servicos
FOTO_FONE = AQUI + "/img/fone.jpg"
from notas.models import EmpresaNotas, LoteNotas, NotaFiscal

IMG = "http://localhost:8766/img/{}.jpg"
agora = timezone.now(); hoje = timezone.localdate()
random.seed(11)
c, _ = ContaAppfiliado.objects.get_or_create(email="bia@exemplo.com")
c.modulos_cortesia = "whatsapp_premium,site_sem_marca,carrosseis_premium,notas"
c.shopee_app_id = "18300000001"; c.shopee_secret_cifrado = cripto.cifrar("demo"); c.shopee_validado_em = agora
c.nome = "Bia Ferreira"; c.definir_senha("uma-senha-boa-123"); c.save()

# (chave, nome, preço, desconto, comissão, extra, vendas, nota, cat_id, cat_nome, loja)
P = [
 ("fone","Fone de Ouvido Bluetooth TWS com Cancelamento de Ruído",79.90,45,12,4,15800,4.8,100013,"Celulares e Dispositivos","Tech Plus Oficial"),
 ("airfryer","Air Fryer Digital 4L com Timer e Painel Touch",329.90,28,8,0,8900,4.9,100010,"Eletrodomésticos","Casa & Cozinha"),
 ("garrafa","Garrafa Térmica Inox 1L Parede Dupla",49.90,32,11,3,12400,4.9,100636,"Casa e Decoração","Utilidades BR"),
 ("mochila","Mochila Notebook Impermeável com Entrada USB",119.90,40,14,6,5400,4.7,100533,"Bolsas Masculinas","Bags Store"),
 ("relogio","Smartwatch D20 com Monitor Cardíaco",89.90,55,10,0,31200,4.6,100534,"Relógios","Smart Time"),
 ("luminaria","Luminária LED de Mesa Recarregável Touch",34.99,25,9,0,6700,4.8,100636,"Casa e Decoração","Luz & Cia"),
 ("tenis","Tênis Esportivo Leve Running Unissex",139.90,38,13,5,9300,4.7,100012,"Sapatos Masculinos","Run Store"),
 ("urso","Urso de Pelúcia Gigante 60cm Macio",59.90,30,12,0,4100,4.9,100633,"Moda Infantil","Mundo Kids"),
 ("batom","Batom Matte Longa Duração Cor Nude",19.90,42,15,5,22100,4.8,100630,"Beleza","Beauty Box"),
 ("panela","Jogo de Panelas Antiaderente 5 Peças",189.90,35,9,0,3300,4.7,100010,"Eletrodomésticos","Casa & Cozinha"),
 ("tapete","Tapete Felpudo Antiderrapante 1,5m",69.90,33,12,0,7800,4.8,100636,"Casa e Decoração","Utilidades BR"),
 ("camera","Câmera de Segurança Wi-Fi 360° Full HD",99.90,44,10,3,6100,4.6,100635,"Câmeras e Drones","Tech Plus Oficial"),
 ("violao","Violão Acústico Iniciante com Capa",259.90,22,8,0,1800,4.8,100639,"Hobbies e Coleções","Música Já"),
 ("planta","Kit 3 Vasos Decorativos com Prato",44.90,36,13,0,5200,4.9,100636,"Casa e Decoração","Verde Casa"),
 ("bolsa","Bolsa Transversal Feminina Couro Sintético",74.90,41,14,4,8800,4.7,100016,"Bolsas Femininas","Bella Bags"),
 ("bike","Bicicleta Ergométrica Dobrável",449.90,20,7,0,950,4.5,100637,"Esportes e Atividades ao Ar Livre","Fit Casa"),
 ("copo","Copo Térmico 1,2L com Canudo e Alça",39.90,48,12,3,26400,4.9,100636,"Casa e Decoração","Utilidades BR"),
 ("controle","Controle Gamer Sem Fio para PC e Celular",84.90,37,10,0,4700,4.6,100634,"Jogos e Consoles","Game Hub"),
 ("secador","Secador de Cabelo Profissional 2000W",129.90,34,11,4,6900,4.8,100630,"Beleza","Beauty Box"),
 ("tv","Suporte Articulado de Parede para TV 32-65\"",54.90,29,10,0,3900,4.8,100010,"Eletrodomésticos","Casa & Cozinha"),
 ("fritadeira","Fritadeira Elétrica Forno Oven 12L",299.90,31,8,0,2400,4.7,100010,"Eletrodomésticos","Casa & Cozinha"),
 ("vaso","Vaso Cerâmica Decorativo Nórdico",29.90,39,13,0,3600,4.8,100636,"Casa e Decoração","Verde Casa"),
 ("livro","Kit 3 Livros Best-Sellers de Desenvolvimento",64.90,46,12,0,2700,4.9,100643,"Livros e Revistas","Livraria Já"),
 ("kit","Maleta de Ferramentas 129 Peças",109.90,43,11,5,5800,4.7,100640,"Automóveis","Auto Pró"),
]
Oferta.objects.all().delete()
for i, (k, nome, preco, desc, com, ext, vend, nota, cid, cnome, loja) in enumerate(P):
    Oferta.objects.create(item_id=900000 + i, nome=nome, nome_curto=nome[:48], imagem_url=IMG.format(k), preco_min=D(str(preco)), preco_max=D(str(preco)),
        percentual_desconto=desc, percentual_comissao=D(str(com))/100, percentual_comissao_extra=D(str(ext))/100, avaliacao=D(str(nota)), vendas=vend,
        categoria_id=cid, categoria_nome=cnome, loja_nome=loja, product_link=f"https://shopee.com.br/p-i.1.{900000+i}", visto_em=agora)
SincronizacaoCatalogo.objects.all().delete()
SincronizacaoCatalogo.objects.create(rodada=hoje, completa=True, ultima_completa=hoje, iniciada_em=agora - dt.timedelta(hours=3), finalizada_em=agora - dt.timedelta(hours=2), produtos_vistos=30412)

# ---- resultados e metas (mês corrente; meta no ritmo) ----
ResultadoDiario.objects.filter(conta=c).delete(); ResultadoSubIdDiario.objects.filter(conta=c).delete()
for i in range(88):
    dia = hoje - dt.timedelta(days=i)
    base = 1900 + 700 * (dia.weekday() in (4, 5, 6)) + random.randint(-400, 800)
    fat = D(base) + D(random.randint(0, 99)) / 100
    est = (fat * D("0.085")).quantize(D("0.01"))
    val = (est * D("0.92")).quantize(D("0.01")) if i > 20 else (est * D(str(i / 30))).quantize(D("0.01"))
    ResultadoDiario.objects.create(conta=c, dia=dia, pedidos=base // 38, faturamento=fat, comissao_estimada=est, comissao_validada=val)
    for sub, peso in (("grupo_ofertas", 0.42), ("grupo_vip", 0.24), ("instagram", 0.17), ("site", 0.10), ("sem_subid", 0.07)):
        ResultadoSubIdDiario.objects.create(conta=c, dia=dia, sub_id=sub, vendas=max(1, int(base // 38 * peso)), comissao_estimada=(est * D(str(peso))).quantize(D("0.01")))
SincronizacaoResultados.objects.update_or_create(conta=c, defaults=dict(iniciada_em=agora - dt.timedelta(minutes=12), concluida_em=agora - dt.timedelta(minutes=11),
    cobertura_inicio=hoje - dt.timedelta(days=87), pedido_em=None, erro=""))
MetaMensal.objects.update_or_create(conta=c, ano=hoje.year, mes=hoje.month, defaults={"faixas": [
    {"percentual": 100, "faturamento": 52000, "bonus": 300}, {"percentual": 125, "faturamento": 65000, "bonus": 500}, {"percentual": 150, "faturamento": 78000, "bonus": 800}]})
RegraSubId.objects.filter(conta=c).delete()
RegraSubId.objects.create(conta=c, operador="comeca", texto="grupo", nome="Grupos de WhatsApp")
RegraSubId.objects.create(conta=c, operador="sem", texto="", nome="Orgânico")
VendaItem.objects.filter(conta=c).delete()
st = ["COMPLETED", "PENDING", "COMPLETED", "COMPLETED", "CANCELLED"]
for n in range(70):
    k = random.choices(range(len(P)), weights=[w[6] for w in P])[0]; pr = P[k]; q = random.choice([1, 1, 1, 2, 3]); valor = D(str(pr[2])) * q
    s = random.choice(st); sit = {"COMPLETED": "concluido", "PENDING": "pendente", "CANCELLED": "cancelado"}[s]
    comp = agora - dt.timedelta(hours=random.randint(1, 24 * 12), minutes=random.randint(0, 59))
    VendaItem.objects.create(conta=c, conversao_id=f"C{n}", pedido_id=f"P{n}", item_id=str(900000 + k), nome=pr[1], imagem_url=IMG.format(pr[0]), loja=pr[10],
        quantidade=q, preco=D(str(pr[2])), valor=valor, comissao=(valor * D(pr[4]) / 100).quantize(D("0.01")), status_shopee=s, situacao=sit,
        sub_id=random.choice(["grupo_ofertas", "grupo_vip", "instagram", "site", "sem_subid"]), comprado_em=comp, concluido_em=comp + dt.timedelta(days=3) if s == "COMPLETED" else None)

# ---- bot ----
GRUPOS = [{"jid": "1@g.us", "nome": "Achadinhos da Bia VIP", "tipo": "grupo", "participantes": 912}, {"jid": "2@g.us", "nome": "Ofertas do Dia 🔥", "tipo": "grupo", "participantes": 640},
          {"jid": "3@newsletter", "nome": "Achadinhos da Bia", "tipo": "canal", "participantes": 2310}]
ConexaoWhatsApp.objects.update_or_create(conta=c, defaults=dict(estado="conectado", numero="5545999990000", nome="Bia Achadinhos", conectado_em=agora - dt.timedelta(days=6), grupos=GRUPOS, grupos_em=agora))
EventoWhatsApp.objects.filter(conta=c).delete()
for t, d, h in [("conectado", "Conectado", 24 * 6), ("desconectado", "Conexão caiu", 50), ("conectado", "Voltou sozinho", 49)]:
    e = EventoWhatsApp.objects.create(conta=c, tipo=t, detalhe=d); EventoWhatsApp.objects.filter(pk=e.pk).update(criado_em=agora - dt.timedelta(hours=h))
cfg, _ = ConfiguracaoOfertas.objects.get_or_create(conta=c)
cfg.ativo = True; cfg.grupos = [{"jid": g["jid"], "nome": g["nome"]} for g in GRUPOS[:2]]; cfg.intervalo_minutos = 10; cfg.limite_diario = 120
cfg.comissao_minima = 8; cfg.desconto_minimo = 20; cfg.avaliacao_minima = D("4.5"); cfg.sub_ids = "grupo_ofertas, grupo_vip"; cfg.cupom = "BIA10"
cfg.categorias = [100636, 100013, 100630]; cfg.save()
EnvioWhatsApp.objects.filter(conta=c).delete()
msg = "🔥 *{n}*\n\n💰 *R$ {p}* ({d}% OFF)\n⭐ 4,8 | {v} vendidos\n\n🛒 Compre aqui: https://s.shopee.com.br/8Kz1aQ\n\nCorre que acaba rápido!"
for i, k in enumerate([0, 8, 16, 2, 5, 12]):
    pr = P[k]; e = EnvioWhatsApp.objects.create(conta=c, destino="1@g.us", destino_nome="Achadinhos da Bia VIP", origem="oferta", item_id=str(900000 + k), produto=pr[1],
        texto=msg.format(n=pr[1], p=f"{pr[2]:.2f}".replace(".", ","), d=pr[3], v=pr[6]), estado="enviado", imagem_url=IMG.format(pr[0]), enviado_em=agora - dt.timedelta(minutes=12 * i + 3), formato="foto")
    EnvioWhatsApp.objects.filter(pk=e.pk).update(criado_em=agora - dt.timedelta(minutes=12 * i + 4))
al, _ = AlertaPreco.objects.get_or_create(conta=c); al.ativo = True; al.intervalo_minutos = 15; al.queda_minima = 10; al.avisar_email = True; al.enviar_grupos = True
al.ultima_conferencia_em = agora - dt.timedelta(minutes=6); al.proxima_conferencia_em = agora + dt.timedelta(minutes=9); al.save()
ProdutoAcompanhado.objects.filter(conta=c).delete(); AlertaDisparado.objects.filter(conta=c).delete()
seg = [(3, 119.90, 99.90), (6, 139.90, 139.90), (18, 129.90, 99.90), (20, 299.90, 299.90), (14, 74.90, 74.90), (11, 99.90, 99.90), (15, 449.90, 449.90), (1, 329.90, 329.90)]
for k, ini, atual in seg:
    pr = P[k]; hist = [[(agora - dt.timedelta(days=8)).strftime("%Y-%m-%dT%H:%M"), ini]] + ([[(agora - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"), atual]] if atual != ini else [])
    pa = ProdutoAcompanhado.objects.create(conta=c, item_id=str(900000 + k), nome=pr[1], imagem=IMG.format(pr[0]), link=f"https://shopee.com.br/p-i.1.{900000+k}",
        preco_inicial=D(str(ini)), preco_atual=D(str(atual)), menor_preco=D(str(min(ini, atual))), referencia=D(str(atual)), historico=hist, conferido_em=agora - dt.timedelta(minutes=6))
    if atual < ini:
        AlertaDisparado.objects.create(conta=c, produto=pa, nome=pr[1], imagem=IMG.format(pr[0]), preco_antes=D(str(ini)), preco_agora=D(str(atual)),
            queda=D(str(round((ini - atual) / ini * 100, 1))), enviado_email=True, postado_grupos=True, visto=False)
cam, _ = CampanhaBot.objects.get_or_create(conta=c); cam.ativo = True; cam.intervalo_minutos = 4; cam.limite_diario = 300; cam.frase_abertura = "🛍️ 11.11: as melhores ofertas do ano"; cam.cupom = "BIA11"
cam.pagina_ativa = True; cam.link_campanha = "https://shopee.com.br/m/11-11"; cam.link_campanha_a_cada = 10; cam.save()

# ---- site ----
SiteAfiliado.objects.filter(conta=c).delete()
foto = open(AQUI + "/img/bolsa.jpg", "rb").read()
s = SiteAfiliado.objects.create(conta=c, endereco="achadinhosdabia", nome="Achadinhos da Bia", frase="As melhores ofertas da Shopee, todo dia ✨", cor="#D6336C", vitrine="bot", vitrine_formato="carrossel",
    redes={"instagram": "https://instagram.com/achadinhosdabia", "tiktok": "https://tiktok.com/@achadinhosdabia", "whatsapp": "5545999990000"}, foto=foto, foto_versao=1)
for i, (t, d) in enumerate([("💬 Entrar no grupo VIP de ofertas", True), ("📣 Canal de ofertas no WhatsApp", False), ("🎟️ Cupons do dia", False), ("📸 Meu Instagram", False)]):
    BotaoSite.objects.create(site=s, texto=t, url="https://example.com", destaque=d, ordem=i)
for i, k in enumerate([0, 8, 16, 2, 5, 12]):
    pr = P[k]; ProdutoSite.objects.create(site=s, fonte="bot", item_id=str(900000 + k), nome=pr[1], imagem_url=IMG.format(pr[0]), preco=D(str(pr[2])), preco_original=(D(str(pr[2])) / (1 - D(pr[3]) / 100)).quantize(D("0.01")),
        desconto=pr[3], categoria="casa", link_produto=f"https://shopee.com.br/p-i.1.{900000+k}", posicao_em=agora - dt.timedelta(minutes=i))

# ---- carrossel ----
Carrossel.objects.filter(conta=c).delete()
prod = {"nome": P[0][1], "preco": 79.90, "de": 145.20, "desconto": 45, "nota": 4.8, "vendas": 15800, "imagem": IMG.format("fone"), "loja": "Tech Plus Oficial", "link": "https://s.shopee.com.br/8Kz1aQ"}
dados = {"nome_curto": "Fone Bluetooth TWS", "arte": "tech", "capa": {"selo": "Achado da semana", "titulo": "Fone *sem fio* com 45% off"},
 "problema": {"rotulo": "Sabe quando", "titulo": "O fio *enrosca* toda hora?", "texto": "Música sem fio e sem enrosco, do treino ao ônibus."},
 "chips": ["Cancela ruído", "Bluetooth", "Estojo carregador"], "prova": {"titulo": "Quem comprou *aprovou*", "texto": "Nota 4,8 e mais de 15 mil vendidos na Shopee."},
 "cta": {"titulo": "Quer o seu?"}, "final": {"titulo": "Gostou? *Salva* e compartilha", "text": ""},
 "vantagens": {"rotulo": "Por que vale a pena", "titulo": "Vale *muito* a pena", "itens": ["Cancelamento de ruído", "Estojo que carrega", "Conexão rápida"]},
 "numeros": {"rotulo": "Em números", "titulo": "Em *números*", "numeros": [{"valor": "-45%", "legenda": "de desconto hoje"}, {"valor": "4,8", "legenda": "de nota na Shopee"}, {"valor": "15,8 mil", "legenda": "vendidos"}]},
 "qualidades": {"rotulo": "Em detalhes", "titulo": "Os *detalhes*", "itens": ["Graves fortes", "Toque touch", "Leve no ouvido", "Estojo compacto"]},
 "legenda": "Achei o fone ideal pra quem treina e pega ônibus todo dia 🎧 Cancelamento de ruído, estojo que carrega e 45% off. Link na bio!", "hashtags": ["fonebluetooth", "achadinhos"]}
import json
from unittest import mock
from carrosseis import roteiro as R
with mock.patch.object(ia.gemini, "disponivel", return_value=True), mock.patch.object(ia.gemini, "_chamar", return_value=json.dumps(dados)):
    roteiros, _ = ia.gerar(prod)
foto = open(FOTO_FONE, "rb").read()
op = servicos.opcoes_iniciais(c); op.update({"modelo": "vitrine", "tema": "verde", "arroba": "@achadinhosdabia"})
Carrossel.objects.create(conta=c, item_id="900000", link_original="https://shopee.com.br/p-i.1.900000", produto=prod,
    roteiros={f: roteiros[f] for f in (R.PADRAO, R.PREMIUM)}, originais={f: {str(sl["_id"]): sl for sl in roteiros[f]} for f in (R.PADRAO, R.PREMIUM)},
    opcoes=op, foto_propria=foto, legenda=roteiros["legenda"], hashtags=roteiros["hashtags"])

# ---- notas ----
EmpresaNotas.objects.filter(conta=c).delete()
e = EmpresaNotas.objects.create(conta=c, cnpj="12345678000195", razao_social="BIA ACHADINHOS LTDA", municipio_ibge="3550308", municipio_nome="São Paulo", uf="SP", regime="mei",
    codigo_tributacao="170601", descricao_servico="Divulgação e venda de produtos", certificado_cifrado="x", senha_cifrada="x", certificado_titular="BIA ACHADINHOS LTDA",
    certificado_validade=dt.date(2027, 5, 1))
lote = LoteNotas.objects.create(empresa=e, ambiente="1", mes_referencia=dt.date(hoje.year, hoje.month, 1) - dt.timedelta(days=1), competencia=hoje, nome_arquivo="MonthlyReport_202609.csv", estado="concluido")
lojas = ["Utilidades BR", "Tech Plus Oficial", "Beauty Box", "Casa & Cozinha", "Bella Bags", "Smart Time", "Mundo Kids", "Verde Casa", "Run Store", "Game Hub"]
notas = []
for i in range(86):
    nome = f"{lojas[i % len(lojas)].upper()} {i//len(lojas)+1} LTDA"
    em = "enviado" if i < 70 else ("pendente" if i < 83 else "sem_email")
    notas.append(NotaFiscal(empresa=e, lote=lote, ambiente="1", tipo="vendedor", competencia=hoje, situacao="autorizada", loja_id=str(1000 + i), loja_nome=lojas[i % len(lojas)],
        tomador_tipo="cnpj", tomador_documento=f"11222333{i:04d}81", tomador_nome=nome, tomador_email="" if em == "sem_email" else f"financeiro{i}@loja.com.br",
        valor=D(str(round(random.uniform(8, 410), 2))), numero=i + 1, serie="1", numero_nfse=str(i + 1), xml_nfse="<x/>", email_situacao=em, enviada_em=agora, autorizada_em=agora))
NotaFiscal.objects.bulk_create(notas)
print("demo pronta, lote", lote.pk)
