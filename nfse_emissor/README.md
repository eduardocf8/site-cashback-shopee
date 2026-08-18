# Emissor de NFS-e em massa — Comissões de Afiliado (Shopee)

Esqueleto de projeto em Python para emitir uma NFS-e por vendedor, a partir de
um relatório de comissões, usando uma API de terceiros (modelo: **Focus NFe**,
integração **NFS-e Nacional**).

> ⚠️ **Este é um esqueleto, não um produto pronto.** Todos os pontos marcados
> com `# AJUSTAR` ou `# CONFIRMAR` no código precisam dos seus dados reais ou
> de confirmação direta na documentação do provedor. Os parâmetros fiscais
> (código de serviço, alíquota de ISS, retenção, CTN, NBS) **precisam ser
> validados por um contador** antes de emitir em produção. Emitir errado em
> massa multiplica o erro por dezenas de notas.

## Estrutura

| Arquivo | Função |
|---|---|
| `config.py` | Credenciais, dados do prestador e parâmetros fiscais. Centraliza tudo. |
| `leitor_comissoes.py` | Lê e valida o CSV de comissões (inclui validação de CPF/CNPJ). |
| `provedor.py` | Fala com a API do provedor. É a única parte específica da Focus NFe. |
| `emitir_em_massa.py` | Script principal: lê o CSV e emite em lote, com log e resumo. |
| `consultar_status.py` | Consulta o status das notas e recupera links de PDF/XML. |
| `comissoes_exemplo.csv` | Exemplo de formato de entrada (ainda não é o export real da Shopee). |

## Pré-requisitos

- Python 3.9+
- Certificado digital **e-CNPJ A1** cadastrado no painel do provedor (não no script)
- Conta na Focus NFe (comece pelo ambiente de homologação)

```bash
pip install requests
```

## Fluxo recomendado (não pule etapas)

1. **Contador primeiro.** Confirme código de serviço (LC 116/2003), CNAE,
   CTN, NBS, alíquota de ISS e se há retenção. Preencha em
   `config.py > SERVICO`.
2. **Preencha `config.py`** com CNPJ, inscrição municipal e token da API.
3. **Cadastre o certificado A1 no painel do provedor** (não vai no código).
4. **Deixe `USAR_PRODUCAO = False`** (ambiente de homologação/teste).
5. **Exporte o relatório da Shopee** e normalize para o formato do CSV
   (veja `comissoes_exemplo.csv`). Ajuste os nomes das colunas em
   `leitor_comissoes.py` quando tiver um exemplo real do relatório.
6. **Rode com poucas linhas primeiro:**
   ```bash
   python emitir_em_massa.py
   ```
7. **Confira** o CSV de resultado em `notas_emitidas/`.
8. **Consulte a autorização:**
   ```bash
   python consultar_status.py
   ```
9. Só depois de tudo certo em homologação, mude para produção
   (`USAR_PRODUCAO = True`) e rode com o volume real.

## Formato do CSV de entrada

Cabeçalho na primeira linha:

```
tomador_cnpj_cpf,tomador_nome,tomador_email,valor_comissao,descricao
```

- `tomador_cnpj_cpf`: só números (11 = CPF, 14 = CNPJ). É validado com dígito verificador.
- `tomador_email`: pode ficar vazio.
- `valor_comissao`: use ponto ou vírgula decimal (`12.50` ou `12,50`).
- `descricao`: se vazio, usa a descrição padrão do `config.py`.

Este ainda é o formato do esqueleto — não o export real da Shopee. Ajuste
`leitor_comissoes.py` assim que houver um exemplo real do relatório.

## Idempotência

`provedor.emitir()` faz uma checagem defensiva: antes de enviar, consulta a
referência (`comissao-{competencia}-{linha}`) e, se ela já existir com status
de processamento/autorizada/cancelada, pula o envio em vez de duplicar. Isso
não depende do comportamento nativo da API da Focus para `ref` repetida, que
**não foi confirmado na documentação** (ver seção abaixo).

## Segurança

- **Nunca** suba `config.py` com token real, nem o certificado, para repositório público.
- Prefira ler o token de variável de ambiente (`FOCUS_NFE_TOKEN`), como já está no código.
- Guarde o `.pfx` do certificado A1 em local seguro e com backup.

## O que ainda falta confirmar na doc do provedor

Ao pesquisar a documentação pública da Focus NFe, o acesso direto a
`doc.focusnfe.com.br` não estava disponível no ambiente onde este projeto foi
revisado (bloqueio de rede). As mudanças abaixo foram feitas com base em
resultados de busca (títulos e trechos de página), **não** na leitura literal
da doc — trate como ponto de partida, não como confirmado:

- **Endpoint**: trocado de `/v2/nfse` (padrão legado/municipal) para
  `/v2/nfsen` (NFS-e Nacional). Existe também uma página de doc específica
  `emitir_dps_nacional`, sugerindo que o modelo Nacional pode exigir enviar
  uma DPS (Declaração de Prestação de Serviço) em vez de uma "nfse" direta —
  **confirme isso antes de emitir em produção**, pode mudar o endpoint ou a
  forma do payload.
- **Campos novos de Reforma Tributária**: adicionados `codigo_tributacao_nacional`
  (CTN) e `codigo_nbs` (NBS) em `config.SERVICO` e no payload de
  `provedor.montar_payload()`, como placeholders `# AJUSTAR/CONFIRMAR`. Nomes
  exatos de campo, formato e obrigatoriedade (incluindo possíveis `cClassTrib`
  e `cIndOp`) não foram confirmados na doc.
- **Status assíncrono**: valores usados (`processando_autorizacao`,
  `autorizado`, `cancelado`) vieram de busca, não da doc literal.
- **Idempotência por referência**: não confirmado o comportamento nativo da
  API para `ref` repetida — por isso a checagem defensiva em `provedor.py`
  (ver seção "Idempotência" acima), que não depende disso.
- **Homologação de Toledo** no padrão Nacional — perguntar ao suporte da
  Focus se já está ativa (a cidade migra em 01/09/2026).

**Próximo passo recomendado**: abrir
`https://doc.focusnfe.com.br/reference/emitir_dps_nacional` (e a página de
consulta correspondente) em um navegador com acesso normal e colar o
conteúdo para revisão, já que o fetch automático desse domínio está
bloqueado no ambiente usado para esta revisão.
