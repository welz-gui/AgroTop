"""O pool reusa conexões Postgres sem misturar transações entre sessões.

Medição de 2026-08-27: cada conexão nova ao Postgres de produção custa ~177 ms
de handshake, contra ~24 ms de uma query em conexão aberta. `_conn()` era
chamado dezenas de vezes por rerun — no financeiro, 29 vezes, ~5,1 s só de
handshake. O pool existe para eliminar isso.

O risco que estes testes travam **não é desempenho, é corrupção de transação.**
`_conn()` é dono da transação: faz commit ao sair e rollback em erro. O
Streamlit atende cada sessão de navegador numa thread do mesmo processo. Se
duas sessões compartilhassem UMA conexão, o rollback de uma abortaria a
gravação em voo da outra — perda de dado silenciosa, com dois usuários
simultâneos (escritório e curral), que é o uso normal do AgroTop.

Por isso cada `with _conn()` tem de receber uma conexão só sua, emprestada e
devolvida. `test_conexoes_simultaneas_sao_objetos_distintos` é o teste que
falha se alguém "simplificar" o pool para uma conexão compartilhada.

⚠️ A suíte roda em SQLite, que **não** é agrupado de propósito (ver
`test_sqlite_nao_segura_o_arquivo`). Os testes aqui travam os invariantes que
valem nos dois backends; o ganho do pool em si se mede contra o Postgres, com
`tools/medir_conexoes.py`.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db                       # noqa: E402
from repositories import conexao            # noqa: E402


class _ContaAberturas:
    """Conta quantas conexões o backend REALMENTE abre."""

    def __init__(self):
        self.n = 0
        self._real = sqlite3.connect

    def __enter__(self):
        def contado(*a, **k):
            self.n += 1
            return self._real(*a, **k)
        sqlite3.connect = contado
        return self

    def __exit__(self, *exc):
        sqlite3.connect = self._real
        return False


class TestSemanticaDeTransacao(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "pool.db"))
        db.init_db(forcar=True)
        db.clear_cache()

    def tearDown(self):
        conexao.fechar_pool()

    def test_conexoes_simultaneas_sao_objetos_distintos(self):
        """A garantia estrutural: dois `_conn()` abertos ao mesmo tempo nunca
        são a MESMA conexão.

        É isto que impede o rollback de uma sessão de abortar a gravação em voo
        de outra. Compartilhar uma conexão faria os dois blocos receberem o
        mesmo objeto — e é exatamente o que este teste recusa.
        """
        with conexao._conn() as primeira:
            with conexao._conn() as segunda:
                self.assertIsNot(primeira, segunda,
                                 "dois `with _conn()` simultâneos receberam a "
                                 "MESMA conexão — o rollback de um desfaria o "
                                 "trabalho do outro")

    def test_rollback_nao_desfaz_o_que_outra_conexao_gravou(self):
        """O efeito observável da garantia acima, sem depender de corrida.

        A versão anterior deste teste punha duas threads escrevendo ao mesmo
        tempo e era **flaky**: o SQLite serializa escritores, então a segunda
        thread esbarrava no lock e quem estourasse o timeout primeiro decidia o
        resultado. Passou local e no CI do PR que o introduziu, e quebrou depois
        num PR só de documentação. Um teste que às vezes exercita o que promete
        é pior que um determinístico que exercita menos.
        """
        with conexao._conn() as con:
            con.execute("CREATE TABLE prova_pool (marca TEXT)")
        with conexao._conn() as con:
            con.execute("INSERT INTO prova_pool VALUES ('a')")

        with self.assertRaises(RuntimeError):
            with conexao._conn() as con:
                con.execute("INSERT INTO prova_pool VALUES ('b')")
                raise RuntimeError("falha proposital: força o rollback")

        with conexao._conn() as con:
            marcas = [r[0] for r in con.execute(
                "SELECT marca FROM prova_pool ORDER BY marca").fetchall()]
        self.assertEqual(marcas, ["a"],
                         "ou o rollback levou junto a gravação anterior, ou a "
                         "gravação que falhou sobreviveu")

    def test_erro_de_negocio_nao_impede_o_uso_seguinte(self):
        """Uma exceção comum não pode deixar a camada de dados inutilizável."""
        for _ in range(5):
            with self.assertRaises(Exception):
                with conexao._conn() as con:
                    con.execute("SELECT * FROM tabela_que_nao_existe")

        with conexao._conn() as con:
            self.assertEqual(con.execute("SELECT 1").fetchone()[0], 1)

    def test_sqlite_nao_segura_o_arquivo(self):
        """SQLite é deixado FORA do pool de propósito.

        Conexão ociosa mantém o arquivo aberto, e no Windows isso faz
        `os.remove()` levantar PermissionError — foi o que quebrou
        `test_schema.py` quando o SQLite chegou a ser agrupado. Como abrir um
        arquivo local custa ~0,02 ms, não havia handshake nenhum a economizar:
        atrito garantido, ganho zero.
        """
        caminho = os.path.join(self.dir, "solto.db")
        db.configurar_sqlite(caminho)
        db.init_db(forcar=True)
        with conexao._conn() as con:
            con.execute("SELECT 1").fetchone()
        os.remove(caminho)      # PermissionError se sobrar handle aberto

    def test_fechar_pool_e_seguro_a_qualquer_momento(self):
        conexao.fechar_pool()
        conexao.fechar_pool()
        with conexao._conn() as con:
            self.assertEqual(con.execute("SELECT 1").fetchone()[0], 1)


class TestGuardaDoInitDb(unittest.TestCase):
    """`app.py` chama `init_db()` a cada rerun do Streamlit. O trabalho é
    idempotente, mas repeti-lo custava 1 conexão + 11 queries por clique —
    ~0,45 s em produção, em toda interação."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "guarda.db"))
        db.init_db(forcar=True)
        db.clear_cache()

    def tearDown(self):
        conexao.fechar_pool()

    def test_segunda_chamada_nao_toca_o_banco(self):
        with _ContaAberturas() as conta:
            db.init_db()
        self.assertEqual(conta.n, 0,
                         "init_db() repetido continua abrindo conexão")

    def test_forcar_ignora_a_guarda(self):
        """Os testes de idempotência dependem disso para continuarem valendo."""
        with _ContaAberturas() as conta:
            db.init_db(forcar=True)
        self.assertGreaterEqual(conta.n, 1, "forcar=True não executou nada")

    def test_banco_novo_reinicializa_sozinho(self):
        """Trocar de banco tem de re-semear, senão a suíte inteira quebraria."""
        db.configurar_sqlite(os.path.join(self.dir, "novo.db"))
        db.init_db()          # sem forcar: a guarda deve perceber o alvo novo
        with conexao._conn() as con:
            n = con.execute("SELECT count(*) FROM properties").fetchone()[0]
        self.assertGreaterEqual(n, 1, "banco novo ficou sem o seed da hierarquia")


