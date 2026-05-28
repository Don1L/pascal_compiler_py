"""
pipeline.py — связывает все этапы компилятора.

Порядок: parse → semantic → optimize → (vm | x86)
"""

from compiler.frontend.parser import parse
from compiler.frontend.ast_printer import AstPrinter
from compiler.analysis.semantic import semantic_check
from compiler.optimizer import optimize


def run(
    source: str,
    *,
    mode: str = 'vm',
    print_ast: bool = False,
    print_ast_after_semantic: bool = False,
    print_ast_after_opt: bool = False,
    print_bytecode: bool = False,
    stop_after_parse: bool = False,
    stop_after_semantic: bool = False,
    no_opt: bool = False,
    x86_output: str = None,
) -> None:

    # 1. Парсинг
    program = parse(source)

    if print_ast:
        print('=== AST ===')
        AstPrinter.print(program)
        print()

    if stop_after_parse:
        return

    # 2. Семантический анализ
    semantic_check(program)

    if print_ast_after_semantic:
        print('=== AST (после семантики) ===')
        AstPrinter.print(program)
        print()

    if stop_after_semantic:
        return

    # 3. Оптимизация
    if not no_opt:
        optimize(program)

    if print_ast_after_opt:
        label = '=== AST (после оптимизации) ===' if not no_opt else '=== AST (без оптимизации) ==='
        print(label)
        AstPrinter.print(program)
        print()

    # 4. Бэкенд
    if mode == 'vm':
        from compiler.backend.vm.codegen import compile_to_bytecode
        from compiler.backend.vm.vm import VM

        bytecode = compile_to_bytecode(program)

        if print_bytecode:
            print('=== Bytecode ===')
            print(bytecode.disassemble())
            print()

        VM().run(bytecode, program)

    elif mode == 'x86':
        from compiler.backend.x86.codegen import compile_to_x86

        asm = compile_to_x86(program)

        if x86_output:
            with open(x86_output, 'w', encoding='utf-8') as f:
                f.write(asm)
            print(f'[x86] Листинг сохранён: {x86_output}')
        else:
            print(asm)

    else:
        raise ValueError(f'Неизвестный режим: {mode}')
