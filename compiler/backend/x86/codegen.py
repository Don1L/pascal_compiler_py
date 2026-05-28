"""
codegen.py — компилятор из AST в x86 NASM-листинг (32-bit, Linux/libc).

Генерирует текстовый .asm файл который можно собрать командами:
    nasm -f elf32 output.asm -o output.o
    gcc -m32 output.o -o output
    ./output

Архитектура:
  - Глобальные переменные → секция .bss (resd/resb)
  - Локальные переменные функций → стек ([ebp - N])
  - Параметры функций → стек ([ebp + 8], [ebp + 12], ...)
  - Вычисления → через регистры eax/ebx/ecx/edx
  - WriteLn/Write → через printf из libc
  - ReadLn/Read   → через scanf из libc
  - Стековый фрейм: push ebp / mov ebp, esp / sub esp, N / pop ebp / ret
"""

from io import StringIO
from compiler.frontend.ast import *


 
# Вспомогательный класс для накопления строк asm
 

class AsmWriter:
    def __init__(self):
        self._buf = StringIO()

    def emit(self, line: str = '') -> None:
        self._buf.write(line + '\n')

    def label(self, name: str) -> None:
        self._buf.write(f'{name}:\n')

    def instr(self, op: str, *args) -> None:
        arg_str = ', '.join(str(a) for a in args)
        self._buf.write(f'    {op:<8} {arg_str}\n' if arg_str else f'    {op}\n')

    def comment(self, text: str) -> None:
        self._buf.write(f'    ; {text}\n')

    def section(self, name: str) -> None:
        self._buf.write(f'\nsection {name}\n')

    def getvalue(self) -> str:
        return self._buf.getvalue()


 
# Генератор x86
 

