# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara

# Ponto de entrada do programa (Fase 3 — Analisador Semântico).
# Uso: python AnalisadorSemantico.py <arquivo.txt>
#
# Fluxo completo:
#   1) prepararEntradaSemantica  → lê arquivo, tokeniza, parseia LL(1)
#   2) se erros léxicos/sintáticos: salva relatório e sai(1)
#   3) construirTabelaSimbolos   → tabela com tipos por nome
#   4) verificarTipos            → anota AST com tipo_inferido
#   5) se erros semânticos: salva relatório e sai(2)  ← NÃO gera Assembly
#   6) gerarArvoreAtribuida      → anota metadados de ASM
#   7) gerar_assembly_de_arvore_atribuida → emite ARMv7 tipado
#   8) salva TODOS os artefatos em output/
#   9) imprime resumo no terminal
#

import argparse
import sys
from pathlib import Path

from src.armv7_generator import gerar_assembly_de_arvore_atribuida
from src.arm_encoder import gerar_hex, gerar_words_cpulator
from src.parser_ll1 import arvore_para_texto, derivacao_para_texto_tabela
from src.pipeline import prepararEntradaSemantica, salvarTokens
from src.semantica import (
    construirTabelaSimbolos,
    formatarTabelaMarkdown,
    gerarArvoreAtribuida,
    salvarArvoreAtribuida,
    salvarTabelaSimbolos,
    verificarTipos,
)


# ---------------------------------------------------------------------------
# helpers de I/O — dump de gramática (mantido da Fase 2)
# ---------------------------------------------------------------------------


def _dump_gramatica(g: dict) -> str:
    """Markdown com produções, FIRST/FOLLOW e tabela LL(1)."""

    def fmt_set(s: set) -> str:
        return "{ " + ", ".join(sorted(s)) + " }" if s else "{ }"

    md: list[str] = []
    md.append("# Gramática LL(1)\n")
    md.append("## 1. Regras de Produção\n")
    md.append("| # | Não-Terminal | Produção |")
    md.append("|---|---|---|")
    for i, (lhs, rhs) in enumerate(g["producoes"]):
        corpo = " ".join(rhs) if rhs else "ε"
        md.append(f"| {i} | {lhs} | {corpo} |")
    md.append("")

    md.append("## 2. Conjuntos FIRST\n")
    md.append("| Não-Terminal | FIRST |")
    md.append("|---|---|")
    for nt in sorted(g["nao_terminais"]):
        md.append(f"| {nt} | {fmt_set(g['first'][nt])} |")
    md.append("")

    md.append("## 3. Conjuntos FOLLOW\n")
    md.append("| Não-Terminal | FOLLOW |")
    md.append("|---|---|")
    for nt in sorted(g["nao_terminais"]):
        md.append(f"| {nt} | {fmt_set(g['follow'][nt])} |")
    md.append("")

    md.append("## 4. Tabela de Análise LL(1)\n")
    md.append("| Não-Terminal | Terminal | Produção |")
    md.append("|---|---|---|")
    for (nt, t), idx in sorted(g["tabela"].items()):
        lhs, rhs = g["producoes"][idx]
        corpo = " ".join(rhs) if rhs else "ε"
        md.append(f"| {nt} | {t} | #{idx}: {lhs} → {corpo} |")
    md.append("")
    return "\n".join(md)


def _salvar_erros_semanticos(erros: list, caminho: Path) -> None:
    """Escreve `output/erros_semanticos.md` (vazio → 'Nenhum erro')."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not erros:
        caminho.write_text(
            "# Erros Semânticos\n\n_Nenhum erro semântico encontrado._\n",
            encoding="utf-8",
        )
        return
    linhas = ["# Erros Semânticos\n"]
    linhas.append(f"Total: **{len(erros)}**\n")
    for i, e in enumerate(erros, 1):
        linhas.append(f"{i}. {e}")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _salvar_relatorio_lexsint(erros: list[str], caminho: Path) -> None:
    """Escreve `output/erros_lexsint.md` para erros das fases 1/2."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas = ["# Erros Léxicos / Sintáticos\n"]
    linhas.append(f"Total: **{len(erros)}**\n")
    for i, e in enumerate(erros, 1):
        linhas.append(f"{i}. {e}")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _imprimir_secao(titulo: str) -> None:
    print()
    print("=" * 60)
    print(titulo)
    print("=" * 60)


