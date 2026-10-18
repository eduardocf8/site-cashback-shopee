class Oferta:
    def __init__(
        self,
        autor="",
        texto_original="",
        links=None,
        link_original=None,
        link_afiliado=None,
        texto_final="",
        tem_imagem=False,
        id_mensagem=None
    ):
        self.autor = autor
        self.texto_original = texto_original
        self.links = links or []
        self.link_original = link_original
        self.link_afiliado = link_afiliado
        self.texto_final = texto_final
        self.tem_imagem = tem_imagem
        self.id_mensagem = id_mensagem