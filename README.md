# RA3 9 — Analisador Semântico + Geração de Assembly ARMv7

| | |
|---|---|
| **Instituição** | Pontifícia Universidade Católica do Paraná |
| **Disciplina** | Linguagens Formais e Compiladores |
| **Professor** | Frank Coelho de Alcantara |
| **Grupo Canvas** | RA3 9 |
| **Fase** | 3 — Analisador Semântico |
| **Linguagem** | Python 3.10+ |
| **Ano/Semestre** | 2026 / 1º Semestre |

### Autor

| Nome | Usuário GitHub |
|---|---|
| Emanuel Riceto da Silva | [emanuelriceto](https://github.com/emanuelriceto) |

---

## Índice

1. [O que o projeto faz](#1-o-que-o-projeto-faz)
2. [Como compilar, executar e testar](#2-como-compilar-executar-e-testar)
3. [A linguagem](#3-a-linguagem-rpn-tipada)
4. [Tipos suportados](#4-tipos-suportados)
5. [Regras de definição e uso de variáveis](#5-regras-de-definição-e-uso-de-variáveis)
6. [Exemplos válidos e inválidos](#6-exemplos-válidos-e-inválidos)
7. [Arquivos de saída](#7-arquivos-de-saída)
8. [Tratamento de erros](#8-tratamento-de-erros)
9. [Estrutura do repositório](#9-estrutura-do-repositório)
10. [Documentação complementar](#10-documentação-complementar)
11. [Distribuição do trabalho](#11-distribuição-do-trabalho)

---

## 1. O que o projeto faz

Este projeto é um **compilador completo** (Fase 1 → 2 → 3) para uma
linguagem em **notação polonesa reversa (RPN)**. Ele lê um arquivo-fonte,
faz **análise léxica** (AFD com suporte a comentários `*{ … }*` estilo
Pascal), **análise sintática** com parser **LL(1)**, **análise
semântica** (tabela de símbolos + verificação de tipos) e finalmente
gera **código Assembly ARMv7** pronto para o simulador
[CPUlator DE1-SoC](https://cpulator.01xz.net/?sys=arm-de1soc).

Pipeline resumido (ver [docs/diagramas.md §13](docs/diagramas.md) para o
fluxograma Mermaid completo):

```
arquivo.txt
    → _strip_comentarios       (Fase 3 §1)
    → AFD lexer                (Fase 1)
    → parser LL(1)             (Fase 2)
    → construirTabelaSimbolos  (Fase 3 §2)
    → verificarTipos           (Fase 3 §4)
    → gerarArvoreAtribuida     (Fase 3 §5)
    → gerar_assembly_de_arvore_atribuida   (Fase 3 §6)
    → output/ultima_execucao.s
```

A geração de Assembly **só ocorre se não houver erros léxicos,
sintáticos ou semânticos** — caso contrário o CLI apaga qualquer `.s`
antigo e devolve um exit-code não-zero (ver §8).

---

## 2. Como compilar, executar e testar

> **Pré-requisito:** Python 3.10 ou superior. Sem dependências externas.

### Executar um arquivo-fonte

```powershell
cd RA3_9
python AnalisadorSemantico.py teste1.txt
```

Opcionalmente pode-se redirecionar a saída de artefatos:

```powershell
python AnalisadorSemantico.py teste1.txt --out-dir saida_local
```

### Exit codes

| Código | Significado |
|---:|---|
| `0` | Análise concluída sem erros — Assembly gerado em `output/ultima_execucao.s` |
| `1` | Erros léxicos ou sintáticos — abortado antes da semântica |
| `2` | Erros semânticos — Assembly **não** gerado / antigo removido |

### Suite de testes

```powershell
python -m unittest discover -s tests
```

Esperado: **108 testes, todos verdes**.

---

## 3. A linguagem (RPN tipada)

```
programa     ::= '(' 'START' ')' stmt* '(' 'END' ')'
stmt         ::= expr
expr         ::= INT | REAL
               | '(' IDENT ')'                       (* leitura de memória *)
               | '(' expr expr OP_BIN ')'            (* aritmética/relacional *)
               | '(' expr IDENT ')'                  (* (v MEM) — escrita de memória *)
               | '(' INT 'RES' ')'                   (* resultado N linhas atrás *)
               | '(' expr expr 'IF' ')'
               | '(' expr expr expr 'IFELSE' ')'
               | '(' expr expr 'WHILE' ')'
OP_BIN       ::= '+' | '-' | '*' | '|' | '/' | '%' | '^'
               | '>' | '<' | '==' | '!=' | '>=' | '<='
```

### Comentários

`*{ ... }*` — estilo Pascal, **multilinha**, **não aninhados** (o
primeiro `}*` fecha o comentário). Aceitos em qualquer das três
posições: linha inteira, fim de linha (após tokens), ou entre tokens.
Um comentário não fechado até o EOF é **erro léxico** com linha/coluna
da abertura.

---

## 4. Tipos suportados

| Tipo | Notação | Origem |
|---|---|---|
| `int` | literais sem ponto: `42`, `0`, `7` | T-IntLit |
| `real` | literais com ponto: `3.14`, `0.0` | T-RealLit |
| `bool` | resultado de `> < == != >= <=` (não há literal) | T-Rel |

> **Decisão de projeto: SEM promoção implícita.**
> `(1 2.5 +)` é **erro semântico**, não soma `1.0 + 2.5`. Veja
> [regras_tipos.md](regras_tipos.md) para o cálculo de sequentes
> completo.

### Operadores e seus tipos

| Operador | Operandos exigidos | Resultado |
|---|---|---|
| `+ - * ^` | `(τ, τ)` com `τ ∈ {int, real}` | `τ` |
| `/ %` | `(int, int)` | `int` |
| `\|` | `(real, real)` | `real` |
| `> < == != >= <=` | `(τ, τ)` com `τ ∈ {int, real}` | `bool` |
| `IF` / `WHILE` | cond `bool`, corpo qualquer | tipo do corpo / unit |
| `IFELSE` | cond `bool`, ramos do mesmo tipo `τ` | `τ` |

---

## 5. Regras de definição e uso de variáveis

A linguagem possui **memórias nomeadas** (identificadores em
maiúsculas, ex.: `X`, `CONT`, `RESULT`) com **escopo único global** —
um arquivo = um escopo. As regras são:

1. **Definição:** `(v MEM)` onde `v` é uma expressão. O tipo de `MEM`
   fica **fixado** com o tipo de `v` na **primeira** definição.
2. **Leitura:** `(MEM)` só é válido **depois** da definição. Uso antes
   da declaração → erro semântico.
3. **Redefinição:** `(v2 MEM)` repetida é permitida **se** `tipo(v2)`
   for igual ao tipo fixado; caso contrário → erro semântico
   (redeclaração com tipo incompatível).
4. **`(N RES)`:** referencia o valor do statement `N` linhas atrás
   (`N` inteiro positivo, `N ≤ #stmts_anteriores`).

A tabela de símbolos guarda, para cada variável: nome, tipo, linha de
declaração, lista de linhas de uso e escopo (sempre `global`). Veja o
artefato concreto em
[output/tabela_simbolos.md](output/tabela_simbolos.md).

---

## 6. Exemplos válidos e inválidos

### Válidos

```text
*{ Exemplo 1 — int puro }*
(START)
(10 3 +)            *{ → 13 }*
(5 CONT)
((CONT) 0 >)        *{ → bool true }*
(((CONT) 0 >) ((CONT) 1 -) IF)
(END)
```

```text
*{ Exemplo 2 — real + IFELSE }*
(START)
(3.14 PI)
((PI) 2.0 *)        *{ → 6.28 }*
((1.0 0.0 >) (1.0) (2.0) IFELSE)
(END)
```

Os arquivos [teste1.txt](teste1.txt), [teste2.txt](teste2.txt) e
[teste3.txt](teste3.txt) cobrem **todos** os operadores, comandos
especiais, estruturas de controle, todos os tipos, expressões
aninhadas e comentários em 3 posições.

### Inválidos (cada bloco é um erro semântico distinto)

```text
((NAODECL) 1 +)         *{ uso antes da declaração }*
(10 X)  (2.5 X)         *{ redefinição int → real }*
((1 2 +) (3 4 +) IF)    *{ condição do IF não é bool }*
(1 2.5 +)               *{ sem promoção implícita }*
(10 3 |)                *{ '|' exige real }*
(10.0 3.0 /)            *{ '/' exige int }*
(99 RES)                *{ N maior que #stmts anteriores }*
```

Veja [teste_erro_semantico.txt](teste_erro_semantico.txt) (9 casos) e
o relatório gerado em [output/erros_semanticos.md](output/erros_semanticos.md).

---

## 7. Arquivos de saída

Todos os artefatos são gravados em `output/` (ou no diretório passado
via `--out-dir`). Por execução:

| Arquivo | Conteúdo |
|---|---|
| [output/ARQUIVO_USADO.txt](output/ARQUIVO_USADO.txt) | Nome do `.txt` da última execução |
| [output/tokens_ultima_execucao.txt](output/tokens_ultima_execucao.txt) | Lista de tokens reconhecidos pelo AFD |
| [output/gramatica_dump.md](output/gramatica_dump.md) | Gramática LL(1), FIRST, FOLLOW, tabela `M` |
| [output/derivacao_ultima_execucao.md](output/derivacao_ultima_execucao.md) | Passo-a-passo do parser LL(1) |
| [output/arvore_ultima_execucao.md / .json](output/arvore_ultima_execucao.md) | AST "crua" da Fase 2 |
| [output/tabela_simbolos.md](output/tabela_simbolos.md) | Tabela de símbolos final |
| [output/erros_semanticos.md](output/erros_semanticos.md) | Relatório de erros (vazio = "Nenhum erro") |
| [output/arvore_atribuida.md / .json](output/arvore_atribuida.md) | AST enriquecida com tipos e metadados ASM |
| [output/ultima_execucao.s](output/ultima_execucao.s) | Assembly ARMv7 — **só** se sem erros |

Se a execução **falha** em léxico/sintaxe, um arquivo
`output/erros_lexsint.md` é adicionado e o `.s` antigo é removido.

---

## 8. Tratamento de erros

| Fase | Detecção | Mensagem | Onde é registrada |
|---|---|---|---|
| **Léxico** | AFD + `_strip_comentarios` | `[léxico] linha L coluna C: …` | `output/erros_lexsint.md` |
| **Sintático** | Parser LL(1) (modo pânico — recupera e segue) | `[sintático] linha L: …` | `output/erros_lexsint.md` |
| **Semântico** | `construirTabelaSimbolos` + `verificarTipos` | `[semântico] (linha L) …` | `output/erros_semanticos.md` |

**Garantia crítica:** o Assembly **nunca** é gerado quando há erros de
qualquer fase. O CLI apaga proativamente o `.s` antigo nesses casos
para impedir que um avaliador execute código obsoleto. Esse contrato é
verificado pelo teste automatizado `test_cli_erro_semantico_apaga_asm_antigo`
em [tests/test_arquivos_e2e.py](tests/test_arquivos_e2e.py).

A análise semântica **não aborta no primeiro erro** — todos os
problemas são acumulados em uma única passagem para que o usuário
corrija o máximo possível por execução.

---

## 9. Estrutura do repositório

```
RA3_9/
├── AnalisadorSemantico.py          (entry point — CLI)
├── README.md                        (este arquivo)
├── gramatica.md                     (gramática LL(1) — Fase 2)
├── gramatica_atribuida.md           (EBNF + ações semânticas — Fase 3)
├── regras_tipos.md                  (cálculo de sequentes — Fase 3)
├── teste1.txt / teste2.txt / teste3.txt   (programas válidos)
├── teste_erro_lexico.txt
├── teste_erro_sintatico.txt
├── teste_erro_semantico.txt
├── docs/
│   └── diagramas.md                 (Mermaid — pipeline, AFD, AST, §13 novo)
├── output/                          (regenerado a cada execução)
├── src/
│   ├── lexer_fsm.py                 (AFD + comentários)
│   ├── parser_ll1.py                (parser LL(1) — Fase 2)
│   ├── semantica.py                 (Fase 3 — tabela + tipos + árvore atribuída)
│   ├── armv7_generator.py           (Assembly tipado)
│   └── pipeline.py                  (prepararEntradaSemantica)
└── tests/
    ├── test_lexer.py                (lexer + comentários)
    ├── test_pipeline.py             (pipeline + assembly tipado)
    ├── test_semantica.py            (semântica — tipos, tabela, árvore atribuída)
    └── test_arquivos_e2e.py         (CLI end-to-end sobre os .txt)
```

---

## 10. Documentação complementar

- [gramatica.md](gramatica.md) — gramática LL(1) original (Fase 2).
- [gramatica_atribuida.md](gramatica_atribuida.md) — gramática com
  ações semânticas (atributos sintetizados, atualização da tabela).
- [regras_tipos.md](regras_tipos.md) — sistema de tipos como **cálculo
  de sequentes**.
- [docs/diagramas.md](docs/diagramas.md) — pipeline, AFD (com `§13
  EM_COMENTARIO`), AST, tabela LL(1), árvore de derivação.

---

## 11. Distribuição do trabalho

Trabalho desenvolvido **integralmente e individualmente** por **Emanuel Riceto da Silva** (*emanuelriceto*), abrangendo todas as etapas da Fase 3: lexer e comentários (§1), `prepararEntradaSemantica` (§3), tabela de símbolos (§2), verificação de tipos (§4), árvore atribuída (§5), gerador ARMv7 tipado (§6), CLI (§7), arquivos de teste e a suíte end-to-end.