class _CursorFalso:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        self.raw.sqls.append(sql)

    def fetchone(self):
        return None

    def close(self):
        pass


class _ConexaoFalsa:
    """Um psycopg2.connection de mentira: registra commits, rollbacks e o
    estado de autocommit, que é o que esta bateria precisa observar."""

    def __init__(self):
        self.autocommit = False
        self.commits = 0
        self.rollbacks = 0
        self.sqls = []

    def cursor(self, **kwargs):
        return _CursorFalso(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class _Psycopg2Falso:
    class extras:
        DictCursor = object


class TestCommitSoQuandoEscreve(unittest.TestCase):
    """Medição de 2026-08-29: com o pool no lugar, o `COMMIT` passou a ser o
    maior custo de cada `with _conn()` — 49,4 ms contra 24,0 ms da query. Como
    a maioria dos usos por rerun é leitura pura, `_PGConn` só abre transação
    quando aparece escrita.

    O risco aqui é o oposto do da bateria anterior: se a detecção classificar
    uma escrita como leitura, o dado é descartado em silêncio. Por isso a regra
    é conservadora e estes testes fixam cada caso.

    A suíte roda em SQLite, que já não abre transação para SELECT — por isso
    `_PGConn` é exercitado direto, com uma conexão falsa.
    """

    def setUp(self):
        self._psycopg2_real = getattr(conexao, "psycopg2", None)
        conexao.psycopg2 = _Psycopg2Falso
        self.raw = _ConexaoFalsa()
        self.con = conexao._PGConn(self.raw)

    def tearDown(self):
        if self._psycopg2_real is None:
            delattr(conexao, "psycopg2")
        else:
            conexao.psycopg2 = self._psycopg2_real

    def test_nasce_em_autocommit(self):
        self.assertTrue(self.raw.autocommit,
                        "a conexão abriu transação antes de saber se vai escrever")

    def test_leitura_pura_nao_faz_commit(self):
        self.con.execute("SELECT 1")
        self.con.commit()
        self.assertEqual(self.raw.commits, 0,
                         "leitura pura pagou um COMMIT (49 ms por uso)")
        self.assertTrue(self.raw.autocommit)

    def test_escrita_abre_transacao_e_faz_commit(self):
        self.con.execute("INSERT INTO animals (id) VALUES (?)", ("X",))
        self.assertFalse(self.raw.autocommit, "escrita ficou fora de transação")
        self.con.commit()
        self.assertEqual(self.raw.commits, 1, "a escrita não foi confirmada")

    def test_leitura_antes_da_escrita_nao_perde_o_commit(self):
        """O caso que mais erra na prática: ler, decidir, gravar."""
        self.con.execute("SELECT peso FROM weighings WHERE animal_id = ?", ("X",))
        self.con.execute("UPDATE animals SET peso = ? WHERE id = ?", (10, "X"))
        self.assertFalse(self.raw.autocommit)
        self.con.commit()
        self.assertEqual(self.raw.commits, 1)

    def test_leitura_depois_da_escrita_fica_na_mesma_transacao(self):
        self.con.execute("INSERT INTO animals (id) VALUES (?)", ("X",))
        self.con.execute("SELECT * FROM animals")
        self.con.commit()
        self.assertEqual(self.raw.commits, 1)

    def test_erro_em_escrita_faz_rollback(self):
        self.con.execute("DELETE FROM animals WHERE id = ?", ("X",))
        self.con.rollback()
        self.assertEqual(self.raw.rollbacks, 1, "a escrita não foi desfeita")

    def test_erro_em_leitura_nao_gasta_rollback(self):
        self.con.execute("SELECT 1")
        self.con.rollback()
        self.assertEqual(self.raw.rollbacks, 0)

    def test_verbo_fora_da_lista_conta_como_escrita(self):
        """Conservador: o que não for reconhecido como leitura vira transação."""
        for sql in ("TRUNCATE animals", "CREATE TABLE t (a int)",
                    "WITH x AS (INSERT INTO t VALUES (1) RETURNING a) SELECT * FROM x",
                    "SET search_path = public", "COPY t FROM STDIN"):
            with self.subTest(sql=sql[:20]):
                raw = _ConexaoFalsa()
                con = conexao._PGConn(raw)
                con.execute(sql)
                self.assertFalse(raw.autocommit,
                                 f"tratado como leitura: {sql[:30]!r}")

    def test_executescript_e_sempre_escrita(self):
        self.con.executescript("CREATE TABLE t (a int)")
        self.assertFalse(self.raw.autocommit)
        self.con.commit()
        self.assertEqual(self.raw.commits, 1)


if __name__ == "__main__":
    unittest.main()
