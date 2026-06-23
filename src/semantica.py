# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA3 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Frank Coelho de Alcantara


# Analisador semântico: construção da tabela de símbolos, verificação de tipos e geração
#
# Este módulo implementa a estrutura de dados responsável por rastrear
# todas as variáveis MEM declaradas e usadas no programa, além de uma
# função utilitária que percorre a AST gerada pelo parser LL(1) da
# Fase 2 e produz a tabela.
#
# Erros detectados nesta etapa (modo "best-effort", coletados em lista):
#   • uso de (MEM) antes de qualquer (v MEM) com o mesmo nome;
#   • redeclaração com tipo incompatível;
#   • (N RES) com N maior do que o número de statements anteriores.
#
# Tipos inferidos nesta fase (inferência completa virá na Sprint 4):
#   • número literal sem ponto  → "int"
#   • número literal com ponto  → "real"
#   • expressão relacional       → "bool"
#   • divisão real  ``|``        → "real"
#   • divisão inteira ``/`` ou ``%`` → "int"
#   • (MEM) referenciando variável conhecida → tipo da variável
#   • demais casos               → "indef"
#
#   081b6905637a0a0f190a087a777a1b282e322f287a1f373b342f3f367a3f7a1c283f3e3f283339357a777a686a686f

from __future__ import annotations

from pathlib import Path


# --------------------------------------------------------------
# Tipos auxiliares
# --------------------------------------------------------------

TIPO_INT = "int"
TIPO_REAL = "real"
TIPO_BOOL = "bool"
TIPO_INDEF = "indef"

_OPS_RELACIONAIS = {">", "<", "==", "!=", ">=", "<="}
_OPS_INT = {"/", "%"}
_OPS_REAL = {"|"}


class ErroSemantico:
    """Erro semântico coletado durante a construção da tabela.

    Mantemos um objeto leve (e não uma exceção) porque a análise
    semântica adota recuperação de erros: queremos reportar todos os
    problemas de uma vez, igual ao parser em modo pânico da Fase 2.
    """

    __slots__ = ("mensagem", "linha")

    def __init__(self, mensagem: str, linha: int = 0) -> None:
        self.mensagem = mensagem
        self.linha = linha

    def __repr__(self) -> str:  # pragma: no cover - utilitário de debug
        return f"ErroSemantico(linha={self.linha}, msg={self.mensagem!r})"

    def __str__(self) -> str:
        prefixo = f"[semântico] (linha {self.linha}) " if self.linha else "[semântico] "
        return prefixo + self.mensagem


# --------------------------------------------------------------
# Tabela de símbolos
# --------------------------------------------------------------


class TabelaSimbolos:
    """Tabela de símbolos do programa (escopo único: ``global``).

    Cada entrada é um ``dict`` com as chaves:
      ``nome``        — identificador da variável MEM;
      ``tipo``        — tipo inferido na primeira declaração;
      ``linha_def``   — linha da primeira ``(v MEM)``;
      ``linhas_uso``  — lista de linhas onde ``(MEM)`` aparece;
      ``escopo``      — sempre ``"global"`` nesta linguagem.
    """

    def __init__(self) -> None:
        self._tab: dict[str, dict] = {}

    # ---- operações principais -----------------------------------

    def declarar(self, nome: str, tipo: str, linha: int) -> list[ErroSemantico]:
        """Registra ``(v MEM)``. Devolve lista de erros (vazia se ok)."""
        erros: list[ErroSemantico] = []
        if nome in self._tab:
            existente = self._tab[nome]
            tipo_atual = existente["tipo"]
            if tipo_atual == TIPO_INDEF and tipo != TIPO_INDEF:
                # promove de indef para o tipo concreto
                existente["tipo"] = tipo
            elif tipo == TIPO_INDEF:
                # nada a fazer: mantém o tipo conhecido
                pass
            elif tipo_atual != tipo:
                erros.append(
                    ErroSemantico(
                        f"redeclaração da variável '{nome}' com tipo "
                        f"incompatível: era '{tipo_atual}', recebeu '{tipo}'",
                        linha,
                    )
                )
            # mesmo se houver erro, registramos a linha como uma "nova def"
            # para que análises subsequentes funcionem
            return erros
        self._tab[nome] = {
            "nome": nome,
            "tipo": tipo,
            "linha_def": linha,
            "linhas_uso": [],
            "escopo": "global",
        }
        return erros

    def usar(self, nome: str, linha: int) -> tuple[dict | None, list[ErroSemantico]]:
        """Registra ``(MEM)``. Devolve (símbolo|None, erros)."""
        if nome not in self._tab:
            return None, [
                ErroSemantico(
                    f"uso da variável '{nome}' antes da declaração (faltou '(v MEM)')",
                    linha,
                )
            ]
        sim = self._tab[nome]
        if linha and linha not in sim["linhas_uso"]:
            sim["linhas_uso"].append(linha)
        return sim, []

    # ---- acesso somente-leitura ---------------------------------

    def obter(self, nome: str) -> dict | None:
        return self._tab.get(nome)

    def itens(self) -> list[dict]:
        return [self._tab[n] for n in sorted(self._tab)]

    def __contains__(self, nome: str) -> bool:  # pragma: no cover - trivial
        return nome in self._tab

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._tab)


