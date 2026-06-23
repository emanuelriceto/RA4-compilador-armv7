# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara

# Notas de projeto da tabela LL(1):
#   Garante que cada produção tenha entrada única na tabela preditiva.
#   Reduz ambiguidade fatorando recursão à esquerda na EBNF.
#   Usa os conjuntos FIRST e FOLLOW para preencher M[A,a].
#   Para cada não-terminal, deriva a coluna pelo lookahead corrente.
#   Os terminais estruturais usam nome simbólico interno (LPAREN, …).
#   A célula vazia da tabela dispara a recuperação de erro.
#   Em modo pânico, sincroniza pelo conjunto FOLLOW do não-terminal.
#   Faz log de cada passo de derivação para fins de auditoria.

# Analisador sintático LL(1) — todo o maquinário do parser está aqui.
#
# Funções principais:
#   construirGramatica()  — define as produções e calcula FIRST, FOLLOW e tabela
#   parsear(tokens, gram) — roda o parser com pilha, gerando a derivação passo a passo
#   gerarArvore(resultado)— constrói a AST semântica a partir dos tokens
#
# A linguagem é baseada em notação pós-fixada (RPN), sempre entre parênteses.
# Todo programa começa com (START) e termina com (END).
#
# Convenção (EBNF / ISO 14977 — ver gramatica.md):
#   MAIÚSCULAS                = não-terminais
#   minúsculas / "literais"   = terminais
# Para legibilidade do código abaixo, os terminais estruturais usam um
# nome simbólico interno (LPAREN = "(", NUMERO = numero, IDENT = ident,
# IF = "IF", …). A correspondência 1-para-1 com a EBNF está documentada
# na seção 1.3 de gramatica.md.
#
# Gramática BNF fatorada (base da tabela LL(1) — numeração #0..#31):
#
#   PROGRAM    -> LPAREN START RPAREN BODY
#   BODY       -> LPAREN BODY_TAIL
#   BODY_TAIL  -> END RPAREN                        # fim do programa
#              |  EXPR_BODY RPAREN BODY              # mais um statement
#   EXPR_BODY  -> ITEM REST1
#   REST1      -> ε                                 # (MEM) — só um item
#              |  ITEM REST2
#   REST2      -> ε                                 # (V MEM) ou (N RES)
#              |  BINOP                              # (A B op)
#              |  KW_CTRL3                           # (COND BLOCO IF/WHILE)
#              |  ITEM ITEM_TAIL
#   ITEM_TAIL  -> KW_CTRL4                           # (COND THEN ELSE IFELSE)
#   ITEM       -> NUMERO | IDENT | RES
#              |  LPAREN EXPR_BODY RPAREN
#   BINOP      -> + | - | * | / | | | % | ^
#              |  > | < | == | != | >= | <=
#   KW_CTRL3   -> IF | WHILE
#   KW_CTRL4   -> IFELSE
#
# Nota sobre a fatoracao de BODY:
#   Tanto "mais um statement" quanto "fim do programa" começam com LPAREN.
#   Para resolver esse conflito LL(1), fatoramos à esquerda:
#   BODY -> LPAREN BODY_TAIL  (consumimos o LPAREN primeiro,
#   depois decidimos pelo próximo símbolo: END vs. inicio de EXPR_BODY)

from __future__ import annotations

from .lexer_fsm import (
    Token,
    Erros,
    TIPO_ABRE,
    TIPO_FECHA,
    TIPO_IDENT,
    TIPO_KEYWORD,
    TIPO_NUMERO,
    TIPO_OPERADOR,
)


# --------------------------------------------------------------
# Símbolos terminais (vocabulário do parser)
# --------------------------------------------------------------
# Usamos strings para os terminais. Para operadores, o próprio lexeme.
# Para parênteses e categorias especiais, nomes simbólicos.

# Convenção EBNF: terminais em minúsculas / literais entre aspas.
# Os "(" e ")" são literais; os demais são categorias léxicas (numero, ident)
# ou os próprios lexemas das palavras-reservadas grafados em minúsculas
# ("res", "start", "end", "if", "while", "ifelse").
T_LPAREN = "("
T_RPAREN = ")"
T_NUMERO = "numero"
T_IDENT = "ident"
T_RES = "res"
T_START = "start"
T_END = "end"
T_IF = "if"
T_WHILE = "while"
T_IFELSE = "ifelse"
T_LED = "led"
T_DELAY = "delay_kw"
T_MORSE = "morse_kw"
T_EOF = "$"

