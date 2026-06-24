# Integrantes:
#   Emanuel Riceto da Silva (emanuelriceto)
# Grupo Canvas: RA4 9
# Instituição: Pontifícia Universidade Católica do Paraná
# Disciplina: Linguagens Formais e Compiladores
# Professor: Valter Klein

# Gerador de código Assembly ARMv7 para o CPUlator DE1-SoC.
# Recebe a AST produzida por parser_ll1.gerarArvore() e percorre
# recursivamente cada nó, emitindo instruções ARM.
#
# Estratégia: pilha de variáveis duplas (d-registers, VFPv3)
#   todos os valores são tratados como double (IEEE 754 64-bit)
#   operações empilham o resultado em d0 e usam VMOV+PUSH para salvar
#
# Operadores suportados:
#   +, -, *  -> VADD/VSUB/VMUL.F64
#   |        -> VDIV.F64 (divisão real)
#   /        -> __op_idiv (divisão inteira via rotina auxiliar)
#   %        -> __op_mod
#   ^        -> __op_pow (expoente inteiro por multiplicações sucessivas)
#   >, <, ==, !=, >=, <= -> VCMP.F64 + desvio condicional -> empilha 1.0 ou 0.0
#
# Estruturas de controle:
#   IF    -> testa condição e desvia sobre o bloco se falso
#   IFELSE-> dois rótulos (else + fim), executa um dos dois ramos
#   WHILE -> rótulo de início + rótulo de saída, desvio condicional
#   QXJ0aHVyIEVtYW51ZWwgZSBGcmVkZXJpY28=


# RA4: tabela de conversão ASCII (A-Z) -> código Morse internacional.
# Usada pelo gerador para expandir (PALAVRA MORSE) numa sequência de
# LED/DELAY em tempo de COMPILAÇÃO — o aluno não precisa mais escrever
# "(1 LED) (300 DELAY) ..." manualmente para cada ponto/traço.
MORSE_TABLE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
}

MORSE_DOT_MS = 300
MORSE_DASH_MS = 600
MORSE_GAP_SIMBOLO_MS = 450   # espaço dentro da letra
MORSE_GAP_LETRA_MS = 900     # espaço entre letras
MORSE_GAP_PALAVRA_MS = 2000  # espaço entre palavras (= intervalo antes de repetir o loop)

# Fator de escala de tempo (apenas visualização no CPUlator).
# O simulador roda mais rápido que o relógio real, então o ponto/traço de
# 300/600 ms "reais" piscam rápido demais para distinguir. Multiplicamos
# TODAS as durações por este fator (as proporções ponto:traço = 1:2 e os
# espaços continuam corretos). Para o tempo EXATO da especificação
# (ponto = 300 ms reais), basta colocar 1 aqui e recompilar.
ESCALA_TEMPO = 1

# Endereços memory-mapped do DE1-SoC, divididos em metades de 16 bits para
# carregar via MOVW/MOVT (assim não precisamos de literal pool / LDR =).
LED_BASE_LO, LED_BASE_HI = 0x0000, 0xFF20      # 0xFF200000 — LEDR (LED0 = bit 0)
TIMER_BASE_LO, TIMER_BASE_HI = 0x2000, 0xFF20  # 0xFF202000 — interval timer
TIMER_HZ = 100_000_000                          # timer do DE1-SoC roda a 100 MHz


def _normalizar_nome_mem(nome: str) -> str:
    return nome.lower()


# ===================================================================
# RA4 — Gerador "hardware-only" (LEDs + timer), mínimo e verificável.
#
# Quando o programa é composto SÓ por (PALAVRA MORSE), (n LED) e (n DELAY)
# com operandos literais, geramos um Assembly enxuto que:
#   • não usa VFP nem pilha (logo, dispensa inicializar SP);
#   • não usa literal pool (endereços via MOVW/MOVT) — sem "pool needs to
#     be closer";
#   • mede o tempo com o interval timer do DE1-SoC (ms exatos);
#   • roda em LOOP infinito.
# O conjunto de instruções resultante (MOVW, MOVT, MOV #imm, STR, LDR, TST,
# BEQ, B) é pequeno e foi conferido bit a bit contra o ARM ARM, então o
# hexadecimal produzido pelo linker é confiável.
# ===================================================================


def _programa_so_hardware(stmts: list[dict]) -> bool:
    """True se todos os statements forem morse_word ou led/delay literais."""
    def _literal(no) -> bool:
        return isinstance(no, dict) and no.get("tipo") == "number"

    if not stmts:
        return False
    for s in stmts:
        t = s.get("tipo")
        if t == "morse_word":
            continue
        if t == "led_write" and _literal(s.get("valor")):
            continue
        if t == "delay_ms" and _literal(s.get("ms")):
            continue
        return False
    return True


def _hw_carrega_ptr(linhas: list[str], reg: str, lo: int, hi: int) -> None:
    linhas.append(f"    MOVW {reg}, #0x{lo:04X}")
    linhas.append(f"    MOVT {reg}, #0x{hi:04X}")


def _hw_led(linhas: list[str], aceso: int) -> None:
    # Escreve 0/1 no LEDR (LED0). r1 = base dos LEDs, r0 = valor.
    _hw_carrega_ptr(linhas, "r1", LED_BASE_LO, LED_BASE_HI)
    linhas.append(f"    MOV r0, #{1 if aceso else 0}")
    linhas.append("    STR r0, [r1]")


