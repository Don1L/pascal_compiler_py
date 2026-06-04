from compiler.frontend.ast import *
from compiler.backend.vm.opcodes import Op, Instr


class Bytecode:

    def __init__(self):
        self.main:        list[Instr]              = []
        self.funcs:       dict[str, list[Instr]]   = {}
        self.func_params: dict[str, list[str]]     = {}
        self.func_locals: dict[str, list[tuple]]   = {}

    def disassemble(self) -> str:
        lines = ['=== main ===']
        for i, instr in enumerate(self.main):
            lines.append(f'  {i:4d}  {instr}')
        for name, code in self.funcs.items():
            lines.append(f'\n=== {name} ===')
            for i, instr in enumerate(code):
                lines.append(f'  {i:4d}  {instr}')
        return '\n'.join(lines)


class _Label:
    _counter = 0

    def __init__(self, name: str = ''):
        _Label._counter += 1
        self.name = f'{name}_{_Label._counter}'

    def __repr__(self):
        return f'<{self.name}>'


class CodeGen:

    def __init__(self):
        self._code:  list[Instr | _Label] = []
        self._loops:     list[tuple[_Label, _Label]] = []
        self._func_name: str | None                  = None

    def emit(self, op: Op, arg=None, row: int = None) -> None:
        self._code.append(Instr(op, arg, row))

    def label(self, name: str = '') -> _Label:
        lbl = _Label(name)
        return lbl

    def place(self, lbl: _Label) -> None:
        self._code.append(lbl)

    def resolve(self) -> list[Instr]:
        addr: dict[str, int] = {}
        idx = 0
        for item in self._code:
            if isinstance(item, _Label):
                addr[item.name] = idx
            else:
                idx += 1

        result: list[Instr] = []
        for item in self._code:
            if isinstance(item, _Label):
                continue
            if item.op in (Op.JUMP, Op.JUMP_FALSE):
                lbl = item.arg
                item = Instr(item.op, addr[lbl.name], item.row)
            result.append(item)
        return result

    def gen_expr(self, node: AstNode) -> None:
        if isinstance(node, LiteralNode):
            self.emit(Op.PUSH, node.value, node.row)

        elif isinstance(node, IdentNode):
            self.emit(Op.LOAD, node.name, node.row)

        elif isinstance(node, ArrayAccessNode):
            self.gen_expr(node.index)
            self.emit(Op.LOAD_IDX, node.arr.name, node.row)

        elif isinstance(node, BinOpNode):
            self._gen_binop(node)

        elif isinstance(node, UnOpNode):
            self.gen_expr(node.arg)
            if node.op == UnOp.MINUS:
                self.emit(Op.NEG, row=node.row)
            elif node.op == UnOp.NOT:
                self.emit(Op.NOT, row=node.row)

        elif isinstance(node, CallNode):
            self._gen_call(node)

        elif isinstance(node, TypeConvertNode):
            self.gen_expr(node.value)

        else:
            raise NotImplementedError(f'gen_expr: {type(node).__name__}')

    def _gen_binop(self, node: BinOpNode) -> None:
        if node.op == BinOp.AND:
            end = self.label('and_end')
            self.gen_expr(node.arg1)
            self.emit(Op.JUMP_FALSE, end, node.row)
            self.gen_expr(node.arg2)
            self.place(end)
            return
        if node.op == BinOp.OR:
            true_lbl = self.label('or_true')
            end = self.label('or_end')
            self.gen_expr(node.arg1)
            self.emit(Op.NOT, row=node.row)
            self.emit(Op.JUMP_FALSE, true_lbl, node.row)
            self.gen_expr(node.arg2)
            self.emit(Op.JUMP, end)
            self.place(true_lbl)
            self.emit(Op.PUSH, True)
            self.place(end)
            return

        self.gen_expr(node.arg1)
        self.gen_expr(node.arg2)
        op_map = {
            BinOp.ADD: Op.ADD, BinOp.SUB: Op.SUB,
            BinOp.MUL: Op.MUL, BinOp.DIV: Op.DIV,
            BinOp.FDIV: Op.DIV, BinOp.MOD: Op.MOD,
            BinOp.EQ: Op.EQ, BinOp.NE: Op.NE,
            BinOp.LT: Op.LT, BinOp.LE: Op.LE,
            BinOp.GT: Op.GT, BinOp.GE: Op.GE,
        }
        self.emit(op_map[node.op], row=node.row)

    def _gen_call(self, node: CallNode) -> None:
        name = node.name.name.lower()

        if name in ('write', 'writeln'):
            for p in node.params:
                self.gen_expr(p)
            newline = (name == 'writeln')
            self.emit(Op.PRINT, newline, node.row)
            return

        if name in ('read', 'readln'):
            var_node = node.params[0]
            t = var_node.node_type
            type_name = str(t) if t else 'integer'
            var_name  = var_node.name if isinstance(var_node, IdentNode) else '?'
            self.emit(Op.READ, (type_name, var_name), node.row)
            return

        if name == 'inc':
            var_name = node.params[0].name
            self.emit(Op.INC, var_name, node.row)
            return

        if name == 'dec':
            var_name = node.params[0].name
            self.emit(Op.DEC, var_name, node.row)
            return

        if name == 'abs':
            self.gen_expr(node.params[0])
            self.emit(Op.ABS, row=node.row)
            return

        for p in node.params:
            self.gen_expr(p)
        self.emit(Op.CALL, (node.name.name, len(node.params)), node.row)

    def gen_stmt(self, node: AstNode) -> None:

        if isinstance(node, StmtListNode):
            for stmt in node.stmts:
                self.gen_stmt(stmt)

        elif isinstance(node, VarDeclNode):
            pass

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
            if not self._loops:
                raise RuntimeError('break вне цикла')
            _, end = self._loops[-1]
            self.emit(Op.JUMP, end, node.row)

        elif isinstance(node, ContinueNode):
            if not self._loops:
                raise RuntimeError('continue вне цикла')
            start, _ = self._loops[-1]
            self.emit(Op.JUMP, start, node.row)

        elif isinstance(node, ReturnNode):
            if node.value:
                self.gen_expr(node.value)
                self.emit(Op.RETURN, row=node.row)
            else:
                self.emit(Op.RETURN_NONE, row=node.row)

        elif isinstance(node, CallNode):
            self._gen_call(node)
            if node.node_type and str(node.node_type) != 'void':
                self.emit(Op.POP)

        else:
            raise NotImplementedError(f'gen_stmt: {type(node).__name__}')

    def _gen_assign(self, node: AssignNode) -> None:
        if isinstance(node.var, IdentNode) and node.var.name == self._func_name:
            self.gen_expr(node.value)
            self.emit(Op.RETURN, row=node.row)
            return

        self.gen_expr(node.value)

        if isinstance(node.var, ArrayAccessNode):
            self.gen_expr(node.var.index)
            self.emit(Op.STORE_IDX, node.var.arr.name, node.row)
        else:
            self.emit(Op.STORE, node.var.name, node.row)

    def _gen_if(self, node: IfNode) -> None:
        else_lbl = self.label('else')
        end_lbl  = self.label('if_end')

        self.gen_expr(node.cond)
        self.emit(Op.JUMP_FALSE, else_lbl, node.row)
        self.gen_stmt(node.then_stmt)
        self.emit(Op.JUMP, end_lbl)
        self.place(else_lbl)
        if node.else_stmt:
            self.gen_stmt(node.else_stmt)
        self.place(end_lbl)

    def _gen_while(self, node: WhileNode) -> None:
        start = self.label('while_start')
        end   = self.label('while_end')
        self._loops.append((start, end))

        self.place(start)
        self.gen_expr(node.cond)
        self.emit(Op.JUMP_FALSE, end, node.row)
        self.gen_stmt(node.body)
        self.emit(Op.JUMP, start)
        self.place(end)

        self._loops.pop()

    def _gen_repeat(self, node: RepeatNode) -> None:
        start = self.label('repeat_start')
        end   = self.label('repeat_end')
        self._loops.append((start, end))

        self.place(start)
        self.gen_stmt(node.body)
        self.gen_expr(node.cond)
        self.emit(Op.JUMP_FALSE, start, node.row)
        self.place(end)

        self._loops.pop()

    def _gen_for(self, node: ForNode) -> None:
        start = self.label('for_start')
        end   = self.label('for_end')
        self._loops.append((start, end))

        var = node.var.name

        self.gen_expr(node.start)
        self.emit(Op.STORE, var, node.row)

        self.place(start)

        self.emit(Op.LOAD, var)
        self.gen_expr(node.finish)
        self.emit(Op.GE if node.downto else Op.LE)
        self.emit(Op.JUMP_FALSE, end)

        self.gen_stmt(node.body)

        self.emit(Op.LOAD, var)
        self.emit(Op.PUSH, 1)
        self.emit(Op.SUB if node.downto else Op.ADD)
        self.emit(Op.STORE, var)

        self.emit(Op.JUMP, start)
        self.place(end)

        self._loops.pop()



def compile_to_bytecode(program: ProgramNode) -> Bytecode:
    bc = Bytecode()

    for func in program.func_decls:
        name = func.name.name
        cg = CodeGen()
        cg._func_name = name
        cg.gen_stmt(func.body)
        cg.emit(Op.RETURN_NONE)
        bc.funcs[name] = cg.resolve()
        bc.func_params[name] = [p.name.name for p in func.params]
        bc.func_locals[name] = [
            (v.name, vd.type.name)
            for vd in func.var_decls
            for v in vd.vars
        ]

    cg = CodeGen()
    cg.gen_stmt(program.body)
    cg.emit(Op.HALT)
    bc.main = cg.resolve()

    return bc
