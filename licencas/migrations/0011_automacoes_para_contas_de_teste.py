"""As Automações do Instagram viraram um módulo próprio (instagram / instagram_premium). Antes elas
vinham com o Estúdio Instagram Premium; as contas que já testam o Estúdio ganham a cortesia das
Automações Premium para não pararem as automações que já estão no ar."""

from django.db import migrations


def dar_cortesia(apps, schema_editor):
    Conta = apps.get_model("licencas", "ContaAppfiliado")
    for conta in Conta.objects.filter(beta_estudio_instagram=True):
        codigos = [c.strip() for c in (conta.modulos_cortesia or "").split(",") if c.strip()]
        novo = ", ".join(codigos + ["instagram_premium"])
        if "instagram_premium" not in codigos and len(novo) <= 200:
            conta.modulos_cortesia = novo
            conta.save(update_fields=["modulos_cortesia"])


class Migration(migrations.Migration):
    dependencies = [("licencas", "0010_estudio_instagram")]
    operations = [migrations.RunPython(dar_cortesia, migrations.RunPython.noop)]
