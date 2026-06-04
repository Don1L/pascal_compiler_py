# Pascal Compiler

Учебный компилятор подмножества языка Pascal на Python. Реализует полный конвейер компиляции: лексический и синтаксический анализ, семантический анализ, оптимизацию AST и генерацию кода для двух бэкендов — стековой виртуальной машины и x86-32 (NASM).

**Зависимости:** Python 3.11+, [lark](https://github.com/lark-parser/lark)

```bash
pip install lark
```

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

Структура программы:

```pascal
program <Имя>;
var <переменные>;
<функции и процедуры>
begin <операторы> end.
```

### Типы данных

| Тип | Примеры |
|-----|---------|
| `integer` | `42`, `-7` |
| `boolean` | `true`, `false` |
| `char` | `'a'`, `''''` |
| `array[lo..hi] of T` | `array[1..10] of integer` |

### Операции

| Группа | Операции | Результат |
|--------|----------|-----------|
| Арифметика | `+`, `-`, `*`, `/`, `div`, `mod` | `integer` |
| Сравнение | `=`, `<>`, `<`, `<=`, `>`, `>=` | `boolean` |
| Логика | `and`, `or`, `not` | `boolean` |
| Унарные | `+`, `-`, `not` | — |

Приоритет: `not`/унарный → `*`/`div`/`mod`/`and` → `+`/`-`/`or` → сравнение. `/` и `div` идентичны для `integer`. `and`/`or` — ленивые.

### Управляющие конструкции

```pascal
x := expr;                          { присваивание }
a[i] := expr;                       { элемент массива }
if cond then stmt [else stmt];      { ветвление }
while cond do stmt;                 { цикл while }
repeat stmt until cond;             { цикл repeat }
for i := a to b do stmt;           { for (downto — убывающий) }
begin stmt; stmt; ... end           { блок; ; — разделитель, не терминатор }
```

`break` и `continue` работают внутри любого цикла.

### Процедуры и функции

```pascal
procedure Foo(x: integer);
begin WriteLn(x); end;

function Max(a: integer; b: integer): integer;
var tmp: integer;
begin
  if a > b then Max := a else Max := b;
end;
```

Возврат — присвоение имени функции: `Max := value`. Параметры по значению. Рекурсия поддерживается.

### Встроенные функции

| Функция | Описание |
|---------|----------|
| `Write(x)`, `WriteLn(x)` | Вывод `integer`/`boolean`/`char`; `boolean` → `TRUE`/`FALSE` |
| `Read(x)`, `ReadLn(x)` | Ввод в переменную |
| `Inc(x)`, `Dec(x)` | `x ± 1` |
| `Abs(x)` | Модуль числа |

### Комментарии

```pascal
// однострочный    { блочный }    (* блочный *)
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

Парсер использует **Lark** (алгоритм Earley), грамматика в `pascal.lark`, регистронезависима. Результат — дерево `AstNode`-объектов: `ProgramNode`, `FuncNode`, `AssignNode`, `IfNode`, `WhileNode`, `ForNode`, `RepeatNode`, `CallNode`, `BinOpNode`, `LiteralNode`, `IdentNode`, `ArrayAccessNode` и др.

```bash
python run.py examples/factorial.pas --ast --parse-only
```

```
program Factorial
+-- var n: integer
+-- function fact(n: integer): integer
|   \-- if (n <= 1) → fact:=1 | fact:=n*fact(n-1)
\-- block
    +-- (n := 6)
    \-- WriteLn(fact(n))
```

### Семантический анализ

Строит таблицу символов (стек областей видимости) и проверяет:
- типы операндов и совместимость в операциях / присваивании
- объявленность переменных и функций, соответствие числа и типов аргументов
- `break`/`continue` только внутри цикла, условия `if`/`while` — `boolean`, индексы массивов — `integer`

```bash
python run.py examples/factorial.pas --sem --sem-only
```

### Оптимизации

За один проход по AST:

| Вид | Пример |
|-----|--------|
| Свёртка констант | `2 + 3*4` → `14` |
| Алгебраические упрощения | `x*1`→`x`, `x+0`→`x`, `not not x`→`x`, `x*0`→`0`, `-(-x)`→`x` |
| Мёртвый код | код после `break`/`continue`, `while false do ...`, `if false then ...` |

```bash
python run.py examples/optimizations.pas --sem --opt --sem-only
```

### Бэкенд: виртуальная машина

Стековая VM, 55 инструкций: `PUSH`/`POP`, `LOAD`/`STORE`, `LOAD_IDX`/`STORE_IDX`, арифметика (`ADD`/`SUB`/`MUL`/`DIV`/`MOD`/`NEG`), сравнение (`EQ`/`NE`/`LT`/`LE`/`GT`/`GE`), логика (`AND`/`OR`/`NOT`), переходы (`JUMP`/`JUMP_FALSE`), функции (`CALL`/`RETURN`), I/O (`PRINT`/`READ`), `INC`/`DEC`/`ABS`, `HALT`. Каждая функция получает свой фрейм с локальными переменными.

```bash
python run.py examples/factorial.pas --vm --dis
```

### Бэкенд: x86-32

Генерирует NASM-формат, Linux ELF 32-bit (System V ABI). Глобальные переменные — в `.bss`, вычисления — через регистры `eax`/`ebx`/`ecx`. Аргументы передаются через стек справа налево (`[ebp+8]`, `[ebp+12]`, ...), локальные переменные — `[ebp-4]`, `[ebp-8]`, ... Ввод/вывод через `printf`/`scanf`.

```bash
# Сборка на Linux:
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
