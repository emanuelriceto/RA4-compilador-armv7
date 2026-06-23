# Gramática Atribuída — Fase 3 (RA3 9)

> EBNF da Fase 2 enriquecida com **ações semânticas** que descrevem
> como cada produção contribui para (a) a Tabela de Símbolos e (b) a
> Árvore Sintática Atribuída.
>
> Notação:
> - `{ ... }` = ação semântica (Python pseudocode), executada **após**
>   o casamento da produção correspondente.
> - `$$` = atributo sintetizado do não-terminal à esquerda.
> - `$n` = atributo sintetizado do n-ésimo símbolo do RHS.
> - `Γ` = tabela de símbolos global (instância única de
>   `TabelaSimbolos`).
> - `linha(t)` = atributo "linha" do token `t` (preservado pelo lexer
>   mesmo quando há comentários).

A gramática **livre de contexto** original está em
[gramatica.md](gramatica.md). Aqui anotamos apenas o necessário para a
fase semântica.

---

## Símbolos terminais relevantes

| Terminal | Lexema(s) | Tipo léxico |
|---|---|---|
| `INT` | `123`, `0`, `42` | `INT` |
| `REAL` | `3.14`, `0.0`, `1.5` | `REAL` |
| `IDENT` | `X`, `MEM1`, `RESULT` | `IDENT` |
| `OP` | `+ - * | / % ^ > < >= <= == !=` | `OP` |
| `START`, `END`, `RES`, `IF`, `IFELSE`, `WHILE` | palavras-chave | `IDENT` |

Comentários `*{ ... }*` são removidos antes do parser pelo lexer
(`_strip_comentarios` em `src/lexer_fsm.py`) — não aparecem aqui.

---

## Produções com ações

### Programa

```
programa → '(' 'START' ')' body
        { $$.tipo_no = 'programa'
          $$.corpo   = $4
          $$.linha   = 1 }
```

### Corpo (sequência de statements)

```
body → stmt body
     { $$ = $1 :: $2 }
     | '(' 'END' ')'
     { $$ = [] }
```

Cada elemento de `body` é registrado em ordem para que o
comando `(N RES)` possa indexá-los para trás.

### Statement

```
stmt → EXPR
     { $$.linha = linha(primeiro_tok)
       /* o índice posicional alimenta T-Res */ }
```

### Expressão atômica

```
expr → INT      { $$.tipo_no='literal'; $$.tipo_inferido='int';
                  $$.valor=int($1) }
     | REAL     { $$.tipo_no='literal'; $$.tipo_inferido='real';
                  $$.valor=float($1) }
     | '(' IDENT ')'
                { /* mem_read */
                  s = Γ.obter($2)
                  if s is None:
                      erro('uso da variável %s antes da declaração' % $2)
                      $$.tipo_inferido = 'indef'
                  else:
                      Γ.usar($2, linha($2))
                      $$.tipo_inferido = s.tipo
                      $$.simbolo_ref   = s
                  $$.tipo_no = 'mem_read'
                  $$.nome    = $2 }
```

### Expressão composta

A forma geral é `'(' OPND OPND OP ')'` (binária) ou
`'(' expr IDENT_KW ')'` (memória / controle). Em pseudo-EBNF:

```
expr → '(' expr expr OP ')'
     { /* T-Arith / T-Rel / T-IntDiv / T-RealDiv */
       τ1, τ2 = $2.tipo_inferido, $3.tipo_inferido
       op     = $4
       $$.tipo_no       = 'binary' if op ∉ relacional else 'relop'
       $$.op            = op
       $$.esq, $$.dir   = $2, $3
       $$.linha         = linha($1)
       $$.tipo_inferido = inferir_tipo_binario(op, τ1, τ2)
       /* registra erro se inferir_tipo_binario devolver 'indef' */ }

     | '(' expr IDENT ')'             /* mem_write: (v MEM) */
     { Γ.declarar($3, $2.tipo_inferido, linha($3))
       $$.tipo_no       = 'mem_write'
       $$.nome          = $3
       $$.expr          = $2
       $$.tipo_inferido = $2.tipo_inferido
       $$.simbolo_ref   = Γ.obter($3) }

     | '(' INT 'RES' ')'              /* T-Res */
     { n = int($2)
       if n > len(stmts_anteriores):
           erro('(n res) fora de faixa')
           $$.tipo_inferido = 'indef'
       else:
           $$.tipo_inferido = stmts_anteriores[-n].tipo_inferido
       $$.tipo_no = 'res'
       $$.n       = n }

     | '(' expr expr 'IF' ')'         /* T-If */
     { if $2.tipo_inferido != 'bool':
           erro("condição do if deve ser 'bool'")
       $$.tipo_no       = 'if'
       $$.cond, $$.then = $2, $3
       $$.tipo_inferido = $3.tipo_inferido }

     | '(' expr expr expr 'IFELSE' ')' /* T-IfElse */
     { if $2.tipo_inferido != 'bool':
           erro("condição do ifelse deve ser 'bool'")
       if $3.tipo_inferido != $4.tipo_inferido:
           erro('ramos do ifelse têm tipos divergentes')
       $$.tipo_no                = 'ifelse'
       $$.cond, $$.then, $$.else = $2, $3, $4
       $$.tipo_inferido          = $3.tipo_inferido }

     | '(' expr expr 'WHILE' ')'      /* T-While */
     { if $2.tipo_inferido != 'bool':
           erro("condição do while deve ser 'bool'")
       $$.tipo_no       = 'while'
       $$.cond, $$.body = $2, $3
       $$.tipo_inferido = 'unit' }
```

---

## Função auxiliar `inferir_tipo_binario`

```python
def inferir_tipo_binario(op, t1, t2):
    if op in {'>', '<', '==', '!=', '>=', '<='}:
        if t1 == t2 and t1 in {'int', 'real'}:
            return 'bool'
        return 'indef'
    if op in {'/', '%'}:
        return 'int' if (t1 == 'int' == t2) else 'indef'
    if op == '|':
        return 'real' if (t1 == 'real' == t2) else 'indef'
    if op in {'+', '-', '*', '^'}:
        if t1 == t2 and t1 in {'int', 'real'}:
            return t1
        return 'indef'
    return 'indef'
```

---

## Metadados adicionados pela "atribuição"

`gerarArvoreAtribuida(arvore, tabela)` enriquece cada nó com:

| Campo | Quando | Conteúdo |
|---|---|---|
| `tipo_inferido` | todo nó | `int` / `real` / `bool` / `unit` / `indef` |
| `simbolo_ref` | `mem_read`, `mem_write` | dicionário do símbolo na tabela |
| `meta_asm.registrador` | nós que produzem valor | `D0` (real / unificação) |
| `meta_asm.modo_int` | binários `+ - *` e relacionais | `True` se ambos operandos são `int` puro |
| `meta_asm.label` | `if`, `ifelse`, `while` | label único `__lblN` para o salto |

O resultado é serializado em
[output/arvore_atribuida.md](output/arvore_atribuida.md) e
[output/arvore_atribuida.json](output/arvore_atribuida.json).

Veja [regras_tipos.md](regras_tipos.md) para a base formal das regras
listadas acima.
