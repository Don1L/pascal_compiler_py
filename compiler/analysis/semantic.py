from enum import Enum
from typing import Optional, Sequence

from compiler.analysis import visitor
from compiler.frontend.ast import *
from compiler.errors import SemanticException


 
# Система типов
 

class BaseType(Enum):
    VOID    = 'void'
    INTEGER = 'integer'
    BOOLEAN = 'boolean'
    CHAR    = 'char'

    def __str__(self):
        return self.value


VOID, INTEGER, BOOLEAN, CHAR = (
    BaseType.VOID, BaseType.INTEGER, BaseType.BOOLEAN, BaseType.CHAR
)


class TypeDesc:
    """Описание типа: простой (integer/boolean/char) или функция, или массив."""

    VOID:    'TypeDesc'
    INTEGER: 'TypeDesc'
    BOOLEAN: 'TypeDesc'
    CHAR:    'TypeDesc'

    def __init__(
        self,
        base: BaseType = None,
        *,
        return_type: 'TypeDesc' = None,
        params: Sequence['TypeDesc'] = None,
        is_array: bool = False,
        elem_type: 'TypeDesc' = None,
        lo: int = None,
        hi: int = None,
    ) -> None:
        self.base = base
        self.return_type = return_type
        self.params = params or []
        self.is_array = is_array
        self.elem_type = elem_type
        self.lo = lo
        self.hi = hi

    @property
    def is_func(self) -> bool:
        return self.return_type is not None

    @property
    def is_simple(self) -> bool:
        return not self.is_func and not self.is_array

    def __hash__(self):
        if self.is_array:
            return hash(('array', self.elem_type, self.lo, self.hi))
        if self.is_func:
            return hash(('func', self.return_type, tuple(self.params)))
        return hash(self.base)

    def __eq__(self, other: 'TypeDesc') -> bool:
        if not isinstance(other, TypeDesc):
            return False
        if self.is_array and other.is_array:
            return self.elem_type == other.elem_type
        if self.is_func != other.is_func:
            return False
        if self.is_func:
            return (self.return_type == other.return_type
                    and len(self.params) == len(other.params)
                    and all(a == b for a, b in zip(self.params, other.params)))
        return self.base == other.base

    @staticmethod
    def from_str(name: str) -> 'TypeDesc':
        name = name.lower()
        mapping = {'integer': INTEGER, 'boolean': BOOLEAN, 'char': CHAR, 'void': VOID}
        if name not in mapping:
            raise SemanticException(f'Неизвестный тип: {name}')
        return mapping[name]

    @staticmethod
    def array_of(elem: 'TypeDesc', lo: int, hi: int) -> 'TypeDesc':
        t = TypeDesc(is_array=True, elem_type=elem, lo=lo, hi=hi)
        return t

    def __str__(self) -> str:
        if self.is_array:
            return f'array[{self.lo}..{self.hi}] of {self.elem_type}'
        if self.is_func:
            params = ', '.join(str(p) for p in self.params)
            return f'{self.return_type}({params})'
        return str(self.base)


# Синглтоны для базовых типов
for _bt in BaseType:
    setattr(TypeDesc, _bt.name, TypeDesc(_bt))
INTEGER = TypeDesc.INTEGER  # noqa
BOOLEAN = TypeDesc.BOOLEAN  # noqa
CHAR    = TypeDesc.CHAR     # noqa
VOID    = TypeDesc.VOID     # noqa


 
# Таблица символов
 

class ScopeKind(Enum):
    GLOBAL = 'global'
    LOCAL  = 'local'
    PARAM  = 'param'

    def __str__(self):
        return self.value


class IdentDesc:
    """Запись о переменной/функции в таблице символов."""

    def __init__(self, name: str, type_: TypeDesc,
                 scope: ScopeKind = ScopeKind.GLOBAL, index: int = 0) -> None:
        self.name  = name
        self.type  = type_
        self.scope = scope
        self.index = index
        self.built_in = False

    def __str__(self) -> str:
        extra = ', built-in' if self.built_in else f', idx={self.index}'
        return f'{self.type}, {self.scope}{extra}'


