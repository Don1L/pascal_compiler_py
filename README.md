# Pascal Compiler

Компилятор подмножества Pascal с использованием lark. Два бэкенда: виртуальная машина (VM) и x86.

**Зависимости:** lark

```
pip install lark
```

---

## Язык

### Типы данных

| Тип | Пример |
|---|---|
| `integer` | `42`, `-7` |
| `boolean` | `true`, `false` |
| `char` | `'a'`, `''''` |
| `array[lo..hi] of T` | `array[1..10] of integer` |

### Операции

| Группа | Операции |
|---|---|
| Арифметика | `+`, `-`, `*`, `/`, `div`, `mod` |
| Сравнение | `=`, `<>`, `<`, `<=`, `>`, `>=` |
| Логика | `and`, `or`, `not` |
| Унарные | `+`, `-`, `not` |

> Для `integer` операции `/` и `div` идентичны.

### Операторы

| Оператор | Синтаксис |
|---|---|
| Присваивание | `x := expr` |
| Ветвление | `if cond then stmt` / `if cond then stmt else stmt` |
| while | `while cond do stmt` |
| repeat | `repeat stmt until cond` |
| for | `for i := a to b do stmt` / `for i := a downto b do stmt` |
| break, continue | в теле любого цикла |
| Блок | `begin stmt; stmt; ... end` |

### Процедуры и функции

| | Синтаксис |
|---|---|
| Процедура | `procedure Name(a: integer; b: boolean);` |
| Функция | `function fact(n: integer): integer;` |
| Возврат значения | `fact := n * fact(n - 1)` — присваивание имени функции |
| Локальные переменные | `var x: integer;` до `begin` |

Параметры передаются по значению. Рекурсия поддерживается.

### Встроенные функции

| Функция | Описание |
|---|---|
| `Write(x)`, `WriteLn(x)` | Вывод |
| `Read(x)`, `ReadLn(x)` | Ввод |
| `Inc(x)`, `Dec(x)` | Увеличить/уменьшить на 1 |
| `Abs(x)` | Модуль числа |

### Комментарии

| Вид | Синтаксис |
|---|---|
| Однострочный | `// текст` |
| Блочный | `{ текст }` или `(* текст *)` |

---

## Архитектура

```
.pas файл
   |
   v
[Parser]         pascal.lark + frontend/parser.py  ->  AST
   |
   v
[Semantic]       analysis/semantic.py              ->  аннотированный AST
   |
   v
[Optimizer]      optimizer.py                      ->  оптимизированный AST
   |
   +---> [VM codegen]   backend/vm/   ->  байткод -> выполнение
   +---> [x86 codegen]  backend/x86/  ->  .asm файл
```

**Оптимизации:** свёртка констант (`2 + 3*4` -> `14`), алгебраические упрощения (`x*1` -> `x`), удаление мёртвого кода (`if false then ...`).

---

## Запуск

```bash
python run.py <файл.pas> --vm          # запустить через VM
python run.py <файл.pas> --x86         # сгенерировать .asm
python run.py <файл.pas> --x86 --out result.asm
```

### Отладочные флаги

```bash
--ast          показать AST после парсинга
--sem          показать AST после семантики
--opt          показать AST после оптимизации
--dis          показать байткод VM
--parse-only   остановиться после парсинга
--sem-only     остановиться после семантики
--no-opt       отключить оптимизации
```

---

## Примеры

```bash
python run.py examples/factorial.pas --vm
python run.py examples/arrays.pas --vm
python run.py examples/break_continue.pas --vm

# посмотреть дерево
python run.py examples/factorial.pas --ast --parse-only

# байткод
python run.py examples/factorial.pas --vm --dis

# дерево до и после оптимизации
python run.py examples/optimizations.pas --sem --opt --parse-only
```

| Файл | Что внутри |
|---|---|
| `examples/hello.pas` | минимальная программа |
| `examples/factorial.pas` | рекурсивная функция |
| `examples/arrays.pas` | массивы, цикл for |
| `examples/procedures.pas` | процедуры и функции |
| `examples/while_loop.pas` | while |
| `examples/for_loop.pas` | for to/downto |
| `examples/break_continue.pas` | break, continue |
| `examples/inc_dec_abs.pas` | встроенные функции |
| `examples/optimizations.pas` | демонстрация оптимизаций |
| `examples/syntax_error.pas` | пример синтаксической ошибки |
| `examples/sem_errors.pas` | пример семантической ошибки |