def _agrupar_tokens_por_linha(tokens: list) -> list[list]:
    """Agrupa a lista plana de Tokens pelo atributo `linha`.

    Usado para alimentar :func:`salvarTokens`, que espera uma lista
    de listas (uma por linha do arquivo-fonte).
    """
    if not tokens:
        return []
    max_linha = max(t.linha for t in tokens)
    grupos: list[list] = [[] for _ in range(max_linha)]
    for t in tokens:
        grupos[t.linha - 1].append(t)
    return grupos


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Analisador Semântico (Fase 3) — RPN ARMv7",
    )
    ap.add_argument("arquivo", help="Arquivo-fonte (.txt) com o programa RPN")
    ap.add_argument(
        "--out-dir",
        default="output",
        help="Diretório de saída (padrão: output/)",
    )
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # registra o arquivo usado nesta execução (§8 do guia)
    (out / "ARQUIVO_USADO.txt").write_text(args.arquivo + "\n", encoding="utf-8")

    print(f"Arquivo analisado : {args.arquivo}")

    # ------------------------------------------------------------
    # 1) Léxico + Sintático
    # ------------------------------------------------------------
    r = prepararEntradaSemantica(args.arquivo)

    # Persiste os tokens reconhecidos pelo lexer em `output/`. É feito
    # mesmo quando a análise sintática falha — assim o avaliador sempre
    # tem o artefato da Fase 1 disponível para inspeção.
    if r["tokens"]:
        salvarTokens(
            out / "tokens_ultima_execucao.txt",
            _agrupar_tokens_por_linha(r["tokens"]),
        )

    # Salvamos derivação e dump da gramática agora (úteis mesmo se a
    # análise abortar mais à frente).
    if r["gramatica"] is not None:
        (out / "gramatica_dump.md").write_text(
            _dump_gramatica(r["gramatica"]) + "\n", encoding="utf-8",
        )
    if r["passos"] and r["tokens"]:
        (out / "derivacao_ultima_execucao.md").write_text(
            derivacao_para_texto_tabela(r["passos"], r["tokens"]) + "\n",
            encoding="utf-8",
        )

    _imprimir_secao("Análise Léxica")
    print(f"Tokens reconhecidos : {len(r['tokens'])}")
    _imprimir_secao("Análise Sintática")
    if r["erros_lexsint"]:
        print(f"Erros léxicos/sintáticos: {len(r['erros_lexsint'])}")
        for e in r["erros_lexsint"]:
            print(f"  - {e}")
        _salvar_relatorio_lexsint(r["erros_lexsint"], out / "erros_lexsint.md")
        # Remove .s antigo para não enganar o avaliador
        asm_path = out / "ultima_execucao.s"
        if asm_path.exists():
            asm_path.unlink()
        print()
        print(f"Relatório de erros : {out / 'erros_lexsint.md'}")
        print("Assembly NÃO foi gerado (existem erros léxicos/sintáticos).")
        return 1
    print("AST construída com sucesso.")
    arvore = r["arvore"]

    # ------------------------------------------------------------
    # 2) Tabela de Símbolos
    # ------------------------------------------------------------
    tabela, erros_ts = construirTabelaSimbolos(arvore)
    caminho_tabela = salvarTabelaSimbolos(tabela, out / "tabela_simbolos.md")

    # ------------------------------------------------------------
    # 3) Verificação de Tipos
    # ------------------------------------------------------------
    arvore_tipada, erros_vt = verificarTipos(arvore, tabela)
    erros_sem = list(erros_ts) + list(erros_vt)

    _imprimir_secao("Análise Semântica")
    print(f"Símbolos declarados : {len(tabela)}")
    print(f"Erros semânticos    : {len(erros_sem)}")
    for e in erros_sem:
        print(f"  - {e}")
    _salvar_erros_semanticos(erros_sem, out / "erros_semanticos.md")

    if erros_sem:
        # política da §6/§7: NÃO gera Assembly com erro semântico
        asm_path = out / "ultima_execucao.s"
        if asm_path.exists():
            asm_path.unlink()
        # salva árvore parcial (sem meta_asm) para diagnóstico
        salvarArvoreAtribuida(arvore_tipada, diretorio=out)
        print()
        print(f"Tabela de símbolos : {caminho_tabela}")
        print(f"Relatório de erros : {out / 'erros_semanticos.md'}")
        print(f"Árvore (parcial)   : {out / 'arvore_atribuida.md'}")
        print("Assembly NÃO foi gerado (existem erros semânticos).")
        return 2

    # ------------------------------------------------------------
    # 4) Árvore Sintática Atribuída
    # ------------------------------------------------------------
    arvore_atribuida = gerarArvoreAtribuida(arvore_tipada, tabela)
    caminho_md, caminho_json = salvarArvoreAtribuida(
        arvore_atribuida, diretorio=out,
    )

    # ------------------------------------------------------------
    # 5) Geração de Assembly tipado
    # ------------------------------------------------------------
    asm = gerar_assembly_de_arvore_atribuida(arvore_atribuida)
    caminho_asm = out / "ultima_execucao.s"
    caminho_asm.write_text(asm, encoding="utf-8")

    # ------------------------------------------------------------
    # 6) Linker: Assembly → Intel HEX
    # ------------------------------------------------------------
    caminho_hex = out / "ultima_execucao.hex"
    caminho_words = out / "ultima_execucao_hex.s"
    try:
        hex_texto = gerar_hex(asm)
        caminho_hex.write_text(hex_texto, encoding="utf-8")
        # Versão .word (hexadecimal) para colar no CPUlator
        caminho_words.write_text(gerar_words_cpulator(asm), encoding="utf-8")
        hex_ok = True
    except Exception as e:
        hex_ok = False
        hex_erro = str(e)

    # ------------------------------------------------------------
    # 7) Resumo final
    # ------------------------------------------------------------
    _imprimir_secao("Resumo")
    print("Análise concluída sem erros.")
    print()
    print("Artefatos gerados:")
    print(f"  Tokens             : {out / 'tokens_ultima_execucao.txt'}")
    print(f"  Gramática (LL1)    : {out / 'gramatica_dump.md'}")
    print(f"  Derivação          : {out / 'derivacao_ultima_execucao.md'}")
    print(f"  Tabela de símbolos : {caminho_tabela}")
    print(f"  Erros semânticos   : {out / 'erros_semanticos.md'}")
    print(f"  Árvore atribuída   : {caminho_md}")
    print(f"  Árvore (JSON)      : {caminho_json}")
    print(f"  Assembly ARMv7     : {caminho_asm}")
    if hex_ok:
        print(f"  Intel HEX          : {caminho_hex}")
        print(f"  Hex p/ CPUlator    : {caminho_words}")
    else:
        print(f"  Intel HEX          : ERRO ao gerar — {hex_erro}")
    print(f"  Arquivo analisado  : {out / 'ARQUIVO_USADO.txt'}")

    # também imprime a árvore "crua" no terminal (útil para inspeção rápida)
    print()
    print("Árvore Sintática (resumo):")
    print(arvore_para_texto(arvore))

    return 0


if __name__ == "__main__":
    sys.exit(main())
