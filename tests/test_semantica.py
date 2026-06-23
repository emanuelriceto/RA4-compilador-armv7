# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara


import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.lexer_fsm import tokenizar_programa
from src.parser_ll1 import construirGramatica, parsear, gerarArvore
from src.semantica import (
    TIPO_BOOL,
    TIPO_INDEF,
    TIPO_INT,
    TIPO_REAL,
    TabelaSimbolos,
    construirTabelaSimbolos,
    formatarTabelaMarkdown,
    gerarArvoreAtribuida,
    inferir_tipo,
    salvarArvoreAtribuida,
    serializarArvoreAtribuidaJSON,
    serializarArvoreAtribuidaMarkdown,
    verificarTipos,
)


def _ast(fonte: str) -> dict:
    """Helper: tokeniza + parseia + devolve a AST de um programa fonte."""
    linhas = fonte.splitlines()
    tokens = tokenizar_programa(linhas)
    gram = construirGramatica()
    resultado = parsear(tokens, gram)
    return gerarArvore(resultado)


# --------------------------------------------------------------
# Casos felizes
# --------------------------------------------------------------


class TestTabelaSimbolosFelizes(unittest.TestCase):
    def test_declaracao_simples_seguida_de_uso(self):
        ast = _ast(
            "(START)\n"
            "(10 X)\n"
            "((X) 2 +)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(erros, [])
        self.assertIn("X", tabela)
        sim = tabela.obter("X")
        self.assertEqual(sim["tipo"], TIPO_INT)
        self.assertEqual(sim["linha_def"], 2)
        self.assertEqual(sim["linhas_uso"], [3])
        self.assertEqual(sim["escopo"], "global")

    def test_varias_variaveis_com_tipos_distintos(self):
        ast = _ast(
            "(START)\n"
            "(1 A)\n"
            "(2.5 B)\n"
            "((1 2 <) C)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(erros, [])
        self.assertEqual(tabela.obter("A")["tipo"], TIPO_INT)
        self.assertEqual(tabela.obter("B")["tipo"], TIPO_REAL)
        self.assertEqual(tabela.obter("C")["tipo"], TIPO_BOOL)
        # itens() devolve em ordem alfabética
        nomes = [s["nome"] for s in tabela.itens()]
        self.assertEqual(nomes, ["A", "B", "C"])

    def test_uso_dentro_de_estrutura_de_controle(self):
        ast = _ast(
            "(START)\n"
            "(0 I)\n"
            "(((I) 3 <) ((I) 1 +) WHILE)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(erros, [])
        sim = tabela.obter("I")
        self.assertEqual(sim["tipo"], TIPO_INT)
        # usado dentro de cond E body do WHILE (mesma linha → registrado uma vez)
        self.assertEqual(sim["linhas_uso"], [3])


# --------------------------------------------------------------
# Casos de erro
# --------------------------------------------------------------


class TestTabelaSimbolosErros(unittest.TestCase):
    def test_uso_sem_declaracao(self):
        ast = _ast(
            "(START)\n"
            "((X) 1 +)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(len(erros), 1)
        self.assertIn("'X'", erros[0].mensagem)
        self.assertIn("antes da declaração", erros[0].mensagem)
        self.assertEqual(erros[0].linha, 2)

    def test_redeclaracao_com_tipo_incompativel(self):
        ast = _ast(
            "(START)\n"
            "(10 X)\n"
            "(2.5 X)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(len(erros), 1)
        self.assertIn("'X'", erros[0].mensagem)
        self.assertIn("incompatível", erros[0].mensagem)
        self.assertEqual(erros[0].linha, 3)

    def test_redeclaracao_com_mesmo_tipo_eh_permitida(self):
        ast = _ast(
            "(START)\n"
            "(10 X)\n"
            "(20 X)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(erros, [])
        # mantém a primeira linha de declaração
        self.assertEqual(tabela.obter("X")["linha_def"], 2)

    def test_res_referencia_invalida(self):
        ast = _ast(
            "(START)\n"
            "(5 RES)\n"
            "(END)\n"
        )
        tabela, erros = construirTabelaSimbolos(ast)
        self.assertEqual(len(erros), 1)
        self.assertIn("5 linhas atrás", erros[0].mensagem)
        self.assertEqual(erros[0].linha, 2)

    def test_res_referencia_valida(self):
        ast = _ast(
            "(START)\n"
            "(1 2 +)\n"
            "(1 RES)\n"
            "(END)\n"
        )
        _, erros = construirTabelaSimbolos(ast)
        self.assertEqual(erros, [])


# --------------------------------------------------------------
# Inferência local + renderização
# --------------------------------------------------------------


class TestInferenciaERender(unittest.TestCase):
    def test_inferir_tipo_literais_e_relacional(self):
        tab = TabelaSimbolos()
        self.assertEqual(inferir_tipo({"tipo": "number", "valor": "42"}, tab), TIPO_INT)
        self.assertEqual(inferir_tipo({"tipo": "number", "valor": "3.14"}, tab), TIPO_REAL)
        rel = {
            "tipo": "binary",
            "op": ">=",
            "esq": {"tipo": "number", "valor": "1"},
            "dir": {"tipo": "number", "valor": "2"},
        }
        self.assertEqual(inferir_tipo(rel, tab), TIPO_BOOL)

    def test_formatar_tabela_markdown(self):
        ast = _ast(
            "(START)\n"
            "(10 X)\n"
            "((X) 2 +)\n"
            "(END)\n"
        )
        tabela, _ = construirTabelaSimbolos(ast)
        md = formatarTabelaMarkdown(tabela)
        self.assertIn("Tabela de Símbolos", md)
        self.assertIn("`X`", md)
        self.assertIn("int", md)
        self.assertIn("global", md)

    def test_formatar_tabela_vazia(self):
        ast = _ast("(START)\n(1 2 +)\n(END)\n")
        tabela, _ = construirTabelaSimbolos(ast)
        md = formatarTabelaMarkdown(tabela)
        self.assertIn("Nenhuma variável", md)


# --------------------------------------------------------------
# Verificação de Tipos (Sprint 3 / §4 do guia)
# --------------------------------------------------------------


def _check(fonte: str):
    """Helper: AST → tabela → verificarTipos; devolve (arvore, tabela, erros)."""
    arvore = _ast(fonte)
    tabela, _ = construirTabelaSimbolos(arvore)
    arvore, erros = verificarTipos(arvore, tabela)
    return arvore, tabela, erros


class TestVerificarTiposFelizes(unittest.TestCase):
    def test_soma_int_int(self):
        ast, _, erros = _check("(START)\n(1 2 +)\n(END)\n")
        self.assertEqual(erros, [])
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_INT)

    def test_soma_real_real(self):
        ast, _, erros = _check("(START)\n(1.5 2.0 +)\n(END)\n")
        self.assertEqual(erros, [])
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_REAL)

    def test_divisao_inteira_ok(self):
        ast, _, erros = _check("(START)\n(10 3 /)\n(END)\n")
        self.assertEqual(erros, [])
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_INT)

    def test_divisao_real_ok(self):
        ast, _, erros = _check("(START)\n(10.0 3.0 |)\n(END)\n")
        self.assertEqual(erros, [])
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_REAL)

    def test_relacional_produz_bool(self):
        ast, _, erros = _check("(START)\n(1 2 <)\n(END)\n")
        self.assertEqual(erros, [])
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_BOOL)

    def test_if_com_cond_bool(self):
        ast, _, erros = _check("(START)\n((1 2 <) (3 4 +) IF)\n(END)\n")
        self.assertEqual(erros, [])
        # tipo do IF = tipo do then_block (int)
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_INT)

    def test_ifelse_ramos_consistentes(self):
        ast, _, erros = _check(
            "(START)\n((1 2 <) (3 4 +) (5 6 +) IFELSE)\n(END)\n"
        )
        self.assertEqual(erros, [])
        self.assertEqual(ast["stmts"][0]["tipo_inferido"], TIPO_INT)


