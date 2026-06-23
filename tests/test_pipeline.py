# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer_fsm import Erros, tokenizar_linha, tokenizar_programa
from src.parser_ll1 import (
    construirGramatica,
    parsear,
    gerarArvore,
)
from src.pipeline import (
    lerArquivo,
    lerTokens,
    salvarTokens,
    executar_fase2,
    gerarAssembly,
    prepararEntradaSemantica,
)


def _programa(linhas):
    tokens = tokenizar_programa(["(START)"] + list(linhas) + ["(END)"])
    return tokens


class TestGramaticaLL1(unittest.TestCase):
    def test_construirGramatica_sem_conflitos(self):
        g = construirGramatica()
        self.assertIn("PROGRAM", g["nao_terminais"])
        self.assertGreater(len(g["tabela"]), 0)
        # PROGRAM é o símbolo inicial
        self.assertEqual(g["inicial"], "PROGRAM")

    def test_first_follow_contem_basicos(self):
        g = construirGramatica()
        self.assertIn("(", g["first"]["PROGRAM"])
        self.assertIn("(", g["first"]["ITEM"])
        self.assertIn(")", g["follow"]["ITEM"])

    def test_tabela_resolve_item(self):
        g = construirGramatica()
        self.assertIn(("ITEM", "numero"), g["tabela"])
        self.assertIn(("ITEM", "("), g["tabela"])


class TestParser(unittest.TestCase):
    def setUp(self):
        self.g = construirGramatica()

    def test_programa_minimo(self):
        toks = _programa([])
        res = parsear(toks, self.g)
        arv = gerarArvore(res)
        self.assertEqual(arv["tipo"], "program")
        self.assertEqual(arv["stmts"], [])

    def test_binaria_simples(self):
        toks = _programa(["(3.0 2.0 +)"])
        res = parsear(toks, self.g)
        arv = gerarArvore(res)
        self.assertEqual(arv["stmts"][0]["tipo"], "binary")
        self.assertEqual(arv["stmts"][0]["op"], "+")

    def test_aninhamento(self):
        toks = _programa(["((3 2 +) (4 1 -) *)"])
        arv = gerarArvore(parsear(toks, self.g))
        no = arv["stmts"][0]
        self.assertEqual(no["tipo"], "binary")
        self.assertEqual(no["op"], "*")
        self.assertEqual(no["esq"]["op"], "+")
        self.assertEqual(no["dir"]["op"], "-")

    def test_mem_write_e_read(self):
        toks = _programa(["(10 MEM)", "(MEM)"])
        arv = gerarArvore(parsear(toks, self.g))
        self.assertEqual(arv["stmts"][0]["tipo"], "mem_write")
        self.assertEqual(arv["stmts"][1]["tipo"], "mem_read")

    def test_res_ref(self):
        toks = _programa(["(3 2 +)", "(1 RES)"])
        arv = gerarArvore(parsear(toks, self.g))
        self.assertEqual(arv["stmts"][1]["tipo"], "res_ref")
        self.assertEqual(arv["stmts"][1]["linhas_atras"], 1)

    def test_if(self):
        toks = _programa(["((A) 0 >) (1 B) IF"])
        # ajusta para sintaxe correta com parens extras
        toks = _programa(["(((A) 0 >) (1 B) IF)"])
        arv = gerarArvore(parsear(toks, self.g))
        self.assertEqual(arv["stmts"][0]["tipo"], "if")

    def test_ifelse(self):
        toks = _programa(["(((A) 0 >) (1 B) (0 B) IFELSE)"])
        arv = gerarArvore(parsear(toks, self.g))
        self.assertEqual(arv["stmts"][0]["tipo"], "ifelse")

    def test_while(self):
        toks = _programa(["(((C) 0 >) ((C) 1 -) WHILE)"])
        arv = gerarArvore(parsear(toks, self.g))
        self.assertEqual(arv["stmts"][0]["tipo"], "while")

    def test_erro_sintatico_token_extra(self):
        toks = _programa(["(3 2 + 5)"])
        with self.assertRaises(Erros):
            parsear(toks, self.g)

    def test_erro_sem_start(self):
        toks = tokenizar_programa(["(3 2 +)", "(END)"])
        with self.assertRaises(Erros):
            parsear(toks, self.g)

    def test_erro_sem_end(self):
        toks = tokenizar_programa(["(START)", "(3 2 +)"])
        with self.assertRaises(Erros):
            parsear(toks, self.g)

    def test_recuperacao_panico_multi_erros(self):
        # Modo panico: o parser deve continuar apos o primeiro erro e
        # reportar varios erros em uma unica execucao. Aqui ha 3 problemas
        # sintaticos distintos no mesmo programa.
        toks = tokenizar_programa([
            "(START)",
            "(3 2 + 5)",          # token extra antes do ')'
            "(1 RES MEM)",        # 3 itens sem IFELSE
            "(((1 2 +) 3 4 -) WHILE)",  # itens demais antes de WHILE
            "(END)",
        ])
        try:
            parsear(toks, self.g)
        except Erros as erro:
            mensagem = str(erro)
        else:  # pragma: no cover - so deveria executar se nao houver erro
            self.fail("parsear() deveria ter levantado Erros")
        # A mensagem deve conter o cabecalho de modo panico e pelo menos
        # 3 erros distintos (um por linha problematica).
        self.assertIn("modo panico", mensagem)
        contagem = mensagem.count("Erro sintatico")
        self.assertGreaterEqual(contagem, 3, f"esperava >=3 erros, veio: {mensagem}")