class IdentScope:
    """Область видимости — узел связного списка областей."""

    def __init__(self, parent: 'IdentScope' = None,
                 func: IdentDesc = None,
                 loop: AstNode = None) -> None:
        self.idents:      dict[str, IdentDesc] = {}
        self.parent:      Optional[IdentScope] = parent
        self.func:        Optional[IdentDesc]  = func
        self.loop:        Optional[AstNode]    = loop
        self._var_index:  int = 0
        self._param_index: int = 0

    @property
    def is_global(self) -> bool:
        return self.parent is None

    @property
    def global_scope(self) -> 'IdentScope':
        curr = self
        while curr.parent:
            curr = curr.parent
        return curr

    @property
    def func_scope(self) -> Optional['IdentScope']:
        curr = self
        while curr and not curr.func:
            curr = curr.parent
        return curr

    @property
    def loop_scope(self) -> Optional['IdentScope']:
        curr = self
        while curr and not curr.loop:
            curr = curr.parent
        return curr

    def add(self, ident: IdentDesc) -> IdentDesc:
        old = self.get(ident.name)
        if old:
            # Разрешаем перекрытие глобальной переменной локальной
            if not (self.func_scope and old.scope == ScopeKind.GLOBAL):
                raise SemanticException(f'Идентификатор "{ident.name}" уже объявлен')

        if not ident.type.is_func:
            if ident.scope == ScopeKind.PARAM:
                fs = self.func_scope or self
                ident.index = fs._param_index
                fs._param_index += 1
            else:
                ident.scope = ScopeKind.LOCAL if self.func_scope else ScopeKind.GLOBAL
                ident.index = self._var_index
                self._var_index += 1

        self.idents[ident.name] = ident
        return ident

    def get(self, name: str) -> Optional[IdentDesc]:
        name_lo = name.lower()
        curr = self
        while curr:
            if name in curr.idents:
                return curr.idents[name]
            for k, v in curr.idents.items():
                if k.lower() == name_lo:
                    return v
            curr = curr.parent
        return None


 
# Таблицы совместимости типов для операций
 

UN_OP_TYPES: dict[UnOp, dict[TypeDesc, TypeDesc]] = {
    UnOp.NOT:   {BOOLEAN: BOOLEAN},
    UnOp.PLUS:  {INTEGER: INTEGER},
    UnOp.MINUS: {INTEGER: INTEGER},
}

BIN_OP_TYPES: dict[BinOp, dict[tuple, TypeDesc]] = {
    BinOp.ADD:  {(INTEGER, INTEGER): INTEGER},
    BinOp.SUB:  {(INTEGER, INTEGER): INTEGER},
    BinOp.MUL:  {(INTEGER, INTEGER): INTEGER},
    BinOp.DIV:  {(INTEGER, INTEGER): INTEGER},
    BinOp.FDIV: {(INTEGER, INTEGER): INTEGER},
    BinOp.MOD:  {(INTEGER, INTEGER): INTEGER},

    BinOp.GT:   {(INTEGER, INTEGER): BOOLEAN, (CHAR, CHAR): BOOLEAN},
    BinOp.GE:   {(INTEGER, INTEGER): BOOLEAN, (CHAR, CHAR): BOOLEAN},
    BinOp.LT:   {(INTEGER, INTEGER): BOOLEAN, (CHAR, CHAR): BOOLEAN},
    BinOp.LE:   {(INTEGER, INTEGER): BOOLEAN, (CHAR, CHAR): BOOLEAN},
    BinOp.EQ:   {(INTEGER, INTEGER): BOOLEAN, (BOOLEAN, BOOLEAN): BOOLEAN, (CHAR, CHAR): BOOLEAN},
    BinOp.NE:   {(INTEGER, INTEGER): BOOLEAN, (BOOLEAN, BOOLEAN): BOOLEAN, (CHAR, CHAR): BOOLEAN},

    BinOp.AND:  {(BOOLEAN, BOOLEAN): BOOLEAN},
    BinOp.OR:   {(BOOLEAN, BOOLEAN): BOOLEAN},
}

# Встроенные функции/процедуры
def _make_builtin(name: str, ret: TypeDesc, *params: TypeDesc) -> IdentDesc:
    d = IdentDesc(name, TypeDesc(return_type=ret, params=list(params)))
    d.built_in = True
    return d


BUILTINS: list[IdentDesc] = [
    _make_builtin('write',   VOID, INTEGER),
    _make_builtin('writeln', VOID, INTEGER),
    _make_builtin('write',   VOID, BOOLEAN),
    _make_builtin('writeln', VOID, BOOLEAN),
    _make_builtin('write',   VOID, CHAR),
    _make_builtin('writeln', VOID, CHAR),
    _make_builtin('read',    VOID, INTEGER),
    _make_builtin('readln',  VOID, INTEGER),
    _make_builtin('inc',     VOID, INTEGER),
    _make_builtin('dec',     VOID, INTEGER),
    _make_builtin('abs',     INTEGER, INTEGER),
]


 
# Семантический анализатор
 

def _err(node: AstNode, msg: str):
    raise SemanticException(msg, row=node.row, col=node.col)


