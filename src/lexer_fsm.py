# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara

# Analisador léxico implementado como um AFD (autômato finito determinístico).
# Não usamos regex — cada estado é uma função Python que decide a transição.
#
# Atualizamos o léxico da Fase 1 para suportar:
#   `/`  = divisão inteira   (mudamos de `//` para `/` pra ficar mais limpo)
#   `|`  = divisão real      (usamos `|` porque `/` já foi tomado)
#   `%`  = resto da divisão
#   `^`  = potenciação
#   `+ - *` = os aritméticos de sempre
#   Relacionais: `>`, `<`, `==`, `!=`, `>=`, `<=`
#   Palavras reservadas novas: START, END, IF, IFELSE, WHILE (além do RES da Fase 1)
#
# Os estados do AFD são:
#   inicial, numero, numero_decimal, identificador,
#   igual, diferente, maior, menor
#
# 0x41727468757220456d616e75656c20652046726564657269636f

from dataclasses import dataclass


class Erros(Exception):
    pass


@dataclass
class Token:
    """Um token com tipo, valor e posição."""
    tipo: str
    valor: str
    linha: int
    coluna: int


TIPO_NUMERO = "NUMERO"
TIPO_OPERADOR = "OPERADOR"
TIPO_ABRE = "PARENTESE_ABRE"
TIPO_FECHA = "PARENTESE_FECHA"
TIPO_IDENT = "IDENTIFICADOR"
TIPO_KEYWORD = "KEYWORD"
TIPO_COMENTARIO = "COMENTARIO"

# Delimitadores de comentário (Fase 3) — definidos pelo grupo.
# Comentários podem ocorrer em linha inteira, no fim de linha, entre
# expressões e também ocupar várias linhas. NÃO são aninhados.
COMENTARIO_ABRE = "*{"
COMENTARIO_FECHA = "}*"

# Palavras reservadas — quando o estado `identificador` fechar um token,
# verificamos se o valor está aqui; se estiver, vira KEYWORD em vez de IDENT.
PALAVRAS_RESERVADAS = {"RES", "START", "END", "IF", "IFELSE", "WHILE", "LED", "DELAY", "MORSE"}


def _eh_digito(char: str) -> bool:
    return "0" <= char <= "9"


def _eh_maiuscula(char: str) -> bool:
    return "A" <= char <= "Z"


def _eh_minuscula(char: str) -> bool:
    return "a" <= char <= "z"


def _adicionar_token(contexto: dict, tipo: str, valor: str) -> None:
    contexto["tokens"].append(
        Token(
            tipo=tipo,
            valor=valor,
            linha=contexto["linha"],
            coluna=contexto["inicio_token"] + 1,
        )
    )


# ---- Estados do AFD ----
# Cada função recebe o caractere atual e o contexto compartilhado,
# e retorna (próximo_estado, consumiu_char).
# Quando consumiu_char = False, o mesmo char vai ser reprocessado no
# novo estado (transição sem consumo = ε-transição implícita).


def estado_inicial(char: str, contexto: dict) -> tuple[str, bool]:
    if char in (" ", "\t", "\r", "\n"):
        return "inicial", True

    if char == "(":
        contexto["inicio_token"] = contexto["i"]
        _adicionar_token(contexto, TIPO_ABRE, "(")
        contexto["paren"] += 1   # conta abertura para verificar balanceamento
        return "inicial", True

    if char == ")":
        contexto["inicio_token"] = contexto["i"]
        if contexto["paren"] <= 0:
            raise Erros(f"Linha {contexto['linha']}: ')' sem '(' correspondente")
        contexto["paren"] -= 1
        _adicionar_token(contexto, TIPO_FECHA, ")")
        return "inicial", True

    if _eh_digito(char):
        contexto["buffer"] = char
        contexto["inicio_token"] = contexto["i"]
        return "numero", True

    if _eh_maiuscula(char):
        contexto["buffer"] = char
        contexto["inicio_token"] = contexto["i"]
        return "identificador", True

    # operadores aritméticos de um caractere
    if char in "+-*/|%^":
        contexto["inicio_token"] = contexto["i"]
        _adicionar_token(contexto, TIPO_OPERADOR, char)
        return "inicial", True

    # relacionais de dois caracteres precisam de estado intermediário
    # porque precisamos olhar o próximo char antes de emitir o token
    if char == "=":
        contexto["inicio_token"] = contexto["i"]
        return "igual", True
    if char == "!":
        contexto["inicio_token"] = contexto["i"]
        return "diferente", True
    if char == ">":
        contexto["inicio_token"] = contexto["i"]
        return "maior", True
    if char == "<":
        contexto["inicio_token"] = contexto["i"]
        return "menor", True

    if char == ".":
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"número malformado — ponto sem dígito antes"
        )

    if _eh_minuscula(char):
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"identificadores devem usar apenas letras maiúsculas, encontrado '{char}'"
        )

    raise Erros(
        f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: caractere inválido '{char}'"
    )


