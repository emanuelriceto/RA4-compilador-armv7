# Gramática LL(1)

## 1. Regras de Produção

| # | Não-Terminal | Produção |
|---|---|---|
| 0 | PROGRAM | ( start ) BODY |
| 1 | BODY | ( BODY_TAIL |
| 2 | BODY_TAIL | end ) |
| 3 | BODY_TAIL | EXPR_BODY ) BODY |
| 4 | EXPR_BODY | ITEM REST1 |
| 5 | REST1 | ε |
| 6 | REST1 | ITEM REST2 |
| 7 | REST2 | ε |
| 8 | REST2 | BINOP |
| 9 | REST2 | KW_CTRL3 |
| 10 | REST2 | ITEM ITEM_TAIL |
| 11 | ITEM_TAIL | KW_CTRL4 |
| 12 | ITEM | numero |
| 13 | ITEM | ident |
| 14 | ITEM | res |
| 15 | ITEM | morse_kw |
| 16 | ITEM | ( EXPR_BODY ) |
| 17 | BINOP | + |
| 18 | BINOP | - |
| 19 | BINOP | * |
| 20 | BINOP | / |
| 21 | BINOP | | |
| 22 | BINOP | % |
| 23 | BINOP | ^ |
| 24 | BINOP | > |
| 25 | BINOP | < |
| 26 | BINOP | == |
| 27 | BINOP | != |
| 28 | BINOP | >= |
| 29 | BINOP | <= |
| 30 | KW_CTRL3 | if |
| 31 | KW_CTRL3 | while |
| 32 | KW_CTRL4 | ifelse |
| 33 | REST1 | led |
| 34 | REST1 | delay_kw |

## 2. Conjuntos FIRST

| Não-Terminal | FIRST |
|---|---|
| BINOP | { !=, %, *, +, -, /, <, <=, ==, >, >=, ^, | } |
| BODY | { ( } |
| BODY_TAIL | { (, end, ident, morse_kw, numero, res } |
| EXPR_BODY | { (, ident, morse_kw, numero, res } |
| ITEM | { (, ident, morse_kw, numero, res } |
| ITEM_TAIL | { ifelse } |
| KW_CTRL3 | { if, while } |
| KW_CTRL4 | { ifelse } |
| PROGRAM | { ( } |
| REST1 | { (, delay_kw, ident, led, morse_kw, numero, res, ε } |
| REST2 | { !=, %, (, *, +, -, /, <, <=, ==, >, >=, ^, ident, if, morse_kw, numero, res, while, |, ε } |

## 3. Conjuntos FOLLOW

| Não-Terminal | FOLLOW |
|---|---|
| BINOP | { ) } |
| BODY | { $ } |
| BODY_TAIL | { $ } |
| EXPR_BODY | { ) } |
| ITEM | { !=, %, (, ), *, +, -, /, <, <=, ==, >, >=, ^, delay_kw, ident, if, ifelse, led, morse_kw, numero, res, while, | } |
| ITEM_TAIL | { ) } |
| KW_CTRL3 | { ) } |
| KW_CTRL4 | { ) } |
| PROGRAM | { $ } |
| REST1 | { ) } |
| REST2 | { ) } |

## 4. Tabela de Análise LL(1)

| Não-Terminal | Terminal | Produção |
|---|---|---|
| BINOP | != | #27: BINOP → != |
| BINOP | % | #22: BINOP → % |
| BINOP | * | #19: BINOP → * |
| BINOP | + | #17: BINOP → + |
| BINOP | - | #18: BINOP → - |
| BINOP | / | #20: BINOP → / |
| BINOP | < | #25: BINOP → < |
| BINOP | <= | #29: BINOP → <= |
| BINOP | == | #26: BINOP → == |
| BINOP | > | #24: BINOP → > |
| BINOP | >= | #28: BINOP → >= |
| BINOP | ^ | #23: BINOP → ^ |
| BINOP | | | #21: BINOP → | |
| BODY | ( | #1: BODY → ( BODY_TAIL |
| BODY_TAIL | ( | #3: BODY_TAIL → EXPR_BODY ) BODY |
| BODY_TAIL | end | #2: BODY_TAIL → end ) |
| BODY_TAIL | ident | #3: BODY_TAIL → EXPR_BODY ) BODY |
| BODY_TAIL | morse_kw | #3: BODY_TAIL → EXPR_BODY ) BODY |
| BODY_TAIL | numero | #3: BODY_TAIL → EXPR_BODY ) BODY |
| BODY_TAIL | res | #3: BODY_TAIL → EXPR_BODY ) BODY |
| EXPR_BODY | ( | #4: EXPR_BODY → ITEM REST1 |
| EXPR_BODY | ident | #4: EXPR_BODY → ITEM REST1 |
| EXPR_BODY | morse_kw | #4: EXPR_BODY → ITEM REST1 |
| EXPR_BODY | numero | #4: EXPR_BODY → ITEM REST1 |
| EXPR_BODY | res | #4: EXPR_BODY → ITEM REST1 |
| ITEM | ( | #16: ITEM → ( EXPR_BODY ) |
| ITEM | ident | #13: ITEM → ident |
| ITEM | morse_kw | #15: ITEM → morse_kw |
| ITEM | numero | #12: ITEM → numero |
| ITEM | res | #14: ITEM → res |
| ITEM_TAIL | ifelse | #11: ITEM_TAIL → KW_CTRL4 |
| KW_CTRL3 | if | #30: KW_CTRL3 → if |
| KW_CTRL3 | while | #31: KW_CTRL3 → while |
| KW_CTRL4 | ifelse | #32: KW_CTRL4 → ifelse |
| PROGRAM | ( | #0: PROGRAM → ( start ) BODY |
| REST1 | ( | #6: REST1 → ITEM REST2 |
| REST1 | ) | #5: REST1 → ε |
| REST1 | delay_kw | #34: REST1 → delay_kw |
| REST1 | ident | #6: REST1 → ITEM REST2 |
| REST1 | led | #33: REST1 → led |
| REST1 | morse_kw | #6: REST1 → ITEM REST2 |
| REST1 | numero | #6: REST1 → ITEM REST2 |
| REST1 | res | #6: REST1 → ITEM REST2 |
| REST2 | != | #8: REST2 → BINOP |
| REST2 | % | #8: REST2 → BINOP |
| REST2 | ( | #10: REST2 → ITEM ITEM_TAIL |
| REST2 | ) | #7: REST2 → ε |
| REST2 | * | #8: REST2 → BINOP |
| REST2 | + | #8: REST2 → BINOP |
| REST2 | - | #8: REST2 → BINOP |
| REST2 | / | #8: REST2 → BINOP |
| REST2 | < | #8: REST2 → BINOP |
| REST2 | <= | #8: REST2 → BINOP |
| REST2 | == | #8: REST2 → BINOP |
| REST2 | > | #8: REST2 → BINOP |
| REST2 | >= | #8: REST2 → BINOP |
| REST2 | ^ | #8: REST2 → BINOP |
| REST2 | ident | #10: REST2 → ITEM ITEM_TAIL |
| REST2 | if | #9: REST2 → KW_CTRL3 |
| REST2 | morse_kw | #10: REST2 → ITEM ITEM_TAIL |
| REST2 | numero | #10: REST2 → ITEM ITEM_TAIL |
| REST2 | res | #10: REST2 → ITEM ITEM_TAIL |
| REST2 | while | #9: REST2 → KW_CTRL3 |
| REST2 | | | #8: REST2 → BINOP |

