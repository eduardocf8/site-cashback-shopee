# Zouti: produtos do lançamento do Instagram

Os planos novos do site (4 módulos e 3 pacotes) estão prontos no código, desligados. Eles entram no ar
quando a variável `APPFILIADO_LANCAMENTO_INSTAGRAM=True` for ligada no Render (web e worker).

Ordem:

1. Criar na Zouti os **10 produtos novos** da tabela abaixo, cada um com os planos **mensal** e **anual**
   (anual = 10× o mensal: 12 meses pelo preço de 10).
2. Cadastrar cada produto no admin (**Licenças › Produtos da Zouti**): o ID do produto (`prod_...`) e os
   módulos da coluna "Libera".
3. Mandar os 10 links de checkout para colocar no site (`landing/planos.py`, `LINKS`). Até lá, os botões
   aparecem como "Em breve".
4. Depois da aprovação da Meta, ligar `APPFILIADO_LANCAMENTO_INSTAGRAM=True` no Render.

Bot de WhatsApp e Meu site continuam com os 4 produtos de hoje (mesmos preços e links).
Os produtos antigos (Gerador de carrosséis e combos) saem do site, mas **não apague nem pause na Zouti**:
quem já assina continua pagando por eles. Quem assina o Gerador de carrosséis passa a usar o Estúdio
Instagram no mesmo nível, sem mudar nada na assinatura.

## Produtos novos

| Produto | Mensal | Anual | Libera |
|---|---|---|---|
| Estúdio Instagram Standard | R$ 29,90 | R$ 299,00 | `carrosseis` |
| Estúdio Instagram Premium | R$ 49,90 | R$ 499,00 | `carrosseis_premium` |
| Automações do Instagram Standard | R$ 29,90 | R$ 299,00 | `instagram` |
| Automações do Instagram Premium | R$ 54,90 | R$ 549,00 | `instagram_premium` |
| Pacote Ofertas Standard | R$ 64,90 | R$ 649,00 | `whatsapp, site` |
| Pacote Ofertas Premium | R$ 112,90 | R$ 1.129,00 | `whatsapp_premium, site_sem_marca` |
| Pacote Instagram Standard | R$ 52,90 | R$ 529,00 | `carrosseis, instagram` |
| Pacote Instagram Premium | R$ 93,90 | R$ 939,00 | `carrosseis_premium, instagram_premium` |
| Pacote Completo Standard | R$ 111,90 | R$ 1.119,00 | `whatsapp, site, carrosseis, instagram` |
| Pacote Completo Premium | R$ 195,90 | R$ 1.959,00 | `whatsapp_premium, site_sem_marca, carrosseis_premium, instagram_premium` |

Os códigos "Libera" já são os que o admin aceita: o Estúdio usa os mesmos códigos do antigo Gerador de
carrosséis (por isso quem já assina passa direto).

## Textos para a página de cada produto

### Estúdio Instagram Standard
Crie posts e stories com o seu link de afiliado e publique direto no seu Instagram, na hora ou agendado.
- 3 criações com IA por dia
- 7 modelos prontos de post e story
- Post a partir do link de um produto da Shopee, com foto e preço
- Publicar no feed e nos stories, na hora ou agendado
- Download em PNG e ZIP

Precisa de: conta de afiliado da Shopee com a API liberada (para os posts de produto) e, para publicar,
um Instagram profissional (comercial ou de criador).

### Estúdio Instagram Premium
Tudo do Standard, com a cara da sua marca.
- 10 criações com IA por dia
- Cores, fundos e ajustes livres em cada slide
- Minha marca: logo, cores e fonte em todos os posts
- Remoção de fundo da foto
- Seus próprios modelos

### Automações do Instagram Standard
Quem comentar a palavra certa no seu post recebe o seu link de afiliado por DM, na hora.
- Respostas a comentários nos posts
- Resposta no comentário e DM com o seu link
- Até 1.000 pessoas respondidas por mês
- Histórico de quem foi respondido

Precisa de: um Instagram profissional (comercial ou de criador).

### Automações do Instagram Premium
Tudo do Standard, também nos stories e nas DMs.
- Respostas a comentários, stories e DMs com palavra-chave
- Até 10.000 pessoas respondidas por mês

### Pacote Ofertas (Standard / Premium)
Bot de WhatsApp + Meu site no mesmo plano, numa assinatura só, cerca de 10% mais barato que separado.

### Pacote Instagram (Standard / Premium)
Estúdio Instagram + Automações do Instagram no mesmo plano, numa assinatura só, cerca de 10% mais barato que separado.

### Pacote Completo (Standard / Premium)
Bot de WhatsApp + Meu site + Estúdio Instagram + Automações do Instagram no mesmo plano, numa assinatura
só, cerca de 15% mais barato que separado.
