# Gramática LL(1), FIRST/FOLLOW e Tabela de Análise

> Documento escrito para a **Fase 2** do projeto da disciplina de
> **Linguagens Formais e Compiladores** — PUCPR (Prof. Frank Coelho de
> Alcantara). Grupo **RA3 9**.
>
> O dump dinâmico (atualizado a cada execução) com todos os conjuntos
> e a tabela completa é gerado automaticamente em `output/gramatica_dump.md`.

---

## 0. Algoritmo de Construção da Tabela de Análise LL(1)

A tabela de análise `M[A, a]` é construída a partir dos conjuntos
**FIRST** e **FOLLOW** seguindo o algoritmo do livro-texto:

**Para cada regra de produção A → α:**

| Passo | Condição | Ação |
|:---:|---|---|
| 1 | Para cada terminal **a** ∈ **FIRST(α)** | Adicione **A → α** em `M[A, a]` |
| 2 | Se **ε** ∈ **FIRST(α)** | Para cada terminal **b** ∈ **FOLLOW(A)**: adicione **A → α** em `M[A, b]` |
| 2a | Se **ε** ∈ **FIRST(α)** e **$** ∈ **FOLLOW(A)** | Adicione **A → α** em `M[A, $]` |
| 3 | Célula vazia | Erro sintático |
| 4 | Célula com **duas produções** distintas | Conflito LL(1) — gramática **não** é LL(1) |

> **Importante:** ε nunca entra como chave na tabela; é apenas o sinalizador
> de "propagar para FOLLOW".

### Como o algoritmo se relaciona com FIRST e FOLLOW

```
FIRST(α) tells the parser: "which terminals can START a string derived from α?"
FOLLOW(A) tells the parser: "which terminals can FOLLOW A in any sentential form?"

When FIRST(α) contains ε, A can "disappear", so whatever comes after A
(i.e. FOLLOW(A)) also guides the choice of A → α.
```

O código Python que implementa este algoritmo está em
`src/parser_ll1.py` → função `_construir_tabela_ll1()`.

---

## 1. Regras de Produção (EBNF)

Convenção (conforme ISO/IEC 14977 e o enunciado da Fase 2):

* **MAIÚSCULAS** = não-terminais (ex.: `PROGRAM`, `EXPR_BODY`).
* **minúsculas** = terminais — categorias léxicas (`numero`, `ident`).
* **Literais entre aspas** (`"("`, `"+"`, `"IF"`, `"START"`) = terminais
  que representam o lexema exato produzido pela Fase 1.
* `=` define uma regra, `;` encerra a regra,
  `[ ... ]` opcional (0 ou 1), `{ ... }` repetição (0 ou mais),
  `( ... )` agrupamento, `|` alternativa.
* `ε` é a cadeia vazia (implícita em `[ ]` e `{ }`); `$` é o marcador de
  fim de entrada usado pela tabela LL(1).

### 1.1. Forma EBNF (com `[ ]` / `{ }` — leitura humana)

#### Como ler EBNF (símbolos da meta-linguagem)

| Símbolo | Significado |
|:---:|---|
| `=` | "é definido como" — abre a regra |
| `,` | **e depois** (concatenação / sequência). **Não é "ou".** |
| `\|` | **ou** (alternativa) |
| `{ X }` | **zero ou mais** ocorrências de `X` (repetição) |
| `[ X ]` | **opcional** — zero ou uma ocorrência de `X` |
| `( ... )` | agrupamento |
| `"texto"` | terminal literal exato |
| `;` | fim da regra |

> **Atenção:** em EBNF a vírgula significa **concatenação**, não escolha.
> `A , B` = "primeiro A, depois B"; `A | B` = "A ou B".

#### A gramática

```ebnf
PROGRAM   = "(" start ")" , { "(" EXPR_BODY ")" } , "(" end ")" ;

EXPR_BODY = ITEM
          | ITEM , ITEM , [ TAIL ] ;

TAIL      = BINOP
          | KW_CTRL3
          | ITEM , KW_CTRL4 ;

ITEM      = numero
          | ident
          | res
          | "(" , EXPR_BODY , ")" ;

BINOP     = "+" | "-" | "*" | "/" | "|" | "%" | "^"
          | ">" | "<" | "==" | "!=" | ">=" | "<=" ;

KW_CTRL3  = if | while ;
KW_CTRL4  = ifelse ;
```

