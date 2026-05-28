"""
vm.py — стековая виртуальная машина.

Цикл fetch-decode-execute:
  fetch  — читаем инструкцию по счётчику IP
  decode — смотрим op
  execute — выполняем, двигаем стек/память

Память:
  Каждый вызов функции создаёт новый Frame со своим словарём переменных.
  Глобальные переменные живут в Frame основного тела.
  Стек значений — общий (Python list).
"""

from compiler.backend.vm.opcodes import Op, Instr
from compiler.backend.vm.codegen import Bytecode
from compiler.frontend.ast import ProgramNode, VarDeclNode
from compiler.errors import RuntimeException


class Frame:
    """Фрейм вызова: локальные переменные + адрес возврата."""

    def __init__(self, code: list[Instr], ret_ip: int, ret_frame: 'Frame | None'):
        self.code      = code
        self.ip        = 0
        self.ret_ip    = ret_ip
        self.ret_frame = ret_frame
        self.vars: dict[str, object] = {}
        self.array_lo: dict[str, int] = {}  # lo для массивов

    def get(self, name: str):
        if name in self.vars:
            return self.vars[name]
        f = self.ret_frame
        while f:
            if name in f.vars:
                return f.vars[name]
            f = f.ret_frame
        raise RuntimeException(f'Переменная "{name}" не инициализирована')

    def get_lo(self, name: str) -> int:
        """Возвращает нижнюю границу массива."""
        f: Frame = self
        while f:
            if name in f.array_lo:
                return f.array_lo[name]
            f = f.ret_frame
        return 0

    def set(self, name: str, value):
        # Если переменная уже есть в цепочке — обновляем там
        f: Frame = self
        while f:
            if name in f.vars:
                f.vars[name] = value
                return
            f = f.ret_frame
        # Новая переменная — в текущий фрейм
        self.vars[name] = value