class TestVerificarTiposErros(unittest.TestCase):
    def test_soma_int_real_eh_erro(self):
        _, _, erros = _check("(START)\n(1 2.5 +)\n(END)\n")
        self.assertEqual(len(erros), 1)
        self.assertIn("'+'", erros[0].mensagem)
        self.assertIn("sem promoção", erros[0].mensagem)

    def test_divisao_inteira_com_real_eh_erro(self):
        _, _, erros = _check("(START)\n(10.0 3.0 /)\n(END)\n")
        self.assertEqual(len(erros), 1)
        self.assertIn("'/'", erros[0].mensagem)
        self.assertIn("'int'", erros[0].mensagem)

    def test_divisao_real_com_int_eh_erro(self):
        _, _, erros = _check("(START)\n(10 3 |)\n(END)\n")
        self.assertEqual(len(erros), 1)
        self.assertIn("'|'", erros[0].mensagem)
        self.assertIn("'real'", erros[0].mensagem)

    def test_if_com_cond_nao_bool_eh_erro(self):
        _, _, erros = _check("(START)\n(5 (1 2 +) IF)\n(END)\n")
        self.assertEqual(len(erros), 1)
        self.assertIn("IF", erros[0].mensagem)
        self.assertIn("'bool'", erros[0].mensagem)

    def test_while_com_cond_nao_bool_eh_erro(self):
        _, _, erros = _check("(START)\n(0 (1 2 +) WHILE)\n(END)\n")
        self.assertEqual(len(erros), 1)
        self.assertIn("WHILE", erros[0].mensagem)

    def test_ifelse_com_ramos_divergentes_eh_erro(self):
        # then = int, else = real → divergente
        _, _, erros = _check(
            "(START)\n((1 2 <) (3 4 +) (3.0 4.0 +) IFELSE)\n(END)\n"
        )
        self.assertEqual(len(erros), 1)
        self.assertIn("IFELSE", erros[0].mensagem)
        self.assertIn("divergentes", erros[0].mensagem)

    def test_relacional_com_tipos_distintos_eh_erro(self):
        _, _, erros = _check("(START)\n(1 2.5 <)\n(END)\n")
        self.assertEqual(len(erros), 1)
        self.assertIn("'<'", erros[0].mensagem)