# operadores binários aceitos em (A B op)
BINOPS = {"+", "-", "*", "/", "|", "%", "^", ">", "<", "==", "!=", ">=", "<="}


def _token_para_terminal(token: Token) -> str:
    """Converte um Token do lexer no terminal equivalente na gramática."""
    if token.tipo == TIPO_ABRE:
        return T_LPAREN
    if token.tipo == TIPO_FECHA:
        return T_RPAREN
    if token.tipo == TIPO_NUMERO:
        return T_NUMERO
    if token.tipo == TIPO_IDENT:
        return T_IDENT
    if token.tipo == TIPO_KEYWORD:
        if token.valor == "RES":
            return T_RES
        if token.valor == "START":
            return T_START
        if token.valor == "END":
            return T_END
        if token.valor == "IF":
            return T_IF
        if token.valor == "WHILE":
            return T_WHILE
        if token.valor == "IFELSE":
            return T_IFELSE
        if token.valor == "LED":
            return T_LED
        if token.valor == "DELAY":
            return T_DELAY
        if token.valor == "MORSE":
            return T_MORSE
    if token.tipo == TIPO_OPERADOR and token.valor in BINOPS:
        return token.valor
    raise Erros(f"Token não mapeado para terminal: {token.tipo}:{token.valor}")


# --------------------------------------------------------------
# Gramática como lista de produções
# --------------------------------------------------------------
# Cada produção é (LHS, [símbolos no RHS]). ε é representado por [].
EPSILON = "ε"


def _definicao_gramatica() -> list[tuple[str, list[str]]]:
    # Lista todas as produções em ordem — a posição na lista é o número
    # da produção (usado como índice na tabela LL(1)).
    # Produção com RHS vazio = produção epsilon.
    producoes: list[tuple[str, list[str]]] = []

    # Convenção EBNF (ISO/IEC 14977 e enunciado da Fase 2):
    # MAIÚSCULAS = não-terminais, terminais usam o símbolo interno
    # (LPAREN, NUMERO, IF, …) ou o próprio lexema (operadores).

    # 0: ponto de entrada do programa
    producoes.append(("PROGRAM", [T_LPAREN, T_START, T_RPAREN, "BODY"]))
    # 1: BODY sempre começa consumindo o LPAREN (fatoração)
    producoes.append(("BODY", [T_LPAREN, "BODY_TAIL"]))
    # 2,3: BODY_TAIL decide se encontramos o END ou mais um statement
    producoes.append(("BODY_TAIL", [T_END, T_RPAREN]))
    producoes.append(("BODY_TAIL", ["EXPR_BODY", T_RPAREN, "BODY"]))
    # 4: toda expressão é um item seguido de resto
    producoes.append(("EXPR_BODY", ["ITEM", "REST1"]))
    # 5,6: REST1 — pode ser vazio (ex.: (MEM)) ou ter mais um item
    producoes.append(("REST1", []))  # ε
    producoes.append(("REST1", ["ITEM", "REST2"]))
    # 7-10: REST2 — decide o tipo da expressão pelo que vem depois
    producoes.append(("REST2", []))  # ε — (V MEM) ou (N RES)
    producoes.append(("REST2", ["BINOP"]))         # (A B op)
    producoes.append(("REST2", ["KW_CTRL3"]))      # (COND BLOCO IF/WHILE)
    producoes.append(("REST2", ["ITEM", "ITEM_TAIL"]))  # (COND THEN ELSE IFELSE)
    # 11: ITEM_TAIL só pode ser IFELSE (o único operador de 4 operandos)
    producoes.append(("ITEM_TAIL", ["KW_CTRL4"]))
    # 12-15: os tipos possíveis de ITEM
    producoes.append(("ITEM", [T_NUMERO]))
    producoes.append(("ITEM", [T_IDENT]))
    producoes.append(("ITEM", [T_RES]))
    producoes.append(("ITEM", [T_MORSE]))
    producoes.append(("ITEM", [T_LPAREN, "EXPR_BODY", T_RPAREN]))
    # uma produção por operador binário (simplifica a tabela)
    for op in ("+", "-", "*", "/", "|", "%", "^", ">", "<", "==", "!=", ">=", "<="):
        producoes.append(("BINOP", [op]))
    # palavras-chave de controle
    producoes.append(("KW_CTRL3", [T_IF]))
    producoes.append(("KW_CTRL3", [T_WHILE]))
    producoes.append(("KW_CTRL4", [T_IFELSE]))
    # RA4: I/O de hardware — (expr LED) e (expr DELAY) usam só 1 operando;
    # ficam em REST1 (não REST2) porque só há um item antes do keyword.
    producoes.append(("REST1", [T_LED]))
    producoes.append(("REST1", [T_DELAY]))

    return producoes


