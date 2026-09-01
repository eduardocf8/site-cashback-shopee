from django.db import migrations

from ofertas.services import resolver_item_id_sem_rede


def preencher_item_id_alvo(apps, schema_editor):
    """Só tenta identificar pelo padrão de texto na URL já salva (sem seguir
    redirecionamento) - rápido e sem chamada de rede, seguro de rodar numa migração.
    Cliques cujo link só resolve seguindo redirecionamento (links curtos) ficam sem
    item_id_alvo, do mesmo jeito que ficariam se fossem criados agora - só passam a
    contar pro piso de venda indireta a partir daqui (ver ROADMAP.md, Fase 41)."""
    Click = apps.get_model("links", "Click")
    for click in Click.objects.exclude(tipo="home").filter(item_id_alvo__isnull=True).iterator():
        item_id = resolver_item_id_sem_rede(click.url_original)
        if item_id is not None:
            click.item_id_alvo = item_id
            click.save(update_fields=["item_id_alvo"])


class Migration(migrations.Migration):

    dependencies = [
        ("links", "0003_click_item_id_alvo"),
    ]

    operations = [
        migrations.RunPython(preencher_item_id_alvo, migrations.RunPython.noop),
    ]
