from pathlib import Path
from lark import Lark, Transformer, v_args, Token, UnexpectedCharacters, UnexpectedToken

from compiler.frontend.ast import *
from compiler.errors import ParserException

_grammar = (Path(__file__).parent / 'pascal.lark').read_text(encoding='utf-8')


def _pos(node: AstNode, meta) -> AstNode:
    node.row = getattr(meta, 'line', None)
    node.col = getattr(meta, 'column', None)
    return node


@v_args(meta=True)
class _ASTBuilder(Transformer):


    #  Токены → строки/значения                                            


    def IDENT(self, tok):    return str(tok)
    def INTEGER(self, tok):  return str(tok)
    def CHAR_LIT(self, tok): return str(tok)

    # Токены ключевых слов типов → строки
    def KW_INTEGER(self, tok): return 'integer'
    def KW_BOOLEAN(self, tok): return 'boolean'
    def KW_CHAR(self, tok):    return 'char'
    # bool-литералы
    def KW_TRUE(self, tok):    return 'true'
    def KW_FALSE(self, tok):   return 'false'

    # Все остальные KW_* токены (if/then/else/begin/end/...) оставляем как Token
    # — они будут отфильтрованы в методах через isinstance(c, Token)


    #  Базовые правила                                                     


    def ident(self, meta, ch):
        return _pos(IdentNode(ch[0]), meta)

    def integer(self, meta, ch):
        return _pos(LiteralNode(ch[0]), meta)

    def char_lit(self, meta, ch):
        return _pos(LiteralNode(ch[0]), meta)

    def bool_lit(self, meta, ch):
        # ch[0] — строка 'true'/'false'
        return _pos(LiteralNode(ch[0]), meta)

    def literal(self, meta, ch):
        return ch[0]


    #  Типы — возвращают TypeNode (AstNode)                               


    def type_kw(self, meta, ch):
        # ch[0] — строка 'integer'/'boolean'/'char' (от KW_INTEGER и т.д.)
        return _pos(TypeNode(ch[0]), meta)

    def simple_type(self, meta, ch):
        return ch[0]  # уже TypeNode из type_kw

    def array_type(self, meta, ch):
        # ch: [LiteralNode(lo), LiteralNode(hi), TypeNode(elem)]
        # Earley может добавить Token'ы KW_ARRAY, KW_OF — фильтруем
        nodes = [c for c in ch if isinstance(c, AstNode)]
        lo = int(nodes[0].value)
        hi = int(nodes[1].value)
        elem_type = nodes[2]
        return _pos(TypeNode('array', elem_type=elem_type, lo=lo, hi=hi), meta)

    def type_node(self, meta, ch):
        return ch[0]


    #  Выражения                                                           


    def args(self, meta, ch):
        return [c for c in ch if isinstance(c, AstNode)]

    def array_access(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return _pos(ArrayAccessNode(nodes[0], nodes[1]), meta)

    def call(self, meta, ch):
        # ch[0] = IdentNode, ch[1] = list from args (may not be AstNode)
        name = ch[0]
        params = ch[1] if len(ch) > 1 and isinstance(ch[1], list) else []
        return _pos(CallNode(name, *params), meta)

    def unary_plus(self, meta, ch):
        return _pos(UnOpNode(UnOp.PLUS,  [c for c in ch if isinstance(c, AstNode)][0]), meta)

    def unary_minus(self, meta, ch):
        return _pos(UnOpNode(UnOp.MINUS, [c for c in ch if isinstance(c, AstNode)][0]), meta)

    def unary_not(self, meta, ch):
        return _pos(UnOpNode(UnOp.NOT,   [c for c in ch if isinstance(c, AstNode)][0]), meta)

    _BIN = {
        'add': BinOp.ADD, 'sub': BinOp.SUB,
        'mul': BinOp.MUL, 'fdiv': BinOp.FDIV,
        'div': BinOp.DIV, 'mod': BinOp.MOD,
        'gt':  BinOp.GT,  'ge':  BinOp.GE,
        'lt':  BinOp.LT,  'le':  BinOp.LE,
        'eq':  BinOp.EQ,  'ne':  BinOp.NE,
        'and_op': BinOp.AND, 'or_op': BinOp.OR,
    }

    def __default__(self, data, ch, meta):
        if data in self._BIN:
            nodes = [c for c in ch if isinstance(c, AstNode)]
            return _pos(BinOpNode(self._BIN[data], nodes[0], nodes[1]), meta)
        nodes = [c for c in ch if isinstance(c, AstNode)]
        if len(nodes) == 1:
            return nodes[0]
        return nodes or None


    #  Операторы                                                           


    def assign(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return _pos(AssignNode(nodes[0], nodes[1]), meta)

    def array_assign(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        lval = _pos(ArrayAccessNode(nodes[0], nodes[1]), meta)
        return _pos(AssignNode(lval, nodes[2]), meta)

    def call_stmt(self, meta, ch):
        # ch[0] = IdentNode, ch[1] = list from args
        name = ch[0]
        params = ch[1] if len(ch) > 1 and isinstance(ch[1], list) else []
        return _pos(CallNode(name, *params), meta)

    def compound_stmt(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return nodes[0] if nodes else _pos(StmtListNode(), meta)

    def stmt_list(self, meta, ch):
        stmts = [c for c in ch if isinstance(c, AstNode)]
        return _pos(StmtListNode(*stmts), meta)

    def if_stmt(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        cond, then = nodes[0], nodes[1]
        else_ = nodes[2] if len(nodes) > 2 else None
        return _pos(IfNode(cond, then, else_), meta)

    def while_stmt(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return _pos(WhileNode(nodes[0], nodes[1]), meta)

    def repeat_stmt(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return _pos(RepeatNode(nodes[0], nodes[1]), meta)

    def for_to(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return _pos(ForNode(nodes[0], nodes[1], nodes[2], downto=False, body=nodes[3]), meta)

    def for_downto(self, meta, ch):
        nodes = [c for c in ch if isinstance(c, AstNode)]
        return _pos(ForNode(nodes[0], nodes[1], nodes[2], downto=True, body=nodes[3]), meta)

    def for_stmt(self, meta, ch):
        return [c for c in ch if isinstance(c, AstNode)][0]

    def break_stmt(self, meta, ch):
        return _pos(BreakNode(), meta)

    def continue_stmt(self, meta, ch):
        return _pos(ContinueNode(), meta)

    def empty_stmt(self, meta, ch):
        return None


    #  Объявления переменных                                               


    def ident_list(self, meta, ch):
        return [c for c in ch if isinstance(c, IdentNode)]

    def var_decl(self, meta, ch):
        # ch[0] = list[IdentNode], ch[1] = TypeNode
        ident_list = ch[0]
        type_node  = ch[1]
        return _pos(VarDeclNode(type_node, *ident_list), meta)

    def var_section(self, meta, ch):
        return [c for c in ch if isinstance(c, AstNode)]


    #  Параметры функций                                                   


    def param(self, meta, ch):
        # ch[0] = list[IdentNode], ch[1] = TypeNode
        ident_list = ch[0]
        type_node  = ch[1]
        return [_pos(ParamNode(type_node, name), meta) for name in ident_list]

    def param_list(self, meta, ch):
        result = []
        for item in ch:
            if isinstance(item, list):
                result.extend(item)
        return result

    def func_body(self, meta, ch):
        # ch: [Token(begin), var_section?, stmt_list, Token(end)]
        var_decls = []
        body = StmtListNode()
        for item in ch:
            if isinstance(item, Token):
                continue
            if isinstance(item, list):      # var_section returns list
                var_decls = item
            elif isinstance(item, StmtListNode):
                body = item
        return (var_decls, body)

    def function_decl(self, meta, ch):
        # ch: [Token(function), IdentNode, list[ParamNode]?, TypeNode, (var_decls, body)]
        items = [c for c in ch if not isinstance(c, Token)]
        name       = items[0]                    # IdentNode
        params     = items[1] if isinstance(items[1], list) else []
        ret_type   = items[2] if params else items[1]   # TypeNode
        body_tuple = items[3] if params else items[2]
        var_decls, body = body_tuple
        return _pos(FuncNode(
            return_type=ret_type,
            name=name, params=params,
            var_decls=var_decls, body=body,
        ), meta)

    def procedure_decl(self, meta, ch):
        # ch: [Token(procedure), IdentNode, list[ParamNode]?, (var_decls, body)]
        items = [c for c in ch if not isinstance(c, Token)]
        name   = items[0]
        params = items[1] if isinstance(items[1], list) and all(isinstance(x, ParamNode) for x in items[1]) else []
        body_tuple = items[2] if params else items[1]
        var_decls, body = body_tuple
        return _pos(FuncNode(
            return_type=None,
            name=name, params=params,
            var_decls=var_decls, body=body,
        ), meta)


    #  Программа                                                           


    def program(self, meta, ch):
        name = None
        var_decls  = []
        func_decls = []
        body       = StmtListNode()

        for item in ch:
            if isinstance(item, Token):
                continue
            if isinstance(item, IdentNode) and name is None:
                name = item
            elif isinstance(item, list):
                for sub in item:
                    if isinstance(sub, VarDeclNode):  var_decls.append(sub)
                    elif isinstance(sub, FuncNode):   func_decls.append(sub)
            elif isinstance(item, FuncNode):
                func_decls.append(item)
            elif isinstance(item, StmtListNode):
                body = item

        return _pos(ProgramNode(name, var_decls, func_decls, body), meta)



#  Публичная функция парсинга


_parser = Lark(_grammar, start='start', propagate_positions=True, parser='earley')


def parse(source: str) -> ProgramNode:
    try:
        tree = _parser.parse(source)
    except UnexpectedCharacters as e:
        raise ParserException(
            f'Неожиданный символ "{e.char}"',
            row=e.line, col=e.column
        )
    except UnexpectedToken as e:
        expected = ', '.join(sorted(str(x) for x in e.expected)[:6])
        raise ParserException(
            f'Неожиданный токен "{e.token}" (ожидалось: {expected})',
            row=e.line, col=e.column
        )

    return _ASTBuilder().transform(tree)