# --------------------------------------------------------------
# FIRST / FOLLOW (algoritmo clássico do livro-texto)
# --------------------------------------------------------------


def _eh_terminal(simbolo: str, nao_terminais: set[str]) -> bool:
    return simbolo not in nao_terminais


def _calcular_first(
    producoes: list[tuple[str, list[str]]],
    nao_terminais: set[str],
) -> dict[str, set[str]]:
    # Algoritmo iterativo clássico do livro:
    # fica rodando até que nenhum conjunto FIRST mude mais (ponto fixo).
    # Para cada produção A -> X1 X2 ... Xn:
    #   - adicionamos FIRST(X1) em FIRST(A)
    #   - se X1 pode derivar ε, também adicionamos FIRST(X2), e assim por diante
    #   - se TODOS os Xi derivam ε, adicionamos ε em FIRST(A)
    first: dict[str, set[str]] = {nt: set() for nt in nao_terminais}

    mudou = True
    while mudou:
        mudou = False
        for lhs, rhs in producoes:
            # produção ε
            if not rhs:
                if EPSILON not in first[lhs]:
                    first[lhs].add(EPSILON)
                    mudou = True
                continue

            # percorre símbolos até um que não derive ε
            anulavel = True
            for sim in rhs:
                if _eh_terminal(sim, nao_terminais):
                    if sim not in first[lhs]:
                        first[lhs].add(sim)
                        mudou = True
                    anulavel = False
                    break
                # não-terminal
                antes = len(first[lhs])
                first[lhs].update(first[sim] - {EPSILON})
                if len(first[lhs]) != antes:
                    mudou = True
                if EPSILON not in first[sim]:
                    anulavel = False
                    break
            if anulavel:
                if EPSILON not in first[lhs]:
                    first[lhs].add(EPSILON)
                    mudou = True
    return first


def _first_de_sequencia(
    seq: list[str],
    first: dict[str, set[str]],
    nao_terminais: set[str],
) -> set[str]:
    """FIRST de uma cadeia de símbolos."""
    resultado: set[str] = set()
    if not seq:
        resultado.add(EPSILON)
        return resultado
    for sim in seq:
        if _eh_terminal(sim, nao_terminais):
            resultado.add(sim)
            return resultado
        resultado.update(first[sim] - {EPSILON})
        if EPSILON not in first[sim]:
            return resultado
    resultado.add(EPSILON)
    return resultado


def _calcular_follow(
    producoes: list[tuple[str, list[str]]],
    nao_terminais: set[str],
    first: dict[str, set[str]],
    inicial: str,
) -> dict[str, set[str]]:
    # FOLLOW(A) = conjunto dos terminais que podem aparecer após A em alguma
    # forma sentencial. Começamos colocando $ em FOLLOW do símbolo inicial.
    follow: dict[str, set[str]] = {nt: set() for nt in nao_terminais}
    follow[inicial].add(T_EOF)

    mudou = True
    while mudou:
        mudou = False
        for lhs, rhs in producoes:
            for i, sim in enumerate(rhs):
                if sim not in nao_terminais:
                    continue
                cauda = rhs[i + 1:]
                first_cauda = _first_de_sequencia(cauda, first, nao_terminais)
                antes = len(follow[sim])
                follow[sim].update(first_cauda - {EPSILON})
                if EPSILON in first_cauda or not cauda:
                    follow[sim].update(follow[lhs])
                if len(follow[sim]) != antes:
                    mudou = True
    return follow


def _construir_tabela_ll1(
    producoes: list[tuple[str, list[str]]],
    nao_terminais: set[str],
    first: dict[str, set[str]],
    follow: dict[str, set[str]],
) -> dict[tuple[str, str], int]:
    # Para cada produção A -> α:
    #   para cada terminal t em FIRST(α): M[A, t] = esta produção
    #   se ε em FIRST(α): para cada t em FOLLOW(A): M[A, t] = esta produção
    # Se alguma entrada já estiver ocupada = conflito = gramática não é LL(1).
    tabela: dict[tuple[str, str], int] = {}
    conflitos: list[str] = []

    for idx, (lhs, rhs) in enumerate(producoes):
        first_rhs = _first_de_sequencia(rhs, first, nao_terminais)
        for term in first_rhs - {EPSILON}:
            chave = (lhs, term)
            if chave in tabela and tabela[chave] != idx:
                conflitos.append(
                    f"Conflito LL(1) em [{lhs}, {term}]: produções {tabela[chave]} e {idx}"
                )
            tabela[chave] = idx
        if EPSILON in first_rhs:
            for term in follow[lhs]:
                chave = (lhs, term)
                if chave in tabela and tabela[chave] != idx:
                    conflitos.append(
                        f"Conflito LL(1) em [{lhs}, {term}]: produções {tabela[chave]} e {idx}"
                    )
                tabela[chave] = idx

    if conflitos:
        raise Erros("Gramática não é LL(1):\n  " + "\n  ".join(conflitos))
    return tabela