def estado_numero(char: str, contexto: dict) -> tuple[str, bool]:
    if _eh_digito(char):
        contexto["buffer"] += char
        return "numero", True

    if char == ".":
        contexto["buffer"] += char
        return "numero_decimal", True

    if _eh_maiuscula(char) or _eh_minuscula(char):
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"número malformado '{contexto['buffer'] + char}' — letra após número"
        )

    _adicionar_token(contexto, TIPO_NUMERO, contexto["buffer"])
    contexto["buffer"] = ""
    return "inicial", False


def estado_numero_decimal(char: str, contexto: dict) -> tuple[str, bool]:
    if _eh_digito(char):
        contexto["buffer"] += char
        return "numero_decimal", True

    if char == ".":
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"número malformado '{contexto['buffer'] + char}' — múltiplos pontos decimais"
        )

    if contexto["buffer"].endswith("."):
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i']}: "
            f"número malformado '{contexto['buffer']}' — ponto sem dígitos depois"
        )

    if _eh_maiuscula(char) or _eh_minuscula(char):
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"número malformado '{contexto['buffer'] + char}' — letra após número"
        )

    _adicionar_token(contexto, TIPO_NUMERO, contexto["buffer"])
    contexto["buffer"] = ""
    return "inicial", False


def estado_identificador(char: str, contexto: dict) -> tuple[str, bool]:
    # só letras maiúsculas são permitidas nos identificadores da linguagem
    if _eh_maiuscula(char):
        contexto["buffer"] += char
        return "identificador", True

    if _eh_minuscula(char):
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"identificador '{contexto['buffer'] + char}' contém letra minúscula"
        )

    if _eh_digito(char):
        raise Erros(
            f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
            f"identificador '{contexto['buffer'] + char}' contém dígito"
        )

    valor = contexto["buffer"]
    # aqui decidimos se é palavra reservada ou identificador de memória
    if valor in PALAVRAS_RESERVADAS:
        _adicionar_token(contexto, TIPO_KEYWORD, valor)
    else:
        _adicionar_token(contexto, TIPO_IDENT, valor)
    contexto["buffer"] = ""
    return "inicial", False


def estado_igual(char: str, contexto: dict) -> tuple[str, bool]:
    if char == "=":
        _adicionar_token(contexto, TIPO_OPERADOR, "==")
        return "inicial", True
    raise Erros(
        f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
        f"operador inválido '=' isolado (use '==')"
    )


def estado_diferente(char: str, contexto: dict) -> tuple[str, bool]:
    if char == "=":
        _adicionar_token(contexto, TIPO_OPERADOR, "!=")
        return "inicial", True
    raise Erros(
        f"Linha {contexto['linha']}, coluna {contexto['i'] + 1}: "
        f"operador inválido '!' isolado (use '!=')"
    )


def estado_maior(char: str, contexto: dict) -> tuple[str, bool]:
    # se o próximo char for '=', emite '>=' ; senão emite '>' e reprocessa
    if char == "=":
        _adicionar_token(contexto, TIPO_OPERADOR, ">=")
        return "inicial", True
    _adicionar_token(contexto, TIPO_OPERADOR, ">")
    return "inicial", False


def estado_menor(char: str, contexto: dict) -> tuple[str, bool]:
    # mesma lógica do maior
    if char == "=":
        _adicionar_token(contexto, TIPO_OPERADOR, "<=")
        return "inicial", True
    _adicionar_token(contexto, TIPO_OPERADOR, "<")
    return "inicial", False


def _finalizar(contexto: dict, estado: str) -> None:
    if estado == "numero":
        _adicionar_token(contexto, TIPO_NUMERO, contexto["buffer"])
    elif estado == "numero_decimal":
        if contexto["buffer"].endswith("."):
            raise Erros(f"Linha {contexto['linha']}: número malformado '{contexto['buffer']}'")
        _adicionar_token(contexto, TIPO_NUMERO, contexto["buffer"])
    elif estado == "identificador":
        valor = contexto["buffer"]
        if valor in PALAVRAS_RESERVADAS:
            _adicionar_token(contexto, TIPO_KEYWORD, valor)
        else:
            _adicionar_token(contexto, TIPO_IDENT, valor)
    elif estado == "maior":
        _adicionar_token(contexto, TIPO_OPERADOR, ">")
    elif estado == "menor":
        _adicionar_token(contexto, TIPO_OPERADOR, "<")
    elif estado in ("igual", "diferente"):
        raise Erros(f"Linha {contexto['linha']}: operador relacional incompleto")

    if contexto["paren"] != 0:
        raise Erros(f"Linha {contexto['linha']}: parênteses desbalanceados")


