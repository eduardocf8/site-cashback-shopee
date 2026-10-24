import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(AQUI, "..", "..", "..")))
os.chdir(os.path.abspath(os.path.join(AQUI, "..", "..", "..")))
from unittest import mock
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cashback_shopee.settings")
django.setup()
import itertools
cont = itertools.count(1)
def gerar(app_id, secret, url, sub_ids):
    return f"https://s.shopee.com.br/{['8Kz1aQ', '4Lp9Xw', '2Vb7Tr', '9Hd3Mn'][next(cont) % 4]}"
mock.patch("bot_whatsapp.shopee_ofertas.gerar_link_afiliado", side_effect=gerar).start()
mock.patch("bot_whatsapp.copia.identificar_produto", return_value="789").start()
mock.patch("bot_whatsapp.shopee_ofertas.buscar_produto_por_item", return_value={"link": "https://shopee.com.br/product/7/789"}).start()
def busca(app_id, secret, config, pagina):
    base = [("Fone Bluetooth TWS Pro com Cancelamento de Ruído", 79.9, 12, 4, 45, 15800, 4.8, "Fone"),
            ("Air Fryer Mondial 4L Preta com Timer", 329.9, 8, 0, 20, 8900, 4.9, "AirFryer"),
            ("Kit 10 Organizadores de Gaveta Empilháveis", 39.9, 15, 5, 38, 22100, 4.7, "Kit"),
            ("Smartwatch D20 Ultra com Monitor Cardíaco", 89.9, 10, 0, 55, 31200, 4.6, "Relogio"),
            ("Garrafa Térmica 1L Inox Parede Dupla", 49.9, 11, 3, 30, 12400, 4.9, "Garrafa"),
            ("Luminária LED de Mesa Recarregável", 59.9, 9, 0, 25, 6700, 4.8, "Luminaria"),
            ("Mochila Notebook Impermeável USB", 119.9, 14, 6, 40, 5400, 4.7, "Mochila"),
            ("Escova Secadora Rotativa 3 em 1", 149.9, 7, 0, 35, 18900, 4.8, "Escova")]
    produtos = [{"item_id": str(5000 + i), "shop_id": "1", "nome": n, "preco": pr, "comissao": c, "comissao_extra": e,
                 "desconto": d, "vendas": v, "avaliacao": a, "loja": "Loja Oficial", "categoria_id": 0,
                 "imagem": f"https://placehold.co/300x300/png?text={t}", "link": f"https://shopee.com.br/p-i.1.{5000+i}"}
                for i, (n, pr, c, e, d, v, a, t) in enumerate(base)]
    if config.ordenacao == "maior_comissao":
        produtos.sort(key=lambda p: p["comissao"], reverse=True)
    return produtos, pagina < 3
mock.patch("bot_whatsapp.shopee_ofertas.buscar_produtos", side_effect=busca).start()
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
