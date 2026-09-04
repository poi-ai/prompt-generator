"""Issue作成依頼プロンプトの質問セットと組み立て処理(直接実行モード専用)

種別ごとの内容収集は、コーディングジャンルの「バグ修正」「新規機能実装」「改修」の
質問(genres/coding.py)をそのまま流用し、Issue本文としてまとめる。
計画立案モードには存在しない(計画を立てさせる意味がない単発の作業のため)。
"""

import directory
import menu
import wizard
from genres.coding import _ask_bugfix, _ask_modification, _ask_new_feature
from wizard import BACK


def _ask(prompt: str, required: bool = True):
    return menu.ask_text(prompt, required=required)


# 種別ラベルと、その種別の内容を尋ねる処理の対応表(テーブル駆動)
# 内容の収集はコーディングジャンルの質問をそのまま流用する
TYPES = [
    ("バグ報告", _ask_bugfix),
    ("機能要望", _ask_new_feature),
    ("変更要望", _ask_modification),
]


def _premise_block(constraints: str, context: str) -> str:
    lines = ["## 前提・制約", ""]
    if constraints:
        lines.append(f"- 次の制約・注意点を必ず守ること: {constraints}")
    if context:
        lines.append(f"- 参考情報: {context}")
    if not constraints and not context:
        lines.append("- 特になし。")
    return "\n".join(lines)


def _build_prompt(target_path, title, type_label, content_bullets, premise):
    blocks = []
    blocks.append("# Issue作成依頼\n\n以下の内容でGitHubにIssueを作成してください。")
    blocks.append(f"## 対象\n\n- 作業ディレクトリ: `{target_path}`")
    blocks.append(
        f"## Issueの内容\n\n下記の「{type_label}」の内容でIssueを作成してください。\n\n"
        f"- タイトル: {title}\n" + "\n".join(content_bullets)
    )
    blocks.append(premise)
    return "\n\n".join(blocks) + "\n"


def _ask_target(_answers):
    return directory.ask()


def _ask_title(_answers):
    value = _ask("Issueのタイトルを教えてください: ")
    return BACK if value is None else value


def _ask_type_and_details(_answers):
    labels = [label for label, _ in TYPES]
    while True:
        index = menu.select("Issueの種別を選択してください。", labels)
        if index is None:
            return BACK
        type_label, ask_type_specific = TYPES[index]
        result = ask_type_specific()
        if result is BACK:
            continue  # 種別選択に戻る
        return (type_label, result)


def _ask_constraints(_answers):
    value = _ask("制約条件・注意点があれば教えてください (なければ空Enter): ", required=False)
    return BACK if value is None else value


def _ask_context(_answers):
    value = _ask("参考情報があれば教えてください (なければ空Enter): ", required=False)
    return BACK if value is None else value


def run(mode: str):
    print("\n--- Issue作成依頼プロンプト作成 ---")

    steps = [
        ("target", _ask_target),
        ("title", _ask_title),
        ("type_and_details", _ask_type_and_details),
        ("constraints", _ask_constraints),
        ("context", _ask_context),
    ]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return wizard.BACK

    target = answers["target"]
    type_label, content_bullets = answers["type_and_details"]
    premise = _premise_block(answers["constraints"], answers["context"])

    return _build_prompt(target.path, answers["title"], type_label, content_bullets, premise)
