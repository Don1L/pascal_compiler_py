from enum import Enum, auto


class Op(Enum):
    #   Стек                        
    PUSH        = auto()   # PUSH value — положить константу на стек
    POP         = auto()   # POP                 — снять верхушку стека

    #   Переменные                     
    LOAD        = auto()   # LOAD name — загрузить значение переменной
    STORE       = auto()   # STORE name — сохранить верхушку в переменную
    LOAD_IDX    = auto()   # LOAD_IDX name — загрузить a[стек] (индекс берётся со стека)
    STORE_IDX   = auto()   # STORE_IDX name — a[стек[-2]] = стек[-1]

    #   Арифметика                     
    ADD         = auto()
    SUB         = auto()
    MUL         = auto()
    DIV         = auto()   # целочисленное
    MOD         = auto()
    NEG         = auto()   # унарный минус

    #   Сравнения (результат: True/False)
    EQ          = auto()
    NE          = auto()
    LT          = auto()
    LE          = auto()
    GT          = auto()
    GE          = auto()

    #   Логика                       
    AND         = auto()
    OR          = auto()
    NOT         = auto()

    #   Переходы                      
    JUMP        = auto()   # JUMP label — безусловный переход
    JUMP_FALSE  = auto()   # JUMP_FALSE label    — переход если False на стеке

    #   Функции
    CALL        = auto()   # CALL name n_args — вызов функции, n_args аргументов на стеке
    RETURN      = auto()   # RETURN — возврат (значение на стеке или None)
    RETURN_NONE = auto()   # RETURN_NONE — возврат из процедуры без значения

    #   Встроенные операции
    PRINT       = auto()   # PRINT newline — вывод верхушки стека
    READ        = auto()   # READ type name — ввод в переменную

    #   Системные функции
    INC         = auto()   # INC name
    DEC         = auto()   # DEC name
    ABS         = auto()   # ABS  — abs(стек)

    #   Конец программы
    HALT        = auto()


class Instr:
    """Одна инструкция байткода."""

    __slots__ = ('op', 'arg', 'row')

    def __init__(self, op: Op, arg=None, row: int = None):
        self.op  = op
        self.arg = arg
        self.row = row

    def __repr__(self) -> str:
        if self.arg is None:
            return self.op.name
        return f'{self.op.name} {self.arg!r}'
