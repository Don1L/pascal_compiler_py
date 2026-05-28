"""
run.py — точка входа и CLI.

Использование:
  python run.py examples/factorial.pas --vm
  python run.py examples/factorial.pas --vm --dis
  python run.py examples/factorial.pas --vm --no-opt
  python run.py examples/factorial.pas --vm --opt
  python run.py examples/factorial.pas --x86
  python run.py examples/factorial.pas --x86 --out result.asm
  python run.py examples/factorial.pas --ast
  python run.py examples/factorial.pas --parse-only
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from compiler.pipeline import run
from compiler.errors import CompilerException


def main():
    parser = argparse.ArgumentParser(
        description='Pascal compiler: VM + x86 (учебный проект)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''примеры:
  python run.py examples/factorial.pas --vm
  python run.py examples/factorial.pas --vm --dis
  python run.py examples/factorial.pas --vm --opt
  python run.py examples/factorial.pas --x86
  python run.py examples/factorial.pas --x86 --out factorial.asm
  python run.py examples/factorial.pas --ast --parse-only
'''
    )
    parser.add_argument('src', help='путь к .pas файлу')

    # Бэкенд
    backend = parser.add_mutually_exclusive_group(required=False)
    backend.add_argument('--vm',  action='store_true', help='бэкенд: виртуальная машина')
    backend.add_argument('--x86', action='store_true', help='бэкенд: x86 NASM-листинг')

    # Флаги вывода
    parser.add_argument('--dis',        action='store_true', help='показать байткод VM')
    parser.add_argument('--out',        metavar='FILE',      help='сохранить .asm в файл')
    parser.add_argument('--ast',        action='store_true', help='показать AST после парсинга')
    parser.add_argument('--sem',        action='store_true', help='показать AST после семантики')
    parser.add_argument('--opt',        action='store_true', help='показать AST после оптимизации')

    # Флаги управления
    parser.add_argument('--no-opt',     action='store_true', help='отключить оптимизации')
    parser.add_argument('--parse-only', action='store_true', help='остановиться после парсинга')
    parser.add_argument('--sem-only',   action='store_true', help='остановиться после семантики')

    args = parser.parse_args()

    src_path = Path(args.src)
    if not src_path.exists():
        print(f'[Ошибка] Файл не найден: {src_path}', file=sys.stderr)
        sys.exit(1)

    mode = 'x86' if args.x86 else 'vm'

    x86_output = None
    if args.x86:
        x86_output = args.out if args.out else str(src_path.with_suffix('.asm'))

    source = src_path.read_text(encoding='utf-8')

    try:
        run(
            source,
            mode=mode,
            print_ast=args.ast,
            print_ast_after_semantic=args.sem,
            print_ast_after_opt=args.opt,
            print_bytecode=args.dis,
            stop_after_parse=args.parse_only,
            stop_after_semantic=args.sem_only,
            no_opt=args.no_opt,
            x86_output=x86_output,
        )
    except CompilerException as e:
        kind = type(e).__name__.replace('Exception', 'Error')
        print(f'[{kind}] {e.message}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
