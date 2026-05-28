from typing import Any


class CompilerException(Exception):
    def __init__(self, message: str, row: int = None, col: int = None, **kwargs: Any) -> None:
        parts = []
        if row:
            parts.append(f'строка {row}')
        if col:
            parts.append(f'позиция {col}')
        if parts:
            message += f' ({", ".join(parts)})'
        self.message = message
        super().__init__(self.message)


class ParserException(CompilerException):
    pass


class SemanticException(CompilerException):
    pass


class RuntimeException(CompilerException):
    pass
