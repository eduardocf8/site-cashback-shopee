from django.contrib import admin

from .models import EmpresaNotas, NotaFiscal


@admin.register(EmpresaNotas)
class EmpresaNotasAdmin(admin.ModelAdmin):
    list_display = ("razao_social", "cnpj", "conta", "regime", "municipio_nome", "certificado_validade")
    search_fields = ("razao_social", "cnpj", "conta__email")
    # O certificado e a senha (cifrados) nunca aparecem no admin.
    exclude = ("certificado_cifrado", "senha_cifrada")
    readonly_fields = ("certificado_titular", "certificado_validade", "ultimo_numero_producao", "ultimo_numero_teste")


@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ("numero", "empresa", "ambiente", "tipo", "tomador_nome", "valor", "situacao", "criada_em")
    list_filter = ("situacao", "ambiente", "tipo")
    search_fields = ("tomador_nome", "tomador_documento", "chave", "empresa__cnpj")
    readonly_fields = [f.name for f in NotaFiscal._meta.fields]