# --------------------------------------------------------------
# Inferência de tipos (versão leve da Sprint 2)
# --------------------------------------------------------------


def _tipo_de_numero(valor: str) -> str:
    return TIPO_REAL if "." in valor else TIPO_INT


def inferir_tipo(no: dict | None, tabela: TabelaSimbolos) -> str:
    """Inferência de tipo *best-effort* a partir da AST.

    Esta versão é minimalista; a Sprint 4 (verificarTipos) fará a
    verificação completa com erros e promoções. Aqui basta o suficiente
    para registrar o tipo declarado nas variáveis MEM.
    """
    if no is None:
        return TIPO_INDEF
    tipo = no.get("tipo")
    if tipo == "number":
        return _tipo_de_numero(no.get("valor", ""))
    if tipo == "binary":
        op = no.get("op", "")
        if op in _OPS_RELACIONAIS:
            return TIPO_BOOL
        if op in _OPS_REAL:
            return TIPO_REAL
        if op in _OPS_INT:
            return TIPO_INT
        # +, -, *, ^  → herdamos o tipo dos operandos (regra simples)
        t_esq = inferir_tipo(no.get("esq"), tabela)
        t_dir = inferir_tipo(no.get("dir"), tabela)
        if t_esq == t_dir and t_esq in (TIPO_INT, TIPO_REAL):
            return t_esq
        if TIPO_REAL in (t_esq, t_dir):
            return TIPO_REAL
        if TIPO_INT in (t_esq, t_dir):
            return TIPO_INT
        return TIPO_INDEF
    if tipo == "mem_read":
        sim = tabela.obter(no.get("nome", ""))
        return sim["tipo"] if sim else TIPO_INDEF
    if tipo == "mem_write":
        # uma escrita não devolve valor utilizável aqui
        return TIPO_INDEF
    if tipo == "res_ref":
        return TIPO_INDEF  # depende do statement referenciado
    if tipo == "if":
        return inferir_tipo(no.get("then_block"), tabela)
    if tipo == "ifelse":
        t1 = inferir_tipo(no.get("then_block"), tabela)
        t2 = inferir_tipo(no.get("else_block"), tabela)
        return t1 if t1 == t2 else TIPO_INDEF
    if tipo == "while":
        return TIPO_INDEF
    if tipo in ("led_write", "delay_ms", "morse_word"):
        return TIPO_INDEF
    return TIPO_INDEF


# --------------------------------------------------------------
# Construção da tabela a partir da AST
# --------------------------------------------------------------


