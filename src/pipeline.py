# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara

# Neguhe Rznahry r Serqrevpb

from __future__ import annotations

import os
from pathlib import Path

from .lexer_fsm import (
    Token,
    Erros,
    TIPO_ABRE,
    TIPO_FECHA,
    TIPO_KEYWORD,
    tokenizar_linha,
    tokenizar_programa,
)
from .parser_ll1 import (
    construirGramatica,
    parsear,
    gerarArvore,
)
from .armv7_generator import gerar_assembly_arvore


# --------------------------------------------------------------
# lerArquivo — leitura do código-fonte
# --------------------------------------------------------------


def lerArquivo(nomeArquivo: str, linhas: list[str]) -> None:
    # Lê o arquivo-fonte ignorando apenas linhas em branco.
    # Comentários usam o delimitador da linguagem (``*{ ... }*``) e são
    # removidos depois, na fase de tokenização. NUNCA usar ``#``.
    if not os.path.isfile(nomeArquivo):
        alternativo = os.path.join("exemplos", nomeArquivo)
        if os.path.isfile(alternativo):
            nomeArquivo = alternativo
    with open(nomeArquivo, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            texto = linha.strip()
            if texto:
                linhas.append(texto)


def _lerArquivoBruto(nomeArquivo: str) -> list[str]:
    """Lê o arquivo preservando TODAS as linhas (inclusive vazias).

    Necessário para a Fase 3: a numeração de linha precisa bater com a
    do arquivo original, e comentários multilinha exigem o conteúdo cru.
    """
    if not os.path.isfile(nomeArquivo):
        alternativo = os.path.join("exemplos", nomeArquivo)
        if os.path.isfile(alternativo):
            nomeArquivo = alternativo
    if not os.path.isfile(nomeArquivo):
        raise Erros(f"Arquivo-fonte não encontrado: {nomeArquivo}")
    with open(nomeArquivo, "r", encoding="utf-8") as arquivo:
        # splitlines preserva linhas vazias e descarta o \n final
        return arquivo.read().splitlines()


def _validarEnvelopeProgramaTokens(tokens: list[Token]) -> str | None:
    """Garante ``(START)`` no início e ``(END)`` no fim da lista de tokens.

    Devolve uma mensagem de erro (str) ou ``None`` quando o envelope está
    correto. A gramática LL(1) também rejeita programas mal-envelopados,
    mas esta checagem produz uma mensagem mais direta e específica para
    o usuário antes da derivação.
    """
    if len(tokens) < 6:
        return "programa deve começar com '(START)' e terminar com '(END)'"
    if not (
        tokens[0].tipo == TIPO_ABRE
        and tokens[1].tipo == TIPO_KEYWORD
        and tokens[1].valor == "START"
        and tokens[2].tipo == TIPO_FECHA
    ):
        prim = tokens[0]
        return (
            f"programa deve iniciar com '(START)' "
            f"(linha {prim.linha}, coluna {prim.coluna})"
        )
    if not (
        tokens[-3].tipo == TIPO_ABRE
        and tokens[-2].tipo == TIPO_KEYWORD
        and tokens[-2].valor == "END"
        and tokens[-1].tipo == TIPO_FECHA
    ):
        ult = tokens[-1]
        return (
            f"programa deve terminar com '(END)' "
            f"(último token na linha {ult.linha}, coluna {ult.coluna})"
        )
    return None


# --------------------------------------------------------------
# prepararEntradaSemantica (Fase 3)
# --------------------------------------------------------------


def prepararEntradaSemantica(arquivo: str) -> dict:
    """Prepara a entrada do analisador semântico (Fase 3).

    Etapas (nessa ordem):
      1. lê o arquivo-fonte bruto (preservando linhas e comentários);
      2. tokeniza com :func:`tokenizar_programa`, descartando comentários
         ``(* ... *)`` (estilo Pascal);
      3. executa a análise sintática LL(1) da Fase 2 com recuperação em
         modo pânico — coleta erros sem abortar no primeiro;
      4. monta a AST inicial (sem anotações de tipo) quando não houver
         erros léxico/sintáticos.

    Retorna um dicionário com as chaves:
      ``linhas``         — lista de linhas do arquivo (cruas);
      ``tokens``         — lista de Tokens (sem comentários);
      ``arvore``         — AST inicial ou ``None`` se houver erros;
      ``erros_lexsint``  — lista de mensagens (vazia se tudo certo);
      ``derivacao``      — derivação LL(1) (quando disponível);
      ``passos``         — passos do parser (quando disponível);
      ``gramatica``      — objeto de gramática construído.

    Não levanta exceções para erros léxicos ou sintáticos — eles vão na
    lista ``erros_lexsint`` para o orquestrador do AnalisadorSemantico
    decidir como apresentá-los e abortar a fase semântica.
    """
    saida: dict = {
        "linhas": [],
        "tokens": [],
        "arvore": None,
        "erros_lexsint": [],
        "derivacao": [],
        "passos": [],
        "gramatica": None,
    }

    # 1) leitura crua
    try:
        linhas = _lerArquivoBruto(arquivo)
    except Erros as e:
        saida["erros_lexsint"].append(str(e))
        return saida
    saida["linhas"] = linhas

    # 2) tokenização (comentários removidos)
    try:
        tokens = tokenizar_programa(linhas)
    except Erros as e:
        saida["erros_lexsint"].append(f"[léxico] {e}")
        return saida
    saida["tokens"] = tokens

    # 2.1) validação explícita de (START) na primeira linha não-comentário
    #      e (END) na última. A gramática LL(1) também garante isso, mas
    #      esta checagem produz uma mensagem mais direta para o usuário
    #      antes de tentar a derivação completa.
    erro_envelope = _validarEnvelopeProgramaTokens(tokens)
    if erro_envelope:
        saida["erros_lexsint"].append(f"[sintático] {erro_envelope}")
        return saida

    # 3) sintático com recuperação em modo pânico
    gram = construirGramatica()
    saida["gramatica"] = gram
    try:
        resultado = parsear(tokens, gram)
    except Erros as e:
        # parsear pode lançar uma exceção contendo TODOS os erros
        # acumulados (modo pânico) — repassamos linha a linha.
        for linha in str(e).splitlines():
            linha = linha.strip()
            if linha:
                saida["erros_lexsint"].append(f"[sintático] {linha}")
        return saida

    saida["derivacao"] = resultado.get("derivacao", [])
    saida["passos"] = resultado.get("passos", [])

    # 4) AST inicial
    try:
        saida["arvore"] = gerarArvore(resultado)
    except Erros as e:
        saida["erros_lexsint"].append(f"[sintático] {e}")

    return saida


# --------------------------------------------------------------
# parseExpressao (compat. Fase 1) e lerTokens (Fase 2)
# --------------------------------------------------------------


def parseExpressao(linha: str, tokens_saida: list[str]) -> list[Token]:
    # Compat. Fase 1: tokeniza uma linha e devolve os Tokens.
    tokens = tokenizar_linha(linha)
    tokens_saida.extend(token.valor for token in tokens)
    return tokens


def salvarTokens(caminho: str | Path, tokens_por_linha: list[list[Token]]) -> None:
    # Salva no formato que a lerTokens sabe ler:
    # cada linha do arquivo = linha_N;TIPO:valor,TIPO:valor,...
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as f:
        for i, tokens in enumerate(tokens_por_linha, start=1):
            pares = [f"{t.tipo}:{t.valor}" for t in tokens]
            f.write(f"linha_{i};" + ",".join(pares) + "\n")


def lerTokens(nomeArquivo: str) -> list[Token]:
    # Lê o arquivo de tokens gerado pelo lexer da Fase 1.
    # Formato esperado por linha:
    #   linha_<N>;TIPO:valor,TIPO:valor,...
    # Reconstrói objetos Token com linha e coluna preservados.
    tokens: list[Token] = []
    if not os.path.isfile(nomeArquivo):
        raise Erros(f"Arquivo de tokens não encontrado: {nomeArquivo}")
    with open(nomeArquivo, "r", encoding="utf-8") as f:
        for bruta in f:
            linha = bruta.strip()
            if not linha:
                continue
            if ";" not in linha:
                raise Erros(f"Linha sem separador ';' no arquivo de tokens: {linha!r}")
            cabecalho, corpo = linha.split(";", 1)
            try:
                numero_linha = int(cabecalho.replace("linha_", "").strip())
            except ValueError:
                numero_linha = 0
            if not corpo:
                continue
            for i, par in enumerate(corpo.split(",")):
                if ":" not in par:
                    raise Erros(f"Par inválido no arquivo de tokens: {par!r}")
                tipo, valor = par.split(":", 1)
                tokens.append(
                    Token(tipo=tipo, valor=valor, linha=numero_linha, coluna=i + 1)
                )
    return tokens


# --------------------------------------------------------------
# executarExpressao (compat Fase 1) + validação semântica básica
# --------------------------------------------------------------


def executarExpressao(tokens: list[Token], contexto: dict) -> dict:
    # Compat. Fase 1: valida uma linha isolada sem precisar de arquivo.
    # Envolvemos a linha em (START)...(END) para poder usar o parser da Fase 2.
    envelope = [
        Token(TIPO_ABRE, "(", 0, 0),
        Token(TIPO_KEYWORD, "START", 0, 0),
        Token(TIPO_FECHA, ")", 0, 0),
        *tokens,
        Token(TIPO_ABRE, "(", 0, 0),
        Token(TIPO_KEYWORD, "END", 0, 0),
        Token(TIPO_FECHA, ")", 0, 0),
    ]
    gram = construirGramatica()
    resultado = parsear(envelope, gram)
    arvore = gerarArvore(resultado)
    stmts = arvore["stmts"]
    if not stmts:
        raise Erros("Expressão vazia")
    no = stmts[0]

    contexto.setdefault("memoria", {})
    contexto.setdefault("resultados", [])

    descricao = "expressão válida"
    if no["tipo"] == "mem_write":
        contexto["memoria"][no["nome"]] = "definida"
        descricao = f"memória {no['nome']} marcada como definida"
    elif no["tipo"] == "mem_read":
        if no["nome"] not in contexto["memoria"]:
            contexto["memoria"][no["nome"]] = "não inicializada"
        descricao = f"leitura da memória {no['nome']}"
    elif no["tipo"] == "res_ref":
        n = no["linhas_atras"]
        if n > len(contexto["resultados"]):
            raise Erros(f"RES inválido: {n} linhas atrás não disponível")
        descricao = f"referência ao resultado de {n} linhas atrás"

    contexto["resultados"].append("gerado_em_assembly")
    return {"ok": True, "descricao": descricao, "arvore": no}


# --------------------------------------------------------------
# gerarAssembly — agora a partir da AST "program"
# --------------------------------------------------------------


def gerarAssembly(arvore_programa: dict) -> str:
    # Simplesmente delega para o gerador ARMv7.
    # Função separada para manter a interface do enunciado.
    return gerar_assembly_arvore(arvore_programa)


# --------------------------------------------------------------
# Exibição
# --------------------------------------------------------------


def exibirResultados(resultados: list[dict]) -> None:
    for i, resultado in enumerate(resultados, start=1):
        print(f"Linha {i}: {resultado['descricao']}")


# --------------------------------------------------------------
# Helpers de alto nível usados pelo main
# --------------------------------------------------------------


def executar_fase2(
    caminho_fonte: str,
    caminho_tokens: str,
    caminho_asm: str,
    caminho_arvore: str,
) -> dict:
    # Orquestrador: chama todas as etapas em ordem e retorna tudo num dict.
    # Esse dict é usado pelo AnalisadorSemantico.py para salvar os artefatos e exibir resultados.
    # 1) leitura do fonte
    linhas: list[str] = []
    lerArquivo(caminho_fonte, linhas)

    # 2) tokenização (descartando comentários *{ ... }*) e salva o arquivo de tokens
    from .lexer_fsm import _strip_comentarios
    linhas_limpas, _ = _strip_comentarios(linhas)
    tokens_por_linha = [
        tokenizar_linha(ln, numero_linha=i + 1) for i, ln in enumerate(linhas_limpas)
    ]
    salvarTokens(caminho_tokens, tokens_por_linha)

    # 3) relê os tokens do arquivo (simula integração com a Fase 1)
    tokens_flat = lerTokens(caminho_tokens)

    # 4) constrói a gramática LL(1) (produções + FIRST + FOLLOW + tabela)
    gram = construirGramatica()

    # 5) roda o parser com pilha
    resultado = parsear(tokens_flat, gram)

    # 6) constrói a AST semântica
    arvore = gerarArvore(resultado)

    # 7) salva a árvore apenas em JSON
    Path(caminho_arvore).parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(caminho_arvore, "w", encoding="utf-8") as f:
        json.dump(arvore, f, ensure_ascii=False, indent=2)

    # 8) gera o Assembly ARMv7
    asm = gerarAssembly(arvore)
    Path(caminho_asm).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho_asm).write_text(asm, encoding="utf-8")

    return {
        "linhas": linhas,
        "tokens": tokens_flat,
        "gramatica": gram,
        "derivacao": resultado["derivacao"],
        "passos": resultado["passos"],
        "arvore": arvore,
        "assembly": asm,
    }