#### Lendo cada regra em português

- **`PROGRAM`** — *uma* sequência fixa: `(start)` no início, depois
  **zero ou mais** blocos `(EXPR_BODY)`, depois `(end)` no fim.
  Não é uma escolha entre alternativas — é a estrutura única e
  obrigatória de qualquer programa válido.
- **`EXPR_BODY`** — o conteúdo de um statement, *sem* os parênteses
  externos. Pode ser **1 item** isolado (forma `(MEM)`) ou **2 itens
  obrigatórios** seguidos de uma `TAIL` opcional.
- **`TAIL`** — o "verbo" de uma expressão pós-fixada: um operador
  binário, uma keyword de 2 operandos (`if`/`while`) ou um terceiro
  item seguido de `ifelse` (4 itens no total).
- **`ITEM`** — um operando: número, identificador de memória, a
  palavra-chave `res`, ou uma sub-expressão completa entre parênteses
  (recursão que permite aninhamento arbitrário).
- **`BINOP`, `KW_CTRL3`, `KW_CTRL4`** — apenas listas de tokens
  terminais; servem para agrupar e dar nome.

#### Exemplo: derivando `(START) (10 3 +) (END)`

```
PROGRAM
  = "(" start ")"  ,  { "(" EXPR_BODY ")" }  ,  "(" end ")"
                       └─ uma iteração ─┘
                       └ EXPR_BODY = 10 , 3 , (TAIL = BINOP = "+")
```

A repetição `{ ... }` deu **uma** volta (um único statement no meio);
poderia ter dado zero (`(START)(END)`) ou várias.

> **Nota sobre caixa.** Em conformidade com a convenção EBNF
> (ISO/IEC 14977), os terminais aparecem em **minúsculas** (`start`,
> `end`, `if`, `while`, `ifelse`, `res`, `numero`, `ident`) ou como
> literais entre aspas. No código-fonte do programa parseado, esses
> mesmos lexemas são escritos em **MAIÚSCULAS** (`(START)`, `(IF …)`).
> A função `_token_para_terminal()` em `src/parser_ll1.py` faz a
> tradução `lexema MAIÚSCULO → terminal minúsculo` que alimenta a
> tabela LL(1).

> **Notas léxicas** (definidas pela Fase 1, `src/lexer_fsm.py`):
> `numero` = inteiro ou decimal sem sinal; `ident` = sequência de
> letras maiúsculas `[A-Z]+`. As palavras reservadas `START`, `END`,
> `RES`, `IF`, `WHILE`, `IFELSE` são tokens literais distintos de `ident`.

> **Por que ainda precisamos da BNF da § 1.2.** EBNF é ótima para
> humanos mas a tabela LL(1) só sabe consultar regras no formato
> `A → α` (sem `{ }` ou `[ ]`). Cada `{ ... }` e `[ ... }` precisa ser
> traduzido para um novo não-terminal recursivo/anulável. Por exemplo,
> a repetição `{ "(" EXPR_BODY ")" } "(" end ")"` vira `BODY → "(" BODY_TAIL`
> com `BODY_TAIL` decidindo a cada iteração entre "acabou" (`end ")"`)
> e "vem mais um statement" (`EXPR_BODY ")" BODY`). Mesma informação,
> formato diferente.

### 1.2. Forma BNF fatorada (numerada — base da tabela LL(1))

A EBNF acima é traduzida internamente para a BNF abaixo, onde cada
construção `[ ]` / `{ }` vira um não-terminal anulável (`REST1`, `REST2`,
`ITEM_TAIL`, `BODY`, `BODY_TAIL`). É **esta** numeração (`#0..#31`) que
aparece como índice de produção na tabela `M[A, a]` da seção 4 e no
arquivo `output/derivacao_ultima_execucao.md`.

