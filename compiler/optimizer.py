"""
optimizer.py — оптимизации AST-дерева.

Реализованы три оптимизации:

1. Constant folding (свёртка констант)
   2 + 3 * 4  →  14
   true and false  →  false

2. Algebraic simplification (упрощение выражений)
   x + 0  →  x
   x * 1  →  x
   x * 0  →  0
   x - 0  →  x
   x / 1  →  x
   not not x  →  x
   0 - x  →  -x

3. Dead code elimination (удаление мёртвого кода)
   Операторы после break/continue в теле цикла недостижимы — удаляем.
   if true then A else B  →  A
   if false then A else B →  B
"""

from compiler.frontend.ast import *


class Optimizer:

    def optimize(self, node: AstNode) -> AstNode:
        """Точка входа — оптимизирует программу и возвращает новый AST."""
        return self._opt(node)


    #  Диспетчер


    def _opt(self, node: AstNode) -> AstNode:
        if node is None:
            return None

        if isinstance(node, ProgramNode):
            return self._opt_program(node)
        if isinstance(node, FuncNode):
            return self._opt_func(node)
        if isinstance(node, StmtListNode):
            return self._opt_stmtlist(node)
        if isinstance(node, AssignNode):
            return self._opt_assign(node)
        if isinstance(node, IfNode):
            return self._opt_if(node)
        if isinstance(node, WhileNode):
            return self._opt_while(node)
        if isinstance(node, RepeatNode):
            return self._opt_repeat(node)
        if isinstance(node, ForNode):
            return self._opt_for(node)
        if isinstance(node, BinOpNode):
            return self._opt_binop(node)
        if isinstance(node, UnOpNode):
            return self._opt_unop(node)
        if isinstance(node, CallNode):
            return self._opt_call(node)
        if isinstance(node, ArrayAccessNode):
            return self._opt_array_access(node)

        # Всё остальное (литералы, идентификаторы и т.д.) — без изменений
        return node


    #  Программа и функции


    def _opt_program(self, node: ProgramNode) -> ProgramNode:
        new_funcs = [self._opt_func(f) for f in node.func_decls]
        new_body  = self._opt_stmtlist(node.body)
        node.func_decls = new_funcs
        node.body = new_body
        return node

    def _opt_func(self, node: FuncNode) -> FuncNode:
        node.body = self._opt_stmtlist(node.body)
        return node


    #  Список операторов — dead code elimination


    def _opt_stmtlist(self, node: StmtListNode) -> StmtListNode:
        new_stmts = []
        for stmt in node.stmts:
            opt_stmt = self._opt(stmt)
            if opt_stmt is not None:
                new_stmts.append(opt_stmt)
            # Если после break/continue есть ещё операторы — удаляем их
            if isinstance(opt_stmt, (BreakNode, ContinueNode)):
                break

        node.stmts = tuple(new_stmts)
        return node


    #  Операторы


    def _opt_assign(self, node: AssignNode) -> AssignNode:
        node.value = self._opt(node.value)
        return node

    def _opt_if(self, node: IfNode) -> AstNode:
        node.cond      = self._opt(node.cond)
        node.then_stmt = self._opt(node.then_stmt)
        if node.else_stmt:
            node.else_stmt = self._opt(node.else_stmt)

        # Если условие — константа, убираем ветвление
        if isinstance(node.cond, LiteralNode):
            if node.cond.value:
                return node.then_stmt   # if true → всегда then
            else:
                return node.else_stmt or StmtListNode()  # if false → всегда else

        return node

    def _opt_while(self, node: WhileNode) -> AstNode:
        node.cond = self._opt(node.cond)
        node.body = self._opt(node.body)

        # while false do ... → убираем целиком
        if isinstance(node.cond, LiteralNode) and not node.cond.value:
            return None

        return node

    def _opt_repeat(self, node: RepeatNode) -> RepeatNode:
        node.body = self._opt_stmtlist(node.body)
        node.cond = self._opt(node.cond)
        return node

    def _opt_for(self, node: ForNode) -> ForNode:
        node.start  = self._opt(node.start)
        node.finish = self._opt(node.finish)
        node.body   = self._opt(node.body)
        return node


    #  Бинарные операции — constant folding + algebraic simplification

    def _opt_binop(self, node: BinOpNode) -> AstNode:
        node.arg1 = self._opt(node.arg1)
        node.arg2 = self._opt(node.arg2)

        a = node.arg1
        b = node.arg2
        op = node.op

        # Constant folding
        if isinstance(a, LiteralNode) and isinstance(b, LiteralNode):
            result = self._fold(op, a.value, b.value)
            if result is not None:
                lit = LiteralNode(str(result).lower() if isinstance(result, bool) else str(result))
                lit.row = node.row
                lit.col = node.col
                lit.node_type = node.node_type
                return lit

        # Algebraic simplification

        # x + 0 → x,  0 + x → x
        if op == BinOp.ADD:
            if _is_zero(b): return a
            if _is_zero(a): return b

        # x - 0 → x
        if op == BinOp.SUB:
            if _is_zero(b): return a
            # 0 - x → -x
            if _is_zero(a):
                return _make_neg(b, node)

        # x * 1 → x,  1 * x → x
        # x * 0 → 0,  0 * x → 0
        if op == BinOp.MUL:
            if _is_one(b):  return a
            if _is_one(a):  return b
            if _is_zero(b): return _make_lit(0, node)
            if _is_zero(a): return _make_lit(0, node)

        # x / 1 → x,  x div 1 → x
        if op in (BinOp.FDIV, BinOp.DIV):
            if _is_one(b): return a

        # x mod 1 → 0
        if op == BinOp.MOD:
            if _is_one(b): return _make_lit(0, node)

        # true and x → x,  x and true → x
        # false and x → false
        if op == BinOp.AND:
            if _is_true(a):  return b
            if _is_true(b):  return a
            if _is_false(a): return _make_lit(False, node)
            if _is_false(b): return _make_lit(False, node)

        # false or x → x,  x or false → x
        # true or x → true
        if op == BinOp.OR:
            if _is_false(a): return b
            if _is_false(b): return a
            if _is_true(a):  return _make_lit(True, node)
            if _is_true(b):  return _make_lit(True, node)

        return node

    @staticmethod
    def _fold(op: BinOp, a, b):
        """Вычисляет бинарную операцию над константами. Возвращает None если нельзя."""
        try:
            if op == BinOp.ADD:  return a + b
            if op == BinOp.SUB:  return a - b
            if op == BinOp.MUL:  return a * b
            if op == BinOp.DIV:
                if b == 0: return None
                return a // b
            if op == BinOp.FDIV:
                if b == 0: return None
                return a // b
            if op == BinOp.MOD:
                if b == 0: return None
                return a % b
            if op == BinOp.EQ:  return a == b
            if op == BinOp.NE:  return a != b
            if op == BinOp.LT:  return a < b
            if op == BinOp.LE:  return a <= b
            if op == BinOp.GT:  return a > b
            if op == BinOp.GE:  return a >= b
            if op == BinOp.AND: return a and b
            if op == BinOp.OR:  return a or b
        except Exception:
            pass
        return None

    #  Унарные операции

    def _opt_unop(self, node: UnOpNode) -> AstNode:
        node.arg = self._opt(node.arg)
        arg = node.arg

        # Constant folding
        if isinstance(arg, LiteralNode):
            if node.op == UnOp.MINUS:
                lit = LiteralNode(str(-arg.value))
                lit.node_type = node.node_type
                lit.row = node.row
                return lit
            if node.op == UnOp.NOT:
                lit = LiteralNode('false' if arg.value else 'true')
                lit.node_type = node.node_type
                lit.row = node.row
                return lit
            if node.op == UnOp.PLUS:
                return arg

        # not (not x) → x
        if node.op == UnOp.NOT and isinstance(arg, UnOpNode) and arg.op == UnOp.NOT:
            return arg.arg

        # --x → x (двойной унарный минус)
        if node.op == UnOp.MINUS and isinstance(arg, UnOpNode) and arg.op == UnOp.MINUS:
            return arg.arg

        return node


    #  Вызов функции


    def _opt_call(self, node: CallNode) -> CallNode:
        node.params = tuple(self._opt(p) for p in node.params)
        return node

    def _opt_array_access(self, node: ArrayAccessNode) -> ArrayAccessNode:
        node.index = self._opt(node.index)
        return node



# Вспомогательные функции


def _is_zero(node: AstNode) -> bool:
    return isinstance(node, LiteralNode) and node.value == 0

def _is_one(node: AstNode) -> bool:
    return isinstance(node, LiteralNode) and node.value == 1

def _is_true(node: AstNode) -> bool:
    return isinstance(node, LiteralNode) and node.value is True

def _is_false(node: AstNode) -> bool:
    return isinstance(node, LiteralNode) and node.value is False

def _make_lit(value, src: AstNode) -> LiteralNode:
    s = str(value).lower() if isinstance(value, bool) else str(value)
    lit = LiteralNode(s)
    lit.row = src.row
    lit.col = src.col
    lit.node_type = src.node_type
    return lit

def _make_neg(node: AstNode, src: AstNode) -> UnOpNode:
    neg = UnOpNode(UnOp.MINUS, node)
    neg.row = src.row
    neg.col = src.col
    neg.node_type = src.node_type
    return neg


# Публичная функция

def optimize(program: ProgramNode) -> ProgramNode:
    """Запускает все оптимизации и возвращает изменённое дерево."""
    return Optimizer().optimize(program)
