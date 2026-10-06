"""Prévia da campanha de cashback, visível SÓ para o administrador.

Para quê: a campanha só pode aparecer para o público no dia certo (e a faixa de aviso, nos 3
dias antes), mas é preciso ver como o site fica com ela no ar - faixa, cards de oferta - ANTES
do dia. Esta prévia mostra o site como ele ficará, para uma única pessoa: o superusuário logado
que ligou a prévia, no navegador dele, por poucas horas.

Como é impossível vazar para outra pessoa (cada trava sozinha já bastaria):

1. **Quem liga.** A tela que liga a prévia só abre para superusuário ativo e logado; para
   qualquer outra pessoa ela responde 404, igual a uma página que não existe.
2. **Quem vê.** A cada requisição o middleware confere de novo que o usuário é superusuário
   ativo e logado - não basta ter a marca na sessão. Uma sessão forjada, ou a de outro usuário,
   não mostra nada.
3. **Onde vale.** Só em GET/HEAD e só em cinco páginas públicas (`CAMINHOS`). Ficam de fora o
   admin, as tarefas agendadas, a geração de story e de e-mail (que usam o mesmo cashback
   estimado) e qualquer POST: nada que grave ou publique um valor da prévia.
4. **Por quanto tempo.** A marca na sessão expira em `DURACAO` e some no logout.
5. **Sem cache.** A resposta da prévia sai com `Cache-Control: private, no-store` e `Vary:
   Cookie`: nenhum navegador compartilhado, proxy ou CDN guarda a página.
6. **Sem vazamento entre requisições.** A prévia vive numa variável de contexto, restaurada em
   `finally` ao fim da requisição: a seguinte, mesmo na mesma thread, volta ao normal.

Não muda nada que é pago: o cashback do pedido é carimbado pela data da compra
(`CampanhaCashback.multiplicador_em`, que a prévia não toca), e nada é gravado no banco.
"""
from contextvars import ContextVar
from datetime import timedelta

# A campanha que está sendo previsada nesta requisição, ou None (o normal).
_campanha_previa: ContextVar = ContextVar("campanha_previa", default=None)

CHAVE_SESSAO = "previa_campanha_ate"
DURACAO = timedelta(hours=2)

# Únicas páginas em que a prévia aparece: as que têm a faixa e os cards de oferta.
CAMINHOS = frozenset({"/", "/ofertas/", "/dashboard/", "/login/", "/registrar/"})


def campanha_da_previa():
    """Campanha em prévia nesta requisição (None fora dela)."""
    return _campanha_previa.get()


def pode_ver_previa(usuario) -> bool:
    """Só superusuário ativo e logado. É esta a trava de "só o administrador"."""
    return bool(
        usuario is not None
        and usuario.is_authenticated
        and usuario.is_active
        and usuario.is_staff
        and usuario.is_superuser
    )
