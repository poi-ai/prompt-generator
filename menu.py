"""矢印キーで選択肢を選ばせるための共通メニュー処理、および自由入力の共通ヘルパー

Windows専用の標準ライブラリ msvcrt を使って矢印キー入力を実現する。
msvcrt が使えない環境(Windows以外)では番号入力にフォールバックする。

いずれの入力方法でも、「1つ前の質問に戻りたい」という意図を受け取った場合は
None を返す。呼び出し元はこれを「戻る」の合図として扱う。
- 矢印キーモード: 選択式・自由入力ともにBackspaceキー(自由入力は入力が空の状態で押した場合)
- 番号入力モード: 選択式は `b`、自由入力は `:b` のみを入力してEnter(矢印キーモードでも使用可)
"""

import os

try:
    import msvcrt

    _HAS_MSVCRT = True
except ImportError:
    _HAS_MSVCRT = False

_ARROW_PREFIXES = (0, 224)
_ARROW_UP = 72
_ARROW_DOWN = 80
_ENTER = 13
_SPACE = 32
_BACKSPACE = 8

_BACK_COMMAND = "b"
_BACK_TEXT_COMMAND = ":b"


def select(title: str, options: list[str]) -> int | None:
    """選択肢から1つ選ばせ、選ばれたインデックス(0始まり)を返す

    戻る操作(矢印キーモード: Backspaceキー、番号入力モード: `b`)をした場合は None を返す。
    """
    if not _HAS_MSVCRT:
        return _select_by_number(title, options)
    return _select_by_arrow_key(title, options)


def _render(title: str, options: list[str], cursor: int) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    print(title)
    print()
    for i, option in enumerate(options):
        marker = "> " if i == cursor else "  "
        print(f"{marker}{option}")
    print("\n(↑↓キーで移動、Enterで決定、Backspaceで前の質問に戻る)")


def _select_by_arrow_key(title: str, options: list[str]) -> int | None:
    cursor = 0
    _render(title, options, cursor)
    while True:
        key = msvcrt.getch()
        code = ord(key)
        if code in _ARROW_PREFIXES:
            code = ord(msvcrt.getch())
            if code == _ARROW_UP:
                cursor = (cursor - 1) % len(options)
                _render(title, options, cursor)
            elif code == _ARROW_DOWN:
                cursor = (cursor + 1) % len(options)
                _render(title, options, cursor)
        elif code == _ENTER:
            return cursor
        elif code == _BACKSPACE:
            return None


def _select_by_number(title: str, options: list[str]) -> int | None:
    print(title)
    for i, option in enumerate(options, start=1):
        print(f"  {i}. {option}")
    print(f"(前の質問に戻る場合は `{_BACK_COMMAND}` を入力)")
    while True:
        choice = input("番号を入力: ").strip()
        if choice.lower() == _BACK_COMMAND:
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice) - 1
        print("入力が不正です。番号を選び直してください。")


def select_multiple(title: str, options: list[str]) -> list[int] | None:
    """選択肢から複数選ばせ、選ばれたインデックス(0始まり)のリストを返す(0件も可)

    戻る操作(矢印キーモード: Backspaceキー、番号入力モード: `b`)をした場合は None を返す。
    """
    if not _HAS_MSVCRT:
        return _select_multiple_by_number(title, options)
    return _select_multiple_by_arrow_key(title, options)


def _render_multi(title: str, options: list[str], cursor: int, selected: set[int]) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    print(title)
    print()
    for i, option in enumerate(options):
        pointer = "> " if i == cursor else "  "
        checkbox = "[x]" if i in selected else "[ ]"
        print(f"{pointer}{checkbox} {option}")
    print("\n(↑↓キーで移動、Spaceで選択/解除、Enterで決定、Backspaceで前の質問に戻る)")


def _select_multiple_by_arrow_key(title: str, options: list[str]) -> list[int] | None:
    cursor = 0
    selected: set[int] = set()
    _render_multi(title, options, cursor, selected)
    while True:
        key = msvcrt.getch()
        code = ord(key)
        if code in _ARROW_PREFIXES:
            code = ord(msvcrt.getch())
            if code == _ARROW_UP:
                cursor = (cursor - 1) % len(options)
                _render_multi(title, options, cursor, selected)
            elif code == _ARROW_DOWN:
                cursor = (cursor + 1) % len(options)
                _render_multi(title, options, cursor, selected)
        elif code == _SPACE:
            selected.symmetric_difference_update({cursor})
            _render_multi(title, options, cursor, selected)
        elif code == _ENTER:
            return sorted(selected)
        elif code == _BACKSPACE:
            return None


def _select_multiple_by_number(title: str, options: list[str]) -> list[int] | None:
    print(title)
    for i, option in enumerate(options, start=1):
        print(f"  {i}. {option}")
    print("(複数選ぶ場合はカンマ区切りで番号を入力。選ばない場合は空Enter)")
    print(f"(前の質問に戻る場合は `{_BACK_COMMAND}` を入力)")
    while True:
        raw = input("番号を入力: ").strip()
        if raw.lower() == _BACK_COMMAND:
            return None
        if not raw:
            return []
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if all(p.isdigit() and 1 <= int(p) <= len(options) for p in parts):
            return sorted({int(p) - 1 for p in parts})
        print("入力が不正です。番号をカンマ区切りで入力し直してください。")


def ask_text(prompt: str, required: bool = True) -> str | None:
    """自由入力を1件受け取る

    前の質問に戻りたい場合は、入力が空の状態でBackspaceキーを押すか、
    `:b` のみを入力する(いずれの場合も None を返す)。
    msvcrt が使えない環境では番号入力モードと同様、`:b` のみに対応する。
    """
    if not _HAS_MSVCRT:
        return _ask_text_by_number(prompt, required)

    while True:
        raw = _ask_text_by_arrow_key(prompt)
        if raw is None:
            return None
        value = raw.strip()
        if value == _BACK_TEXT_COMMAND:
            return None
        if value or not required:
            return value
        print("未入力です。入力してください。")


def _render_text(prompt: str, buffer: str, prev_len: int) -> int:
    """自由入力の入力中の行を再描画し、新しい表示済み文字数を返す"""
    line = prompt + buffer
    pad = max(0, prev_len - len(line))
    print("\r" + line + " " * pad + "\r" + line, end="", flush=True)
    return len(line)


def _ask_text_by_arrow_key(prompt: str) -> str | None:
    buffer = ""
    rendered_len = _render_text(prompt, buffer, 0)
    while True:
        key = msvcrt.getwch()
        code = ord(key)
        if code in _ARROW_PREFIXES:
            msvcrt.getwch()  # 矢印キーなどの特殊キーは読み捨てる
        elif code == _ENTER:
            print()
            return buffer
        elif code == _BACKSPACE:
            if buffer:
                buffer = buffer[:-1]
                rendered_len = _render_text(prompt, buffer, rendered_len)
            else:
                print()
                return None
        elif code >= 0x20 and code != 0x7F:
            buffer += key
            rendered_len = _render_text(prompt, buffer, rendered_len)


def _ask_text_by_number(prompt: str, required: bool) -> str | None:
    while True:
        value = input(prompt).strip()
        if value == _BACK_TEXT_COMMAND:
            return None
        if value or not required:
            return value
        print("未入力です。入力してください。")