def construirTabelaSimbolos(arvore: dict) -> tuple[TabelaSimbolos, list[ErroSemantico]]:
    """Percorre a AST do programa e devolve ``(tabela, erros)``.

    O percurso é pré-ordem; para ``mem_write`` registramos a declaração
    ANTES de descer no valor (uma definição numa expressão imbricada
    passa a valer a partir daquele ponto). Para ``mem_read`` registramos
    o uso. Para ``res_ref`` validamos o N contra o índice do statement
    de topo atual.
    """
    tabela = TabelaSimbolos()
    erros: list[ErroSemantico] = []
    if not arvore or arvore.get("tipo") != "program":
        return tabela, erros

    stmts: list[dict] = arvore.get("stmts", [])

    def visitar(no: dict | None, idx_stmt_topo: int) -> None:
        if not isinstance(no, dict):
            return
        tipo = no.get("tipo")
        linha = no.get("linha", 0) or 0

        if tipo == "mem_write":
            # primeiro descemos no valor (ele não pode usar a própria
            # MEM antes de ela existir — mas pode usar OUTRAS MEMs já
            # declaradas anteriormente)
            visitar(no.get("valor"), idx_stmt_topo)
            tipo_inferido = inferir_tipo(no.get("valor"), tabela)
            erros.extend(tabela.declarar(no.get("nome", ""), tipo_inferido, linha))
            return

        if tipo == "mem_read":
            _, errs = tabela.usar(no.get("nome", ""), linha)
            erros.extend(errs)
            return

        if tipo == "res_ref":
            n = no.get("linhas_atras", 0)
            if n > idx_stmt_topo:
                erros.append(
                    ErroSemantico(
                        f"(N RES) referencia {n} linhas atrás, mas só existem "
                        f"{idx_stmt_topo} statement(s) anterior(es)",
                        linha,
                    )
                )
            return

        if tipo == "binary":
            visitar(no.get("esq"), idx_stmt_topo)
            visitar(no.get("dir"), idx_stmt_topo)
            return

        if tipo == "if":
            visitar(no.get("cond"), idx_stmt_topo)
            visitar(no.get("then_block"), idx_stmt_topo)
            return

        if tipo == "ifelse":
            visitar(no.get("cond"), idx_stmt_topo)
            visitar(no.get("then_block"), idx_stmt_topo)
            visitar(no.get("else_block"), idx_stmt_topo)
            return

        if tipo == "while":
            visitar(no.get("cond"), idx_stmt_topo)
            visitar(no.get("body"), idx_stmt_topo)
            return

        if tipo == "led_write":
            visitar(no.get("valor"), idx_stmt_topo)
            return

        if tipo == "delay_ms":
            visitar(no.get("ms"), idx_stmt_topo)
            return

        if tipo == "morse_word":
            # "nome" aqui é a palavra literal a soletrar em Morse, não uma
            # variável MEM — não declara nem usa símbolo na tabela.
            return

        # number, ident, keyword: folhas sem efeito sobre a tabela

    for i, stmt in enumerate(stmts):
        # idx_stmt_topo = i  → quantos statements existem ANTES deste
        visitar(stmt, i)

    return tabela, erros


# --------------------------------------------------------------
# Renderização: tabela em Markdown
# --------------------------------------------------------------


def formatarTabelaMarkdown(tabela: TabelaSimbolos) -> str:
    """Devolve uma representação Markdown da tabela de símbolos."""
    linhas: list[str] = []
    linhas.append("# Tabela de Símbolos\n")
    if len(tabela) == 0:
        linhas.append("_Nenhuma variável MEM declarada._\n")
        return "\n".join(linhas)
    linhas.append("| Nome | Tipo | Escopo | Linha def. | Linhas de uso |")
    linhas.append("|------|------|--------|-----------:|---------------|")
    for sim in tabela.itens():
        usos = ", ".join(str(u) for u in sim["linhas_uso"]) or "—"
        linhas.append(
            f"| `{sim['nome']}` | {sim['tipo']} | {sim['escopo']} | "
            f"{sim['linha_def']} | {usos} |"
        )
    return "\n".join(linhas) + "\n"


def salvarTabelaSimbolos(
    tabela: TabelaSimbolos, caminho: str | Path = "output/tabela_simbolos.md"
) -> Path:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(formatarTabelaMarkdown(tabela), encoding="utf-8")
    return p


# --------------------------------------------------------------
# Verificação de Tipos (Sprint 3 / §4 do guia)
# --------------------------------------------------------------

