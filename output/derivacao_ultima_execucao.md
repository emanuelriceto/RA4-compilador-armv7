# Derivação LL(1) — Passo a Passo

| Passo | Pilha (topo →) | Entrada (→) | Ação |
|------:|---|---|---|
| 1 | `PROGRAM $` | `( START ) ( EMANUEL MORSE ) ( END )` | Expande: `PROGRAM` → `( start ) BODY` |
| 2 | `( start ) BODY $` | `( START ) ( EMANUEL MORSE ) ( END )` | Casa: `(` |
| 3 | `start ) BODY $` | `START ) ( EMANUEL MORSE ) ( END )` | Casa: `start` |
| 4 | `) BODY $` | `) ( EMANUEL MORSE ) ( END )` | Casa: `)` |
| 5 | `BODY $` | `( EMANUEL MORSE ) ( END )` | Expande: `BODY` → `( BODY_TAIL` |
| 6 | `( BODY_TAIL $` | `( EMANUEL MORSE ) ( END )` | Casa: `(` |
| 7 | `BODY_TAIL $` | `EMANUEL MORSE ) ( END )` | Expande: `BODY_TAIL` → `EXPR_BODY ) BODY` |
| 8 | `EXPR_BODY ) BODY $` | `EMANUEL MORSE ) ( END )` | Expande: `EXPR_BODY` → `ITEM REST1` |
| 9 | `ITEM REST1 ) BODY $` | `EMANUEL MORSE ) ( END )` | Expande: `ITEM` → `ident` |
| 10 | `ident REST1 ) BODY $` | `EMANUEL MORSE ) ( END )` | Casa: `ident` |
| 11 | `REST1 ) BODY $` | `MORSE ) ( END )` | Expande: `REST1` → `ITEM REST2` |
| 12 | `ITEM REST2 ) BODY $` | `MORSE ) ( END )` | Expande: `ITEM` → `morse_kw` |
| 13 | `morse_kw REST2 ) BODY $` | `MORSE ) ( END )` | Casa: `morse_kw` |
| 14 | `REST2 ) BODY $` | `) ( END )` | Expande: `REST2` → `ε` |
| 15 | `) BODY $` | `) ( END )` | Casa: `)` |
| 16 | `BODY $` | `( END )` | Expande: `BODY` → `( BODY_TAIL` |
| 17 | `( BODY_TAIL $` | `( END )` | Casa: `(` |
| 18 | `BODY_TAIL $` | `END )` | Expande: `BODY_TAIL` → `end )` |
| 19 | `end ) $` | `END )` | Casa: `end` |
| 20 | `) $` | `)` | Casa: `)` |
| 21 | `$` | `$` | Casa: `$` |