```
(#0)  PROGRAM   = "(" , "START" , ")" , BODY ;
(#1)  BODY      = "(" , BODY_TAIL ;
(#2)  BODY_TAIL = "END" , ")" ;
(#3)            | EXPR_BODY , ")" , BODY ;
(#4)  EXPR_BODY = ITEM , REST1 ;
(#5)  REST1     = ε ;
(#6)            | ITEM , REST2 ;
(#7)  REST2     = ε ;
(#8)            | BINOP ;
(#9)            | KW_CTRL3 ;
(#10)           | ITEM , ITEM_TAIL ;
(#11) ITEM_TAIL = KW_CTRL4 ;
(#12) ITEM      = numero ;
(#13)           | ident ;
(#14)           | "RES" ;
(#15)           | "(" , EXPR_BODY , ")" ;
(#16) BINOP     = "+" ;
(#17)           | "-" ;
(#18)           | "*" ;
(#19)           | "/" ;       (* divisão inteira *)
(#20)           | "|" ;       (* divisão real    *)
(#21)           | "%" ;
(#22)           | "^" ;
(#23)           | ">" ;
(#24)           | "<" ;
(#25)           | "==" ;
(#26)           | "!=" ;
(#27)           | ">=" ;
(#28)           | "<=" ;
(#29) KW_CTRL3  = "IF" ;
(#30)           | "WHILE" ;
(#31) KW_CTRL4  = "IFELSE" ;
```

### 1.3. Mapeamento literal → símbolo interno

A implementação em `src/parser_ll1.py` e o dump automático em
`output/gramatica_dump.md` usam **nomes simbólicos** para os terminais
estruturais (em vez do lexema literal), pois é mais legível em código
e evita ambiguidade no relatório. A correspondência é:

| Literal (EBNF) | Símbolo interno | Significado |
|---|---|---|
| `"("`     | `LPAREN`  | abre parêntese |
| `")"`     | `RPAREN`  | fecha parêntese |
| `numero`  | `NUMERO`  | número (categoria léxica) |
| `ident`   | `IDENT`   | identificador (categoria léxica) |
| `"START"` | `START`   | palavra reservada |
| `"END"`   | `END`     | palavra reservada |
| `"RES"`   | `RES`     | palavra reservada |
| `"IF"`    | `IF`      | palavra reservada |
| `"WHILE"` | `WHILE`   | palavra reservada |
| `"IFELSE"`| `IFELSE`  | palavra reservada |
| `+ - * / \| % ^ > < == != >= <=` | o próprio lexema | operadores binários |

> **Convenção das próximas seções (FIRST, FOLLOW e Tabela LL(1)):** os
> não-terminais aparecem em **MAIÚSCULAS** (`PROGRAM`, `BODY`, …) como
> exige a Fase 2. Os terminais aparecem com seus **símbolos internos**
> (`LPAREN`, `NUMERO`, `IDENT`, `IF`, …) — equivalentes 1-para-1 aos
> literais EBNF (`"("`, `numero`, `ident`, `"IF"`, …) listados na
> tabela acima — para casar exatamente com o dump auto-gerado em
> `output/gramatica_dump.md`. Operadores são exibidos pelo próprio
> lexema (`+`, `-`, `==`, …).

### Observações sobre o desenho da gramática

1. **Fatoração à esquerda em `BODY`.** Sem ela, a forma EBNF
   `PROGRAM → "(" start ")" { "(" EXPR_BODY ")" } "(" end ")"`,
   ao ser traduzida diretamente em BNF, geraria duas alternativas
   começando com `"("` (uma para mais um statement, outra para
   `"(" end ")"`). Isso causaria conflito LL(1). Consumimos o `"("`
   antes (em `BODY → "(" BODY_TAIL`) e só então decidimos pelo
   terminal de *lookahead* (`end` vs. início de `EXPR_BODY`).
2. **`REST1` / `REST2` / `ITEM_TAIL` são anuláveis somente quando
   necessário.** Isso garante que, no pior caso, a decisão use apenas
   um símbolo de *lookahead*.
3. **Comandos especiais** (`(V MEM)`, `(MEM)`, `(N RES)`) e
   **estruturas de controle** (`(COND BODY IF)`, `(COND BODY WHILE)`,
   `(COND THEN ELSE IFELSE)`) compartilham as mesmas regras estruturais —
   a distinção é feita semanticamente ao construir a árvore.

---

## 2. Conjuntos FIRST

```
FIRST(PROGRAM)   = { LPAREN }
FIRST(BODY)      = { LPAREN }
FIRST(BODY_TAIL) = { END, IDENT, LPAREN, NUMERO, RES }
FIRST(EXPR_BODY) = { IDENT, LPAREN, NUMERO, RES }
FIRST(REST1)     = { IDENT, LPAREN, NUMERO, RES, ε }
FIRST(REST2)     = { !=, %, *, +, -, /, <, <=, ==, >, >=,
                     IDENT, IF, LPAREN, NUMERO, RES, WHILE, ^, |, ε }
FIRST(ITEM_TAIL) = { IFELSE }
FIRST(ITEM)      = { IDENT, LPAREN, NUMERO, RES }
FIRST(BINOP)     = { !=, %, *, +, -, /, <, <=, ==, >, >=, ^, | }
FIRST(KW_CTRL3)  = { IF, WHILE }
FIRST(KW_CTRL4)  = { IFELSE }
```