class X86CodeGen:

    def __init__(self):
        self._data   = AsmWriter()   # секция .data  (форматные строки)
        self._bss    = AsmWriter()   # секция .bss   (глобальные переменные)
        self._text   = AsmWriter()   # секция .text  (код)
        self._label_counter = 0

        # Имена строковых констант для форматов
        self._fmt_int  = '_fmt_int'
        self._fmt_bool_true  = '_fmt_true'
        self._fmt_bool_false = '_fmt_false'
        self._fmt_char = '_fmt_char'
        self._fmt_scan_int  = '_fmt_scan_int'
        self._fmt_scan_char = '_fmt_scan_char'
        self._fmt_nl   = '_fmt_nl'

        # Контекст: имя текущей функции и таблица локальных переменных
        self._current_func: str | None = None
        self._locals: dict[str, int] = {}   # имя → смещение от ebp (отрицательное)
        self._params: dict[str, int] = {}   # имя → смещение от ebp (положительное)
        self._local_size: int = 0

        # Глобальные переменные (для .bss)
        self._globals: set[str] = set()

        # Метки для break/continue
        self._loop_end_labels:   list[str] = []
        self._loop_start_labels: list[str] = []

    
    #  Метки
    

    def _new_label(self, name: str = 'L') -> str:
        self._label_counter += 1
        return f'.{name}_{self._label_counter}'

    
    #  Доступ к переменной
    

    def _var_ref(self, name: str) -> str:
        """Возвращает ссылку на переменную: [ebp±N] или [_name]."""
        if name in self._locals:
            return f'[ebp{self._locals[name]:+d}]'
        if name in self._params:
            return f'[ebp+{self._params[name]}]'
        return f'[_{name}]'

    def _var_ref_lea(self, name: str) -> str:
        """Адрес переменной для lea."""
        if name in self._locals:
            return f'ebp{self._locals[name]:+d}'
        if name in self._params:
            return f'ebp+{self._params[name]}'
        return f'_{name}'

    
    #  Секция .data
    

    def _init_data(self) -> None:
        self._data.section('.data')
        self._data.emit(f'{self._fmt_int}  db "%d", 0')
        self._data.emit(f'{self._fmt_nl}   db "%d", 10, 0')
        self._data.emit(f'{self._fmt_bool_true}  db "TRUE", 10, 0')
        self._data.emit(f'{self._fmt_bool_false} db "FALSE", 10, 0')
        self._data.emit(f'{self._fmt_char} db "%c", 0')
        self._data.emit(f'{self._fmt_scan_int}  db "%d", 0')
        self._data.emit(f'{self._fmt_scan_char} db " %c", 0')

    
    #  Выражения → результат в eax
    

    def _gen_expr(self, node: AstNode) -> None:
        t = self._text

        if isinstance(node, LiteralNode):
            if isinstance(node.value, bool):
                t.instr('mov', 'eax', 1 if node.value else 0)
            elif isinstance(node.value, int):
                t.instr('mov', 'eax', node.value)
            elif isinstance(node.value, str):
                # char — ASCII-код
                t.instr('mov', 'eax', ord(node.value[0]) if node.value else 0)

        elif isinstance(node, IdentNode):
            t.instr('mov', 'eax', f'dword {self._var_ref(node.name)}')

        elif isinstance(node, ArrayAccessNode):
            # Индекс в ecx, база в edx
            self._gen_expr(node.index)
            t.instr('mov', 'ecx', 'eax')
            # lo хранится в типе — для простоты считаем lo=1 если не 0
            lo = 0
            if node.arr.node_type and node.arr.node_type.is_array:
                lo = node.arr.node_type.lo
            if lo:
                t.instr('sub', 'ecx', lo)
            t.instr('lea', 'edx', f'[{self._var_ref_lea(node.arr.name)}]')
            t.instr('mov', 'eax', f'dword [edx + ecx*4]')

        elif isinstance(node, UnOpNode):
            self._gen_expr(node.arg)
            if node.op == UnOp.MINUS:
                t.instr('neg', 'eax')
            elif node.op == UnOp.NOT:
                t.instr('xor', 'eax', 1)   # 0→1, 1→0 для boolean

        elif isinstance(node, BinOpNode):
            self._gen_binop(node)

        elif isinstance(node, CallNode):
            self._gen_call_expr(node)

        elif isinstance(node, TypeConvertNode):
            self._gen_expr(node.value)

    def _gen_binop(self, node: BinOpNode) -> None:
        t = self._text
        op = node.op

        # Ленивые вычисления and/or
        if op == BinOp.AND:
            false_lbl = self._new_label('and_false')
            end_lbl   = self._new_label('and_end')
            self._gen_expr(node.arg1)
            t.instr('test', 'eax', 'eax')
            t.instr('jz', false_lbl)
            self._gen_expr(node.arg2)
            t.instr('test', 'eax', 'eax')
            t.instr('jz', false_lbl)
            t.instr('mov', 'eax', 1)
            t.instr('jmp', end_lbl)
            t.label(false_lbl)
            t.instr('mov', 'eax', 0)
            t.label(end_lbl)
            return

        if op == BinOp.OR:
            true_lbl = self._new_label('or_true')
            end_lbl  = self._new_label('or_end')
            self._gen_expr(node.arg1)
            t.instr('test', 'eax', 'eax')
            t.instr('jnz', true_lbl)
            self._gen_expr(node.arg2)
            t.instr('test', 'eax', 'eax')
            t.instr('jnz', true_lbl)
            t.instr('mov', 'eax', 0)
            t.instr('jmp', end_lbl)
            t.label(true_lbl)
            t.instr('mov', 'eax', 1)
            t.label(end_lbl)
            return

        # Вычисляем arg1 → eax, сохраняем на стек, arg2 → eax, берём обратно
        self._gen_expr(node.arg1)
        t.instr('push', 'eax')
        self._gen_expr(node.arg2)
        t.instr('mov', 'ebx', 'eax')   # ebx = arg2
        t.instr('pop', 'eax')           # eax = arg1

        if op == BinOp.ADD:
            t.instr('add', 'eax', 'ebx')
        elif op == BinOp.SUB:
            t.instr('sub', 'eax', 'ebx')
        elif op == BinOp.MUL:
            t.instr('imul', 'eax', 'ebx')
        elif op in (BinOp.DIV, BinOp.FDIV):
            t.instr('cdq')
            t.instr('idiv', 'ebx')
        elif op == BinOp.MOD:
            t.instr('cdq')
            t.instr('idiv', 'ebx')
            t.instr('mov', 'eax', 'edx')   # остаток в edx
        else:
            # Сравнения → результат 0 или 1 в eax
            t.instr('cmp', 'eax', 'ebx')
            t.instr('mov', 'eax', 0)
            t.instr('mov', 'ecx', 1)
            jmp = {
                BinOp.EQ: 'cmove',
                BinOp.NE: 'cmovne',
                BinOp.LT: 'cmovl',
                BinOp.LE: 'cmovle',
                BinOp.GT: 'cmovg',
                BinOp.GE: 'cmovge',
            }[op]
            t.instr(jmp, 'eax', 'ecx')

    def _gen_call_expr(self, node: CallNode) -> None:
        """Вызов функции как выражения (результат в eax)."""
        t = self._text
        name = node.name.name.lower()

        if name == 'abs':
            self._gen_expr(node.params[0])
            lbl = self._new_label('abs_pos')
            t.instr('test', 'eax', 'eax')
            t.instr('jns', lbl)
            t.instr('neg', 'eax')
            t.label(lbl)
            return

        # Пользовательская функция
        # Аргументы пушим справа налево
        for p in reversed(node.params):
            self._gen_expr(p)
            t.instr('push', 'eax')
        func_label = f'_func_{node.name.name}'
        t.instr('call', func_label)
        if node.params:
            t.instr('add', 'esp', len(node.params) * 4)

    
    #  Операторы
    

    def _gen_stmt(self, node: AstNode) -> None:
        t = self._text

        if isinstance(node, StmtListNode):
            for stmt in node.stmts:
                self._gen_stmt(stmt)

        elif isinstance(node, VarDeclNode):
            pass  # уже объявлены в прологе

        elif isinstance(node, AssignNode):
            self._gen_assign(node)

        elif isinstance(node, IfNode):
            self._gen_if(node)

        elif isinstance(node, WhileNode):
            self._gen_while(node)

        elif isinstance(node, RepeatNode):
            self._gen_repeat(node)

        elif isinstance(node, ForNode):
            self._gen_for(node)

        elif isinstance(node, BreakNode):
            t.instr('jmp', self._loop_end_labels[-1])

        elif isinstance(node, ContinueNode):
            t.instr('jmp', self._loop_start_labels[-1])

        elif isinstance(node, ReturnNode):
            if node.value:
                self._gen_expr(node.value)
            self._gen_epilogue()
            t.instr('ret')

        elif isinstance(node, CallNode):
            self._gen_call_stmt(node)

    def _gen_assign(self, node: AssignNode) -> None:
        t = self._text

        # Pascal-стиль: funcname := value = return
        if isinstance(node.var, IdentNode) and node.var.name == self._current_func:
            self._gen_expr(node.value)
            self._gen_epilogue()
            t.instr('ret')
            return

        self._gen_expr(node.value)

        if isinstance(node.var, ArrayAccessNode):
            t.instr('push', 'eax')   # сохраняем значение
            # Вычисляем индекс
            self._gen_expr(node.var.index)
            t.instr('mov', 'ecx', 'eax')
            lo = 0
            if node.var.arr.node_type and node.var.arr.node_type.is_array:
                lo = node.var.arr.node_type.lo
            if lo:
                t.instr('sub', 'ecx', lo)
            t.instr('pop', 'eax')
            t.instr('lea', 'edx', f'[{self._var_ref_lea(node.var.arr.name)}]')
            t.instr('mov', f'dword [edx + ecx*4]', 'eax')
        else:
            t.instr('mov', f'dword {self._var_ref(node.var.name)}', 'eax')

    def _gen_if(self, node: IfNode) -> None:
        t = self._text
        else_lbl = self._new_label('else')
        end_lbl  = self._new_label('if_end')

        self._gen_expr(node.cond)
        t.instr('test', 'eax', 'eax')
        t.instr('jz', else_lbl)
        self._gen_stmt(node.then_stmt)
        t.instr('jmp', end_lbl)
        t.label(else_lbl)
        if node.else_stmt:
            self._gen_stmt(node.else_stmt)
        t.label(end_lbl)

    def _gen_while(self, node: WhileNode) -> None:
        t = self._text
        start = self._new_label('while_start')
        end   = self._new_label('while_end')

        self._loop_start_labels.append(start)
        self._loop_end_labels.append(end)

        t.label(start)
        self._gen_expr(node.cond)
        t.instr('test', 'eax', 'eax')
        t.instr('jz', end)
        self._gen_stmt(node.body)
        t.instr('jmp', start)
        t.label(end)

        self._loop_start_labels.pop()
        self._loop_end_labels.pop()

    def _gen_repeat(self, node: RepeatNode) -> None:
        t = self._text
        start = self._new_label('repeat_start')
        end   = self._new_label('repeat_end')

        self._loop_start_labels.append(start)
        self._loop_end_labels.append(end)

        t.label(start)
        self._gen_stmt(node.body)
        self._gen_expr(node.cond)
        t.instr('test', 'eax', 'eax')
        t.instr('jz', start)
        t.label(end)

        self._loop_start_labels.pop()
        self._loop_end_labels.pop()

    def _gen_for(self, node: ForNode) -> None:
        t = self._text
        start = self._new_label('for_start')
        end   = self._new_label('for_end')

        self._loop_start_labels.append(start)
        self._loop_end_labels.append(end)

        var_ref = self._var_ref(node.var.name)

        # Инициализация
        self._gen_expr(node.start)
        t.instr('mov', f'dword {var_ref}', 'eax')

        t.label(start)
        # Условие
        t.instr('mov', 'eax', f'dword {var_ref}')
        self._gen_expr(node.finish)
        t.instr('mov', 'ebx', 'eax')
        t.instr('mov', 'eax', f'dword {var_ref}')
        t.instr('cmp', 'eax', 'ebx')
        if node.downto:
            t.instr('jl', end)
        else:
            t.instr('jg', end)

        # Тело
        self._gen_stmt(node.body)

        # Шаг
        if node.downto:
            t.instr('dec', f'dword {var_ref}')
        else:
            t.instr('inc', f'dword {var_ref}')
        t.instr('jmp', start)
        t.label(end)

        self._loop_start_labels.pop()
        self._loop_end_labels.pop()

    def _gen_call_stmt(self, node: CallNode) -> None:
        t = self._text
        name = node.name.name.lower()

        if name in ('write', 'writeln'):
            newline = (name == 'writeln')
            for p in node.params:
                ptype = p.node_type
                self._gen_expr(p)
                t.instr('push', 'eax')
                if ptype and str(ptype) == 'boolean':
                    # boolean: печатаем TRUE/FALSE
                    t.instr('pop', 'eax')
                    lbl_true = self._new_label('bool_true')
                    lbl_end  = self._new_label('bool_end')
                    t.instr('test', 'eax', 'eax')
                    t.instr('jnz', lbl_true)
                    t.instr('push', self._fmt_bool_false)
                    t.instr('call', 'printf')
                    t.instr('add', 'esp', 4)
                    t.instr('jmp', lbl_end)
                    t.label(lbl_true)
                    t.instr('push', self._fmt_bool_true)
                    t.instr('call', 'printf')
                    t.instr('add', 'esp', 4)
                    t.label(lbl_end)
                elif ptype and str(ptype) == 'char':
                    fmt = self._fmt_char
                    t.instr('push', fmt)
                    t.instr('call', 'printf')
                    t.instr('add', 'esp', 8)
                else:
                    fmt = self._fmt_nl if newline else self._fmt_int
                    t.instr('push', fmt)
                    t.instr('call', 'printf')
                    t.instr('add', 'esp', 8)
            return

        if name in ('read', 'readln'):
            for p in node.params:
                ptype = p.node_type
                if ptype and str(ptype) == 'char':
                    fmt = self._fmt_scan_char
                else:
                    fmt = self._fmt_scan_int
                t.instr('lea', 'eax', f'[{self._var_ref_lea(p.name)}]')
                t.instr('push', 'eax')
                t.instr('push', fmt)
                t.instr('call', 'scanf')
                t.instr('add', 'esp', 8)
            return

        if name == 'inc':
            t.instr('inc', f'dword {self._var_ref(node.params[0].name)}')
            return

        if name == 'dec':
            t.instr('dec', f'dword {self._var_ref(node.params[0].name)}')
            return

        if name == 'abs':
            self._gen_expr(node.params[0])
            lbl = self._new_label('abs_pos')
            t.instr('test', 'eax', 'eax')
            t.instr('jns', lbl)
            t.instr('neg', 'eax')
            t.label(lbl)
            return

        # Пользовательская процедура
        for p in reversed(node.params):
            self._gen_expr(p)
            t.instr('push', 'eax')
        func_label = f'_func_{node.name.name}'
        t.instr('call', func_label)
        if node.params:
            t.instr('add', 'esp', len(node.params) * 4)

    
    #  Пролог / эпилог функции
    

    def _gen_prologue(self, local_size: int) -> None:
        t = self._text
        t.instr('push', 'ebp')
        t.instr('mov', 'ebp', 'esp')
        if local_size:
            t.instr('sub', 'esp', local_size)

    def _gen_epilogue(self) -> None:
        t = self._text
        t.instr('mov', 'esp', 'ebp')
        t.instr('pop', 'ebp')

    
    #  Вычисление размера локальных переменных
    

    def _setup_locals(self, var_decls: list, params: list) -> int:
        """Заполняет self._locals и self._params, возвращает размер локальных."""
        self._locals = {}
        self._params = {}
        offset = 0

        for vd in var_decls:
            for var in vd.vars:
                if vd.type.name == 'array':
                    size = (vd.type.hi - vd.type.lo + 1) * 4
                else:
                    size = 4
                offset += size
                self._locals[var.name] = -offset

        # Параметры: [ebp+8], [ebp+12], ...
        param_offset = 8
        for p in params:
            self._params[p.name.name] = param_offset
            param_offset += 4

        return offset

    
    #  Глобальные переменные → .bss
    

    def _declare_globals(self, var_decls: list) -> None:
        for vd in var_decls:
            for var in vd.vars:
                self._globals.add(var.name)
                if vd.type.name == 'array':
                    size = (vd.type.hi - vd.type.lo + 1) * 4
                    self._bss.emit(f'    _{var.name} resd {vd.type.hi - vd.type.lo + 1}')
                else:
                    self._bss.emit(f'    _{var.name} resd 1')

    
    #  Генерация функции
    

    def _gen_func(self, func: FuncNode) -> None:
        t = self._text
        name = func.name.name
        self._current_func = name

        local_size = self._setup_locals(func.var_decls, func.params)

        t.emit()
        t.comment(f'--- {"function" if func.return_type else "procedure"} {name} ---')
        t.label(f'_func_{name}')
        self._gen_prologue(local_size)

        self._gen_stmt(func.body)

        # Дефолтный эпилог (для процедур и функций без явного return)
        self._gen_epilogue()
        t.instr('ret')

        self._current_func = None

    
    #  Точка входа — генерация программы
    

    def generate(self, program: ProgramNode) -> str:
        # .data
        self._init_data()

        # .bss — глобальные переменные
        self._bss.section('.bss')
        self._declare_globals(program.var_decls)

        # .text — заголовок
        self._text.section('.text')
        self._text.emit('    global main')
        self._text.emit('    extern printf, scanf')

        # Функции и процедуры
        for func in program.func_decls:
            self._gen_func(func)

        # main
        self._current_func = None
        self._locals = {}
        self._params = {}

        self._text.emit()
        self._text.comment('--- main ---')
        self._text.label('main')
        self._gen_prologue(0)

        self._gen_stmt(program.body)

        self._gen_epilogue()
        self._text.instr('xor', 'eax', 'eax')   # return 0
        self._text.instr('ret')

        # Собираем всё вместе
        out = StringIO()
        out.write('; Generated by Pascal x86 compiler\n')
        out.write('; Build: nasm -f elf32 output.asm -o output.o\n')
        out.write(';        gcc -m32 -no-pie output.o -o output\n')
        out.write('\n')
        out.write(self._data.getvalue())
        out.write(self._bss.getvalue())
        out.write(self._text.getvalue())
        out.write('\nsection .note.GNU-stack noalloc noexec nowrite progbits\n')
        return out.getvalue()


 
# Публичная функция
 

def compile_to_x86(program: ProgramNode) -> str:
    """Возвращает строку с NASM-листингом."""
    return X86CodeGen().generate(program)