# --------------------------------------------------------------
# API pública: construirGramatica
# --------------------------------------------------------------


def construirGramatica() -> dict:
    # Junta tudo: cria as produções, separa terminais de não-terminais,
    # calcula FIRST e FOLLOW, e monta a tabela LL(1).
    # O dict retornado é passado para parsear() e também salvo como
    # artefato de documentação no output/.
    producoes = _definicao_gramatica()

    nao_terminais: set[str] = set()
    terminais: set[str] = {T_EOF}
    for lhs, rhs in producoes:
        nao_terminais.add(lhs)
    for lhs, rhs in producoes:
        for sim in rhs:
            if sim not in nao_terminais:
                terminais.add(sim)

    inicial = producoes[0][0]
    first = _calcular_first(producoes, nao_terminais)
    follow = _calcular_follow(producoes, nao_terminais, first, inicial)
    tabela = _construir_tabela_ll1(producoes, nao_terminais, first, follow)

    return {
        "producoes": producoes,
        "nao_terminais": nao_terminais,
        "terminais": terminais,
        "inicial": inicial,
        "first": first,
        "follow": follow,
        "tabela": tabela,
    }


# --------------------------------------------------------------
# Parser LL(1) com pilha (table-driven) produzindo derivação
# --------------------------------------------------------------


# Limite de erros sintaticos coletados antes de abortar (evita spam em arquivos
# com muitos problemas em cascata).
MAX_ERROS_SINTATICOS = 50


