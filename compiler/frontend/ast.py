from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from compiler.analysis.semantic import TypeDesc, IdentDesc


def ast_dataclass(cls, **kwargs):
    """dataclass без автоматического repr — используем свой __str__"""
    return dataclass(cls, repr=False, **kwargs)


# Базовые классы

class AstNode(ABC):
    """Базовый класс всех узлов AST."""

    row: int = None
    col: int = None
    node_type: 'TypeDesc' = None   # заполняется семантическим анализатором
    node_ident: 'IdentDesc' = None  # заполняется семантическим анализатором

    @property
    def children(self) -> Sequence['AstNode']:
        """Дети узла — все поля-AstNode и элементы полей-Sequence[AstNode]."""
        result: list[AstNode] = []
        for v in self.__dict__.values():
            if isinstance(v, AstNode):
                result.append(v)
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, AstNode):
                        result.append(item)
        return result

    def __str__(self) -> str:
        # Пробуем найти «говорящее» поле
        for field_name in ('name', 'op', 'type', 'desc', 'literal'):
            if hasattr(self, field_name):
                val = getattr(self, field_name)
                if val is None:
                    continue
                if hasattr(val, 'value'):       # Enum
                    return str(val.value)
                if isinstance(val, AstNode):
                    return str(val)
                return str(val)
        # Fallback: имя класса
        name = self.__class__.__name__
        if name.endswith('Node'):
            name = name[:-4].lower()
        return name


class ExprNode(AstNode, ABC):
    pass


class ValueNode(ExprNode, ABC):
    pass


class StmtNode(AstNode, ABC):
    pass



# Литералы и идентификаторы


@ast_dataclass
class LiteralNode(ValueNode):
    """Литерал: целое число, boolean, char."""
    literal: str
    value: Any

    def __init__(self, literal: str) -> None:
        self.literal = str(literal)
        low = literal.lower()
        if low == 'true':
            self.value = True
        elif low == 'false':
            self.value = False
        elif literal.startswith("'") and literal.endswith("'"):
            inner = literal[1:-1]
            self.value = inner.replace("''", "'")
        else:
            try:
                self.value = int(literal)
            except ValueError:
                self.value = float(literal)

    def __str__(self) -> str:
        return self.literal


@ast_dataclass
class IdentNode(ExprNode):
    """Имя переменной / функции."""
    name: str

    def __str__(self) -> str:
        return self.name


@ast_dataclass
class TypeNode(ExprNode):
    """Узел типа данных: integer, boolean, char, array[lo..hi] of T."""
    name: str                        # 'integer' | 'boolean' | 'char' | 'array'
    elem_type: Optional['TypeNode'] = None  # для array
    lo: Optional[int] = None
    hi: Optional[int] = None

    def __str__(self) -> str:
        if self.name == 'array':
            return f'array[{self.lo}..{self.hi}] of {self.elem_type}'
        return self.name



# Операторы


class BinOp(Enum):
    ADD = '+'
    SUB = '-'
    MUL = '*'
    FDIV = '/'      # вещественное деление (на всякий случай)
    DIV = 'div'
    MOD = 'mod'
    GT = '>'
    GE = '>='
    LT = '<'
    LE = '<='
    EQ = '='
    NE = '<>'
    AND = 'and'
    OR = 'or'

    def __str__(self):
        return self.value


class UnOp(Enum):
    NOT = 'not'
    PLUS = '+'
    MINUS = '-'

    def __str__(self):
        return self.value



# Выражения


@ast_dataclass
class BinOpNode(ExprNode):
    op: BinOp
    arg1: ExprNode
    arg2: ExprNode


@ast_dataclass
class UnOpNode(ExprNode):
    op: UnOp
    arg: ExprNode


@ast_dataclass
class AssignNode(StmtNode):
    var: ExprNode       # IdentNode или ArrayAccessNode
    value: ExprNode


@ast_dataclass
class ArrayAccessNode(ExprNode):
    """Обращение к элементу массива: a[i]"""
    arr: IdentNode
    index: ExprNode

    def __str__(self) -> str:
        return f'{self.arr}[]'