def _hw_delay(linhas: list[str], ms: int, ctx: dict) -> None:
    # Espera exata de `ms` via interval timer (one-shot + polling do bit TO).
    # Registradores do timer (offsets a partir de 0xFF202000):
    #   +0x00 status (bit0=TO), +0x04 control (bit2=START,bit3=STOP),
    #   +0x08 periodl, +0x0C periodh.
    n = int(ms) * (TIMER_HZ // 1000) * ESCALA_TEMPO   # ciclos = ms * 100000 * escala
    lo = n & 0xFFFF
    hi = (n >> 16) & 0xFFFF
    ctx["n"] += 1
    wlbl = f"__espera_{ctx['n']}"
    linhas.append(f"    @ ---- delay {ms} ms (x{ESCALA_TEMPO}) -> N = {n} ciclos @ 100 MHz ----")
    _hw_carrega_ptr(linhas, "r1", TIMER_BASE_LO, TIMER_BASE_HI)
    linhas.append("    MOV r0, #0x8")
    linhas.append("    STR r0, [r1, #4]      @ control = STOP")
    linhas.append(f"    MOVW r0, #0x{lo:04X}")
    linhas.append("    STR r0, [r1, #8]      @ periodl")
    linhas.append(f"    MOVW r0, #0x{hi:04X}")
    linhas.append("    STR r0, [r1, #12]     @ periodh")
    linhas.append("    MOV r0, #0")
    linhas.append("    STR r0, [r1, #0]      @ limpa flag TO")
    linhas.append("    MOV r0, #0x4")
    linhas.append("    STR r0, [r1, #4]      @ control = START (one-shot)")
    linhas.append(f"{wlbl}:")
    linhas.append("    LDR r0, [r1, #0]      @ lê status")
    linhas.append("    TST r0, #1            @ bit TO setou?")
    linhas.append(f"    BEQ {wlbl}           @ não: continua esperando")


def _hw_morse(linhas: list[str], nome: str, ctx: dict) -> None:
    letras = [c for c in nome.upper() if c in MORSE_TABLE]
    n_letras = len(letras)
    linhas.append(f"    @ ============ MORSE: {nome} ============")
    if not letras:
        linhas.append(f"    @ (nenhuma letra A-Z em '{nome}')")
        return
    for li, letra in enumerate(letras):
        codigo = MORSE_TABLE[letra]
        linhas.append(f"    @ letra '{letra}' = {codigo}")
        for si, simbolo in enumerate(codigo):
            dur_on = MORSE_DASH_MS if simbolo == "-" else MORSE_DOT_MS
            _hw_led(linhas, 1)
            _hw_delay(linhas, dur_on, ctx)
            _hw_led(linhas, 0)
            ult_simbolo = si == len(codigo) - 1
            ult_letra = li == n_letras - 1
            if not ult_simbolo:
                gap = MORSE_GAP_SIMBOLO_MS      # 450 — dentro da letra
            elif not ult_letra:
                gap = MORSE_GAP_LETRA_MS        # 900 — entre letras
            else:
                gap = MORSE_GAP_PALAVRA_MS      # 2000 — entre palavras (antes de repetir)
            _hw_delay(linhas, gap, ctx)


def _gerar_assembly_hardware(stmts: list[dict]) -> str:
    """Assembly enxuto p/ programas de hardware, em loop infinito."""
    ctx = {"n": 0}
    linhas: list[str] = []
    linhas.append("@ =====================================================")
    linhas.append("@  RA4 — Código Morse nos LEDs do DE1-SoC (ARMv7)")
    linhas.append("@  LED0 (0xFF200000) + interval timer (0xFF202000)")
    linhas.append("@  Loop infinito. Tempos: ponto=300 traço=600")
    linhas.append("@  intra-letra=450 entre-letras=900 entre-palavras=2000 (ms)")
    linhas.append("@ =====================================================")
    linhas.append(".global _start")
    linhas.append(".text")
    linhas.append("_start:")
    linhas.append("loop_principal:")
    for stmt in stmts:
        t = stmt.get("tipo")
        if t == "morse_word":
            _hw_morse(linhas, stmt.get("nome", ""), ctx)
        elif t == "led_write":
            _hw_led(linhas, int(float(stmt["valor"]["valor"])))
        elif t == "delay_ms":
            _hw_delay(linhas, int(float(stmt["ms"]["valor"])), ctx)
    linhas.append("    B loop_principal      @ repete o nome para sempre")
    return "\n".join(linhas) + "\n"


def _coletar_memorias(no: dict, memorias: set[str]) -> None:
    tipo = no["tipo"]
    if tipo == "program":
        for s in no["stmts"]:
            _coletar_memorias(s, memorias)
        return
    if tipo == "mem_write":
        memorias.add(_normalizar_nome_mem(no["nome"]))
        _coletar_memorias(no["valor"], memorias)
        return
    if tipo == "mem_read":
        memorias.add(_normalizar_nome_mem(no["nome"]))
        return
    if tipo == "binary":
        _coletar_memorias(no["esq"], memorias)
        _coletar_memorias(no["dir"], memorias)
        return
    if tipo == "if":
        _coletar_memorias(no["cond"], memorias)
        _coletar_memorias(no["then_block"], memorias)
        return
    if tipo == "ifelse":
        _coletar_memorias(no["cond"], memorias)
        _coletar_memorias(no["then_block"], memorias)
        _coletar_memorias(no["else_block"], memorias)
        return
    if tipo == "while":
        _coletar_memorias(no["cond"], memorias)
        _coletar_memorias(no["body"], memorias)
        return
    if tipo == "led_write":
        _coletar_memorias(no["valor"], memorias)
        return
    if tipo == "delay_ms":
        _coletar_memorias(no["ms"], memorias)
        return
    if tipo == "morse_word":
        return


# ---- Utilitários de pilha ----
# Como o ARMv7 não tem instrução de push/pop para registradores VFP,
# usamos r4/r5 como intermediários: VMOV move os 64 bits de d0 para r4:r5
# e então PUSH coloca eles na pilha de memória.


def _emit_push_d0(linhas: list[str]) -> None:
    linhas.append("    VMOV r4, r5, d0")
    linhas.append("    PUSH {r4, r5}")


def _emit_pop_para_d(linhas: list[str], reg_d: str) -> None:
    linhas.append("    POP {r4, r5}")
    linhas.append(f"    VMOV {reg_d}, r4, r5")


def _novo_rotulo(ctx: dict, base: str) -> str:
    # gera rótulos únicos incrementando um contador global do contexto
    ctx["contador_rotulos"] += 1
    return f"L_{base}_{ctx['contador_rotulos']}"


# ---- Emissão recursiva de expressões ----


def _emit_expressao(no: dict, linhas: list[str], ctx: dict) -> None:
    # Despacha para a função correta de acordo com o tipo do nó da AST.
    tipo = no["tipo"]

    if tipo == "number":
        # constante numérica: guardamos no segmento .data e carregamos via LDR
        valor = no["valor"]
        mapa = ctx["constantes"]
        if valor not in mapa:
            rotulo = f"const_{ctx['contador_const'][0]}"
            mapa[valor] = rotulo
            ctx["contador_const"][0] += 1
        else:
            rotulo = mapa[valor]
        linhas.append(f"    LDR r0, ={rotulo}")
        linhas.append("    VLDR.F64 d0, [r0]")
        _emit_push_d0(linhas)
        return

    if tipo == "mem_read":
        mem = _normalizar_nome_mem(no["nome"])
        linhas.append(f"    LDR r0, =mem_{mem}")
        linhas.append("    VLDR.F64 d0, [r0]")
        _emit_push_d0(linhas)
        return

    if tipo == "res_ref":
        # (N RES) -> acessa o resultado que ficou salvo N linhas antes
        alvo = ctx["indice_linha"] - no["linhas_atras"]
        if alvo < 0:
            alvo = 0
        linhas.append(f"    LDR r0, =resultado_{alvo}")
        linhas.append("    VLDR.F64 d0, [r0]")
        _emit_push_d0(linhas)
        return

    if tipo == "mem_write":
        _emit_expressao(no["valor"], linhas, ctx)
        _emit_pop_para_d(linhas, "d0")
        mem = _normalizar_nome_mem(no["nome"])
        linhas.append(f"    LDR r0, =mem_{mem}")
        linhas.append("    VSTR.F64 d0, [r0]")
        _emit_push_d0(linhas)
        return

    if tipo == "binary":
        _emit_binario(no, linhas, ctx)
        return

    if tipo == "if":
        _emit_if(no, linhas, ctx)
        return
    if tipo == "ifelse":
        _emit_ifelse(no, linhas, ctx)
        return
    if tipo == "while":
        _emit_while(no, linhas, ctx)
        return
    if tipo == "led_write":
        _emit_led_write(no, linhas, ctx)
        return
    if tipo == "delay_ms":
        _emit_delay_ms(no, linhas, ctx)
        return
    if tipo == "morse_word":
        _emit_morse_word(no, linhas, ctx)
        return

    raise ValueError(f"Nó inválido: {tipo}")


def _emit_led_write(no: dict, linhas: list[str], ctx: dict) -> None:
    # (valor LED) — escreve 0 ou 1 no registrador de LEDs (DE1-SoC: 0xFF200000)
    linhas.append("    @ LED write")
    _emit_expressao(no["valor"], linhas, ctx)
    _emit_pop_para_d(linhas, "d0")
    linhas.append("    VCVT.S32.F64 s0, d0")
    linhas.append("    VMOV r0, s0")
    linhas.append("    LDR r1, =0xFF200000")
    linhas.append("    STR r0, [r1]")
    # empilha 0.0 como resultado neutro
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d0, [r0]")
    _emit_push_d0(linhas)


def _emit_delay_ms(no: dict, linhas: list[str], ctx: dict) -> None:
    # (ms DELAY) — aguarda ms milissegundos usando rotina __delay_ms
    linhas.append("    @ DELAY ms")
    _emit_expressao(no["ms"], linhas, ctx)
    _emit_pop_para_d(linhas, "d0")
    linhas.append("    VCVT.S32.F64 s0, d0")
    linhas.append("    VMOV r0, s0")
    linhas.append("    BL __delay_ms")
    # empilha 0.0 como resultado neutro
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d0, [r0]")
    _emit_push_d0(linhas)


def _emit_morse_word(no: dict, linhas: list[str], ctx: dict) -> None:
    # (PALAVRA MORSE) — para cada letra, consulta MORSE_TABLE (ASCII -> Morse)
    # e expande em LED on/off + DELAY, usando as mesmas constantes de tempo
    # do enunciado. Tudo resolvido em tempo de compilação: a letra já é
    # conhecida (é o lexema do identificador), então geramos instruções
    # ARM diretas (MOV/LDR + STR + BL __delay_ms), sem percorrer a pilha VFP.
    nome = no.get("nome", "")
    letras = [c for c in nome.upper() if c in MORSE_TABLE]
    linhas.append(f"    @ MORSE: {nome}")
    if not letras:
        linhas.append(f"    @ (nenhuma letra A-Z reconhecida em '{nome}')")

    for idx_letra, letra in enumerate(letras):
        codigo = MORSE_TABLE[letra]
        linhas.append(f"    @ letra '{letra}' = {codigo}")
        for si, simbolo in enumerate(codigo):
            dur_on = MORSE_DASH_MS if simbolo == "-" else MORSE_DOT_MS
            ultimo_simbolo = si == len(codigo) - 1
            gap = MORSE_GAP_LETRA_MS if ultimo_simbolo else MORSE_GAP_SIMBOLO_MS

            linhas.append("    MOV r0, #1")
            linhas.append("    LDR r1, =0xFF200000")
            linhas.append("    STR r0, [r1]")
            linhas.append(f"    LDR r0, ={dur_on}")
            linhas.append("    BL __delay_ms")
            linhas.append("    MOV r0, #0")
            linhas.append("    LDR r1, =0xFF200000")
            linhas.append("    STR r0, [r1]")
            linhas.append(f"    LDR r0, ={gap}")
            linhas.append("    BL __delay_ms")

        # protege contra "pool needs to be closer" em palavras longas:
        # libera o literal pool a cada poucas letras, saltando por cima dele.
        if (idx_letra + 1) % 4 == 0 and idx_letra < len(letras) - 1:
            skip = _novo_rotulo(ctx, "morse_ltorg")
            linhas.append(f"    B {skip}")
            linhas.append("    .ltorg")
            linhas.append("    .balign 4")
            linhas.append(f"{skip}:")

    # empilha 0.0 como resultado neutro (mantém disciplina de pilha unificada)
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d0, [r0]")
    _emit_push_d0(linhas)


def _emit_binario(no: dict, linhas: list[str], ctx: dict) -> None:
    # avalia esq e dir (resultados ficam na pilha),
    # depois desempilha para d1 (dir) e d0 (esq) e aplica o operador
    _emit_expressao(no["esq"], linhas, ctx)
    _emit_expressao(no["dir"], linhas, ctx)
    _emit_pop_para_d(linhas, "d1")
    _emit_pop_para_d(linhas, "d0")

    op = no["op"]

    # Dispatch tipado (Etapa 5): se o nó foi anotado por
    # gerarArvoreAtribuida e ambos os operandos são `int`, emitimos
    # instruções ARM inteiras (ADD/SUB/MUL/CMP+MOV). Caso contrário,
    # mantemos o caminho VFP (F64) usado historicamente pela Fase 2.
    if _eh_int_puro(no) and op in ("+", "-", "*"):
        _emit_arith_int(op, linhas)
    elif _eh_int_puro(no) and op in (">", "<", "==", "!=", ">=", "<="):
        _emit_comparacao_int(op, linhas, ctx)
    elif op == "+":
        linhas.append("    @ tipo=real +  → VADD.F64")
        linhas.append("    VADD.F64 d0, d0, d1")
    elif op == "-":
        linhas.append("    @ tipo=real -  → VSUB.F64")
        linhas.append("    VSUB.F64 d0, d0, d1")
    elif op == "*":
        linhas.append("    @ tipo=real *  → VMUL.F64")
        linhas.append("    VMUL.F64 d0, d0, d1")
    elif op == "|":
        linhas.append("    @ divisão real → VDIV.F64")
        linhas.append("    VDIV.F64 d0, d0, d1")  # divisão real
    elif op == "/":
        linhas.append("    @ divisão inteira → BL __op_idiv")
        linhas.append("    BL __op_idiv")         # divisão inteira
    elif op == "%":
        linhas.append("    @ módulo inteiro → BL __op_mod")
        linhas.append("    BL __op_mod")
    elif op == "^":
        linhas.append("    @ potência (expoente int) → BL __op_pow")
        linhas.append("    BL __op_pow")
    elif op in (">", "<", "==", "!=", ">=", "<="):
        _emit_comparacao(op, linhas, ctx)
    else:
        raise ValueError(f"Operador não suportado: {op}")

    _emit_push_d0(linhas)


def _eh_int_puro(no: dict) -> bool:
    """Verifica se um nó binário deve usar o caminho ARM inteiro.

    True quando *ambos* os operandos têm ``tipo_inferido == "int"``. A
    ausência da anotação faz o teste retornar False — assim a geração
    de código sobre ASTs não-tipadas (testes da Fase 2) continua usando
    o caminho VFP histórico.
    """
    esq = no.get("esq") or {}
    dir_ = no.get("dir") or {}
    return (
        esq.get("tipo_inferido") == "int"
        and dir_.get("tipo_inferido") == "int"
    )


def _emit_arith_int(op: str, linhas: list[str]) -> None:
    """Emite ADD/SUB/MUL inteiro convertendo d0/d1 em r0/r1.

    Mantemos a pilha de operandos como F64 para compatibilidade com o
    restante do gerador. Converter no operador é simples e correto
    porque a análise de tipos já garantiu que os valores cabem em int32.
    """
    instr = {"+": "ADD", "-": "SUB", "*": "MUL"}[op]
    linhas.append(f"    @ tipo=int {op} → {instr} (ARM inteiro)")
    linhas.append("    VCVT.S32.F64 s0, d0")
    linhas.append("    VCVT.S32.F64 s2, d1")
    linhas.append("    VMOV r0, s0")
    linhas.append("    VMOV r1, s2")
    linhas.append(f"    {instr} r0, r0, r1")
    linhas.append("    VMOV s0, r0")
    linhas.append("    VCVT.F64.S32 d0, s0")


def _emit_comparacao_int(op: str, linhas: list[str], ctx: dict) -> None:
    """Comparação relacional ARM inteira (CMP + MOVcc), resultado 0/1.

    O resultado bool é devolvido como 0.0 ou 1.0 em ``d0`` (mesma
    convenção da comparação F64) para que IF/WHILE/IFELSE continuem
    testando contra ``const_zero``.
    """
    cc = {">": "GT", "<": "LT", ">=": "GE", "<=": "LE", "==": "EQ", "!=": "NE"}[op]
    linhas.append(f"    @ tipo=bool ({op} int) → CMP + MOV{cc}")
    linhas.append("    VCVT.S32.F64 s0, d0")
    linhas.append("    VCVT.S32.F64 s2, d1")
    linhas.append("    VMOV r0, s0")
    linhas.append("    VMOV r1, s2")
    linhas.append("    CMP r0, r1")
    linhas.append("    MOV r0, #0")
    linhas.append(f"    MOV{cc} r0, #1")
    # promove o bool a F64 0.0/1.0 para a pilha unificada
    linhas.append("    VMOV s0, r0")
    linhas.append("    VCVT.F64.S32 d0, s0")


def _emit_comparacao(op: str, linhas: list[str], ctx: dict) -> None:
    # VCMP.F64 compara d0 e d1 e atualiza o FPSCR.
    # VMRS transfere as flags do FPSCR para os flags ARM (APSR_nzcv),
    # permitindo usar os desvios condicionais normais (BGT, BLT, etc.).
    # Resultado: d0 recebe 1.0 se verdadeiro, 0.0 se falso.
    linhas.append("    VCMP.F64 d0, d1")
    linhas.append("    VMRS APSR_nzcv, FPSCR")

    rotulo_true = _novo_rotulo(ctx, "cmp_t")
    rotulo_end = _novo_rotulo(ctx, "cmp_e")

    # escolhe o branch condicional correto para cada operador relacional
    if op == ">":
        linhas.append(f"    BGT {rotulo_true}")
    elif op == "<":
        linhas.append(f"    BLT {rotulo_true}")
    elif op == ">=":
        linhas.append(f"    BGE {rotulo_true}")
    elif op == "<=":
        linhas.append(f"    BLE {rotulo_true}")
    elif op == "==":
        linhas.append(f"    BEQ {rotulo_true}")
    elif op == "!=":
        linhas.append(f"    BNE {rotulo_true}")

    # Falso -> carrega 0.0 em d0
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d0, [r0]")
    linhas.append(f"    B {rotulo_end}")
    linhas.append(f"{rotulo_true}:")
    linhas.append("    LDR r0, =const_one")
    linhas.append("    VLDR.F64 d0, [r0]")
    linhas.append(f"{rotulo_end}:")


def _emit_cond_valor(no: dict, linhas: list[str], ctx: dict) -> None:
    """Avalia condição e deixa 1.0/0.0 no topo da pilha."""
    _emit_expressao(no, linhas, ctx)


def _emit_if(no: dict, linhas: list[str], ctx: dict) -> None:
    # (COND BLOCO IF): avalia COND; se 0.0 (falso) pula o bloco inteiro
    rotulo_fim = _novo_rotulo(ctx, "if_fim")
    _emit_cond_valor(no["cond"], linhas, ctx)
    _emit_pop_para_d(linhas, "d0")
    # compara com 0.0 -> se igual, pula o bloco
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d1, [r0]")
    linhas.append("    VCMP.F64 d0, d1")
    linhas.append("    VMRS APSR_nzcv, FPSCR")
    linhas.append(f"    BEQ {rotulo_fim}")
    _emit_expressao(no["then_block"], linhas, ctx)
    # bloco deixou um valor na pilha -> descarta (IF não produz valor útil)
    _emit_pop_para_d(linhas, "d0")
    linhas.append(f"{rotulo_fim}:")
    # IF empilha 0.0 como resultado neutro (padroniza aridade)
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d0, [r0]")
    _emit_push_d0(linhas)


def _emit_ifelse(no: dict, linhas: list[str], ctx: dict) -> None:
    # (COND THEN ELSE IFELSE): dois rótulos — um pro else, outro pro fim.
    # Se COND for falso, desvia pra else_block; senão executa then_block e pula.
    rotulo_else = _novo_rotulo(ctx, "else")
    rotulo_fim = _novo_rotulo(ctx, "ife_fim")
    _emit_cond_valor(no["cond"], linhas, ctx)
    _emit_pop_para_d(linhas, "d0")
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d1, [r0]")
    linhas.append("    VCMP.F64 d0, d1")
    linhas.append("    VMRS APSR_nzcv, FPSCR")
    linhas.append(f"    BEQ {rotulo_else}")
    _emit_expressao(no["then_block"], linhas, ctx)
    linhas.append(f"    B {rotulo_fim}")
    linhas.append(f"{rotulo_else}:")
    _emit_expressao(no["else_block"], linhas, ctx)
    linhas.append(f"{rotulo_fim}:")
    # valor resultante do ramo escolhido já está no topo da pilha


def _emit_while(no: dict, linhas: list[str], ctx: dict) -> None:
    # (COND BLOCO WHILE): rótulo no início do loop e outro na saída.
    # Avalia COND a cada iteração; se falso, desvia para o fim.
    # O resultado do corpo é descartado (while só serve para efeitos colaterais).
    rotulo_ini = _novo_rotulo(ctx, "while_i")
    rotulo_fim = _novo_rotulo(ctx, "while_f")
    linhas.append(f"{rotulo_ini}:")
    _emit_cond_valor(no["cond"], linhas, ctx)
    _emit_pop_para_d(linhas, "d0")
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d1, [r0]")
    linhas.append("    VCMP.F64 d0, d1")
    linhas.append("    VMRS APSR_nzcv, FPSCR")
    linhas.append(f"    BEQ {rotulo_fim}")
    _emit_expressao(no["body"], linhas, ctx)
    _emit_pop_para_d(linhas, "d0")  # descarta valor do corpo
    linhas.append(f"    B {rotulo_ini}")
    linhas.append(f"{rotulo_fim}:")
    linhas.append("    LDR r0, =const_zero")
    linhas.append("    VLDR.F64 d0, [r0]")
    _emit_push_d0(linhas)


# -------------------- Geração do programa final --------------------


def gerar_assembly_de_arvore_atribuida(arvore_atribuida: dict) -> str:
    """Wrapper para Etapa 5: gera Assembly a partir da árvore atribuída.

    Adiciona um cabeçalho documentando os tipos inferidos por statement
    (Etapa 3) e então delega a :func:`gerar_assembly_arvore`. A geração
    real continua sendo a mesma função — mas como os nós já vêm com
    ``tipo_inferido`` anotado, o dispatch tipado em ``_emit_binario``
    (instruções ARM inteiras x VFP) entra em ação automaticamente.

    Esta é a função que o ``AnalisadorSemantico.py`` deve chamar quando
    NÃO houver erros léxicos/sintáticos/semânticos. A política de
    "não gera Assembly quando há erro" é responsabilidade do orquestrador
    (não desta função): aqui assumimos uma árvore válida e atribuída.
    """
    if not arvore_atribuida or arvore_atribuida.get("tipo") != "program":
        raise ValueError("gerar_assembly_de_arvore_atribuida: AST inválida")

    cabecalho: list[str] = ["@ ====================================================="]
    cabecalho.append("@  Assembly gerado a partir da ÁRVORE SINTÁTICA ATRIBUÍDA")
    cabecalho.append("@  (Fase 3 — Etapa 5)")
    cabecalho.append("@  Tipos inferidos por statement de topo:")
    for i, stmt in enumerate(arvore_atribuida.get("stmts", []), 1):
        ti = stmt.get("tipo_inferido", "—")
        cabecalho.append(f"@    stmt #{i}: {ti}")
    cabecalho.append("@ =====================================================")
    cabecalho.append("")

    corpo = gerar_assembly_arvore(arvore_atribuida)
    return "\n".join(cabecalho) + corpo


# Encaminha para a função que opera sobre a árvore atribuída.
def gerarAssembly(arvore_atribuida: dict) -> str:
    return gerar_assembly_de_arvore_atribuida(arvore_atribuida)


def gerar_assembly_arvore(arvore_programa: dict) -> str:
    # Função principal do gerador. Percorre todos os statements da AST,
    # emite o código de cada um e salva o resultado em resultado_N no .data.
    # No final, adiciona as rotinas auxiliares e a seção .data com todas
    # as constantes e variáveis de memória coletadas durante o percurso.
    if arvore_programa.get("tipo") != "program":
        raise ValueError("Raiz da AST deve ser do tipo 'program'")
    stmts = arvore_programa["stmts"]

    # RA4: programas só de hardware (Morse/LED/DELAY) usam o gerador enxuto
    # e verificável (sem VFP/pilha/pool), com timer real e loop infinito.
    if _programa_so_hardware(stmts):
        return _gerar_assembly_hardware(stmts)

    memorias: set[str] = set()
    _coletar_memorias(arvore_programa, memorias)

    ctx = {
        "constantes": {},
        "contador_const": [0],
        "contador_rotulos": 0,
        "indice_linha": 0,
    }

    linhas: list[str] = []
    linhas.append(".syntax unified")
    linhas.append(".cpu cortex-a9")
    linhas.append(".fpu vfpv3")
    linhas.append(".global _start")
    linhas.append("")
    linhas.append(".text")
    linhas.append("_start:")
    # Inicializa o Stack Pointer. É indispensável quando o programa é
    # carregado como Intel HEX cru no CPUlator (nesse modo o simulador NÃO
    # configura o SP automaticamente, ao contrário do "Compile and Load").
    # A pilha mora no próprio .data (__pilha_topo), garantindo endereço
    # válido e carregado junto com o binário.
    linhas.append("    LDR sp, =__pilha_topo")

    # Emite .ltorg a cada LTORG_INTERVAL statements para que as pseudo-instruções
    # LDR rX, =label encontrem o literal pool dentro dos ±4096 bytes obrigatórios.
    # O pool fica em uma "ilha" pulada por um branch incondicional.
    LTORG_INTERVAL = 15
    _IO_TIPOS = {"led_write", "delay_ms", "morse_word"}
    for indice, stmt in enumerate(stmts):
        ctx["indice_linha"] = indice
        linhas.append(f"    @ Expressão {indice + 1}")
        _emit_expressao(stmt, linhas, ctx)
        _emit_pop_para_d(linhas, "d0")
        linhas.append(f"    LDR r0, =resultado_{indice}")
        linhas.append("    VSTR.F64 d0, [r0]")
        # exibe nos displays HEX apenas para statements que produzem valores úteis
        if stmt.get("tipo") not in _IO_TIPOS:
            linhas.append(f"    @ Exibir resultado {indice + 1} nos HEX displays")
            linhas.append("    VCVT.S32.F64 s0, d0")
            linhas.append("    VMOV r0, s0")
            linhas.append("    BL __exibir_hex")
        # Dump literal pool periodicamente para evitar "pool needs to be closer"
        if (indice + 1) % LTORG_INTERVAL == 0 and indice < len(stmts) - 1:
            skip = f"__ltorg_skip_{indice}"
            linhas.append(f"    B {skip}")
            linhas.append("    .ltorg")
            linhas.append("    .balign 4")
            linhas.append(f"{skip}:")

    linhas.append("")
    linhas.append("loop_final:")
    linhas.append("    B loop_final")
    linhas.append("    .ltorg")

    # ---- Rotinas auxiliares ----
    linhas.extend(_rotinas_auxiliares())

    # ---- .data ----
    linhas.append(".data")
    for valor, rotulo in ctx["constantes"].items():
        linhas.append(f"{rotulo}: .double {valor}")
    linhas.append("const_zero: .double 0.0")
    linhas.append("const_one:  .double 1.0")
    for mem in sorted(memorias):
        linhas.append(f"mem_{mem}: .double 0.0")
    for indice in range(len(stmts)):
        linhas.append(f"resultado_{indice}: .double 0.0")
    if not stmts:
        linhas.append("resultado_0: .double 0.0")

    linhas.append("")
    linhas.append("@ Tabela 7-segmentos (0-9) para display HEX")
    linhas.append("__hex_tabela:")
    for byte, digito in zip(
        ("0x3F", "0x06", "0x5B", "0x4F", "0x66", "0x6D", "0x7D", "0x07", "0x7F", "0x6F"),
        range(10),
    ):
        linhas.append(f"    .byte {byte}  @ {digito}")

    # Pilha do programa (1 KB). __pilha_topo fica no fim do bloco porque a
    # pilha ARM cresce para baixo (full-descending). O SP é inicializado
    # com este rótulo no _start.
    linhas.append("")
    linhas.append(".balign 8")
    linhas.append("__pilha_base:")
    linhas.append("    .space 1024")
    linhas.append("__pilha_topo:")
    linhas.append("    .word 0")

    return "\n".join(linhas) + "\n"


def _rotinas_auxiliares() -> list[str]:
    # Rotinas em Assembly puro para operações que não têm instrução nativa:
    #   __op_idiv : divisão inteira (converte double -> int, divide, volta para double)
    #   __op_mod  : resto da divisão inteira (divide e subtraí o quociente * divisor)
    #   __op_pow  : potência com expoente inteiro (laço de multiplicações)
    #   __sdiv32  : divisão de 32 bits por subtrações (Não existe SDIV no Cortex-A9)
    #   __exibir_hex: exibe valor inteiro nos 6 displays HEX do DE1-SoC
    linhas: list[str] = []
    linhas.append("")
    # idiv
    linhas.append("__op_idiv:")
    linhas.append("    PUSH {lr}")
    linhas.append("    VCVT.S32.F64 s0, d0")
    linhas.append("    VCVT.S32.F64 s2, d1")
    linhas.append("    VMOV r0, s0")
    linhas.append("    VMOV r1, s2")
    linhas.append("    BL __sdiv32")
    linhas.append("    VMOV s0, r0")
    linhas.append("    VCVT.F64.S32 d0, s0")
    linhas.append("    POP {lr}")
    linhas.append("    BX lr")
    linhas.append("")
    # mod
    linhas.append("__op_mod:")
    linhas.append("    PUSH {r4, lr}")
    linhas.append("    VCVT.S32.F64 s0, d0")
    linhas.append("    VCVT.S32.F64 s2, d1")
    linhas.append("    VMOV r2, s0")
    linhas.append("    VMOV r3, s2")
    linhas.append("    MOV r0, r2")
    linhas.append("    MOV r1, r3")
    linhas.append("    BL __sdiv32")
    linhas.append("    MUL r4, r0, r3")
    linhas.append("    SUB r2, r2, r4")
    linhas.append("    VMOV s0, r2")
    linhas.append("    VCVT.F64.S32 d0, s0")
    linhas.append("    POP {r4, lr}")
    linhas.append("    BX lr")
    linhas.append("")
    # pow
    linhas.append("__op_pow:")
    linhas.append("    PUSH {lr}")
    linhas.append("    VCVT.S32.F64 s2, d1")
    linhas.append("    VMOV r3, s2")
    linhas.append("    CMP r3, #0")
    linhas.append("    BLE __pow_zero_ou_negativo")
    linhas.append("    VMOV.F64 d2, d0")
    linhas.append("    SUB r3, r3, #1")
    linhas.append("__pow_loop:")
    linhas.append("    CMP r3, #0")
    linhas.append("    BEQ __pow_done")
    linhas.append("    VMUL.F64 d2, d2, d0")
    linhas.append("    SUB r3, r3, #1")
    linhas.append("    B __pow_loop")
    linhas.append("__pow_done:")
    linhas.append("    VMOV.F64 d0, d2")
    linhas.append("    POP {lr}")
    linhas.append("    BX lr")
    linhas.append("__pow_zero_ou_negativo:")
    linhas.append("    LDR r0, =const_one")
    linhas.append("    VLDR.F64 d0, [r0]")
    linhas.append("    POP {lr}")
    linhas.append("    BX lr")
    linhas.append("")
    # sdiv32
    linhas.append("__sdiv32:")
    linhas.append("    PUSH {r2, r3, r4, lr}")
    linhas.append("    CMP r1, #0")
    linhas.append("    BEQ __sdiv32_divzero")
    linhas.append("    MOV r2, #0")
    linhas.append("    CMP r0, #0")
    linhas.append("    RSBMI r0, r0, #0")
    linhas.append("    EORMI r2, r2, #1")
    linhas.append("    CMP r1, #0")
    linhas.append("    RSBMI r1, r1, #0")
    linhas.append("    EORMI r2, r2, #1")
    linhas.append("    MOV r3, #0")
    linhas.append("__sdiv32_loop:")
    linhas.append("    CMP r0, r1")
    linhas.append("    BLT __sdiv32_done")
    linhas.append("    SUB r0, r0, r1")
    linhas.append("    ADD r3, r3, #1")
    linhas.append("    B __sdiv32_loop")
    linhas.append("__sdiv32_done:")
    linhas.append("    CMP r2, #0")
    linhas.append("    RSBNE r3, r3, #0")
    linhas.append("    MOV r0, r3")
    linhas.append("    POP {r2, r3, r4, lr}")
    linhas.append("    BX lr")
    linhas.append("__sdiv32_divzero:")
    linhas.append("    MOV r0, #0")
    linhas.append("    POP {r2, r3, r4, lr}")
    linhas.append("    BX lr")
    linhas.append("")
    # exibir_hex
    linhas.append("__exibir_hex:")
    linhas.append("    PUSH {r1, r2, r3, r4, r5, r6, lr}")
    linhas.append("    LDR r1, =__hex_tabela")
    linhas.append("    LDR r6, =0xFF200020")
    linhas.append("    MOV r5, #0")
    linhas.append("    CMP r0, #0")
    linhas.append("    RSBMI r0, r0, #0")
    linhas.append("    MOVMI r5, #1")
    linhas.append("    MOV r4, #0")
    linhas.append("    MOV r2, #10")
    linhas.append("    BL __udiv_simples")
    linhas.append("    LDRB r3, [r1, r3]")
    linhas.append("    ORR r4, r4, r3")
    linhas.append("    MOV r2, #10")
    linhas.append("    BL __udiv_simples")
    linhas.append("    LDRB r3, [r1, r3]")
    linhas.append("    ORR r4, r4, r3, LSL #8")
    linhas.append("    MOV r2, #10")
    linhas.append("    BL __udiv_simples")
    linhas.append("    LDRB r3, [r1, r3]")
    linhas.append("    ORR r4, r4, r3, LSL #16")
    linhas.append("    CMP r5, #1")
    linhas.append("    MOVEQ r3, #0x40")
    linhas.append("    BEQ __exibir_hex_store")
    linhas.append("    MOV r2, #10")
    linhas.append("    BL __udiv_simples")
    linhas.append("    LDRB r3, [r1, r3]")
    linhas.append("    ORR r4, r4, r3, LSL #24")
    linhas.append("    B __exibir_hex_fim")
    linhas.append("__exibir_hex_store:")
    linhas.append("    ORR r4, r4, r3, LSL #24")
    linhas.append("__exibir_hex_fim:")
    linhas.append("    STR r4, [r6]")
    linhas.append("    POP {r1, r2, r3, r4, r5, r6, lr}")
    linhas.append("    BX lr")
    linhas.append("")
    # udiv_simples
    linhas.append("__udiv_simples:")
    linhas.append("    MOV r3, #0")
    linhas.append("__udiv_simples_loop:")
    linhas.append("    CMP r0, r2")
    linhas.append("    BLT __udiv_simples_done")
    linhas.append("    SUB r0, r0, r2")
    linhas.append("    ADD r3, r3, #1")
    linhas.append("    B __udiv_simples_loop")
    linhas.append("__udiv_simples_done:")
    linhas.append("    MOV r12, r0")
    linhas.append("    MOV r0, r3")
    linhas.append("    MOV r3, r12")
    linhas.append("    BX lr")
    linhas.append("")
    # delay_ms: r0 = milissegundos; loop de espera (~50000 iterações/ms a 200 MHz)
    linhas.append("__delay_ms:")
    linhas.append("    PUSH {r1, r2, lr}")
    linhas.append("    LDR r1, =50000")
    linhas.append("    MUL r2, r0, r1")
    linhas.append("__delay_ms_loop:")
    linhas.append("    SUBS r2, r2, #1")
    linhas.append("    BNE __delay_ms_loop")
    linhas.append("    POP {r1, r2, lr}")
    linhas.append("    BX lr")
    linhas.append("")
    return linhas


# Compatibilidade: assinatura usada internamente pelo pipeline da Fase 2
gerarAssembly = gerar_assembly_arvore