# Regras formais (cálculo de sequentes) — ver `regras_tipos.md`.
# Sumário (Γ = ambiente da tabela de símbolos):
#
#   • literal sem ponto         → int
#   • literal com ponto         → real
#   • (e1 e2 op),  op ∈ {+,-,*,^}  exige  e1:τ, e2:τ, τ ∈ {int, real}  → τ
#   • (e1 e2 /),  (e1 e2 %)      exige  e1:int, e2:int                  → int
#   • (e1 e2 |)                  exige  e1:real, e2:real                → real
#   • (e1 e2 ⊳),  ⊳ ∈ {>,<,==,!=,>=,<=}  exige  e1:τ, e2:τ, τ numérico  → bool
#   • (cond block IF)            exige  cond:bool                       → τ(block)
#   • (cond t e IFELSE)          exige  cond:bool ∧ τ(t) = τ(e)         → τ(t)
#   • (cond body WHILE)          exige  cond:bool                       → unit
#   • (v MEM)                    declara MEM:τ(v)                       (Γ' = Γ, MEM:τ(v))
#   • (MEM)                      exige  MEM ∈ Γ                         → τ(MEM)
#
# Política sobre tipos numéricos: NÃO há promoção implícita int→real.
#   `(1 2.5 +)` é erro semântico. Justificativa: o gerador ARMv7 escolhe
#   instruções diferentes para int (ADD) e real (VADD.F64); manter os
#   tipos disjuntos simplifica a geração de código e respeita a regra
#   "tipo da variável fixado no momento da definição" (§2.3).
# Tipos indefinidos (TIPO_INDEF) são tratados como "joker": não geram
# erros em cascata (o erro original já foi reportado pela TabelaSimbolos).


def _emitir(erros: list[ErroSemantico], msg: str, linha: int) -> None:
    erros.append(ErroSemantico(msg, linha))


def verificarTipos(
    arvore: dict, tabela: TabelaSimbolos
) -> tuple[dict, list[ErroSemantico]]:
    """Aplica as regras de tipos sobre a AST e devolve ``(arvore, erros)``.

    A árvore recebida é mutada in-place: cada nó relevante recebe a
    chave ``tipo_inferido``. Os erros são acumulados em lista (sem
    abortar no primeiro), seguindo o estilo de recuperação adotado em
    todo o projeto.
    """
    erros: list[ErroSemantico] = []
    if not arvore or arvore.get("tipo") != "program":
        return arvore, erros

    stmts_tipados: list[dict] = []  # contexto para resolução de (N RES)

    def tipar(no) -> str:
        if not isinstance(no, dict):
            return TIPO_INDEF
        t = no.get("tipo")
        linha = no.get("linha", 0) or 0

        if t == "number":
            ti = _tipo_de_numero(no.get("valor", ""))
        elif t == "mem_read":
            sim = tabela.obter(no.get("nome", ""))
            ti = sim["tipo"] if sim else TIPO_INDEF
        elif t == "res_ref":
            # Tipo de (N RES) = tipo do statement N posições antes do atual.
            n = no.get("linhas_atras", 0) or 0
            if 1 <= n <= len(stmts_tipados):
                ti = stmts_tipados[-n].get("tipo_inferido", TIPO_INDEF)
            else:
                ti = TIPO_INDEF
        elif t == "mem_write":
            # mem_write propaga o tipo do valor escrito (T-MemDef/T-MemSet).
            ti = tipar(no.get("valor"))
        elif t == "binary":
            ti = _tipar_binario(no, tipar, erros)
        elif t == "if":
            tc = tipar(no.get("cond"))
            tb = tipar(no.get("then_block"))
            if tc not in (TIPO_BOOL, TIPO_INDEF):
                _emitir(erros, f"condição do IF deve ser 'bool', recebeu '{tc}'", linha)
            ti = tb
        elif t == "ifelse":
            tc = tipar(no.get("cond"))
            tt = tipar(no.get("then_block"))
            te = tipar(no.get("else_block"))
            if tc not in (TIPO_BOOL, TIPO_INDEF):
                _emitir(erros, f"condição do IFELSE deve ser 'bool', recebeu '{tc}'", linha)
            if tt == te:
                ti = tt
            elif TIPO_INDEF in (tt, te):
                ti = tt if tt != TIPO_INDEF else te
            else:
                _emitir(
                    erros,
                    f"ramos do IFELSE têm tipos divergentes: 'then':{tt} vs 'else':{te}",
                    linha,
                )
                ti = TIPO_INDEF
        elif t == "while":
            tc = tipar(no.get("cond"))
            tipar(no.get("body"))
            if tc not in (TIPO_BOOL, TIPO_INDEF):
                _emitir(erros, f"condição do WHILE deve ser 'bool', recebeu '{tc}'", linha)
            ti = TIPO_INDEF
        elif t == "led_write":
            tipar(no.get("valor"))
            ti = TIPO_INDEF
        elif t == "delay_ms":
            tipar(no.get("ms"))
            ti = TIPO_INDEF
        elif t == "morse_word":
            ti = TIPO_INDEF
        else:
            ti = TIPO_INDEF

        no["tipo_inferido"] = ti
        return ti

    for stmt in arvore.get("stmts", []):
        tipar(stmt)
        stmts_tipados.append(stmt)
    return arvore, erros