def parsear(tokens: list[Token], tabela_ll1: dict) -> dict:
    # Parser LL(1) dirigido por tabela com pilha explicita, com recuperacao
    # de erros em "modo panico" (Aho et al., 4.4.5). A ideia eh continuar
    # analisando depois de cada erro, em vez de abortar no primeiro:
    #
    #   - mismatch de terminal: registra o erro e "insere" o terminal
    #     esperado (como ele ja foi removido da pilha pelo pop(), basta
    #     continuar sem avancar a entrada).
    #   - nao ha producao em M[A, t]: registra o erro e sincroniza usando
    #     FOLLOW(A) U {"(", ")"} como conjunto de sincronismo. Se o token
    #     atual esta no sincronismo, descarta o nao-terminal (epsilon
    #     forcado); senao, descarta o token atual e re-empilha o nao-terminal.
    #
    # Todos os erros coletados sao reportados de uma vez ao final, em vez
    # de uma excecao por erro. Isso atende ao requisito R4 (recuperacao).
    producoes = tabela_ll1["producoes"]
    tabela = tabela_ll1["tabela"]
    inicial = tabela_ll1["inicial"]
    nao_terminais = tabela_ll1["nao_terminais"]
    follow: dict[str, set[str]] = tabela_ll1.get("follow", {})

    # buffer de entrada: lista de (terminal, token) com $ marcador no final
    entrada: list[tuple[str, Token | None]] = [
        (_token_para_terminal(tok), tok) for tok in tokens
    ]
    entrada.append((T_EOF, None))

    # pilha com o topo a direita (pop() retorna o topo)
    # iniciamos com EOF e o simbolo inicial
    pilha: list[str] = [T_EOF, inicial]
    derivacao: list[dict] = []
    passos: list[dict] = []   # rastreamento completo para a tabela de derivacao
    erros: list[str] = []     # mensagens coletadas durante a analise
    i = 0

    # Conjunto de sincronismo "forte" comum a toda a linguagem: parenteses
    # e fim de entrada. Em RPN tudo eh delimitado por (...), entao esses
    # tokens sao otimos pontos de re-sincronizacao.
    SYNC_FORTE = {T_LPAREN, T_RPAREN, T_EOF}

    def registrar_erro(msg: str) -> None:
        """Registra um erro sintatico e marca o passo correspondente."""
        erros.append(msg)
        passos.append({"tipo": "erro", "pilha": list(pilha), "pos": i, "mensagem": msg})

    while pilha:
        if len(erros) >= MAX_ERROS_SINTATICOS:
            erros.append(f"... analise abortada apos {MAX_ERROS_SINTATICOS} erros.")
            break

        pilha_snap = list(pilha)           # snapshot antes do pop (topo = ultimo)
        topo = pilha.pop()
        terminal_atual, token_atual = entrada[i]

        if topo == T_EOF:
            if terminal_atual == T_EOF:
                passos.append({"tipo": "casa", "pilha": pilha_snap, "pos": i, "simbolo": T_EOF})
                break
            # tokens extras apos o fim do programa: reportamos uma unica
            # vez (contando quantos sobraram) e encerramos -- nao adianta
            # continuar empilhando porque nada mais sera casado.
            sobrando = len(entrada) - 1 - i
            registrar_erro(
                f"Entrada extra apos o fim do programa: {_descreve(token_atual, terminal_atual)}"
                + (f" (e mais {sobrando - 1} token(s))" if sobrando > 1 else "")
            )
            break

        # terminal no topo -> casar com entrada
        if topo not in nao_terminais:
            if topo == terminal_atual:
                passos.append({"tipo": "casa", "pilha": pilha_snap, "pos": i, "simbolo": topo})
                i += 1
                continue
            # Recuperacao por mismatch de terminal:
            #   1) Se o terminal esperado eh ")" e o token atual eh "(" ou EOF,
            #      o usuario esqueceu de fechar -- assume insercao do ")".
            #   2) Caso contrario, tambem assumimos insercao (descarte) do
            #      terminal esperado e seguimos sem avancar a entrada. Isso
            #      permite que o parser tente casar o token atual mais a
            #      frente da pilha.
            registrar_erro(
                f"Erro sintatico: esperado '{topo}' mas encontrado "
                f"{_descreve(token_atual, terminal_atual)}"
            )
            # Se o token atual nao parece sincronizavel com nada, descarta-o
            # para evitar loop (ex.: terminal esperado nao aparece nunca mais).
            if terminal_atual not in SYNC_FORTE and terminal_atual != T_EOF:
                i += 1
            continue

        # nao-terminal -> consulta a tabela
        chave = (topo, terminal_atual)
        if chave not in tabela:
            registrar_erro(
                f"Erro sintatico: nao ha producao para [{topo}, {terminal_atual}] "
                f"(token {_descreve(token_atual, terminal_atual)})"
            )
            follow_topo = follow.get(topo, set())
            # Se o token atual ja esta em FOLLOW(topo), tratamos a producao
            # como epsilon (basta nao re-empilhar nada).
            if terminal_atual in follow_topo or terminal_atual == T_EOF:
                continue
            # FIRST(topo) extraido da tabela LL(1): tudo que mapeia para topo.
            first_topo: set[str] = {term for (nt, term) in tabela.keys() if nt == topo}
            sync = first_topo | follow_topo | {T_EOF}
            # Descarta tokens ate achar algo que o nao-terminal aceite (FIRST)
            # ou algo que possa segui-lo (FOLLOW). Mantem o nao-terminal na
            # pilha para tentar de novo.
            pilha.append(topo)
            while (
                i < len(entrada) - 1
                and entrada[i][0] not in sync
            ):
                i += 1
            # Se paramos em algo de FOLLOW (e nao FIRST), descarta o
            # nao-terminal (epsilon forcado) para nao travar.
            if (
                i < len(entrada) - 1
                and entrada[i][0] in follow_topo
                and entrada[i][0] not in first_topo
            ):
                if pilha and pilha[-1] == topo:
                    pilha.pop()
            continue
        idx = tabela[chave]
        lhs, rhs = producoes[idx]
        passos.append({"tipo": "expande", "pilha": pilha_snap, "pos": i,
                       "idx": idx, "lhs": lhs, "rhs": list(rhs)})
        derivacao.append({"idx": idx, "lhs": lhs, "rhs": list(rhs), "pos_token": i})
        # empilha o RHS em ordem reversa para consumir da esquerda
        for sim in reversed(rhs):
            pilha.append(sim)

    # garantir que toda a entrada foi consumida (mais erros, se houver)
    if i != len(entrada) - 1 and not erros:
        terminal_atual, token_atual = entrada[i]
        erros.append(
            f"Erro sintatico: tokens extras apos o programa "
            f"({_descreve(token_atual, terminal_atual)})"
        )

    if erros:
        # Reporta todos os erros em uma unica excecao multi-linha. O caller
        # (AnalisadorSemantico.py) imprime a mensagem inteira.
        cabecalho = (
            f"Foram encontrados {len(erros)} erro(s) sintatico(s) "
            f"(analise prosseguiu em modo panico para reportar todos):"
        )
        corpo = "\n".join(f"  - {m}" for m in erros)
        raise Erros(cabecalho + "\n" + corpo)

    return {"derivacao": derivacao, "passos": passos, "tokens": tokens, "erros": erros}


