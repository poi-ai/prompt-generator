"""対象システムのディレクトリ選択

過去に自由入力されたディレクトリパスを履歴として保持し、
次回以降は選択肢から選べるようにする。
"""

from pathlib import Path
from typing import NamedTuple

import menu
import wizard

_HISTORY_FILE = Path("history") / "directories.txt"
_HISTORY_LIMIT = 10
_OTHER_LABEL = "その他(自由入力)"

_ENV_OPTIONS = ["ローカル環境(このPC上のディレクトリ)", "リモート環境(クラウド上のセッション等)"]
_ENV_LOCAL = 0


class DirectoryInfo(NamedTuple):
    path: str
    is_git_repo: bool


def _is_git_repo(path: str) -> bool:
    """直下に.gitがあるかどうかで判定する(画面には出さない裏判定)"""
    return (Path(path) / ".git").exists()


def _load_recent() -> list[str]:
    if not _HISTORY_FILE.exists():
        return []

    lines = [line.strip() for line in _HISTORY_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]

    recent: list[str] = []
    for line in reversed(lines):
        if line not in recent:
            recent.append(line)
        if len(recent) >= _HISTORY_LIMIT:
            break
    return recent


def _write_history(entries: list[str]) -> None:
    _HISTORY_FILE.parent.mkdir(exist_ok=True)
    body = "\n".join(reversed(entries)) + "\n" if entries else ""
    _HISTORY_FILE.write_text(body, encoding="utf-8")


def _save(directory: str) -> None:
    recent = _load_recent()
    if directory in recent:
        recent.remove(directory)
    recent.insert(0, directory)
    recent = recent[:_HISTORY_LIMIT]
    _write_history(recent)


def _prune_missing(recent: list[str]) -> list[str]:
    """履歴の中から既に存在しなくなったディレクトリを除外し、履歴ファイルにも反映する"""
    valid = [d for d in recent if Path(d).is_dir()]
    if valid != recent:
        _write_history(valid)
    return valid


def ask():
    """作業環境(ローカル/リモート)とディレクトリを選ばせ、パスとgitリポジトリかどうかを返す

    このジャンルの質問フローの先頭にあたるため、戻る操作をした場合は
    wizard.BACK を返す(呼び出し元でジャンル選択のやり直しなどに使う)。
    """
    while True:
        env_index = menu.select("作業を行う環境を選択してください。", _ENV_OPTIONS)
        if env_index is None:
            return wizard.BACK

        result = _ask_local() if env_index == _ENV_LOCAL else _ask_remote()
        if result is wizard.BACK:
            continue  # 環境選択に戻る
        return result


def _ask_local():
    """ローカル環境向け: 履歴からの選択、または実在チェック付きのパス入力"""
    recent = _prune_missing(_load_recent())

    if not recent:
        path = _ask_local_path()
        if path is wizard.BACK:
            return wizard.BACK
        _save(path)
        return DirectoryInfo(path, _is_git_repo(path))

    while True:
        options = recent + [_OTHER_LABEL]
        index = menu.select("対象システムのディレクトリを選択してください。", options)
        if index is None:
            return wizard.BACK
        if index < len(recent):
            path = recent[index]
            return DirectoryInfo(path, _is_git_repo(path))

        path = _ask_local_path()
        if path is wizard.BACK:
            continue  # 履歴選択に戻る
        _save(path)
        return DirectoryInfo(path, _is_git_repo(path))


def _ask_local_path():
    while True:
        value = menu.ask_text(
            "ディレクトリのフルパスを入力してください (例: C:\\Users\\name\\project): "
        )
        if value is None:
            return wizard.BACK
        if not Path(value).is_dir():
            print("指定されたディレクトリが見つかりません。存在するパスを入力してください。")
            continue
        return value


def _ask_remote():
    """リモート環境向け: 実在チェックは行わず、gitリポジトリかどうかを直接質問する

    このPC上には存在しないパスが前提のため、履歴への保存も行わない。
    """

    def ask_path():
        value = menu.ask_text("対象ディレクトリのパスやリポジトリ名など、作業対象がわかる情報を入力してください: ")
        return wizard.BACK if value is None else value

    def ask_is_git_repo():
        index = menu.select("対象はgitリポジトリですか?", ["はい", "いいえ"])
        return wizard.BACK if index is None else index == 0

    result = wizard.ask_sequence([ask_path, ask_is_git_repo])
    if result is wizard.BACK:
        return wizard.BACK
    path, is_git_repo = result
    return DirectoryInfo(path, is_git_repo)
