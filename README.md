# Pascal Compiler

Учебный компилятор подмножества языка Pascal на Python. Реализует полный конвейер компиляции: лексический и синтаксический анализ, семантический анализ, оптимизацию AST и генерацию кода для двух бэкендов — стековой виртуальной машины и x86-32 (NASM).

**Зависимости:** Python 3.11+, [lark](https://github.com/lark-parser/lark)

```bash
pip install lark
```

---

## Содержание

1. [Быстрый старт](#быстрый-старт)
2. [CLI — флаги и опции](#cli--флаги-и-опции)
3. [Язык Pascal](#язык-pascal)
   - [Типы данных](#типы-данных)
   - [Операции](#операции)
   - [Управляющие конструкции](#управляющие-конструкции)
   - [Процедуры и функции](#процедуры-и-функции)
   - [Встроенные функции](#встроенные-функции)
   - [Комментарии](#комментарии)
4. [Архитектура компилятора](#архитектура-компилятора)
5. [Стадии компиляции](#стадии-компиляции)
   - [Парсинг и AST](#парсинг-и-ast)
   - [Семантический анализ](#семантический-анализ)
   - [Оптимизации](#оптимизации)
   - [Бэкенд: виртуальная машина](#бэкенд-виртуальная-машина)
   - [Бэкенд: x86-32](#бэкенд-x86-32)
6. [Примеры программ](#примеры-программ)
7. [Запуск через Docker](#запуск-через-docker)
8. [Структура проекта](#структура-проекта)

---

## Быстрый старт

### Локально

```bash
# Установить зависимости
pip install lark

# Запустить через виртуальную машину
python run.py examples/factorial.pas --vm

# Сгенерировать x86 NASM-листинг
python run.py examples/factorial.pas --x86

# Сохранить ассемблер в файл
python run.py examples/factorial.pas --x86 --out result.asm
```

### Через Docker

```bash
# Собрать образ (один раз)
docker build -t pascal-compiler .

# Полный цикл: Pascal → ASM → бинарник → запуск
docker run --entrypoint bash pascal-compiler -c "
  python run.py examples/factorial.pas --x86 --out /tmp/out.asm &&
  nasm -f elf32 /tmp/out.asm -o /tmp/out.o &&
  gcc -m32 -no-pie /tmp/out.o -o /tmp/out &&
  /tmp/out
"
# → 720
```

---

## CLI — флаги и опции

```
python run.py <файл.pas> [бэкенд] [флаги]
```

### Бэкенды (взаимоисключающие)

| Флаг | Описание |
|------|----------|
| `--vm` | Запустить программу через встроенную виртуальную машину |
| `--x86` | Сгенерировать x86-32 NASM-листинг |

### Параметры вывода

| Флаг | Описание |
|------|----------|
| `--out FILE` | Сохранить `.asm`-файл по указанному пути (для `--x86`) |
| `--ast` | Показать AST сразу после парсинга |
| `--sem` | Показать AST после семантического анализа |
| `--opt` | Показать AST после оптимизации |
| `--dis` | Показать байткод виртуальной машины |

### Управление конвейером

| Флаг | Описание |
|------|----------|
| `--parse-only` | Остановиться после парсинга |
| `--sem-only` | Остановиться после семантического анализа |
| `--no-opt` | Отключить оптимизации |

### Примеры запуска

```bash
# Просто запустить программу
python run.py examples/factorial.pas --vm

# Запустить и показать байткод
python run.py examples/factorial.pas --vm --dis

# Запустить без оптимизаций
python run.py examples/factorial.pas --vm --no-opt

# Показать AST до и после оптимизации
python run.py examples/optimizations.pas --ast --opt --sem-only

# Сгенерировать asm и сохранить
python run.py examples/factorial.pas --x86 --out factorial.asm
```

---

## Язык Pascal

Компилятор поддерживает подмножество стандартного Pascal. Программа имеет структуру:

```pascal
program <Имя>;

var
  <переменные>;

<объявления функций и процедур>

begin
  <операторы>
end.
```

### Типы данных

| Тип | Описание | Примеры значений |
|-----|----------|-----------------|
| `integer` | Целое число | `42`, `-7`, `0` |
| `boolean` | Логический | `true`, `false` |
| `char` | Символ | `'a'`, `'Z'`, `''''` (одиночная кавычка) |
| `array[lo..hi] of T` | Массив | `array[1..10] of integer` |

Массивы могут иметь любые целочисленные границы, в том числе с нуля: `array[0..9] of boolean`.

### Операции

| Группа | Операции | Типы операндов | Тип результата |
|--------|----------|----------------|----------------|
| Арифметика | `+`, `-`, `*` | `integer` | `integer` |
| Целочисленное деление | `/`, `div` | `integer` | `integer` |
| Остаток | `mod` | `integer` | `integer` |
| Сравнение | `=`, `<>`, `<`, `<=`, `>`, `>=` | `integer`, `char` | `boolean` |
| Равенство | `=`, `<>` | `boolean` | `boolean` |
| Логика | `and`, `or` | `boolean` | `boolean` |
| Отрицание | `not` | `boolean` | `boolean` |
| Унарный минус | `-` | `integer` | `integer` |
| Унарный плюс | `+` | `integer` | `integer` |

> Для `integer` операции `/` и `div` идентичны — результат целый.

**Приоритет операций** (от высшего к низшему):

```
1. Унарные:       not, унарный -/+
2. Мультипликативные: *, /, div, mod, and
3. Аддитивные:    +, -, or
4. Сравнение:     =, <>, <, <=, >, >=
```

`and` и `or` используют **ленивые вычисления**: правый операнд не вычисляется, если результат уже известен по левому.

### Управляющие конструкции

#### Присваивание

```pascal
x := 42;
a[i] := x + 1;
```

#### Условие

```pascal
if x > 0 then
  WriteLn(x);

if x > 0 then
  WriteLn(x)
else
  WriteLn(0);
```

#### Цикл while

```pascal
while i <= 10 do
begin
  WriteLn(i);
  i := i + 1;
end;
```

#### Цикл repeat..until

```pascal
repeat
  ReadLn(x);
until x > 0;
```

#### Цикл for

```pascal
for i := 1 to 10 do     { возрастающий, шаг +1 }
  s := s + i;

for i := 10 downto 1 do  { убывающий, шаг -1 }
  WriteLn(i);
```

#### break и continue

Работают внутри любого цикла (`while`, `repeat`, `for`):

```pascal
while true do
begin
  i := i + 1;
  if i mod 2 = 0 then continue;  { перейти к следующей итерации }
  if i > 10 then break;           { выйти из цикла }
  WriteLn(i);
end;
```

#### Блок операторов

```pascal
begin
  stmt1;
  stmt2;
  stmt3
end
```

Точка с запятой — **разделитель** между операторами (не терминатор), перед `end` не ставится.

### Процедуры и функции

#### Объявление процедуры

```pascal
procedure PrintSquare(x: integer);
begin
  WriteLn(x * x);
end;
```

#### Объявление функции

```pascal
function Max(a: integer; b: integer): integer;
begin
  if a > b then
    Max := a
  else
    Max := b;
end;
```

Возврат значения — присвоение имени функции: `FuncName := value`.

#### Локальные переменные

```pascal
function Fib(n: integer): integer;
var
  a: integer;
  b: integer;
begin
  { ... }
end;
```

#### Вызов

```pascal
PrintSquare(5);
result := Max(a, b);
WriteLn(fact(n));   { вложенный вызов }
```

Параметры передаются **по значению**. Рекурсия поддерживается.

### Встроенные функции

| Функция | Аргумент | Описание |
|---------|----------|----------|
| `Write(x)` | `integer`, `boolean`, `char` | Вывод без переноса строки |
| `WriteLn(x)` | `integer`, `boolean`, `char` | Вывод с переносом строки |
| `Read(x)` | переменная `integer` или `char` | Ввод |
| `ReadLn(x)` | переменная `integer` или `char` | Ввод |
| `Inc(x)` | переменная `integer` | Увеличить на 1 (`x := x + 1`) |
| `Dec(x)` | переменная `integer` | Уменьшить на 1 (`x := x - 1`) |
| `Abs(x)` | `integer` | Модуль числа |

`boolean` выводится как `TRUE` / `FALSE` (заглавными буквами).

### Комментарии

```pascal
// Однострочный комментарий

{ Блочный комментарий }

(* Ещё один блочный комментарий *)
```

---

## Архитектура компилятора

```
Исходный .pas файл
        │
        ▼
┌─────────────────┐
│    Parser        │  pascal.lark + frontend/parser.py
│  (Lark Earley)   │
└────────┬────────┘
         │  AST (дерево узлов AstNode)
         ▼
┌─────────────────┐
│    Semantic      │  analysis/semantic.py
│    Checker       │  — проверка типов
│                  │  — таблица символов
└────────┬────────┘
         │  аннотированный AST
         ▼
┌─────────────────┐
│    Optimizer     │  optimizer.py
│                  │  — свёртка констант
│                  │  — алгебраические упрощения
│                  │  — удаление мёртвого кода
└────────┬────────┘
         │  оптимизированный AST
         ├──────────────────────┐
         ▼                      ▼
┌──────────────┐     ┌─────────────────┐
│  VM Codegen  │     │  x86 Codegen    │
│  backend/vm/ │     │  backend/x86/   │
└──────┬───────┘     └────────┬────────┘
       │ байткод               │ NASM-листинг
       ▼                      ▼
┌──────────────┐     ┌─────────────────┐
│  Виртуальная │     │  nasm + gcc -m32│
│  машина (VM) │     │  → ELF бинарник │
└──────────────┘     └─────────────────┘
```

### Компоненты

| Модуль | Файл | Описание |
|--------|------|----------|
| `pipeline` | `compiler/pipeline.py` | Оркестрация всего конвейера |
| `parser` | `compiler/frontend/parser.py` | Lark-парсер → AST |
| `ast` | `compiler/frontend/ast.py` | Определения узлов AST |
| `ast_printer` | `compiler/frontend/ast_printer.py` | Вывод AST в текстовом виде |
| `semantic` | `compiler/analysis/semantic.py` | Семантический анализ и типизация |
| `visitor` | `compiler/analysis/visitor.py` | Инфраструктура паттерна Visitor |
| `optimizer` | `compiler/optimizer.py` | Оптимизации на уровне AST |
| `vm/codegen` | `compiler/backend/vm/codegen.py` | Генерация байткода |
| `vm/opcodes` | `compiler/backend/vm/opcodes.py` | Набор инструкций VM |
| `vm/vm` | `compiler/backend/vm/vm.py` | Исполнитель байткода |
| `x86/codegen` | `compiler/backend/x86/codegen.py` | Генерация NASM x86-32 |
| `errors` | `compiler/errors.py` | Классы ошибок компилятора |

---

## Стадии компиляции

### Парсинг и AST

Парсер использует библиотеку **Lark** с алгоритмом Earley и грамматикой в файле `pascal.lark`. Грамматика регистронезависима (ключевые слова можно писать в любом регистре).

Результат парсинга — дерево объектов `AstNode`. Основные узлы:

| Узел | Описание |
|------|----------|
| `ProgramNode` | Корень: имя, глобальные переменные, функции, тело |
| `FuncNode` | Функция или процедура |
| `VarDeclNode` | Объявление переменных |
| `StmtListNode` | Список операторов |
| `AssignNode` | Присваивание |
| `IfNode` | Ветвление |
| `WhileNode` | Цикл while |
| `RepeatNode` | Цикл repeat..until |
| `ForNode` | Цикл for |
| `BreakNode`, `ContinueNode` | Управление циклом |
| `CallNode` | Вызов функции / процедуры |
| `BinOpNode` | Бинарная операция |
| `UnOpNode` | Унарная операция |
| `LiteralNode` | Литерал (число, булево, символ) |
| `IdentNode` | Идентификатор |
| `ArrayAccessNode` | Доступ к элементу массива `a[i]` |

Просмотр AST:

```bash
python run.py examples/factorial.pas --ast --parse-only
```

Пример вывода:

```
program Factorial
+-- var n: integer
+-- var result: integer
+-- function fact(n: integer): integer
|   \-- block
|       \-- if
|           +-- (n <= 1)
|           +-- (fact := 1)
|           \-- (fact := n * fact(n - 1))
\-- block
    +-- (n := 6)
    \-- WriteLn(fact(n))
```

### Семантический анализ

Модуль `semantic.py` обходит AST и выполняет:

**Таблица символов** — стек областей видимости (`IdentScope`):
- Глобальная область: переменные программы и имена функций
- Локальная область функции: параметры + локальные переменные

**Проверки типов:**
- Тип каждого выражения вычисляется и проставляется в поле `node.node_type`
- Несовместимые типы в операциях → `SemanticException`
- Присваивание совместимых типов (целое → вещественное — авто-конвертация через `TypeConvertNode`)

**Другие проверки:**
- Использование необъявленных переменных
- Вызов несуществующих функций
- Количество и типы аргументов при вызове
- `break` / `continue` только внутри цикла
- Условие в `if` / `while` должно быть `boolean`
- Индекс массива должен быть `integer`

**Встроенные операторы и их типы:**

```
NOT boolean → boolean
+, - integer → integer
integer + integer → integer
integer < integer → boolean
boolean and boolean → boolean
```

Просмотр AST после семантики:

```bash
python run.py examples/factorial.pas --sem --sem-only
```

### Оптимизации

Оптимизатор обходит AST и трансформирует узлы. Выполняется за один проход.

#### Свёртка констант

Выражения из литералов вычисляются на этапе компиляции:

```pascal
x := 2 + 3 * 4;   { → x := 14 }
x := 10 div 3;    { → x := 3  }
flag := 3 > 1;    { → flag := true }
```

#### Алгебраические упрощения

| До | После |
|----|-------|
| `x + 0` | `x` |
| `x - 0` | `x` |
| `0 - x` | `-x` |
| `x * 0` | `0` |
| `x * 1` | `x` |
| `x / 1` | `x` |
| `x mod 1` | `0` |
| `true and x` | `x` |
| `false and x` | `false` |
| `true or x` | `true` |
| `false or x` | `x` |
| `not (not x)` | `x` |
| `-(-x)` | `x` |

#### Удаление мёртвого кода

```pascal
{ Недостижимый код после break/continue убирается }
while true do
begin
  break;
  WriteLn(999);  { удаляется }
end;

{ Цикл с заведомо ложным условием убирается целиком }
while false do
  WriteLn(1);   { удаляется весь while }

{ Ветка if с константным условием }
if true then x := 1 else x := 2;   { → x := 1 }
if false then x := 999;             { → убирается }
```

Просмотр AST до и после оптимизации:

```bash
python run.py examples/optimizations.pas --sem --opt --sem-only
```

### Бэкенд: виртуальная машина

Стековая VM с набором из 55 инструкций.

#### Модель выполнения

- **Стек значений** — для вычисления выражений
- **Фреймы** — у каждой функции свой фрейм с локальными переменными
- **Указатель инструкций (ip)** — индекс текущей инструкции

#### Основные инструкции

| Группа | Инструкции |
|--------|-----------|
| Стек | `PUSH val`, `POP` |
| Переменные | `LOAD name`, `STORE name` |
| Массивы | `LOAD_IDX name`, `STORE_IDX name` |
| Арифметика | `ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `NEG` |
| Сравнение | `EQ`, `NE`, `LT`, `LE`, `GT`, `GE` |
| Логика | `AND`, `OR`, `NOT` |
| Переходы | `JUMP addr`, `JUMP_FALSE addr` |
| Функции | `CALL name`, `RETURN`, `RETURN_NONE` |
| I/O | `PRINT`, `READ` |
| Встроенные | `INC`, `DEC`, `ABS` |
| Завершение | `HALT` |

#### Просмотр байткода

```bash
python run.py examples/factorial.pas --vm --dis
```

Пример вывода для `factorial.pas`:

```
=== main ===
  0: PUSH         6
  1: STORE        n
  2: LOAD         n
  3: CALL         fact
  4: PRINT        nl
  5: HALT

=== fact ===
  0: LOAD         n
  1: PUSH         1
  2: LE
  3: JUMP_FALSE   7
  4: PUSH         1
  5: RETURN
  6: JUMP         15
  7: LOAD         n
  8: LOAD         n
  9: PUSH         1
 10: SUB
 11: CALL         fact
 12: MUL
 13: RETURN
```

### Бэкенд: x86-32

Генерирует NASM-формат, 32-битные Linux ELF (System V ABI).

#### Соглашения о вызовах

- Аргументы передаются через стек справа налево: `push arg_n ... push arg_1`
- Возвращаемое значение в регистре `eax`
- Пролог функции: `push ebp / mov ebp, esp`
- Параметры доступны через `[ebp + 8]`, `[ebp + 12]`, ...
- Локальные переменные через `[ebp - 4]`, `[ebp - 8]`, ...
- Стек выравнивается вызывающей стороной: `add esp, N` после вызова

#### Регистры

| Регистр | Использование |
|---------|--------------|
| `eax` | Результат выражения, возвращаемое значение |
| `ebx` | Второй операнд бинарной операции |
| `ecx` | Временный (для cmov) |
| `ebp` | База стекового фрейма |
| `esp` | Вершина стека |

#### Структура сгенерированного файла

```nasm
; Generated by Pascal x86 compiler
; Build: nasm -f elf32 output.asm -o output.o
;        gcc -m32 -no-pie output.o -o output

section .data
    _fmt_int   db "%d", 0       ; Write(integer)
    _fmt_nl    db "%d", 10, 0   ; WriteLn(integer)
    _fmt_true  db "TRUE", 10, 0
    _fmt_false db "FALSE", 10, 0
    _fmt_char  db "%c", 0

section .bss
    _x resd 1        ; глобальные integer-переменные
    _flag resd 1

section .text
    global main
    extern printf, scanf

    ; --- функции пользователя ---
_func_fact:
    push  ebp
    mov   ebp, esp
    ...
    pop   ebp
    ret

    ; --- точка входа ---
main:
    push  ebp
    mov   ebp, esp
    ...
    xor   eax, eax
    ret

section .note.GNU-stack noalloc noexec nowrite progbits
```

#### Сборка и запуск (Linux)

```bash
nasm -f elf32 output.asm -o output.o
gcc -m32 -no-pie output.o -o output
./output
```

---

## Примеры программ

### hello.pas — минимальная программа

```pascal
program Hello;
begin
  WriteLn(42);
end.
```

```
Вывод: 42
```

### factorial.pas — рекурсивная функция

```pascal
program Factorial;
var
  n: integer;
  result: integer;

function fact(n: integer): integer;
begin
  if n <= 1 then
    fact := 1
  else
    fact := n * fact(n - 1);
end;

begin
  n := 6;
  WriteLn(fact(n));
end.
```

```
Вывод: 720
```

### procedures.pas — процедуры и функции

```pascal
program Procedures;
var
  n: integer;

procedure printLine(x: integer);
begin
  WriteLn(x);
end;

function square(x: integer): integer;
begin
  square := x * x;
end;

begin
  for n := 1 to 5 do
    printLine(square(n));
end.
```

```
Вывод:
1
4
9
16
25
```

### for_loop.pas — цикл for

```pascal
program ForLoop;
var
  i: integer;
  s: integer;
begin
  s := 0;
  for i := 1 to 10 do
    s := s + i;
  WriteLn(s);
end.
```

```
Вывод: 55
```

### while_loop.pas — цикл while

```pascal
program WhileLoop;
var
  i: integer;
begin
  i := 1;
  while i <= 5 do
  begin
    WriteLn(i);
    i := i + 1;
  end;
end.
```

```
Вывод:
1
2
3
4
5
```

### break_continue.pas — break и continue

```pascal
program BreakContinue;
var
  i: integer;
begin
  i := 0;
  while true do
  begin
    i := i + 1;
    if i mod 2 = 0 then
      continue;
    if i > 7 then
      break;
    WriteLn(i);
  end;
end.
```

```
Вывод:
1
3
5
7
```

### inc_dec_abs.pas — встроенные функции

```pascal
program IncDecAbs;
var
  x: integer;
begin
  x := 5;
  Inc(x);
  Inc(x);
  WriteLn(x);   { 7 }
  Dec(x);
  WriteLn(x);   { 6 }
  x := -10;
  WriteLn(Abs(x));  { 10 }
end.
```

```
Вывод:
7
6
10
```

### optimizations.pas — демонстрация оптимизаций

```pascal
program Optimizations;
var
  x: integer;
  flag: boolean;
begin
  x := 2 + 3 * 4;    { свёртка: вычисляется в 14 на этапе компиляции }
  WriteLn(x);

  x := x * 1;        { упрощение: x * 1 → x }
  x := x + 0;        { упрощение: x + 0 → x }
  WriteLn(x);

  flag := not not true;  { двойное отрицание → true }
  WriteLn(x);

  while true do
  begin
    x := x + 1;
    break;
    x := 999;       { мёртвый код — удаляется }
    WriteLn(999);   { мёртвый код — удаляется }
  end;
  WriteLn(x);

  if false then
    x := 999;       { ветка удаляется целиком }
  WriteLn(x);
end.
```

```
Вывод:
14
14
14
15
15
```

### arrays.pas — массивы

```pascal
var a: array[1..5] of integer;
for i := 1 to 5 do
  a[i] := i * i;
for i := 1 to 5 do
  WriteLn(a[i]);
```

```
Вывод:
1
4
9
16
25
```

### sem_errors.pas — семантическая ошибка (пример)

```pascal
{ Этот файл намеренно содержит ошибку типов }
var x: integer;
begin
  x := true;   { ошибка: нельзя присвоить boolean в integer }
end.
```

```
[SemanticError] несовместимые типы в присваивании ... строка 3, позиция 3
```

### syntax_error.pas — синтаксическая ошибка (пример)

```pascal
{ Этот файл намеренно содержит синтаксическую ошибку }
var x: integer
begin
  x := 1;
end.
```

```
[ParserError] ожидался ';' ... строка 2, позиция 15
```

---

## Запуск через Docker

### Сборка образа

```bash
# Из папки pascal_compiler_py/
docker build -t pascal-compiler .
```

Образ на базе `python:3.11-slim` включает:
- Python 3.11 + lark
- NASM (ассемблер)
- gcc + gcc-multilib (компиляция 32-битных ELF)

### Полный x86-цикл: Pascal → бинарник → запуск

**hello.pas**
```bash
docker run --entrypoint bash pascal-compiler -c "python run.py examples/hello.pas --x86 --out /tmp/out.asm && nasm -f elf32 /tmp/out.asm -o /tmp/out.o && gcc -m32 -no-pie /tmp/out.o -o /tmp/out && /tmp/out"
```

**factorial.pas**
```bash
docker run --entrypoint bash pascal-compiler -c "python run.py examples/factorial.pas --x86 --out /tmp/out.asm && nasm -f elf32 /tmp/out.asm -o /tmp/out.o && gcc -m32 -no-pie /tmp/out.o -o /tmp/out && /tmp/out"
```

**procedures.pas**
```bash
docker run --entrypoint bash pascal-compiler -c "python run.py examples/procedures.pas --x86 --out /tmp/out.asm && nasm -f elf32 /tmp/out.asm -o /tmp/out.o && gcc -m32 -no-pie /tmp/out.o -o /tmp/out && /tmp/out"
```

**for_loop.pas**
```bash
docker run --entrypoint bash pascal-compiler -c "python run.py examples/for_loop.pas --x86 --out /tmp/out.asm && nasm -f elf32 /tmp/out.asm -o /tmp/out.o && gcc -m32 -no-pie /tmp/out.o -o /tmp/out && /tmp/out"
```

**while_loop.pas**
```bash
docker run --entrypoint bash pascal-compiler -c "python run.py examples/while_loop.pas --x86 --out /tmp/out.asm && nasm -f elf32 /tmp/out.asm -o /tmp/out.o && gcc -m32 -no-pie /tmp/out.o -o /tmp/out && /tmp/out"
```

**inc_dec_abs.pas**
```bash
docker run --entrypoint bash pascal-compiler -c "python run.py examples/inc_dec_abs.pas --x86 --out /tmp/out.asm && nasm -f elf32 /tmp/out.asm -o /tmp/out.o && gcc -m32 -no-pie /tmp/out.o -o /tmp/out && /tmp/out"
```

### Сохранить .asm на хост

Добавьте `-v` для монтирования папки `examples`:

```bash
docker run --entrypoint bash \
  -v "$(pwd)/examples:/pascal/examples" \
  pascal-compiler -c "
    python run.py examples/factorial.pas --x86 --out examples/factorial.asm &&
    nasm -f elf32 examples/factorial.asm -o /tmp/out.o &&
    gcc -m32 -no-pie /tmp/out.o -o /tmp/out &&
    /tmp/out
  "
```

После выполнения файл `examples/factorial.asm` появится локально рядом с `.pas`.

### Запуск через VM (без NASM/gcc)

```bash
docker run pascal-compiler examples/factorial.pas --vm
```

---

## Структура проекта

```
pascal_compiler_py/
├── run.py                        # Точка входа, CLI
├── Dockerfile                    # Docker-образ (python + nasm + gcc-multilib)
├── README.md                     # Документация
│
├── compiler/
│   ├── pipeline.py               # Конвейер компиляции
│   ├── optimizer.py              # Оптимизации AST
│   ├── errors.py                 # CompilerException, ParserException, SemanticException
│   │
│   ├── frontend/
│   │   ├── pascal.lark           # Lark-грамматика языка Pascal
│   │   ├── parser.py             # Парсер: .pas → AST
│   │   ├── ast.py                # Определения узлов AST (dataclasses)
│   │   └── ast_printer.py        # ASCII-вывод дерева AST
│   │
│   ├── analysis/
│   │   ├── visitor.py            # Инфраструктура паттерна Visitor
│   │   └── semantic.py           # Семантический анализ и таблица символов
│   │
│   └── backend/
│       ├── vm/
│       │   ├── opcodes.py        # Набор инструкций VM (55 опкодов)
│       │   ├── codegen.py        # AST → байткод
│       │   └── vm.py             # Исполнитель байткода
│       └── x86/
│           └── codegen.py        # AST → NASM x86-32
│
└── examples/
    ├── hello.pas                 # Минимальная программа
    ├── factorial.pas             # Рекурсия
    ├── procedures.pas            # Процедуры и функции
    ├── arrays.pas                # Массивы
    ├── for_loop.pas              # Цикл for
    ├── while_loop.pas            # Цикл while
    ├── break_continue.pas        # break, continue
    ├── inc_dec_abs.pas           # Встроенные функции
    ├── variables.pas             # Переменные и выражения
    ├── if_else.pas               # Ветвление
    ├── expr_test.pas             # Приоритет операций
    ├── optimizations.pas         # Демонстрация оптимизаций
    ├── sem_errors.pas            # Пример семантической ошибки
    └── syntax_error.pas          # Пример синтаксической ошибки
```
