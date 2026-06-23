# Regras de Tipos — Fase 3 (RA3 9)

> Cálculo de sequentes que descreve formalmente o sistema de tipos
> implementado em [src/semantica.py](src/semantica.py).

## Domínio

```
τ ∈ { int, real, bool, indef }
Γ : MEM → τ            (tabela de símbolos — escopo global único)
```

`indef` é usado apenas internamente para nós que falharam a inferência —
não pode aparecer no programa final sem que um erro tenha sido emitido.

**Decisão de projeto:** **sem promoção implícita** entre `int` e `real`.
Toda combinação heterogênea é erro semântico. Conversões devem ser
expressas pelo programador (ex.: usando uma `MEM` `real` que recebeu um
literal `real`).

---

## 1. Literais

```
─────────────  (T-IntLit)             ─────────────  (T-RealLit)
 Γ ⊢ n : int                            Γ ⊢ r : real
```

`bool` não tem literal próprio — só nasce de operadores relacionais.

## 2. Aritmética homogênea (`+ - * ^`)

```
 Γ ⊢ e1 : τ      Γ ⊢ e2 : τ      τ ∈ { int, real }
─────────────────────────────────────────────────── (T-Arith)
 Γ ⊢ (e1 e2 op) : τ           op ∈ { +, -, *, ^ }
```

## 3. Divisão e módulo inteiros (`/ %`)

```
 Γ ⊢ e1 : int     Γ ⊢ e2 : int
────────────────────────────────  (T-IntDiv)
 Γ ⊢ (e1 e2 op) : int          op ∈ { /, % }
```

Operandos `real` em `/` ou `%` → erro. Use `|` para divisão real.

## 4. Divisão real (`|`)

```
 Γ ⊢ e1 : real    Γ ⊢ e2 : real
─────────────────────────────────  (T-RealDiv)
 Γ ⊢ (e1 e2 |) : real
```

Operandos `int` em `|` → erro.

## 5. Operadores relacionais

```
 Γ ⊢ e1 : τ      Γ ⊢ e2 : τ      τ ∈ { int, real }
─────────────────────────────────────────────────── (T-Rel)
 Γ ⊢ (e1 e2 op) : bool       op ∈ { >, <, ==, !=, >=, <= }
```

Tipos devem ser idênticos. `bool` em relacional → erro.

## 6. Estruturas de controle

```
 Γ ⊢ cond : bool      Γ ⊢ block : τ
────────────────────────────────────  (T-If)
 Γ ⊢ (cond block IF) : τ


 Γ ⊢ cond : bool   Γ ⊢ t : τ   Γ ⊢ e : τ
──────────────────────────────────────────  (T-IfElse)
 Γ ⊢ (cond t e IFELSE) : τ


 Γ ⊢ cond : bool      Γ ⊢ body : τ
────────────────────────────────────  (T-While)
 Γ ⊢ (cond body WHILE) : unit
```

`IFELSE` exige que os dois ramos tenham o **mesmo** tipo `τ` — sem
unificação por promoção.

## 7. Memória

```
 Γ ⊢ v : τ
──────────────────────────────────────  (T-MemDef)        Γ' = Γ, MEM:τ
 Γ ⊢ (v MEM) ⊣ Γ'


 MEM : τ ∈ Γ
──────────────────  (T-MemRead)
 Γ ⊢ (MEM) : τ
```

Redeclarar `(v MEM)` com um `v` cujo tipo difere do `τ` original → erro
(tipo da variável é fixado na primeira definição).

Usar `(MEM)` antes da definição → erro (uso antes da declaração).

## 8. Comando `(N RES)`

```
 N ∈ ℕ        N ≤ #stmts_anteriores
────────────────────────────────────  (T-Res)
 Γ ⊢ (N RES) : τ_{ stmt[−N] }
```

`N` maior do que o número de statements já emitidos → erro semântico.

---

## Resumo das mensagens de erro

| Situação | Mensagem (prefixo `[semântico]`) |
|---|---|
| Uso antes de declarar | `uso da variável 'X' antes da declaração (faltou '(v mem)')` |
| Redeclaração incompatível | `redeclaração da variável 'X' com tipo incompatível: era 'τ1', recebeu 'τ2'` |
| `IF`/`WHILE` cond não-bool | `condição do if/while deve ser 'bool', recebeu 'τ'` |
| `IFELSE` ramos divergentes | `ramos do ifelse têm tipos divergentes: 'then':τ1 vs 'else':τ2` |
| Aritmética heterogênea | `operador 'op' exige operandos numéricos do mesmo tipo (sem promoção implícita), recebeu 'τ1' e 'τ2'` |
| `\|` com int | `operador '\|' (divisão real) exige operandos 'real', recebeu 'τ1' e 'τ2'` |
| `/` ou `%` com real | `operador 'op' exige operandos 'int', recebeu 'τ1' e 'τ2'` |
| `(N RES)` fora de faixa | `(n res) referencia N linhas atrás, mas só existem M statement(s) anterior(es)` |

---

## Recuperação de erros

A verificação **não aborta** no primeiro erro: todos os nós continuam a
ser tipados (atribuindo `indef` quando necessário) para que o relatório
final liste o máximo de problemas em uma única execução. Veja
[output/erros_semanticos.md](output/erros_semanticos.md).

A geração de código (`output/ultima_execucao.s`) só ocorre se a lista de
erros for vazia — caso contrário, o CLI apaga qualquer `.s` antigo para
evitar que o avaliador execute código obsoleto.
