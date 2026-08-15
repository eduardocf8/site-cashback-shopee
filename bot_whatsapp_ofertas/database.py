import sqlite3
from datetime import datetime


class Database:
    def __init__(self, caminho="mensagens.db"):
        self.conn = sqlite3.connect(caminho)
        self.criar_tabela()

    def criar_tabela(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mensagens (
                id TEXT PRIMARY KEY,
                autor TEXT,
                texto TEXT,
                link TEXT,
                criado_em TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS links_enviados (
                link_original TEXT NOT NULL,
                grupo_destino TEXT NOT NULL DEFAULT '',
                link_afiliado TEXT,
                texto_final TEXT,
                criado_em TEXT,
                PRIMARY KEY (link_original, grupo_destino)
            )
        """)
        self.conn.commit()
        self._migrar_links_enviados_para_por_grupo()

    def _migrar_links_enviados_para_por_grupo(self):
        """Migra bancos antigos (de antes do controle por grupo de destino).

        Antes, 'links_enviados' tinha link_original como chave unica, ou
        seja, uma oferta enviada para QUALQUER grupo bloqueava reenvio para
        TODOS os grupos. Agora a chave e (link_original, grupo_destino),
        permitindo que a mesma oferta seja enviada a um grupo novo mesmo
        que ja tenha sido enviada a outro.

        Como o esquema antigo nao guardava a qual grupo cada link foi
        enviado, as linhas antigas sao migradas com grupo_destino=''
        (nao corresponde a nenhum grupo real), preservando o historico
        para consulta mas sem bloquear reenvios a partir de agora.
        """
        colunas = [
            linha[1]
            for linha in self.conn.execute("PRAGMA table_info(links_enviados)")
        ]
        if "grupo_destino" in colunas:
            return

        self.conn.execute("ALTER TABLE links_enviados RENAME TO links_enviados_legado")
        self.conn.execute("""
            CREATE TABLE links_enviados (
                link_original TEXT NOT NULL,
                grupo_destino TEXT NOT NULL DEFAULT '',
                link_afiliado TEXT,
                texto_final TEXT,
                criado_em TEXT,
                PRIMARY KEY (link_original, grupo_destino)
            )
        """)
        self.conn.execute("""
            INSERT INTO links_enviados
                (link_original, grupo_destino, link_afiliado, texto_final, criado_em)
            SELECT link_original, '', link_afiliado, texto_final, criado_em
            FROM links_enviados_legado
        """)
        self.conn.execute("DROP TABLE links_enviados_legado")
        self.conn.commit()

    def existe(self, id_msg):
        cursor = self.conn.execute(
            "SELECT 1 FROM mensagens WHERE id = ?",
            (id_msg,)
        )
        return cursor.fetchone() is not None

    def salvar(self, id_msg, autor, texto, link):
        self.conn.execute("""
            INSERT OR IGNORE INTO mensagens
            (id, autor, texto, link, criado_em)
            VALUES (?, ?, ?, ?, ?)
        """, (
            id_msg,
            autor,
            texto,
            link,
            datetime.now().isoformat(timespec="seconds")
        ))
        self.conn.commit()

    def fechar(self):
        self.conn.close()

    def quantidade(self):
        cursor = self.conn.execute("SELECT COUNT(*) FROM mensagens")
        return cursor.fetchone()[0]

    def link_ja_enviado(self, link_original, grupo_destino):
        """Verifica se este link ja foi enviado para ESTE grupo especifico.

        O controle e por (link_original, grupo_destino): enviar uma oferta
        para o Grupo X nao impede que a mesma oferta seja enviada depois
        para o Grupo Y, caso o Grupo Y ainda nao a tenha recebido.
        """
        cursor = self.conn.execute(
            "SELECT 1 FROM links_enviados WHERE link_original = ? AND grupo_destino = ?",
            (link_original, grupo_destino)
        )
        return cursor.fetchone() is not None

    def link_ja_enviado_para_todos(self, link_original, grupos_destino):
        """Verifica se o link ja foi enviado para TODOS os grupos da lista.

        Util para decidir, antes de montar a oferta, se ela pode ser
        descartada de vez (ja foi enviada a todos os destinos atuais) ou
        se ainda vale a pena processar (falta enviar a pelo menos um
        grupo novo).
        """
        grupos = [g for g in grupos_destino if g]
        if not grupos:
            return False
        return all(self.link_ja_enviado(link_original, grupo) for grupo in grupos)

    def salvar_link_enviado(self, link_original, link_afiliado, texto_final, grupo_destino):
        self.conn.execute("""
            INSERT OR REPLACE INTO links_enviados
            (link_original, grupo_destino, link_afiliado, texto_final, criado_em)
            VALUES (?, ?, ?, ?, ?)
        """, (
            link_original,
            grupo_destino,
            link_afiliado,
            texto_final,
            datetime.now().isoformat(timespec="seconds")
        ))
        self.conn.commit()

    def listar_links_enviados(self, limite=200):
        cursor = self.conn.execute("""
            SELECT criado_em, link_original, grupo_destino, link_afiliado, texto_final
            FROM links_enviados
            ORDER BY criado_em DESC
            LIMIT ?
        """, (limite,))
        return cursor.fetchall()

    def limpar_links_enviados(self):
        self.conn.execute("DELETE FROM links_enviados")
        self.conn.commit()
