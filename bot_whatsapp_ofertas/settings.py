import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


def caminho_user_data_navegador_pessoal(tipo_navegador="chrome"):
    """
    Retorna a pasta raiz "User Data" do navegador instalado no sistema (a
    que contém as pastas "Default", "Profile 1" etc.), usada para copiar o
    perfil pessoal de verdade (histórico, cookies e confiança acumulada),
    em vez de um perfil novo e "zerado" criado só para o bot. Suporta
    Chrome ("chrome") e Microsoft Edge ("msedge"). Retorna None se não
    conseguir localizar (sistema operacional não reconhecido).
    """

    home = Path.home()
    pasta_navegador = "Microsoft" if tipo_navegador == "msedge" else "Google"
    nome_navegador = "Edge" if tipo_navegador == "msedge" else "Chrome"

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            return None
        return str(Path(base) / pasta_navegador / nome_navegador / "User Data")
    if sys.platform == "darwin":
        if tipo_navegador == "msedge":
            return str(home / "Library" / "Application Support" / "Microsoft Edge")
        return str(home / "Library" / "Application Support" / "Google" / "Chrome")
    if tipo_navegador == "msedge":
        return str(home / ".config" / "microsoft-edge")
    return str(home / ".config" / "google-chrome")


def caminho_user_data_chrome_pessoal():
    """Mantido por compatibilidade; equivale a caminho_user_data_navegador_pessoal("chrome")."""
    return caminho_user_data_navegador_pessoal("chrome")


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

USER_CONFIG_PATH = APP_DIR / "config_usuario.json"
CONFIG_BACKUP_DIR = APP_DIR / "backups"


