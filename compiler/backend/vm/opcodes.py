from enum import Enum, auto


class Op(Enum):
    # Стек
    PUSH        = auto()
    POP         = auto()

    # Переменные
    LOAD        = auto()
    STORE       = auto()
    LOAD_IDX    = auto()
    STORE_IDX   = auto()

    # Арифметика
    ADD         = auto()
    SUB         = auto()
    MUL         = auto()
    DIV         = auto()
    MOD         = auto()
    NEG         = auto()

    # Сравнения
    EQ          = auto()
    NE          = auto()
    LT          = auto()
    LE          = auto()
    GT          = auto()
    GE          = auto()

    # Логика
    AND         = auto()
    OR          = auto()
    NOT         = auto()

    # Переходы
    JUMP        = auto()
    JUMP_FALSE  = auto()

    # Функции
    CALL        = auto()
    RETURN      = auto()
    RETURN_NONE = auto()

    # Ввод/вывод
    PRINT       = auto()
    READ        = auto()

    # Системные
    INC         = auto()
    DEC         = auto()
    ABS         = auto()

    HALT        = auto()


# Одна инструкция байткода
class Instr:

    __slots__ = ('op', 'arg', 'row')

    def __init__(self, op: Op, arg=None, row: int = None):
        self.op  = op
        self.arg = arg
        self.row = row

    def __repr__(self) -> str:
        if self.arg is None:
            return self.op.name
        return f'{self.op.name} {self.arg!r}'