## 3. Conjuntos FOLLOW

```
FOLLOW(PROGRAM)   = { $ }
FOLLOW(BODY)      = { $ }
FOLLOW(BODY_TAIL) = { $ }
FOLLOW(EXPR_BODY) = { RPAREN }
FOLLOW(REST1)     = { RPAREN }
FOLLOW(REST2)     = { RPAREN }
FOLLOW(ITEM_TAIL) = { RPAREN }
FOLLOW(ITEM)      = { !=, %, *, +, -, /, <, <=, ==, >, >=,
                      IDENT, IF, IFELSE, LPAREN, NUMERO, RES,
                      RPAREN, WHILE, ^, | }
FOLLOW(BINOP)     = { RPAREN }
FOLLOW(KW_CTRL3)  = { RPAREN }
FOLLOW(KW_CTRL4)  = { RPAREN }
```

---

## 4. Tabela de Análise LL(1)

Cada célula `M[A, a]` indica a produção a aplicar quando o topo da pilha é o
não-terminal **A** e o token corrente é o terminal **a**.
Células ausentes = **erro sintático**.
A gramática é **livre de conflitos** — nenhuma célula recebe duas produções.

### 4.1. Formato plano (M[A, a] → #produção)

| M[A, a] | Produção |
|---|---|
| M[PROGRAM, LPAREN] | #0  PROGRAM → LPAREN START RPAREN BODY |
| M[BODY, LPAREN] | #1  BODY → LPAREN BODY_TAIL |
| M[BODY_TAIL, END] | #2  BODY_TAIL → END RPAREN |
| M[BODY_TAIL, LPAREN / NUMERO / IDENT / RES] | #3  BODY_TAIL → EXPR_BODY RPAREN BODY |
| M[EXPR_BODY, LPAREN / NUMERO / IDENT / RES] | #4  EXPR_BODY → ITEM REST1 |
| M[REST1, RPAREN] | #5  REST1 → ε |
| M[REST1, LPAREN / NUMERO / IDENT / RES] | #6  REST1 → ITEM REST2 |
| M[REST2, RPAREN] | #7  REST2 → ε |
| M[REST2, +/-/\*/…(operadores)] | #8  REST2 → BINOP |
| M[REST2, IF / WHILE] | #9  REST2 → KW_CTRL3 |
| M[REST2, LPAREN / NUMERO / IDENT / RES] | #10 REST2 → ITEM ITEM_TAIL |
| M[ITEM_TAIL, IFELSE] | #11 ITEM_TAIL → KW_CTRL4 |
| M[ITEM, NUMERO] | #12 ITEM → NUMERO |
| M[ITEM, IDENT]  | #13 ITEM → IDENT |
| M[ITEM, RES]    | #14 ITEM → RES |
| M[ITEM, LPAREN] | #15 ITEM → LPAREN EXPR_BODY RPAREN |
| M[BINOP, +/-/\*/…] | #16–#28 um por operador |
| M[KW_CTRL3, IF] | #29 KW_CTRL3 → IF |
| M[KW_CTRL3, WHILE] | #30 KW_CTRL3 → WHILE |
| M[KW_CTRL4, IFELSE] | #31 KW_CTRL4 → IFELSE |

A tabela completa com todas as 57 entradas é gerada automaticamente em
[`output/gramatica_dump.md`](output/gramatica_dump.md) (seção 4 do dump).

---

### 4.2. Formato matricial 2D — M[A, a]

Número = índice da produção (ver seção 1). `—` = erro sintático.
Uma única tabela com **todos** os terminais (tokens, palavras-chave, operadores e `$`).