def _descreve(token: Token | None, terminal: str) -> str:
    if token is None:
        return f"'$' (fim de entrada, terminal {terminal})"
    return f"'{token.valor}' (linha {token.linha}, coluna {token.coluna})"


# --------------------------------------------------------------
# gerarArvore: constrói a AST semântica a partir dos tokens
#
# A derivação LL(1) é útil para ver o processo de parsing, mas para gerar
# assembly é muito mais prático ter uma AST com nós com significado.
# Por isso re-parseamos os tokens de forma recursiva descendente aqui.
# Na prática, essa função é o parser recursivo "limpo" que o parser com
# pilha já validou antes.


def gerarArvore(resultado_parse: dict) -> dict:
    # Recebe o dict retornado por parsear() e devolve a AST.
    # A AST tem a forma: {"tipo": "program", "stmts": [<stmt>, ...]}
    # onde cada <stmt> pode ser: number, ident, res_ref, mem_read,
    # mem_write, binary, if, ifelse ou while.
    tokens: list[Token] = resultado_parse["tokens"]
    pos = [0]  # cursor mutável

    def esperar_terminal(terminal: str, valor: str | None = None) -> Token:
        if pos[0] >= len(tokens):
            raise Erros(f"Fim inesperado; esperado {terminal}")
        tok = tokens[pos[0]]
        t = _token_para_terminal(tok)
        if t != terminal or (valor is not None and tok.valor != valor):
            raise Erros(
                f"Esperado {terminal}{' ' + valor if valor else ''} mas veio "
                f"{_descreve(tok, t)}"
            )
        pos[0] += 1
        return tok

    def parse_item() -> dict:
        tok = tokens[pos[0]]
        t = _token_para_terminal(tok)
        if t == T_NUMERO:
            pos[0] += 1
            return {"tipo": "number", "valor": tok.valor}
        if t == T_IDENT:
            pos[0] += 1
            return {"tipo": "ident", "valor": tok.valor}
        if t == T_RES:
            pos[0] += 1
            return {"tipo": "keyword", "valor": "RES"}
        if t == T_MORSE:
            pos[0] += 1
            return {"tipo": "keyword", "valor": "MORSE"}
        if t == T_LPAREN:
            return parse_expr()
        raise Erros(f"Item inválido: {_descreve(tok, t)}")

    def parse_expr() -> dict:
        # captura a linha do '(' que abre a expressão para anotar no nó
        linha_inicio = tokens[pos[0]].linha if pos[0] < len(tokens) else 0
        esperar_terminal(T_LPAREN)
        primeiro = parse_item()

        tok = tokens[pos[0]]
        t = _token_para_terminal(tok)

        # (item)  ->  mem_read
        if t == T_RPAREN:
            pos[0] += 1
            if primeiro["tipo"] != "ident":
                raise Erros("Comando (MEM) exige identificador em letras maiúsculas")
            return {"tipo": "mem_read", "nome": primeiro["valor"], "linha": linha_inicio}

        # RA4: (expr LED) e (expr DELAY) — um operando + keyword + )
        if t == T_LED:
            pos[0] += 1
            esperar_terminal(T_RPAREN)
            return {"tipo": "led_write", "valor": primeiro, "linha": linha_inicio}
        if t == T_DELAY:
            pos[0] += 1
            esperar_terminal(T_RPAREN)
            return {"tipo": "delay_ms", "ms": primeiro, "linha": linha_inicio}

        segundo = parse_item()
        tok = tokens[pos[0]]
        t = _token_para_terminal(tok)

        # dois itens + ')'
        if t == T_RPAREN:
            pos[0] += 1
            # (N RES)
            if segundo.get("tipo") == "keyword" and segundo.get("valor") == "RES":
                if primeiro.get("tipo") != "number" or not _eh_int_nao_negativo(primeiro.get("valor", "")):
                    raise Erros("Comando (N RES) exige N inteiro não negativo")
                return {"tipo": "res_ref", "linhas_atras": int(primeiro["valor"]), "linha": linha_inicio}
            # RA4: (PALAVRA MORSE) — expande a palavra em LED/DELAY via tabela ASCII→Morse
            if segundo.get("tipo") == "keyword" and segundo.get("valor") == "MORSE":
                if primeiro.get("tipo") != "ident":
                    raise Erros("Comando (PALAVRA MORSE) exige identificador em letras maiúsculas")
                return {"tipo": "morse_word", "nome": primeiro["valor"], "linha": linha_inicio}
            # (V MEM)
            if segundo.get("tipo") == "ident":
                return {"tipo": "mem_write", "nome": segundo["valor"], "valor": primeiro, "linha": linha_inicio}
            raise Erros("Expressão de dois itens inválida")

        # binop + ')'
        if tok.tipo == TIPO_OPERADOR and tok.valor in BINOPS:
            pos[0] += 1
            esperar_terminal(T_RPAREN)
            return {"tipo": "binary", "op": tok.valor, "esq": primeiro, "dir": segundo, "linha": linha_inicio}

        # kw_ctrl3 + ')'  -> (COND BODY IF) ou (COND BODY WHILE)
        if t == T_IF:
            pos[0] += 1
            esperar_terminal(T_RPAREN)
            return {"tipo": "if", "cond": primeiro, "then_block": segundo, "linha": linha_inicio}
        if t == T_WHILE:
            pos[0] += 1
            esperar_terminal(T_RPAREN)
            return {"tipo": "while", "cond": primeiro, "body": segundo, "linha": linha_inicio}

        # terceiro item -> (COND THEN ELSE IFELSE)
        terceiro = parse_item()
        kw = tokens[pos[0]]
        kw_t = _token_para_terminal(kw)
        if kw_t != T_IFELSE:
            raise Erros(
                f"Expressão de 3 itens exige IFELSE como quarto símbolo, "
                f"veio {_descreve(kw, kw_t)}"
            )
        pos[0] += 1
        esperar_terminal(T_RPAREN)
        return {
            "tipo": "ifelse",
            "cond": primeiro,
            "then_block": segundo,
            "else_block": terceiro,
            "linha": linha_inicio,
        }

    # program: ( START ) stmt_list ( END )
    esperar_terminal(T_LPAREN)
    esperar_terminal(T_START, "START")
    esperar_terminal(T_RPAREN)

    stmts: list[dict] = []
    while True:
        if pos[0] >= len(tokens):
            raise Erros("Programa não foi finalizado com (END)")
        tok = tokens[pos[0]]
        # detecta (END) olhando 3 tokens à frente
        if (
            tok.tipo == TIPO_ABRE
            and pos[0] + 2 < len(tokens)
            and tokens[pos[0] + 1].tipo == TIPO_KEYWORD
            and tokens[pos[0] + 1].valor == "END"
            and tokens[pos[0] + 2].tipo == TIPO_FECHA
        ):
            break
        stmts.append(parse_expr())

    esperar_terminal(T_LPAREN)
    esperar_terminal(T_END, "END")
    esperar_terminal(T_RPAREN)
    if pos[0] != len(tokens):
        tok = tokens[pos[0]]
        raise Erros(f"Tokens extras após (END): {_descreve(tok, _token_para_terminal(tok))}")

    return {"tipo": "program", "stmts": stmts}