class SemanticChecker:

    @visitor.on('node')
    def check(self, node, scope: IdentScope):
        pass

    #   Литералы  

    @visitor.when(LiteralNode)
    def check(self, node: LiteralNode, scope: IdentScope):
        if isinstance(node.value, bool):
            node.node_type = BOOLEAN
        elif isinstance(node.value, int):
            node.node_type = INTEGER
        elif isinstance(node.value, float):
            node.node_type = INTEGER  # нет float в нашем подмножестве
        elif isinstance(node.value, str):
            node.node_type = CHAR

    #   Идентификатор (использование)  

    @visitor.when(IdentNode)
    def check(self, node: IdentNode, scope: IdentScope):
        ident = scope.get(node.name)
        if ident is None:
            _err(node, f'Идентификатор "{node.name}" не объявлен')
        node.node_ident = ident
        node.node_type = ident.type

    #   Доступ к элементу массива  

    @visitor.when(ArrayAccessNode)
    def check(self, node: ArrayAccessNode, scope: IdentScope):
        self.check(node.arr, scope)
        self.check(node.index, scope)
        arr_type = node.arr.node_type
        if not arr_type.is_array:
            _err(node, f'"{node.arr.name}" не является массивом')
        if node.index.node_type != INTEGER:
            _err(node, 'Индекс массива должен быть integer')
        node.node_type = arr_type.elem_type

    #   Унарные операции  

    @visitor.when(UnOpNode)
    def check(self, node: UnOpNode, scope: IdentScope):
        self.check(node.arg, scope)
        arg_t = node.arg.node_type
        table = UN_OP_TYPES.get(node.op, {})
        result = table.get(arg_t)
        if result is None:
            _err(node, f'Оператор "{node.op}" неприменим к типу {arg_t}')
        node.node_type = result

    #   Бинарные операции  

    @visitor.when(BinOpNode)
    def check(self, node: BinOpNode, scope: IdentScope):
        self.check(node.arg1, scope)
        self.check(node.arg2, scope)
        t1, t2 = node.arg1.node_type, node.arg2.node_type
        table = BIN_OP_TYPES.get(node.op, {})
        result = table.get((t1, t2))
        if result is None:
            _err(node, f'Оператор "{node.op}" неприменим к типам {t1} и {t2}')
        node.node_type = result

    #   Присваивание  

    @visitor.when(AssignNode)
    def check(self, node: AssignNode, scope: IdentScope):
        self.check(node.value, scope)
        val_t = node.value.node_type

        # Присваивание имени функции (return-значение в Pascal-стиле: fact := ...)
        if isinstance(node.var, IdentNode):
            fs = scope.func_scope
            if fs and fs.func and node.var.name == fs.func.name:
                ret_t = fs.func.type.return_type
                if val_t != ret_t:
                    _err(node, f'Тип возвращаемого значения {val_t} не совпадает с {ret_t}')
                node.var.node_type = ret_t
                node.node_type = ret_t
                return

        self.check(node.var, scope)
        var_t = node.var.node_type
        if var_t != val_t:
            _err(node, f'Нельзя присвоить {val_t} переменной типа {var_t}')
        node.node_type = var_t

    #   Вызов функции/процедуры  

    @visitor.when(CallNode)
    def check(self, node: CallNode, scope: IdentScope):
        for p in node.params:
            self.check(p, scope)

        name = node.name.name.lower()
        param_types = tuple(p.node_type for p in node.params)

        # Сначала ищем в таблице символов (пользовательские функции)
        ident = scope.get(name)
        if ident and ident.type.is_func:
            expected = tuple(ident.type.params)
            if param_types != expected:
                _err(node, f'Неверные типы аргументов для "{name}"')
            node.name.node_ident = ident
            node.node_type = ident.type.return_type
            return

        # Встроенные — ищем по имени (допускаем разные перегрузки)
        candidates = [b for b in BUILTINS if b.name == name]
        if not candidates:
            _err(node, f'Функция/процедура "{name}" не объявлена')

        matched = next(
            (b for b in candidates if tuple(b.type.params) == param_types),
            None
        )
        # Для Write/WriteLn допускаем любой примитивный тип
        if matched is None and name in ('write', 'writeln', 'read', 'readln'):
            matched = candidates[0]
        if matched is None:
            _err(node, f'Нет подходящей перегрузки "{name}" для типов {param_types}')

        node.name.node_ident = matched
        node.node_type = matched.type.return_type

    #   if  

    @visitor.when(IfNode)
    def check(self, node: IfNode, scope: IdentScope):
        self.check(node.cond, scope)
        if node.cond.node_type != BOOLEAN:
            _err(node.cond, f'Условие if должно быть boolean, получен {node.cond.node_type}')
        self.check(node.then_stmt, scope)
        if node.else_stmt:
            self.check(node.else_stmt, scope)

    #   while  

    @visitor.when(WhileNode)
    def check(self, node: WhileNode, scope: IdentScope):
        self.check(node.cond, scope)
        if node.cond.node_type != BOOLEAN:
            _err(node.cond, f'Условие while должно быть boolean, получен {node.cond.node_type}')
        loop_scope = IdentScope(parent=scope, loop=node)
        self.check(node.body, loop_scope)

    #   repeat  

    @visitor.when(RepeatNode)
    def check(self, node: RepeatNode, scope: IdentScope):
        loop_scope = IdentScope(parent=scope, loop=node)
        self.check(node.body, loop_scope)
        self.check(node.cond, loop_scope)
        if node.cond.node_type != BOOLEAN:
            _err(node.cond, f'Условие repeat..until должно быть boolean')

    #   for  

    @visitor.when(ForNode)
    def check(self, node: ForNode, scope: IdentScope):
        self.check(node.var, scope)
        if node.var.node_type != INTEGER:
            _err(node.var, 'Переменная цикла for должна быть integer')
        self.check(node.start, scope)
        self.check(node.finish, scope)
        if node.start.node_type != INTEGER:
            _err(node.start, 'Начальное значение for должно быть integer')
        if node.finish.node_type != INTEGER:
            _err(node.finish, 'Конечное значение for должно быть integer')
        loop_scope = IdentScope(parent=scope, loop=node)
        self.check(node.body, loop_scope)

    #   break / continue  

    @visitor.when(BreakNode)
    def check(self, node: BreakNode, scope: IdentScope):
        if scope.loop_scope is None:
            _err(node, 'break вне цикла')

    @visitor.when(ContinueNode)
    def check(self, node: ContinueNode, scope: IdentScope):
        if scope.loop_scope is None:
            _err(node, 'continue вне цикла')

    #   return  

    @visitor.when(ReturnNode)
    def check(self, node: ReturnNode, scope: IdentScope):
        fs = scope.func_scope
        if fs is None:
            _err(node, 'return вне функции')
        if node.value:
            self.check(node.value, scope)
            expected = fs.func.type.return_type
            if node.value.node_type != expected:
                _err(node, f'return: ожидается {expected}, получен {node.value.node_type}')

    #   Список операторов  

    @visitor.when(StmtListNode)
    def check(self, node: StmtListNode, scope: IdentScope):
        for stmt in node.stmts:
            self.check(stmt, scope)

    #   Объявление переменных  

    @visitor.when(VarDeclNode)
    def check(self, node: VarDeclNode, scope: IdentScope):
        type_desc = _resolve_type(node.type)
        for var_ident in node.vars:
            ident = IdentDesc(var_ident.name, type_desc)
            try:
                scope.add(ident)
            except SemanticException as e:
                raise SemanticException(e.message, row=var_ident.row, col=var_ident.col)
            var_ident.node_ident = ident
            var_ident.node_type = type_desc

    #   Объявление функции/процедуры  

    @visitor.when(FuncNode)
    def check(self, node: FuncNode, scope: IdentScope):
        ret_type = TypeDesc.VOID if node.return_type is None else _resolve_type(node.return_type)
        param_types = [_resolve_type(p.type) for p in node.params]
        func_type = TypeDesc(return_type=ret_type, params=param_types)
        func_ident = IdentDesc(node.name.name, func_type)
        scope.add(func_ident)
        node.name.node_ident = func_ident

        func_scope = IdentScope(parent=scope, func=func_ident)
        for param, ptype in zip(node.params, param_types):
            pd = IdentDesc(param.name.name, ptype, scope=ScopeKind.PARAM)
            func_scope.add(pd)
            param.name.node_ident = pd

        for vd in node.var_decls:
            self.check(vd, func_scope)

        self.check(node.body, func_scope)

    #   Программа  

    @visitor.when(ProgramNode)
    def check(self, node: ProgramNode, scope: IdentScope):
        for vd in node.var_decls:
            self.check(vd, scope)
        for fd in node.func_decls:
            self.check(fd, scope)
        self.check(node.body, scope)



# Вспомогательные функции


def _resolve_type(type_node: TypeNode) -> TypeDesc:
    if type_node.name == 'array':
        elem = TypeDesc.from_str(type_node.elem_type.name)
        return TypeDesc.array_of(elem, type_node.lo, type_node.hi)
    return TypeDesc.from_str(type_node.name)


def semantic_check(program: ProgramNode) -> IdentScope:
    """Запускает семантический анализ. Возвращает глобальную область видимости."""
    global_scope = IdentScope()
    checker = SemanticChecker()
    checker.check(program, global_scope)
    return global_scope