class VM:
    """Виртуальная машина."""

    def __init__(self):
        self._stack:  list = []
        self._frame:  Frame | None = None
        self._bc:     Bytecode | None = None

     
    #  Стек                                                                
     

    def _push(self, v):
        self._stack.append(v)

    def _pop(self):
        if not self._stack:
            raise RuntimeException('Стек пуст')
        return self._stack.pop()

    def _peek(self):
        return self._stack[-1]

     
    #  Запуск                                                              
     

    def run(self, bc: Bytecode, program: ProgramNode = None) -> None:
        self._bc = bc

        # Создаём главный фрейм
        main_frame = Frame(bc.main, -1, None)

        # Инициализируем глобальные переменные
        if program:
            for vd in program.var_decls:
                for var in vd.vars:
                    main_frame.vars[var.name] = self._default(vd.type)
                    if vd.type.name == 'array':
                        main_frame.array_lo[var.name] = vd.type.lo

        self._frame = main_frame
        self._execute()

    def _execute(self) -> None:
        frame = self._frame

        while True:
            instr = frame.code[frame.ip]
            frame.ip += 1
            op  = instr.op
            arg = instr.arg

            #   Стек  
            if op == Op.PUSH:
                self._push(arg)

            elif op == Op.POP:
                self._pop()

            #   Переменные                       
            elif op == Op.LOAD:
                self._push(frame.get(arg))

            elif op == Op.STORE:
                frame.set(arg, self._pop())

            elif op == Op.LOAD_IDX:
                idx = self._pop()
                arr = frame.get(arg)
                lo  = frame.get_lo(arg)
                self._push(arr[idx - lo])

            elif op == Op.STORE_IDX:
                idx   = self._pop()
                value = self._pop()
                arr   = frame.get(arg)
                lo    = frame.get_lo(arg)
                arr[idx - lo] = value

            #   Арифметика                       
            elif op == Op.ADD:
                b, a = self._pop(), self._pop()
                self._push(a + b)

            elif op == Op.SUB:
                b, a = self._pop(), self._pop()
                self._push(a - b)

            elif op == Op.MUL:
                b, a = self._pop(), self._pop()
                self._push(a * b)

            elif op == Op.DIV:
                b, a = self._pop(), self._pop()
                if b == 0:
                    raise RuntimeException('Деление на ноль', row=instr.row)
                self._push(a // b)

            elif op == Op.MOD:
                b, a = self._pop(), self._pop()
                if b == 0:
                    raise RuntimeException('Деление на ноль (mod)', row=instr.row)
                self._push(a % b)

            elif op == Op.NEG:
                self._push(-self._pop())

            #   Сравнения
            elif op == Op.EQ:
                b, a = self._pop(), self._pop(); self._push(a == b)
            elif op == Op.NE:
                b, a = self._pop(), self._pop(); self._push(a != b)
            elif op == Op.LT:
                b, a = self._pop(), self._pop(); self._push(a < b)
            elif op == Op.LE:
                b, a = self._pop(), self._pop(); self._push(a <= b)
            elif op == Op.GT:
                b, a = self._pop(), self._pop(); self._push(a > b)
            elif op == Op.GE:
                b, a = self._pop(), self._pop(); self._push(a >= b)

            #   Логика                         
            elif op == Op.AND:
                b, a = self._pop(), self._pop(); self._push(a and b)
            elif op == Op.OR:
                b, a = self._pop(), self._pop(); self._push(a or b)
            elif op == Op.NOT:
                self._push(not self._pop())

            #   Переходы                        
            elif op == Op.JUMP:
                frame.ip = arg

            elif op == Op.JUMP_FALSE:
                if not self._pop():
                    frame.ip = arg

            #   Функции
            elif op == Op.CALL:
                func_name, n_args = arg
                args = [self._pop() for _ in range(n_args)]
                args.reverse()

                if func_name not in self._bc.funcs:
                    raise RuntimeException(f'Функция "{func_name}" не найдена',
                                           row=instr.row)

                func_code = self._bc.funcs[func_name]
                new_frame = Frame(func_code, frame.ip, frame)

                # Параметры кладём как переменные — имена берём из программы
                # (хранятся в порядке объявления; используем позиционный доступ)
                # Простой вариант: параметры называем _arg0, _arg1, ...
                # Codegen при LOAD/STORE использует имя параметра из AST,
                # поэтому нам нужно хранить их под правильными именами.
                # Имена передаём через _bc.func_params (заполняется ниже).
                param_names = self._bc.func_params.get(func_name, [])
                for i, val in enumerate(args):
                    name = param_names[i] if i < len(param_names) else f'_arg{i}'
                    new_frame.vars[name] = val

                # Инициализируем локальные переменные функции
                for vd_info in self._bc.func_locals.get(func_name, []):
                    vname, vtype = vd_info
                    if vname not in new_frame.vars:
                        new_frame.vars[vname] = self._default_by_name(vtype)

                self._frame = new_frame
                frame = new_frame

            elif op == Op.RETURN:
                ret_val = self._pop()
                frame = frame.ret_frame
                self._frame = frame
                self._push(ret_val)

            elif op == Op.RETURN_NONE:
                frame = frame.ret_frame
                self._frame = frame

            #   Встроенные операции
            elif op == Op.PRINT:
                newline = arg
                val = self._pop()
                if isinstance(val, bool):
                    s = 'TRUE' if val else 'FALSE'
                else:
                    s = str(val)
                print(s, end='\n' if newline else '')

            elif op == Op.READ:
                type_name, var_name = arg
                raw = input()
                if 'integer' in type_name:
                    val = int(raw)
                elif 'boolean' in type_name:
                    val = raw.strip().lower() in ('true', '1', 'yes')
                elif 'char' in type_name:
                    val = raw[0] if raw else '\x00'
                else:
                    val = raw
                frame.set(var_name, val)

            elif op == Op.INC:
                frame.set(arg, frame.get(arg) + 1)

            elif op == Op.DEC:
                frame.set(arg, frame.get(arg) - 1)

            elif op == Op.ABS:
                self._push(abs(self._pop()))

            #   Конец программы
            elif op == Op.HALT:
                break

            else:
                raise RuntimeException(f'Неизвестная инструкция: {op}')

     
    #  Вспомогательные методы
     

    @staticmethod
    def _default(type_node) -> object:
        from compiler.frontend.ast import TypeNode
        if isinstance(type_node, TypeNode):
            name = type_node.name
            if name == 'integer': return 0
            if name == 'boolean': return False
            if name == 'char':    return '\x00'
            if name == 'array':
                lo, hi = type_node.lo, type_node.hi
                return [0] * (hi - lo + 1)
        return None

    @staticmethod
    def _default_by_name(type_name: str) -> object:
        if type_name == 'integer': return 0
        if type_name == 'boolean': return False
        if type_name == 'char':    return '\x00'
        return None
