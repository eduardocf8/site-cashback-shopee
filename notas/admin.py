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

    # Apagar aqui só tira a nota do Appfiliado: no governo ela continua valendo. Por isso, nota
    # que pode ter virado NFS-e (autorizada, cancelada, enviando ou sem resposta) não se apaga -
    # nem sozinha, nem junto com a empresa ou a conta (o Django confere cada nota antes).
    # Para tirar a validade, use "Cancelar" na tela de notas do painel.
    SITUACOES_QUE_NAO_SE_APAGAM = (NotaFiscal.AUTORIZADA, NotaFiscal.CANCELADA, NotaFiscal.ENVIANDO, NotaFiscal.ERRO)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.situacao in self.SITUACOES_QUE_NAO_SE_APAGAM:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        acoes = super().get_actions(request)
        acoes.pop("delete_selected", None)  # apagar em massa passaria por cima da regra acima
        return acoes
