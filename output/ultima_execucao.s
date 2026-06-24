@ =====================================================
@  Assembly gerado a partir da ÁRVORE SINTÁTICA ATRIBUÍDA
@  (Fase 3 — Etapa 5)
@  Tipos inferidos por statement de topo:
@    stmt #1: indef
@ =====================================================
@ =====================================================
@  RA4 — Código Morse nos LEDs do DE1-SoC (ARMv7)
@  LED0 (0xFF200000) + interval timer (0xFF202000)
@  Loop infinito. Tempos: ponto=300 traço=600
@  intra-letra=450 entre-letras=900 entre-palavras=2000 (ms)
@ =====================================================
.global _start
.text
_start:
loop_principal:
    @ ============ MORSE: EMANUEL ============
    @ letra 'E' = .
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_1:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_1           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 900 ms (x1) -> N = 90000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x4A80
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x055D
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_2:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_2           @ não: continua esperando
    @ letra 'M' = --
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 600 ms (x1) -> N = 60000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x8700
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0393
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_3:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_3           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_4:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_4           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 600 ms (x1) -> N = 60000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x8700
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0393
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_5:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_5           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 900 ms (x1) -> N = 90000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x4A80
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x055D
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_6:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_6           @ não: continua esperando
    @ letra 'A' = .-
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_7:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_7           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_8:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_8           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 600 ms (x1) -> N = 60000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x8700
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0393
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_9:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_9           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 900 ms (x1) -> N = 90000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x4A80
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x055D
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_10:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_10           @ não: continua esperando
    @ letra 'N' = -.
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 600 ms (x1) -> N = 60000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x8700
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0393
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_11:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_11           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_12:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_12           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_13:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_13           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 900 ms (x1) -> N = 90000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x4A80
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x055D
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_14:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_14           @ não: continua esperando
    @ letra 'U' = ..-
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_15:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_15           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_16:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_16           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_17:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_17           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_18:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_18           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 600 ms (x1) -> N = 60000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x8700
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0393
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_19:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_19           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 900 ms (x1) -> N = 90000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x4A80
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x055D
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_20:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_20           @ não: continua esperando
    @ letra 'E' = .
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_21:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_21           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 900 ms (x1) -> N = 90000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x4A80
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x055D
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_22:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_22           @ não: continua esperando
    @ letra 'L' = .-..
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_23:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_23           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_24:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_24           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 600 ms (x1) -> N = 60000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0x8700
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0393
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_25:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_25           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_26:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_26           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_27:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_27           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 450 ms (x1) -> N = 45000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xA540
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x02AE
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_28:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_28           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #1
    STR r0, [r1]
    @ ---- delay 300 ms (x1) -> N = 30000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC380
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x01C9
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_29:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_29           @ não: continua esperando
    MOVW r1, #0x0000
    MOVT r1, #0xFF20
    MOV r0, #0
    STR r0, [r1]
    @ ---- delay 2000 ms (x1) -> N = 200000000 ciclos @ 100 MHz ----
    MOVW r1, #0x2000
    MOVT r1, #0xFF20
    MOV r0, #0x8
    STR r0, [r1, #4]      @ control = STOP
    MOVW r0, #0xC200
    STR r0, [r1, #8]      @ periodl
    MOVW r0, #0x0BEB
    STR r0, [r1, #12]     @ periodh
    MOV r0, #0
    STR r0, [r1, #0]      @ limpa flag TO
    MOV r0, #0x4
    STR r0, [r1, #4]      @ control = START (one-shot)
__espera_30:
    LDR r0, [r1, #0]      @ lê status
    TST r0, #1            @ bit TO setou?
    BEQ __espera_30           @ não: continua esperando
    B loop_principal      @ repete o nome para sempre