def tokenizar_linha(linha: str, numero_linha: int = 1) -> list[Token]:
    # Roda o AFD caractere por caractere.
    # Adicionamos '\n' ao final para forçar o fechamento do último token
    # (ex.: número ou identificador que encosta no final da string).
    contexto = {
        "tokens": [],
        "buffer": "",
        "i": 0,
        "inicio_token": 0,
        "linha": numero_linha,
        "paren": 0,
    }

    estado = "inicial"
    # mapeamos os nomes de estado para as funções correspondentes
    maquina = {
        "inicial": estado_inicial,
        "numero": estado_numero,
        "numero_decimal": estado_numero_decimal,
        "identificador": estado_identificador,
        "igual": estado_igual,
        "diferente": estado_diferente,
        "maior": estado_maior,
        "menor": estado_menor,
    }

    chars = linha + "\n"
    while contexto["i"] < len(chars):
        char = chars[contexto["i"]]
        proximo_estado, avancar = maquina[estado](char, contexto)
        estado = proximo_estado
        if avancar:
            contexto["i"] += 1

    _finalizar(contexto, estado)
    return contexto["tokens"]


def tokenizar_programa(linhas: list[str], manter_comentarios: bool = False) -> list[Token]:
    """Tokeniza todas as linhas preservando a numeração de linha.

    Fase 3: comentários no formato ``*{ ... }*`` são removidos antes da
    tokenização. Eles podem aparecer em qualquer posição (linha inteira,
    fim de linha, no meio de uma expressão) e também atravessar várias
    linhas. Aninhamento NÃO é suportado. Se ``manter_comentarios=True``
    os tokens ``COMENTARIO`` são retornados ao final da lista (apenas
    para inspeção/debug).
    Levanta :class:`Erros` se um comentário ficar aberto até o EOF.
    """
    linhas_limpas, coments = _strip_comentarios(linhas)
    todos: list[Token] = []
    for idx, linha in enumerate(linhas_limpas, start=1):
        todos.extend(tokenizar_linha(linha, numero_linha=idx))
    if manter_comentarios:
        todos.extend(coments)
    return todos


def _strip_comentarios(linhas: list[str]) -> tuple[list[str], list[Token]]:
    """Remove comentários ``*{ ... }*`` substituindo o conteúdo por espaços.

    Manter o tamanho original das linhas preserva colunas/linhas dos
    tokens reais — importante para mensagens de erro do parser. Retorna
    a lista de linhas limpas e os tokens de comentário coletados (com a
    posição de abertura).
    """
    limpas: list[str] = []
    coments: list[Token] = []
    em_com = False
    inicio_lin = 0
    inicio_col = 0
    buffer = ""

    for nlin, linha in enumerate(linhas, start=1):
        saida: list[str] = []
        i = 0
        n = len(linha)
        while i < n:
            ch = linha[i]
            prox = linha[i + 1] if i + 1 < n else ""
            if not em_com:
                if ch == "*" and prox == "{":
                    em_com = True
                    inicio_lin = nlin
                    inicio_col = i + 1
                    buffer = "*{"
                    saida.append("  ")
                    i += 2
                    continue
                saida.append(ch)
                i += 1
            else:
                if ch == "}" and prox == "*":
                    buffer += "}*"
                    coments.append(
                        Token(
                            tipo=TIPO_COMENTARIO,
                            valor=buffer,
                            linha=inicio_lin,
                            coluna=inicio_col,
                        )
                    )
                    em_com = False
                    buffer = ""
                    saida.append("  ")
                    i += 2
                    continue
                # dentro do comentário: descarta caractere preservando coluna
                buffer += ch
                saida.append(" ")
                i += 1
        if em_com:
            # quebra de linha dentro do comentário — preserva no buffer
            buffer += "\n"
        limpas.append("".join(saida))

    if em_com:
        raise Erros(
            f"Comentário não fechado iniciado na linha {inicio_lin}, "
            f"coluna {inicio_col} (esperado '}}*' antes do fim do arquivo)"
        )
    return limpas, coments
