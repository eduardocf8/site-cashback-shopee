import credenciais_seguras as cs


def _instalar_dpapi_falso(monkeypatch):
    """Simula o DPAPI do Windows com uma transformacao reversivel simples,
    pra poder testar a logica de cifrar/decifrar em qualquer sistema
    operacional (o pywin32 de verdade so existe no Windows)."""

    marcador = b"|MAQUINA-FAKE"

    def cifrar(dados: bytes) -> bytes:
        return dados[::-1] + marcador

    def decifrar(dados: bytes) -> bytes:
        if not dados.endswith(marcador):
            raise ValueError("nao amarrado a esta maquina/usuario fake")
        return dados[: -len(marcador)][::-1]

    monkeypatch.setattr(cs, "_dpapi_disponivel", lambda: True)
    monkeypatch.setattr(cs, "_dpapi_criptografar_bytes", cifrar)
    monkeypatch.setattr(cs, "_dpapi_descriptografar_bytes", decifrar)


class TestSemDpapiDisponivel:
    """Cobre o caso real deste ambiente de desenvolvimento (Linux, sem
    pywin32) e qualquer maquina sem suporte a DPAPI - o valor tem que
    seguir funcionando em texto puro, nunca travar."""

    def test_proteger_e_passthrough(self, monkeypatch):
        monkeypatch.setattr(cs, "_dpapi_disponivel", lambda: False)
        assert cs.proteger("minha-senha-123") == "minha-senha-123"
        assert cs.proteger("") == ""

    def test_revelar_trata_como_texto_legado(self, monkeypatch):
        monkeypatch.setattr(cs, "_dpapi_disponivel", lambda: False)
        falhas = []
        assert cs.revelar("texto-qualquer", falhas) == "texto-qualquer"
        assert falhas == []


class TestComDpapiDisponivel:
    def test_proteger_cifra_e_usa_prefixo(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        cifrado = cs.proteger("S3gred0-Shopee!@#")
        assert cifrado.startswith(cs.PREFIXO_CIFRADO)
        assert cifrado != "S3gred0-Shopee!@#"

    def test_round_trip_cifra_e_decifra(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        original = "senha-de-app-do-gmail"
        assert cs.revelar(cs.proteger(original)) == original

    def test_idempotente_nao_cifra_duas_vezes(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        cifrado = cs.proteger("abc123")
        assert cs.proteger(cifrado) == cifrado

    def test_vazio_continua_vazio(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        assert cs.proteger("") == ""
        assert cs.revelar("") == ""

    def test_texto_legado_nao_cifrado_passa_direto(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        # Uma config antiga, salva antes dessa protecao existir, nao deve
        # ser tratada como cifrada so porque o DPAPI esta disponivel agora.
        falhas = []
        assert cs.revelar("senha-antiga-em-texto-puro", falhas) == "senha-antiga-em-texto-puro"
        assert falhas == []


class TestFalhaDeDecifragem:
    def test_valor_cifrado_em_outra_maquina_vira_vazio_e_marca_falha(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        cifrado = cs.proteger("segredo-da-api")

        def decifrar_maquina_diferente(dados: bytes) -> bytes:
            raise OSError("Key not valid for use in specified state")

        monkeypatch.setattr(cs, "_dpapi_descriptografar_bytes", decifrar_maquina_diferente)

        falhas = []
        resultado = cs.revelar(cifrado, falhas)
        assert resultado == ""
        assert falhas == [cifrado]

    def test_sem_lista_de_falhas_ainda_assim_nao_quebra(self, monkeypatch):
        _instalar_dpapi_falso(monkeypatch)
        cifrado = cs.proteger("segredo-da-api")
        monkeypatch.setattr(
            cs,
            "_dpapi_descriptografar_bytes",
            lambda dados: (_ for _ in ()).throw(OSError("falhou")),
        )
        assert cs.revelar(cifrado) == ""