def _tipar_binario(no: dict, tipar, erros: list[ErroSemantico]) -> str:
    op = no.get("op", "")
    linha = no.get("linha", 0) or 0
    te = tipar(no.get("esq"))
    td = tipar(no.get("dir"))

    numericos = {TIPO_INT, TIPO_REAL}

    if op in _OPS_RELACIONAIS:
        if TIPO_INDEF in (te, td):
            return TIPO_BOOL
        if te == td and te in numericos:
            return TIPO_BOOL
        _emitir(
            erros,
            f"operador relacional '{op}' exige operandos numéricos do mesmo tipo, "
            f"recebeu '{te}' e '{td}'",
            linha,
        )
        return TIPO_BOOL

    if op == "|":
        if TIPO_INDEF in (te, td):
            return TIPO_REAL
        if te == TIPO_REAL and td == TIPO_REAL:
            return TIPO_REAL
        _emitir(
            erros,
            f"operador '|' (divisão real) exige operandos 'real', recebeu '{te}' e '{td}'",
            linha,
        )
        return TIPO_REAL

    if op in _OPS_INT:
        if TIPO_INDEF in (te, td):
            return TIPO_INT
        if te == TIPO_INT and td == TIPO_INT:
            return TIPO_INT
        _emitir(
            erros,
            f"operador '{op}' exige operandos 'int', recebeu '{te}' e '{td}'",
            linha,
        )
        return TIPO_INT

    # operadores que aceitam int OU real (homogêneo): + - * ^
    if TIPO_INDEF in (te, td):
        # propaga o tipo conhecido (se houver) — evita avalanche
        if te in numericos:
            return te
        if td in numericos:
            return td
        return TIPO_INDEF
    if te == td and te in numericos:
        return te
    _emit(
        erros,
        f"operador '{op}' exige operandos numéricos do mesmo tipo (sem promoção implícita), "
        f"recebeu '{te}' e '{td}'",
        linha,
    )
    return TIPO_INDEF


def _emit(erros: list[ErroSemantico], msg: str, linha: int) -> None:  # pragma: no cover - alias
    _emitir(erros, msg, linha)


# --------------------------------------------------------------
# Árvore Sintática Atribuída (Etapa 4 / §5 do guia)
# --------------------------------------------------------------

# A "árvore atribuída" é a AST original enriquecida com:
#   • ``tipo_inferido``   — já posto por verificarTipos (Etapa 3);
#   • ``meta_asm``        — metadados para a fase de geração de código
#                           (registrador alvo sugerido e, para nós de
#                           controle, os rótulos que serão usados);
#   • ``simbolo_ref``     — em nós ``mem_read``/``mem_write``: cópia
#                           dos campos relevantes da entrada da
#                           TabelaSimbolos (não usamos uma referência
#                           direta para que a árvore continue serializável
#                           em JSON sem ciclos).
#
# Não duplicamos nós — anotamos in-place (mesma estratégia de
# verificarTipos). Quem quiser preservar a árvore "crua" deve copiar
# antes via ``copy.deepcopy``.


# Mapa tipo_inferido → registrador sugerido para o gerador.
_REG_ALVO = {
    TIPO_INT: "R0",
    TIPO_BOOL: "R0",   # bool fica em registrador inteiro (0/1)
    TIPO_REAL: "D0",
    TIPO_INDEF: "D0",  # fallback conservador: dobro
}


def _meta_asm_base(no: dict, ctx: dict) -> dict:
    tipo = no.get("tipo_inferido", TIPO_INDEF)
    meta: dict = {"registrador": _REG_ALVO.get(tipo, "D0"), "tipo": tipo}
    return meta