class TestGeracaoAssembly(unittest.TestCase):
    def setUp(self):
        self.g = construirGramatica()

    def _gerar(self, linhas):
        arv = gerarArvore(parsear(_programa(linhas), self.g))
        return gerarAssembly(arv)

    def test_instrucoes_basicas(self):
        asm = self._gerar(["(3.0 2.0 +)", "(5.0 1.0 -)", "(2.0 3.0 *)", "(6.0 2.0 |)"])
        self.assertIn("VADD.F64", asm)
        self.assertIn("VSUB.F64", asm)
        self.assertIn("VMUL.F64", asm)
        self.assertIn("VDIV.F64", asm)

    def test_rotinas_idiv_mod_pow(self):
        asm = self._gerar(["(10 3 /)", "(10 3 %)", "(2 5 ^)"])
        self.assertIn("__op_idiv", asm)
        self.assertIn("__op_mod", asm)
        self.assertIn("__op_pow", asm)

    def test_assembly_com_while(self):
        asm = self._gerar(["(10 C)", "(((C) 0 >) ((C) 1 -) WHILE)"])
        self.assertIn("L_while_i", asm)
        self.assertIn("L_while_f", asm)

    def test_assembly_com_ifelse(self):
        asm = self._gerar(["(((A) 0 >) (1 B) (0 B) IFELSE)"])
        self.assertIn("L_else", asm)
        self.assertIn("L_ife_fim", asm)

    def test_ieee754_double(self):
        asm = self._gerar(["(3.14 2.0 +)"])
        self.assertIn(".double", asm)
        self.assertIn("F64", asm)


class TestLerTokens(unittest.TestCase):
    def test_ciclo_tokens(self):
        linhas = [[t for t in tokenizar_linha("(3 2 +)", numero_linha=1)]]
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "toks.txt")
            salvarTokens(caminho, linhas)
            recuperados = lerTokens(caminho)
        self.assertEqual([t.valor for t in recuperados], ["(", "3", "2", "+", ")"])


class TestLerArquivoEFluxo(unittest.TestCase):
    def test_ler_arquivo_ignora_linhas_em_branco(self):
        # Coment\u00e1rios da linguagem usam ``*{ ... }*`` e s\u00e3o removidos
        # somente na fase de tokeniza\u00e7\u00e3o. lerArquivo deve apenas pular
        # linhas em branco \u2014 ``#`` n\u00e3o \u00e9 mais reconhecido como coment\u00e1rio.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("(START)\n\n*{ comentario }*\n(1 2 +)\n(END)\n")
            nome = f.name
        try:
            linhas = []
            lerArquivo(nome, linhas)
            self.assertEqual(
                linhas,
                ["(START)", "*{ comentario }*", "(1 2 +)", "(END)"],
            )
        finally:
            os.unlink(nome)

    def test_pipeline_fim_a_fim(self):
        conteudo = "(START)\n(3 2 +)\n(1 RES)\n(END)\n"
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "p.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(conteudo)
            r = executar_fase2(
                caminho_fonte=src,
                caminho_tokens=os.path.join(d, "tk.txt"),
                caminho_asm=os.path.join(d, "o.s"),
                caminho_arvore=os.path.join(d, "a.txt"),
            )
            self.assertIn("VADD.F64", r["assembly"])
            self.assertEqual(r["arvore"]["stmts"][1]["tipo"], "res_ref")