def _eh_int_nao_negativo(valor: str) -> bool:
    if not valor:
        return False
    for ch in valor:
        if ch < "0" or ch > "9":
            return False
    return True


# --------------------------------------------------------------
# Utilitários de apresentação
# --------------------------------------------------------------


def arvore_para_texto(no: dict, nivel: int = 0) -> str:
    # Serializa a AST com indentação para facilitar a leitura.
    # Cada nível a mais = 2 espaços.
    ident = "  " * nivel
    tipo = no.get("tipo")
    if tipo == "program":
        linhas = [f"{ident}program"]
        for s in no["stmts"]:
            linhas.append(arvore_para_texto(s, nivel + 1))
        return "\n".join(linhas)
    if tipo == "number":
        return f"{ident}number({no['valor']})"
    if tipo == "ident":
        return f"{ident}ident({no['valor']})"
    if tipo == "keyword":
        return f"{ident}keyword({no['valor']})"
    if tipo == "res_ref":
        return f"{ident}res_ref(linhas_atras={no['linhas_atras']})"
    if tipo == "mem_read":
        return f"{ident}mem_read({no['nome']})"
    if tipo == "mem_write":
        linhas = [f"{ident}mem_write({no['nome']})"]
        linhas.append(arvore_para_texto(no["valor"], nivel + 1))
        return "\n".join(linhas)
    if tipo == "binary":
        linhas = [f"{ident}binary({no['op']})"]
        linhas.append(arvore_para_texto(no["esq"], nivel + 1))
        linhas.append(arvore_para_texto(no["dir"], nivel + 1))
        return "\n".join(linhas)
    if tipo == "if":
        linhas = [f"{ident}if"]
        linhas.append(f"{ident}  cond:")
        linhas.append(arvore_para_texto(no["cond"], nivel + 2))
        linhas.append(f"{ident}  then:")
        linhas.append(arvore_para_texto(no["then_block"], nivel + 2))
        return "\n".join(linhas)
    if tipo == "ifelse":
        linhas = [f"{ident}ifelse"]
        linhas.append(f"{ident}  cond:")
        linhas.append(arvore_para_texto(no["cond"], nivel + 2))
        linhas.append(f"{ident}  then:")
        linhas.append(arvore_para_texto(no["then_block"], nivel + 2))
        linhas.append(f"{ident}  else:")
        linhas.append(arvore_para_texto(no["else_block"], nivel + 2))
        return "\n".join(linhas)
    if tipo == "while":
        linhas = [f"{ident}while"]
        linhas.append(f"{ident}  cond:")
        linhas.append(arvore_para_texto(no["cond"], nivel + 2))
        linhas.append(f"{ident}  body:")
        linhas.append(arvore_para_texto(no["body"], nivel + 2))
        return "\n".join(linhas)
    if tipo == "led_write":
        linhas = [f"{ident}led_write"]
        linhas.append(arvore_para_texto(no["valor"], nivel + 1))
        return "\n".join(linhas)
    if tipo == "delay_ms":
        linhas = [f"{ident}delay_ms"]
        linhas.append(arvore_para_texto(no["ms"], nivel + 1))
        return "\n".join(linhas)
    if tipo == "morse_word":
        return f"{ident}morse_word({no['nome']})"
    return f"{ident}{tipo}?"