def _proximo_rotulo(ctx: dict, base: str) -> str:
    ctx["rotulo"] = ctx.get("rotulo", 0) + 1
    return f"L_{base}_{ctx['rotulo']}"


def gerarArvoreAtribuida(arvore: dict, tabela: TabelaSimbolos) -> dict:
    """Enriquece a AST (já tipada) com metadados para Assembly.

    Pré-condição: a AST deve ter passado por :func:`verificarTipos`
    (todos os nós relevantes têm ``tipo_inferido``). A AST é mutada
    in-place e também devolvida.
    """
    if not arvore or arvore.get("tipo") != "program":
        return arvore

    ctx: dict = {"rotulo": 0}

    def visitar(no) -> None:
        if not isinstance(no, dict):
            return
        t = no.get("tipo")

        if t == "number":
            no["meta_asm"] = _meta_asm_base(no, ctx)
            return

        if t == "mem_read":
            sim = tabela.obter(no.get("nome", ""))
            if sim is not None:
                no["simbolo_ref"] = {
                    "nome": sim["nome"],
                    "tipo": sim["tipo"],
                    "linha_def": sim["linha_def"],
                    "escopo": sim["escopo"],
                }
            meta = _meta_asm_base(no, ctx)
            meta["mem_label"] = f"mem_{no.get('nome', '').lower()}"
            no["meta_asm"] = meta
            return

        if t == "mem_write":
            visitar(no.get("valor"))
            sim = tabela.obter(no.get("nome", ""))
            if sim is not None:
                no["simbolo_ref"] = {
                    "nome": sim["nome"],
                    "tipo": sim["tipo"],
                    "linha_def": sim["linha_def"],
                    "escopo": sim["escopo"],
                }
            meta = _meta_asm_base(no, ctx)
            meta["mem_label"] = f"mem_{no.get('nome', '').lower()}"
            no["meta_asm"] = meta
            return

        if t == "res_ref":
            no["meta_asm"] = _meta_asm_base(no, ctx)
            return

        if t == "binary":
            visitar(no.get("esq"))
            visitar(no.get("dir"))
            meta = _meta_asm_base(no, ctx)
            op = no.get("op", "")
            t_esq = (no.get("esq") or {}).get("tipo_inferido", TIPO_INDEF)
            t_dir = (no.get("dir") or {}).get("tipo_inferido", TIPO_INDEF)
            meta["op"] = op
            meta["instrucao_sugerida"] = _instrucao_sugerida(op, t_esq, t_dir)
            no["meta_asm"] = meta
            return

        if t == "if":
            visitar(no.get("cond"))
            visitar(no.get("then_block"))
            meta = _meta_asm_base(no, ctx)
            meta["label_fim"] = _proximo_rotulo(ctx, "if_fim")
            no["meta_asm"] = meta
            return

        if t == "ifelse":
            visitar(no.get("cond"))
            visitar(no.get("then_block"))
            visitar(no.get("else_block"))
            meta = _meta_asm_base(no, ctx)
            meta["label_else"] = _proximo_rotulo(ctx, "else")
            meta["label_fim"] = _proximo_rotulo(ctx, "ife_fim")
            no["meta_asm"] = meta
            return

        if t == "while":
            visitar(no.get("cond"))
            visitar(no.get("body"))
            meta = _meta_asm_base(no, ctx)
            meta["label_inicio"] = _proximo_rotulo(ctx, "while_i")
            meta["label_fim"] = _proximo_rotulo(ctx, "while_f")
            no["meta_asm"] = meta
            return

        if t == "led_write":
            visitar(no.get("valor"))
            no["meta_asm"] = _meta_asm_base(no, ctx)
            return

        if t == "delay_ms":
            visitar(no.get("ms"))
            no["meta_asm"] = _meta_asm_base(no, ctx)
            return

        if t == "morse_word":
            no["meta_asm"] = _meta_asm_base(no, ctx)
            return

    for stmt in arvore.get("stmts", []):
        visitar(stmt)

    return arvore


