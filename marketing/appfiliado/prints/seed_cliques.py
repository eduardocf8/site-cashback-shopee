import random, datetime as dt
from django.utils import timezone
from meusite.models import SiteAfiliado, CliqueSite, BotaoSite, ProdutoSite
random.seed(5); s=SiteAfiliado.objects.get(endereco="achadinhosdabia"); hoje=timezone.localdate()
CliqueSite.objects.filter(site=s).delete()
botoes=list(BotaoSite.objects.filter(site=s)); prods=list(ProdutoSite.objects.filter(site=s))
for i in range(30):
    d=hoje-dt.timedelta(days=i)
    CliqueSite.objects.create(site=s,dia=d,tipo="visita",alvo_id=0,total=random.randint(60,190))
    for j,b in enumerate(botoes): CliqueSite.objects.create(site=s,dia=d,tipo="botao",alvo_id=b.pk,alvo_nome=b.texto,total=random.randint(5,40)//(j+1)+1)
    for p in prods[:4]: CliqueSite.objects.create(site=s,dia=d,tipo="produto",alvo_id=p.pk,alvo_nome=p.nome,total=random.randint(2,18))
    CliqueSite.objects.create(site=s,dia=d,tipo="conversor",alvo_id=0,total=random.randint(3,14))
print("ok")