# --------------------------------------------------------------
# Sprint 4 / Etapa 4: Árvore Sintática Atribuída
# --------------------------------------------------------------


class TestArvoreAtribuida(unittest.TestCase):
    def _atribuida(self, fonte: str):
        ast = _ast(fonte)
        tabela, erros1 = construirTabelaSimbolos(ast)
        ast2, erros2 = verificarTipos(ast, tabela)
        self.assertEqual(erros1, [])
        self.assertEqual(erros2, [])
        return gerarArvoreAtribuida(ast2, tabela), tabela

    def test_binary_int_recebe_instrucao_add(self):
        arv, _ = self._atribuida("(START)\n(1 2 +)\n(END)\n")
        bin_no = arv["stmts"][0]
        self.assertEqual(bin_no["tipo"], "binary")
        self.assertEqual(bin_no["meta_asm"]["instrucao_sugerida"], "ADD")
        self.assertEqual(bin_no["meta_asm"]["registrador"], "R0")
        self.assertEqual(bin_no["tipo_inferido"], "int")

    def test_binary_real_recebe_vadd_e_d0(self):
        arv, _ = self._atribuida("(START)\n(1.0 2.0 +)\n(END)\n")
        bin_no = arv["stmts"][0]
        self.assertEqual(bin_no["meta_asm"]["instrucao_sugerida"], "VADD.F64")
        self.assertEqual(bin_no["meta_asm"]["registrador"], "D0")

    def test_memwrite_carrega_simbolo_ref(self):
        arv, tabela = self._atribuida(
            "(START)\n(10 X)\n((X) 1 +)\n(END)\n"
        )
        decl = arv["stmts"][0]   # mem_write X
        self.assertEqual(decl["tipo"], "mem_write")
        self.assertEqual(decl["simbolo_ref"]["nome"], "X")
        self.assertEqual(decl["simbolo_ref"]["tipo"], TIPO_INT)
        self.assertEqual(decl["meta_asm"]["mem_label"], "mem_x")

    def test_if_recebe_label_fim(self):
        arv, _ = self._atribuida(
            "(START)\n((1 2 <) (3 4 +) IF)\n(END)\n"
        )
        no = arv["stmts"][0]
        self.assertEqual(no["tipo"], "if")
        self.assertIn("label_fim", no["meta_asm"])

    def test_ifelse_recebe_dois_labels(self):
        arv, _ = self._atribuida(
            "(START)\n((1 2 <) (3 4 +) (5 6 +) IFELSE)\n(END)\n"
        )
        no = arv["stmts"][0]
        self.assertEqual(no["tipo"], "ifelse")
        self.assertIn("label_else", no["meta_asm"])
        self.assertIn("label_fim", no["meta_asm"])

    def test_while_recebe_label_inicio_e_fim(self):
        arv, _ = self._atribuida(
            "(START)\n((1 2 <) (3 4 +) WHILE)\n(END)\n"
        )
        no = arv["stmts"][0]
        self.assertEqual(no["tipo"], "while")
        self.assertIn("label_inicio", no["meta_asm"])
        self.assertIn("label_fim", no["meta_asm"])

    def test_serializacao_json_e_md(self):
        import json

        arv, _ = self._atribuida("(START)\n(1 2 +)\n(END)\n")
        js = serializarArvoreAtribuidaJSON(arv)
        # round-trip por JSON
        decod = json.loads(js)
        self.assertEqual(decod["tipo"], "program")
        md = serializarArvoreAtribuidaMarkdown(arv)
        self.assertIn("Árvore Sintática Atribuída", md)
        self.assertIn("instr=ADD", md)

    def test_salvar_arvore_atribuida_em_disco(self):
        import tempfile

        arv, _ = self._atribuida("(START)\n(1 2 +)\n(END)\n")
        with tempfile.TemporaryDirectory() as tmp:
            p_md, p_json = salvarArvoreAtribuida(arv, diretorio=tmp)
            self.assertTrue(p_md.exists())
            self.assertTrue(p_json.exists())
            self.assertIn("Árvore", p_md.read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

    def test_multiplos_erros_acumulam(self):
        _, _, erros = _check(
            "(START)\n"
            "(1 2.5 +)\n"          # erro 1: int + real
            "(10 3.0 |)\n"         # erro 2: | com int
            "(5 (1 2 +) IF)\n"     # erro 3: IF com cond não-bool
            "(END)\n"
        )
        self.assertEqual(len(erros), 3)

    def test_uso_de_var_indef_nao_gera_erro_em_cascata(self):
        # X não foi declarada → erro reportado pela tabela, mas a soma
        # ((X) 1 +) NÃO deve gerar um segundo erro de tipo.
        ast = _ast("(START)\n((X) 1 +)\n(END)\n")
        tabela, erros_tab = construirTabelaSimbolos(ast)
        _, erros_tipo = verificarTipos(ast, tabela)
        self.assertEqual(len(erros_tab), 1)
        self.assertEqual(erros_tipo, [])


class TestPropagacaoTabela(unittest.TestCase):
    def test_tipo_de_mem_read_segue_tabela(self):
        ast = _ast(
            "(START)\n"
            "(1.5 X)\n"
            "((X) 2.0 +)\n"
            "(END)\n"
        )
        tabela, errs_tab = construirTabelaSimbolos(ast)
        self.assertEqual(errs_tab, [])
        self.assertEqual(tabela.obter("X")["tipo"], TIPO_REAL)
        ast, errs = verificarTipos(ast, tabela)
        self.assertEqual(errs, [])
        # ((X) 2.0 +) → real (porque X é real)
        self.assertEqual(ast["stmts"][1]["tipo_inferido"], TIPO_REAL)

    def test_mem_write_anota_tipo_indef_e_recursa_no_valor(self):
        ast, _, erros = _check(
            "(START)\n"
            "(1 X)\n"
            "(END)\n"
        )
        self.assertEqual(erros, [])
        no = ast["stmts"][0]
        self.assertEqual(no["tipo"], "mem_write")
        # mem_write propaga o tipo do valor escrito (T-MemDef)
        self.assertEqual(no["tipo_inferido"], TIPO_INT)
        # e o valor interno também foi anotado
        self.assertEqual(no["valor"]["tipo_inferido"], TIPO_INT)


if __name__ == "__main__":
    unittest.main()
