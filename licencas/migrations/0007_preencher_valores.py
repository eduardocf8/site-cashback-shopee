"""Preenche o valor, o ciclo (mensal/anual) e a data de encerramento das assinaturas que já
existiam, a partir dos avisos da Zouti guardados (EventoWebhookZouti.corpo_bruto)."""

import json

from django.db import migrations


def preencher(apps, schema_editor):
    from licencas.services import valor_e_ciclo

    Assinatura = apps.get_model("licencas", "Assinatura")
    Evento = apps.get_model("licencas", "EventoWebhookZouti")
    for assinatura in Assinatura.objects.all():
        eventos = (Evento.objects.filter(zouti_object_id=assinatura.zouti_subscription_id, assinatura_valida=True)
                   .order_by("-recebido_em"))
        if not eventos.exists():  # evento antigo sem o id no cabeçalho: procura no corpo
            eventos = (Evento.objects.filter(corpo_bruto__contains=assinatura.zouti_subscription_id, assinatura_valida=True)
                       .order_by("-recebido_em"))
        for evento in eventos[:20]:
            try:
                payload = json.loads(evento.corpo_bruto)
            except ValueError:
                continue
            if not isinstance(payload, dict) or str(payload.get("id") or "") != assinatura.zouti_subscription_id:
                continue
            valor, meses = valor_e_ciclo(payload)
            if valor is not None:
                assinatura.valor, assinatura.meses_por_ciclo = valor, meses or 1
                break
        if assinatura.status in ("cancelada", "reembolsada", "chargeback") and not assinatura.encerrada_em:
            assinatura.encerrada_em = assinatura.zouti_atualizada_em or assinatura.atualizada_em
        assinatura.save(update_fields=["valor", "meses_por_ciclo", "encerrada_em"])


class Migration(migrations.Migration):
    dependencies = [("licencas", "0006_painel_do_dono")]
    operations = [migrations.RunPython(preencher, migrations.RunPython.noop)]