class TestPrepararEntradaSemantica(unittest.TestCase):
    """Fase 3 §3 — função ``prepararEntradaSemantica(arquivo)``."""

    def _escrever(self, d, conteudo):
        caminho = os.path.join(d, "p.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        return caminho

    def test_arquivo_valido_retorna_arvore(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(d, "(START)\n(1 2 +)\n(END)\n")
            r = prepararEntradaSemantica(src)
        self.assertEqual(r["erros_lexsint"], [])
        self.assertIsNotNone(r["arvore"])
        self.assertEqual(r["arvore"]["tipo"], "program")
        self.assertTrue(len(r["tokens"]) > 0)

    def test_descarta_comentarios(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(
                d,
                "(START)\n*{ comentario }*\n(1 *{ x }* 2 +)\n(END)\n",
            )
            r = prepararEntradaSemantica(src)
        self.assertEqual(r["erros_lexsint"], [])
        valores = [t.valor for t in r["tokens"]]
        self.assertNotIn("*{", valores)
        self.assertNotIn("}*", valores)

    def test_erro_lexico_vai_para_lista(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(d, "(START)\n(1 & 2 +)\n(END)\n")
            r = prepararEntradaSemantica(src)
        self.assertIsNone(r["arvore"])
        self.assertTrue(any("[léxico]" in e for e in r["erros_lexsint"]))

    def test_comentario_aberto_vai_para_lista(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(d, "(START)\n*{ aberto\n(1 2 +)\n(END)\n")
            r = prepararEntradaSemantica(src)
        self.assertIsNone(r["arvore"])
        self.assertTrue(any("não fechado" in e for e in r["erros_lexsint"]))

    def test_erro_sintatico_vai_para_lista(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(d, "(START)\n(1 2)\n(END)\n")
            r = prepararEntradaSemantica(src)
        self.assertIsNone(r["arvore"])
        self.assertTrue(any("[sintático]" in e for e in r["erros_lexsint"]))

    def test_falta_start_eh_reportado(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(d, "(1 2 +)\n(END)\n")
            r = prepararEntradaSemantica(src)
        self.assertIsNone(r["arvore"])
        self.assertTrue(
            any("(START)" in e for e in r["erros_lexsint"]),
            f"erros: {r['erros_lexsint']}",
        )

    def test_falta_end_eh_reportado(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._escrever(d, "(START)\n(1 2 +)\n")
            r = prepararEntradaSemantica(src)
        self.assertIsNone(r["arvore"])
        self.assertTrue(
            any("(END)" in e for e in r["erros_lexsint"]),
            f"erros: {r['erros_lexsint']}",
        )


class TestAssemblyTipado(unittest.TestCase):
    """Sprint 5 / Etapa 5: dispatch ARM int x VFP real por tipo_inferido."""

    def _gerar(self, fonte: str) -> str:
        from src.semantica import (
            construirTabelaSimbolos,
            gerarArvoreAtribuida,
            verificarTipos,
        )
        from src.armv7_generator import gerar_assembly_de_arvore_atribuida

        linhas = fonte.splitlines()
        tokens = tokenizar_programa(linhas)
        gram = construirGramatica()
        resultado = parsear(tokens, gram)
        ast = gerarArvore(resultado)
        tabela, e1 = construirTabelaSimbolos(ast)
        ast2, e2 = verificarTipos(ast, tabela)
        self.assertEqual(e1, [])
        self.assertEqual(e2, [])
        atribuida = gerarArvoreAtribuida(ast2, tabela)
        return gerar_assembly_de_arvore_atribuida(atribuida)

    def test_int_soma_usa_add_arm(self):
        asm = self._gerar("(START)\n(1 2 +)\n(END)\n")
        self.assertIn("tipo=int +", asm)
        self.assertIn("ADD r0, r0, r1", asm)
        self.assertNotIn("VADD.F64 d0, d0, d1", asm)

    def test_real_soma_usa_vadd(self):
        asm = self._gerar("(START)\n(1.0 2.0 +)\n(END)\n")
        self.assertIn("VADD.F64 d0, d0, d1", asm)
        self.assertNotIn("ADD r0, r0, r1", asm)

    def test_int_subtracao_e_multiplicacao(self):
        asm = self._gerar("(START)\n(5 2 -)\n(3 4 *)\n(END)\n")
        self.assertIn("SUB r0, r0, r1", asm)
        self.assertIn("MUL r0, r0, r1", asm)

    def test_int_relacional_usa_cmp_movcc(self):
        asm = self._gerar("(START)\n(1 2 <)\n(END)\n")
        self.assertIn("CMP r0, r1", asm)
        self.assertIn("MOVLT r0, #1", asm)

    def test_cabecalho_lista_tipos_por_stmt(self):
        asm = self._gerar("(START)\n(1 2 +)\n(1.0 2.0 +)\n(END)\n")
        self.assertIn("ÁRVORE SINTÁTICA ATRIBUÍDA", asm)
        self.assertIn("stmt #1: int", asm)
        self.assertIn("stmt #2: real", asm)


if __name__ == "__main__":
    unittest.main()
