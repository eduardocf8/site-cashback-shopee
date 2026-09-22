import json
import re
import urllib.error
import urllib.request
from datetime import date, timedelta


class RevisorIA:
    def __init__(self, settings, logger=None):
        self.settings = settings
        self.logger = logger or (lambda message: None)

    def revisar_texto(self, texto, link_afiliado):
        if not self.settings.ia_revisao_ativa:
            self._atualizar_status("Revisão por IA desativada.")
            return texto

        if not self.settings.ia_gemini_api_key:
            self._atualizar_status("Revisão por IA ignorada: chave Gemini não informada.")
            return texto

        self._resetar_contador_se_preciso()

        if self._ia_pausada():
            return texto

        if self.settings.ia_revisoes_hoje >= self.settings.ia_limite_diario_revisoes:
            self._pausar_ate_amanha(
                "Limite diário de revisões por IA atingido. "
                "A IA foi pausada e o bot continuará enviando as ofertas normalmente."
            )
            return texto

        try:
            texto_revisado = self._chamar_gemini(texto)
            if not texto_revisado:
                self._atualizar_status("A IA retornou vazio. Texto original mantido.")
                return texto

            if link_afiliado and link_afiliado not in texto_revisado:
                self._atualizar_status("A IA alterou/removou o link. Texto original mantido por segurança.")
                return texto

            validacao = self._validar_resposta(texto, texto_revisado)
            if validacao:
                self._atualizar_status(f"{validacao} Texto original mantido por segurança.")
                return texto

            self.settings.ia_revisoes_hoje += 1
            self._atualizar_status(
                f"Oferta revisada por IA ({self._nome_tipo_revisao()}). Uso hoje: "
                f"{self.settings.ia_revisoes_hoje}/{self.settings.ia_limite_diario_revisoes}."
            )
            return texto_revisado.strip()

        except urllib.error.HTTPError as error:
            status_code = getattr(error, "code", 0)
            body = self._ler_erro_http(error)
            if status_code in (403, 429) or "quota" in body.lower() or "limit" in body.lower():
                self._pausar_ate_amanha(
                    "Limite/cota da IA atingido. Revisão automática pausada até amanhã. "
                    "As ofertas continuarão sendo enviadas normalmente."
                )
            else:
                self._atualizar_status(f"Falha na IA ({status_code}). Texto original mantido.")
            return texto

        except Exception as error:
            self._atualizar_status(f"Falha na IA: {error}. Texto original mantido.")
            return texto

    def _chamar_gemini(self, texto):
        modelo = self.settings.ia_modelo or "gemini-3.1-flash-lite"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
            f"?key={self.settings.ia_gemini_api_key}"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": self._montar_prompt(texto)}],
                }
            ],
            "generationConfig": {
                "temperature": self._temperatura(),
                "maxOutputTokens": 1200,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = max(3, int(self.settings.ia_timeout_segundos or 10))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))

        candidates = result.get("candidates") or []
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts") or []
        return "\n".join(part.get("text", "") for part in parts).strip()

    def _montar_prompt(self, texto):
        tipo = self.settings.ia_tipo_revisao or "contextual"
        regras_fixas = (
            "Você revisa ofertas para WhatsApp em português do Brasil.\n"
            "Regras obrigatórias:\n"
            "- Retorne somente o texto final revisado, sem explicações.\n"
            "- Não altere links, preços, cupons, emojis, medidas, voltagem, quantidades ou nomes próprios.\n"
            "- Não invente características técnicas, descontos, frete, garantia ou informações que não estejam no texto.\n"
            "- Preserve a estrutura geral da oferta e a ordem dos links.\n"
            "- Se não tiver certeza, faça apenas correções leves de português.\n"
        )

        if tipo == "leve":
            modo = (
                "Modo: revisão leve.\n"
                "Corrija ortografia, acentuação, pontuação e pequenas falhas de clareza. "
                "Não reescreva benefícios nem mude o tom da oferta.\n"
            )
        elif tipo == "criativa":
            modo = (
                "Modo: revisão criativa controlada.\n"
                "Além de corrigir português e frases incoerentes, você pode melhorar a chamada e deixar o texto mais atraente. "
                "Mesmo assim, não crie fatos novos e não aumente promessas sobre o produto.\n"
            )
        else:
            modo = (
                "Modo: revisão contextual conservadora.\n"
                "Leia o tipo de produto e identifique frases claramente estranhas ou copiadas de outro produto. "
                "Se uma frase não combina com o produto, substitua por uma frase genérica e segura que combine com a categoria. "
                "Exemplo: se o produto for utensílio de cozinha, não diga que decora o ambiente; diga que ajuda no preparo ou organização. "
                "Se o produto for roupa/calçado, foque em conforto, estilo ou uso no dia a dia. "
                "Se o produto for decoração, foque em ambiente, charme ou estilo.\n"
            )

        return f"{regras_fixas}\n{modo}\nTexto da oferta:\n{texto}"

    def _temperatura(self):
        tipo = self.settings.ia_tipo_revisao or "contextual"
        if tipo == "criativa":
            return 0.45
        if tipo == "leve":
            return 0.1
        return 0.25

    def _validar_resposta(self, texto_original, texto_revisado):
        links_originais = self._extrair_links(texto_original)
        links_revisados = self._extrair_links(texto_revisado)
        if links_originais != links_revisados:
            return "A IA alterou a lista de links."

        precos_originais = self._extrair_precos(texto_original)
        precos_revisados = self._extrair_precos(texto_revisado)
        if precos_originais != precos_revisados:
            return "A IA alterou algum preço."

        if len(texto_revisado) > max(600, len(texto_original) * 2.2):
            return "A IA expandiu demais o texto."

        return ""

    def _extrair_links(self, texto):
        links = re.findall(r"https?://[^\s]+", texto or "")
        return [link.rstrip(").,;!?") for link in links]

    def _extrair_precos(self, texto):
        return re.findall(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2}", texto or "")

    def _nome_tipo_revisao(self):
        nomes = {
            "leve": "leve",
            "contextual": "contextual",
            "criativa": "criativa",
        }
        return nomes.get(self.settings.ia_tipo_revisao or "contextual", "contextual")

    def _resetar_contador_se_preciso(self):
        hoje = date.today().isoformat()
        if self.settings.ia_data_revisoes != hoje:
            self.settings.ia_data_revisoes = hoje
            self.settings.ia_revisoes_hoje = 0
            if self.settings.ia_retomar_no_dia_seguinte:
                self.settings.ia_pausada_ate = ""
            self.settings.save()

    def _ia_pausada(self):
        pausada_ate = self.settings.ia_pausada_ate
        if not pausada_ate:
            return False

        hoje = date.today().isoformat()
        if self.settings.ia_retomar_no_dia_seguinte and hoje >= pausada_ate:
            self.settings.ia_pausada_ate = ""
            self._atualizar_status("Revisão por IA retomada automaticamente.")
            return False

        self._atualizar_status(
            "Revisão por IA pausada por limite/cota. "
            "O bot continuará enviando ofertas com o texto original."
        )
        return True

    def _pausar_ate_amanha(self, mensagem):
        if self.settings.ia_pausar_ao_limite:
            self.settings.ia_pausada_ate = (date.today() + timedelta(days=1)).isoformat()
        self._atualizar_status(mensagem)

    def _atualizar_status(self, mensagem):
        self.settings.ia_status_mensagem = mensagem
        try:
            self.settings.save()
        except Exception:
            pass
        self.logger(mensagem)

    def _ler_erro_http(self, error):
        try:
            return error.read().decode("utf-8", errors="ignore")
        except Exception:
            return str(error)