def derivacao_para_texto(derivacao: list[dict]) -> str:
    # Formato simples: lista numerada das produções aplicadas.
    # Mais fácil de ler que a tabela completa quando só queremos ver as expansões.
    linhas: list[str] = []
    for i, passo in enumerate(derivacao, start=1):
        rhs = " ".join(passo["rhs"]) if passo["rhs"] else "ε"
        linhas.append(f"{i:03d}. {passo['lhs']} -> {rhs}")
    return "\n".join(linhas)


def derivacao_para_texto_tabela(passos: list[dict], tokens: list[Token]) -> str:
    # Formato de tabela markdown com 3 colunas:
    #   Passo | Pilha (topo →) | Entrada (→) | Ação (expande ou casa)
    # Cada linha corresponde a um passo do algoritmo.
    MAX_PILHA = 50
    MAX_ENT   = 40

    def _escape_md(s: str) -> str:
        """Escapa caracteres que quebram células de tabela Markdown."""
        return s.replace("|", r"\|")

    def _pilha_str(snap: list[str]) -> str:
        s = " ".join(reversed(snap))
        s = _escape_md(s)
        return s if len(s) <= MAX_PILHA else s[:MAX_PILHA - 1] + "…"

    def _ent_str(pos: int) -> str:
        # Mostra os lexemas reais do código-fonte (ex.: "START", "10",
        # "CONT", "+") — exatamente como aparecem no arquivo de entrada.
        vals = [_escape_md(t.valor) for t in tokens[pos:pos + 10]]
        if pos + 10 < len(tokens):
            vals.append("…")
        if not vals:
            vals = ["$"]
        s = " ".join(vals)
        return s if len(s) <= MAX_ENT else s[:MAX_ENT - 1] + "…"

    linhas: list[str] = []
    linhas.append("# Derivação LL(1) — Passo a Passo")
    linhas.append("")
    linhas.append("| Passo | Pilha (topo →) | Entrada (→) | Ação |")
    linhas.append("|------:|---|---|---|")
    for n, p in enumerate(passos, start=1):
        pilha_s = _pilha_str(p["pilha"])
        ent_s   = _ent_str(p["pos"])
        if p["tipo"] == "expande":
            rhs = " ".join(_escape_md(s) for s in p["rhs"]) if p["rhs"] else "ε"
            acao = f"Expande: `{_escape_md(p['lhs'])}` → `{rhs}`"
        else:
            acao = f"Casa: `{_escape_md(p['simbolo'])}`"
        linhas.append(f"| {n} | `{pilha_s}` | `{ent_s}` | {acao} |")
    return "\n".join(linhas)