@ast_dataclass
class CallNode(ExprNode, StmtNode):
    """Вызов функции / процедуры: Write, WriteLn, Inc, Dec, Abs, пользовательские."""
    name: IdentNode
    params: Sequence[ExprNode]

    def __init__(self, name: IdentNode, *params: ExprNode) -> None:
        self.name = name
        self.params = params[0] if len(params) == 1 and isinstance(params[0], (list, tuple)) else params

    def __str__(self) -> str:
        return f'{self.name}()'



# Объявления


@ast_dataclass
class VarDeclNode(StmtNode):
    """Объявление одной или нескольких переменных одного типа: x, y: integer"""
    type: TypeNode
    vars: Sequence[IdentNode]

    def __init__(self, type_: TypeNode, *vars_: IdentNode) -> None:
        self.type = type_
        self.vars = vars_[0] if len(vars_) == 1 and isinstance(vars_[0], (list, tuple)) else vars_

    def __str__(self) -> str:
        return str(self.type)


@ast_dataclass
class ParamNode(StmtNode):
    """Параметр функции/процедуры: a: integer"""
    type: TypeNode
    name: IdentNode

    def __str__(self) -> str:
        return f'{self.name}: {self.type}'


@ast_dataclass
class FuncNode(StmtNode):
    """Объявление функции или процедуры."""
    return_type: Optional[TypeNode]   # None для procedure
    name: IdentNode
    params: Sequence[ParamNode]
    var_decls: Sequence[VarDeclNode]
    body: 'StmtListNode'

    def __str__(self) -> str:
        kind = 'procedure' if self.return_type is None else 'function'
        params = ', '.join(str(p) for p in self.params)
        return f'{kind} {self.name}({params})'



# Операторы (statements)


@ast_dataclass
class StmtListNode(StmtNode):
    """Последовательность операторов (begin … end или тело программы)."""
    stmts: Sequence[StmtNode]

    def __init__(self, *stmts: StmtNode) -> None:
        self.stmts = stmts[0] if len(stmts) == 1 and isinstance(stmts[0], (list, tuple)) else stmts

    def __str__(self) -> str:
        return '...'


@ast_dataclass
class IfNode(StmtNode):
    cond: ExprNode
    then_stmt: StmtNode
    else_stmt: Optional[StmtNode] = None

    def __init__(self, cond: ExprNode, then_stmt: StmtNode,
                 else_stmt: Optional[StmtNode] = None) -> None:
        self.cond = cond
        self.then_stmt = then_stmt or StmtListNode()
        self.else_stmt = else_stmt

    def __str__(self) -> str:
        return 'if'


@ast_dataclass
class WhileNode(StmtNode):
    cond: ExprNode
    body: StmtNode

    def __init__(self, cond: ExprNode, body: StmtNode) -> None:
        self.cond = cond
        self.body = body or StmtListNode()

    def __str__(self) -> str:
        return 'while'


@ast_dataclass
class RepeatNode(StmtNode):
    """repeat … until cond"""
    body: StmtListNode
    cond: ExprNode

    def __str__(self) -> str:
        return 'repeat'


@ast_dataclass
class ForNode(StmtNode):
    """for var := start to/downto finish do body"""
    var: IdentNode
    start: ExprNode
    finish: ExprNode
    downto: bool
    body: StmtNode

    def __str__(self) -> str:
        direction = 'downto' if self.downto else 'to'
        return f'for ({direction})'


@ast_dataclass
class BreakNode(StmtNode):
    def __str__(self) -> str:
        return 'break'


@ast_dataclass
class ContinueNode(StmtNode):
    def __str__(self) -> str:
        return 'continue'


@ast_dataclass
class ReturnNode(StmtNode):
    value: Optional[ExprNode] = None

    def __str__(self) -> str:
        return 'return'



# Корень программы


@ast_dataclass
class ProgramNode(AstNode):
    """Корень AST: program Name; var ...; begin ... end."""
    name: IdentNode
    var_decls: Sequence[VarDeclNode]
    func_decls: Sequence[FuncNode]
    body: StmtListNode

    def __str__(self) -> str:
        return f'program {self.name}'



# Узел преобразования типов (вставляется семантическим анализатором)


@ast_dataclass
class TypeConvertNode(ExprNode):
    """Неявное приведение типа, добавляемое семантикой."""
    value: ExprNode
    type: 'TypeDesc'

    def __init__(self, expr: ExprNode, type_: 'TypeDesc') -> None:
        self.value = expr
        self.type = type_
        self.node_type = type_

    def __str__(self) -> str:
        return f'({self.type})'
