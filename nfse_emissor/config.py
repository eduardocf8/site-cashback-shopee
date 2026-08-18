"""
config.py
---------
Configurações centrais do emissor. Preencha com seus dados reais.

NUNCA suba este arquivo (nem o .env) para um repositório público.
Idealmente carregue os valores sensíveis de variáveis de ambiente.
"""

import os

# ---------------------------------------------------------------------------
# CREDENCIAIS DO PROVEDOR (ex.: Focus NFe)
# ---------------------------------------------------------------------------
# O ideal é NÃO deixar o token escrito aqui. Defina uma variável de ambiente
# e leia dela. Exemplo no terminal (Linux/Mac):
#     export FOCUS_NFE_TOKEN="seu_token_aqui"
# No Windows (PowerShell):
#     setx FOCUS_NFE_TOKEN "seu_token_aqui"

PROVIDER_TOKEN = os.environ.get("FOCUS_NFE_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")

# URL base da API. A Focus NFe tem ambiente de HOMOLOGAÇÃO (testes) e PRODUÇÃO.
# Comece SEMPRE em homologação. Confirme as URLs atuais na documentação:
#   https://doc.focusnfe.com.br/
BASE_URL_HOMOLOGACAO = "https://homologacao.focusnfe.com.br"
BASE_URL_PRODUCAO = "https://api.focusnfe.com.br"

# Alterne aqui entre teste e produção
USAR_PRODUCAO = False
BASE_URL = BASE_URL_PRODUCAO if USAR_PRODUCAO else BASE_URL_HOMOLOGACAO

# ---------------------------------------------------------------------------
# DADOS DO PRESTADOR (você / seu CNPJ)
# ---------------------------------------------------------------------------
PRESTADOR = {
    "cnpj": "00000000000000",          # AJUSTAR: seu CNPJ, só números
    "inscricao_municipal": "000000",   # AJUSTAR: sua inscrição municipal em Toledo
    "codigo_municipio": "4127700",     # 4127700 = Toledo/PR (código IBGE). CONFIRMAR.
    "razao_social": "SUA RAZAO SOCIAL LTDA",  # AJUSTAR
}

# ---------------------------------------------------------------------------
# PARÂMETROS FISCAIS DO SERVIÇO  ---  VALIDAR COM CONTADOR
# ---------------------------------------------------------------------------
# Estes campos definem COMO a nota é tributada. Errado aqui = erro em massa.
# Peça ao seu contador o código de serviço (LC 116/2003), a alíquota de ISS
# e se há retenção. Os valores abaixo são PLACEHOLDERS.
SERVICO = {
    "codigo_servico_lc116": "10.09",   # AJUSTAR: ex. "10.09" (agenciamento/intermediação). CONTADOR VALIDA.
    "cnae": "0000000",                 # AJUSTAR: seu CNAE
    "descricao_padrao": "Comissao por intermediacao de vendas - programa de afiliados",  # AJUSTAR

    # --- Campos da NFS-e Nacional / Reforma Tributária (IBS/CBS) ---
    # A migração de Toledo para o padrão Nacional (01/09/2026) e a Reforma
    # Tributária trazem campos novos que substituem/complementam o
    # item_lista_servico tradicional. NÃO CONFIRMADOS na doc ainda (o acesso
    # a doc.focusnfe.com.br está bloqueado neste ambiente) — valide o nome
    # exato do campo e a obrigatoriedade em:
    #   https://doc.focusnfe.com.br/reference/emitir_dps_nacional
    # antes de usar em produção. Peça ao contador o CTN e o NBS corretos
    # (ligados ao seu código LC 116 acima), já que definem a incidência de
    # IBS/CBS na nota.
    "codigo_tributacao_nacional": "000000000",  # AJUSTAR/CONFIRMAR: CTN (Código de Tributação Nacional)
    "codigo_nbs": "000000000",                  # AJUSTAR/CONFIRMAR: NBS (Nomenclatura Brasileira de Serviços)

    "aliquota_iss": 0.0,               # AJUSTAR: ex. 0.02 para 2%. CONTADOR VALIDA.
    "iss_retido": False,               # AJUSTAR: True/False conforme orientação do contador
}

# ---------------------------------------------------------------------------
# ARQUIVOS
# ---------------------------------------------------------------------------
ARQUIVO_ENTRADA = "comissoes.csv"      # relatório de comissões (exportado/normalizado)
PASTA_SAIDA = "notas_emitidas"         # onde salvar PDFs/XMLs e o log de resultados