def backup_user_config(path=USER_CONFIG_PATH, max_backups=10):
    path = Path(path)
    if not path.exists():
        return None

    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = CONFIG_BACKUP_DIR / f"config_usuario_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    backup_path.write_bytes(path.read_bytes())

    backups = sorted(
        CONFIG_BACKUP_DIR.glob("config_usuario_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[max_backups:]:
        try:
            old_backup.unlink()
        except OSError:
            pass

    return backup_path


@dataclass
class AppSettings:
    grupo_origem: str = "OLAPROMOS"
    # Conversas/grupos normais do WhatsApp (aba "Conversas") que recebem as ofertas.
    grupos_destino: list[str] = field(default_factory=lambda: ["Ofertas @vegrassi"])
    # Canais do WhatsApp (WhatsApp Channels, aba "Canais"/"Updates" - area
    # separada dos grupos normais) que tambem recebem as ofertas. So quem
    # administra o canal consegue publicar nele. Pode ser usado junto com
    # grupos_destino: quando os dois estao preenchidos, o bot envia a mesma
    # oferta para os grupos E para os canais no mesmo ciclo.
    canais_destino: list[str] = field(default_factory=list)
    shopee_api_app_id: str = ""
    shopee_api_secret: str = ""
    shopee_api_sub_ids: list[str] = field(default_factory=list)
    intervalo_ms: int = 5000
    processar_historico_ao_iniciar: bool = True
    ignorar_links_ja_enviados: bool = True
    modo_simulacao: bool = False
    headless: bool = False
    agendamento_ativo: bool = False
    horario_inicio: str = "07:00"
    horario_fim: str = "23:00"
    recuperacao_automatica: bool = True
    recuperacao_max_tentativas: int = 5
    recuperacao_intervalo_segundos: int = 30
    modo_origem_ofertas: str = "whatsapp"
    shopee_ofertas_tipo_busca: str = "geral"
    shopee_ofertas_link_colecao: str = ""
    shopee_ofertas_cupom: str = ""
    shopee_ofertas_palavra_chave: str = ""
    shopee_ofertas_shop_id: str = ""
    shopee_ofertas_categoria_id: str = ""
    shopee_ofertas_categorias: list[str] = field(default_factory=list)
    shopee_ofertas_pagina_atual: int = 1
    shopee_ofertas_pagina_atualizada_em: str = ""
    shopee_ofertas_ordenacao: str = "mais_vendidos"
    shopee_ofertas_comissao_minima: int = 0
    shopee_ofertas_desconto_minimo: int = 0
    shopee_ofertas_preco_minimo: str = ""
    shopee_ofertas_preco_maximo: str = ""
    shopee_ofertas_vendas_minimas: int = 0
    shopee_ofertas_avaliacao_minima: str = ""
    shopee_ofertas_quantidade_por_ciclo: int = 10
    shopee_ofertas_intervalo_envio_segundos: int = 300
    shopee_ofertas_nao_repetir: bool = True
    aguardar_previa_link: bool = True
    timeout_previa_link_ms: int = 15000
    espera_minima_previa_link_ms: int = 5000
    timeout_imagem_previa_link_ms: int = 15000
    shopee_api_timeout_segundos: int = 30
    tema_visual: str = "padrao"
    ia_revisao_ativa: bool = False
    ia_gemini_api_key: str = ""
    ia_modelo: str = "gemini-3.1-flash-lite"
    ia_tipo_revisao: str = "contextual"
    ia_limite_diario_revisoes: int = 180
    ia_timeout_segundos: int = 10
    ia_pausar_ao_limite: bool = True
    ia_retomar_no_dia_seguinte: bool = True
    ia_status_mensagem: str = "Revisão por IA desativada."
    ia_revisoes_hoje: int = 0
    ia_data_revisoes: str = ""
    ia_pausada_ate: str = ""
    api_validada_em: str = ""
    grupos_validados_em: str = ""
    profile_dir: str = "perfil_whatsapp_app"
    database_path: str = "mensagens_app.db"
    shopee_usar_perfil_chrome_pessoal: bool = False
    shopee_perfil_chrome_nome: str = "Default"
    shopee_navegador_tipo: str = "chrome"

    # Relatorio diario de vendas/comissao por SubID, enviado por email
    relatorio_email_ativo: bool = False
    relatorio_email_hora: str = "11:00"
    relatorio_email_destinatarios: str = ""
    relatorio_email_remetente: str = ""
    relatorio_email_senha_app: str = ""
    relatorio_email_servidor_smtp: str = "smtp.gmail.com"
    relatorio_email_porta_smtp: int = 587
    relatorio_email_ultimo_envio: str = ""

    @classmethod
    def load(cls, path=USER_CONFIG_PATH):
        path = Path(path)
        if not path.exists():
            settings = cls()
            settings.save(path)
            return settings

        defaults = asdict(cls())
        data = json.loads(path.read_text(encoding="utf-8"))
        known_data = {key: value for key, value in data.items() if key in defaults}
        defaults.update(known_data)
        return cls(**defaults)

    def save(self, path=USER_CONFIG_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def normalized_destinos(self):
        return [g.strip() for g in self.grupos_destino if str(g).strip()]

    def normalized_canais_destino(self):
        return [c.strip() for c in self.canais_destino if str(c).strip()]

    def normalized_destinos_com_tipo(self):
        """Todos os destinos (grupos + canais) como tuplas (nome, tipo),
        onde tipo e "grupo" ou "canal". Usado para enviar a mesma oferta
        para os dois de uma vez, e para checagens de link ja enviado que
        precisam considerar todos os destinos configurados."""
        return (
            [(nome, "grupo") for nome in self.normalized_destinos()]
            + [(nome, "canal") for nome in self.normalized_canais_destino()]
        )

    def normalized_sub_ids(self):
        return [s.strip() for s in self.shopee_api_sub_ids if str(s).strip()]

    def normalized_destinatarios_relatorio(self):
        bruto = str(self.relatorio_email_destinatarios or "")
        return [e.strip() for e in bruto.replace(";", ",").split(",") if e.strip()]