| NT \ T | $ | LPAREN | RPAREN | NUMERO | IDENT | END | RES | IF | WHILE | IFELSE | + | - | \* | / | \| | % | ^ | > | < | == | != | >= | <= |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `PROGRAM`   | — | **#0**  | — | —      | —      | —     | —      | —     | —      | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `BODY`      | — | **#1**  | — | —      | —      | —     | —      | —     | —      | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `BODY_TAIL` | — | **#3**  | — | **#3** | **#3** | **#2**| **#3** | —     | —      | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `EXPR_BODY` | — | **#4**  | — | **#4** | **#4** | —     | **#4** | —     | —      | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `ITEM`      | — | **#15** | — | **#12**| **#13**| —     | **#14**| —     | —      | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `REST1`     | — | **#6**  | **#5** | **#6** | **#6** | —  | **#6** | —     | —      | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `REST2`     | — | **#10** | **#7** | **#10**| **#10**| —  | **#10**| **#9**| **#9** | —      | **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8**| **#8** |
| `ITEM_TAIL` | — | —       | — | —      | —      | —     | —      | —     | —      | **#11**| — | — | — | — | — | — | — | — | — | — | — | — | — |
| `BINOP`     | — | —       | — | —      | —      | —     | —      | —     | —      | —      |**#16**|**#17**|**#18**|**#19**|**#20**|**#21**|**#22**|**#23**|**#24**|**#25**|**#26**|**#27**|**#28**|
| `KW_CTRL3`  | — | —       | — | —      | —      | —     | —      |**#29**|**#30** | —      | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `KW_CTRL4`  | — | —       | — | —      | —      | —     | —      | —     | —      |**#31** | — | — | — | — | — | — | — | — | — | — | — | — | — |

---

### 4.3. Como ler a tabela (passo a passo do parser)

O parser mantém uma **pilha** e um **buffer de tokens**. A cada iteração:

```
Se topo da pilha == terminal:
    Se topo == token corrente  →  consome (avança no buffer)
    Caso contrário             →  ERRO SINTÁTICO

Se topo da pilha == não-terminal A, token corrente == a:
    Se M[A, a] existe          →  expande A com a produção M[A, a]
    Caso contrário             →  ERRO SINTÁTICO

Se topo == $ e token == $      →  ACEITA ✓
```

**Exemplo** para `(START) (3 4 +) (END)`:

| Pilha (topo →) | Token | Ação |
|---|---|---|
| `PROGRAM $` | `(` | M[PROGRAM, LPAREN] = #0 → expande |
| `LPAREN START RPAREN BODY $` | `(` | terminal: casa `(` |
| `START RPAREN BODY $` | `START` | terminal: casa `START` |
| `RPAREN BODY $` | `)` | terminal: casa `)` |
| `BODY $` | `(` | M[BODY, LPAREN] = #1 → expande |
| `LPAREN BODY_TAIL $` | `(` | terminal: casa `(` |
| `BODY_TAIL $` | `3` | M[BODY_TAIL, NUMERO] = #3 → expande |
| `EXPR_BODY RPAREN BODY $` | `3` | M[EXPR_BODY, NUMERO] = #4 → expande |
| … | … | … |

O passo a passo completo da última execução está em
[`output/derivacao_ultima_execucao.md`](output/derivacao_ultima_execucao.md).

---

## 5. Árvore Sintática do Último Teste (`teste1.txt`)

Gerada pelo comando `python AnalisadorSemantico.py teste1.txt`, salva também em
[`output/arvore_ultima_execucao.txt`](output/arvore_ultima_execucao.txt)
e [`output/arvore_ultima_execucao.json`](output/arvore_ultima_execucao.json):

```
program
  binary(+)
    number(10)
    number(3)
  binary(-)
    number(7.5)
    number(2.5)
  binary(*)
    number(4)
    number(2.5)
  binary(|)
    number(10.0)
    number(4.0)
  binary(/)
    number(10)
    number(3)
  binary(%)
    number(10)
    number(3)
  binary(^)
    number(2)
    number(5)
  mem_write(VARA)
    number(20)
  binary(|)
    mem_read(VARA)
    number(2)
  res_ref(linhas_atras=2)
  while
    cond:
      binary(>)
        mem_read(VARA)
        number(0)
    body:
      binary(-)
        mem_read(VARA)
        number(1)
  ifelse
    cond:
      binary(>=)
        mem_read(VARA)
        number(5)
    then:
      mem_write(FLAG)
        number(1)
    else:
      mem_write(FLAG)
        number(0)
  binary(==)
    mem_read(FLAG)
    number(0)
  binary(-)
    binary(+)
      number(10)
      number(3)
    binary(*)
      number(2)
      number(4)
```

