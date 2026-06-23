# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.armv7_generator import gerar_assembly_de_arvore_atribuida
from src.parser_ll1 import construirGramatica, gerarArvore, parsear
from src.lexer_fsm import tokenizar_programa
from src.pipeline import prepararEntradaSemantica
from src.semantica import (
    construirTabelaSimbolos,
    gerarArvoreAtribuida,
    verificarTipos,
)


CLI = ROOT / "AnalisadorSemantico.py"
CWD = ROOT  # garante caminhos relativos dos arquivos teste*.txt


def _rodar_cli(arquivo: str, out_dir: Path) -> int:
    """Executa o AnalisadorSemantico.py como subprocesso e devolve o exit."""
    cmd = [sys.executable, str(CLI), arquivo, "--out-dir", str(out_dir)]
    proc = subprocess.run(
        cmd,
        cwd=str(CWD),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode


def _pipeline_em_processo(arquivo: str) -> tuple[list[str], list]:
    """Roda o pipeline (sem CLI) e devolve (erros_lex_sint, erros_sem)."""
    abs_path = str(CWD / arquivo)
    r = prepararEntradaSemantica(abs_path)
    if r["erros_lexsint"]:
        return r["erros_lexsint"], []
    tabela, e1 = construirTabelaSimbolos(r["arvore"])
    _, e2 = verificarTipos(r["arvore"], tabela)
    return [], list(e1) + list(e2)


# ---------------------------------------------------------------------------
# casos "felizes": teste1/2/3.txt devem passar sem erros
# ---------------------------------------------------------------------------


class TestArquivosTesteValidos(unittest.TestCase):

    def _verifica_arquivo_valido(self, nome: str) -> None:
        erros_ls, erros_sem = _pipeline_em_processo(nome)
        self.assertEqual(
            erros_ls, [],
            f"{nome} não deveria ter erros léxicos/sintáticos: {erros_ls}",
        )
        self.assertEqual(
            erros_sem, [],
            f"{nome} não deveria ter erros semânticos: "
            f"{[str(e) for e in erros_sem]}",
        )

    def test_teste1_txt_passa_limpo(self):
        self._verifica_arquivo_valido("teste1.txt")

    def test_teste2_txt_passa_limpo(self):
        self._verifica_arquivo_valido("teste2.txt")

    def test_teste3_txt_passa_limpo(self):
        self._verifica_arquivo_valido("teste3.txt")

    def test_cada_valido_gera_assembly(self):
        # Garante que a árvore atribuída de fato vira código ARM.
        for nome in ("teste1.txt", "teste2.txt", "teste3.txt"):
            with self.subTest(arquivo=nome):
                r = prepararEntradaSemantica(str(CWD / nome))
                tabela, e1 = construirTabelaSimbolos(r["arvore"])
                ast2, e2 = verificarTipos(r["arvore"], tabela)
                self.assertEqual(e1, [])
                self.assertEqual(e2, [])
                atribuida = gerarArvoreAtribuida(ast2, tabela)
                asm = gerar_assembly_de_arvore_atribuida(atribuida)
                self.assertIn("_start:", asm)
                self.assertIn(".data", asm)


# ---------------------------------------------------------------------------
# CLI end-to-end + verificação "Assembly NÃO gerado quando há erro"
# ---------------------------------------------------------------------------


class TestCliFimAFim(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="ra3_e2e_")
        self.out = Path(self.tmp)
        self.asm = self.out / "ultima_execucao.s"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------- felizes -------

    def test_cli_teste1_exit_zero_e_gera_assembly(self):
        rc = _rodar_cli("teste1.txt", self.out)
        self.assertEqual(rc, 0)
        self.assertTrue(self.asm.exists(), "ultima_execucao.s deveria existir")
        self.assertGreater(self.asm.stat().st_size, 0)

    def test_cli_teste2_exit_zero_e_gera_assembly(self):
        rc = _rodar_cli("teste2.txt", self.out)
        self.assertEqual(rc, 0)
        self.assertTrue(self.asm.exists())

    def test_cli_teste3_exit_zero_e_gera_assembly(self):
        rc = _rodar_cli("teste3.txt", self.out)
        self.assertEqual(rc, 0)
        self.assertTrue(self.asm.exists())

    def test_cli_gera_todos_artefatos_obrigatorios(self):
        _rodar_cli("teste1.txt", self.out)
        # nota: tokens_ultima_execucao.txt é salvo pelo lexer no diretório
        # output/ padrão (ver pipeline.tokenizar_programa), não no --out-dir.
        obrigatorios = [
            "ARQUIVO_USADO.txt",
            "gramatica_dump.md",
            "derivacao_ultima_execucao.md",
            "tabela_simbolos.md",
            "erros_semanticos.md",
            "arvore_atribuida.md",
            "arvore_atribuida.json",
            "ultima_execucao.s",
        ]
        for nome in obrigatorios:
            with self.subTest(arquivo=nome):
                self.assertTrue(
                    (self.out / nome).exists(),
                    f"artefato obrigatório ausente: {nome}",
                )

    def test_cli_arquivo_usado_registra_nome(self):
        _rodar_cli("teste2.txt", self.out)
        conteudo = (self.out / "ARQUIVO_USADO.txt").read_text(encoding="utf-8")
        self.assertIn("teste2.txt", conteudo)

    # ------- erros -------

    def test_cli_erro_lexico_exit_1_sem_assembly(self):
        rc = _rodar_cli("teste_erro_lexico.txt", self.out)
        self.assertEqual(rc, 1)
        self.assertFalse(
            self.asm.exists(),
            "Assembly NÃO deve ser gerado quando há erro léxico",
        )

    def test_cli_erro_sintatico_exit_1_sem_assembly(self):
        rc = _rodar_cli("teste_erro_sintatico.txt", self.out)
        self.assertEqual(rc, 1)
        self.assertFalse(self.asm.exists())

    def test_cli_erro_semantico_exit_2_sem_assembly(self):
        rc = _rodar_cli("teste_erro_semantico.txt", self.out)
        self.assertEqual(rc, 2)
        self.assertFalse(
            self.asm.exists(),
            "Assembly NÃO deve ser gerado quando há erro semântico",
        )
        # mas o relatório de erros precisa existir
        self.assertTrue(
            (self.out / "erros_semanticos.md").exists(),
            "erros_semanticos.md deve ser gerado mesmo com erros",
        )

    def test_cli_erro_semantico_apaga_asm_antigo(self):
        # primeiro roda um caso válido para criar o .s
        _rodar_cli("teste1.txt", self.out)
        self.assertTrue(self.asm.exists())
        # agora roda um caso com erro semântico — o .s antigo deve sumir
        _rodar_cli("teste_erro_semantico.txt", self.out)
        self.assertFalse(
            self.asm.exists(),
            "ultima_execucao.s antigo deveria ter sido removido",
        )


# ---------------------------------------------------------------------------
# pipeline em-processo: contagem de erros do teste_erro_semantico
# ---------------------------------------------------------------------------


class TestErroSemanticoDetalhado(unittest.TestCase):

    def test_teste_erro_semantico_reporta_multiplos_erros(self):
        erros_ls, erros_sem = _pipeline_em_processo("teste_erro_semantico.txt")
        self.assertEqual(erros_ls, [], "não deve haver erro léxico/sintático")
        # o arquivo cobre 9 casos distintos; aceitamos qualquer número >=5
        self.assertGreaterEqual(
            len(erros_sem), 5,
            f"esperava ao menos 5 erros semânticos, obteve: {erros_sem}",
        )

    def test_teste_erro_semantico_inclui_nao_declarada(self):
        _, erros_sem = _pipeline_em_processo("teste_erro_semantico.txt")
        msgs = [str(e).lower() for e in erros_sem]
        self.assertTrue(
            any("antes da declara" in m or "não declarada" in m for m in msgs),
            f"esperava menção a variável não declarada, obteve: {msgs}",
        )

    def test_teste_erro_semantico_inclui_condicao_nao_bool(self):
        _, erros_sem = _pipeline_em_processo("teste_erro_semantico.txt")
        msgs = [str(e).lower() for e in erros_sem]
        self.assertTrue(
            any("if" in m or "while" in m for m in msgs),
            f"esperava menção a condição IF/WHILE, obteve: {msgs}",
        )


if __name__ == "__main__":
    unittest.main()