def _instrucao_sugerida(op: str, t_esq: str, t_dir: str) -> str:
    """Devolve a string da instrução ARM que o gerador deveria emitir.

    Serve como documentação dentro da árvore atribuída e também guia o
    gerador de Assembly da Etapa 5 (ele inspeciona ``meta_asm``).
    """
    if op in _OPS_RELACIONAIS:
        if t_esq == TIPO_INT and t_dir == TIPO_INT:
            return "CMP+MOV"
        return "VCMP.F64+MOV"
    if op == "|":
        return "VDIV.F64"
    if op == "/":
        return "BL __op_idiv"
    if op == "%":
        return "BL __op_mod"
    if op == "^":
        return "BL __op_pow"
    if op in ("+", "-", "*"):
        # ARM puro para int, VFP para real
        if t_esq == TIPO_INT and t_dir == TIPO_INT:
            return {"+": "ADD", "-": "SUB", "*": "MUL"}[op]
        return {"+": "VADD.F64", "-": "VSUB.F64", "*": "VMUL.F64"}[op]
    return "?"


# ---- Serialização ----------------------------------------------------


def serializarArvoreAtribuidaJSON(arvore: dict) -> str:
    import json

    return json.dumps(arvore, ensure_ascii=False, indent=2)


def serializarArvoreAtribuidaMarkdown(arvore: dict) -> str:
    """Render bonito em Markdown (árvore indentada com tipo + meta)."""
    if not arvore or arvore.get("tipo") != "program":
        return "# Árvore Atribuída\n\n_Vazia._\n"
    linhas: list[str] = ["# Árvore Sintática Atribuída\n"]
    linhas.append("Cada nó traz `tipo_inferido` (Etapa 3) e `meta_asm` (Etapa 4).\n")
    linhas.append("```text")
    for i, stmt in enumerate(arvore.get("stmts", []), 1):
        linhas.append(f"stmt #{i}")
        _render_no(stmt, linhas, prefixo="  ")
    linhas.append("```")
    return "\n".join(linhas) + "\n"


def _render_no(no, linhas: list[str], prefixo: str) -> None:
    if not isinstance(no, dict):
        linhas.append(f"{prefixo}<{no!r}>")
        return
    t = no.get("tipo", "?")
    ti = no.get("tipo_inferido", "—")
    meta = no.get("meta_asm", {})
    cab = f"{prefixo}{t}  : tipo={ti}"
    if meta:
        extras = []
        if "instrucao_sugerida" in meta:
            extras.append(f"instr={meta['instrucao_sugerida']}")
        if "registrador" in meta:
            extras.append(f"reg={meta['registrador']}")
        if "label_inicio" in meta:
            extras.append(f"L_ini={meta['label_inicio']}")
        if "label_else" in meta:
            extras.append(f"L_else={meta['label_else']}")
        if "label_fim" in meta:
            extras.append(f"L_fim={meta['label_fim']}")
        if "mem_label" in meta:
            extras.append(f"mem={meta['mem_label']}")
        if extras:
            cab += "  [" + ", ".join(extras) + "]"
    if t == "number":
        cab += f"  valor={no.get('valor')!r}"
    if t == "res_ref":
        cab += f"  linhas_atras={no.get('linhas_atras')}"
    if t in ("mem_read", "mem_write"):
        cab += f"  nome={no.get('nome')!r}"
    if "simbolo_ref" in no:
        s = no["simbolo_ref"]
        cab += f"  → sim(tipo={s['tipo']}, def={s['linha_def']})"
    linhas.append(cab)

    filhos = []
    for chave in ("valor", "esq", "dir", "cond", "then_block", "else_block", "body"):
        if chave in no:
            filhos.append((chave, no[chave]))
    for chave, filho in filhos:
        linhas.append(f"{prefixo}  ├─ {chave}:")
        _render_no(filho, linhas, prefixo + "  │  ")


def salvarArvoreAtribuida(
    arvore: dict,
    diretorio: str | Path = "output",
) -> tuple[Path, Path]:
    """Escreve a árvore atribuída em ``output/arvore_atribuida.{md,json}``.

    Devolve ``(caminho_md, caminho_json)``.
    """
    base = Path(diretorio)
    base.mkdir(parents=True, exist_ok=True)
    p_md = base / "arvore_atribuida.md"
    p_json = base / "arvore_atribuida.json"
    p_md.write_text(serializarArvoreAtribuidaMarkdown(arvore), encoding="utf-8")
    p_json.write_text(serializarArvoreAtribuidaJSON(arvore), encoding="utf-8")
    return p_md, p_json
