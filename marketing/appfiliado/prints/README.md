# Telas do painel para a landing (appfiliado.com.br)

As imagens de `landing/static/landing/prints/` são prints reais do painel com uma conta fictícia ("Achadinhos da Bia").
Pra refazer depois de mudar alguma tela:

1. `python gerar_fotos.py` (fotos de produto de exemplo em `img/`, feitas com emojis).
2. Banco novo: `DATABASE_URL=sqlite:///.../demo.sqlite3 python manage.py migrate` e depois
   `python manage.py shell < marketing/appfiliado/prints/seed_demo.py` e `seed_cliques.py` (mesma `DATABASE_URL`).
3. Em outro terminal: `python -m http.server 8766 --bind 127.0.0.1` dentro desta pasta (serve `img/`).
4. Painel: `APPFILIADO_PAINEL_HOSTS=localhost APPFILIADO_PAINEL_URL=http://localhost:8765 python servidor_demo.py runserver 8765 --noreload`
   (o `servidor_demo.py` troca a Shopee e o WhatsApp por respostas de exemplo).
5. `python final.py` regrava as imagens `.webp` em `landing/static/landing/prints/`.

Cada tela sai em duas versões: computador (1100 px, sem o menu lateral) e celular (`-m`, layout de celular em 2x). Os tamanhos ficam em `landing/recursos.py` (`TAMANHOS`, vêm do `tamanhos.json` que o `final.py` grava): atualize se mudar o recorte.
