"""設計書作成計画依頼プロンプトの質問セットと組み立て処理

回答は選択肢のまま羅列せず、意図が伝わる説明文としてプロンプトに埋め込む。
質問の前後移動は wizard.py の共通ヘルパーを使う。
"""

import directory
import execution_strategy
import github
import menu
import wizard
from wizard import BACK


def _ask(prompt: str, required: bool = True):
    return menu.ask_text(prompt, required=required)


def _ask_new_document():
    def ask_overview():
        value = _ask("対象の機能・システムの概要を教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_overview])
    if result is BACK:
        return BACK
    return [f"- 対象の機能・システムの概要: {result[0]}"]


def _ask_update_document():
    def ask_target_file():
        value = _ask("更新対象の設計書ファイルを教えてください: ")
        return BACK if value is None else value

    def ask_content():
        value = _ask("更新したい内容を教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_target_file, ask_content])
    if result is BACK:
        return BACK
    target_file, content = result
    return [
        f"- 更新対象の設計書ファイル: {target_file}",
        f"- 更新したい内容: {content}",
    ]


# 種別ラベルと、その種別の対象を尋ねる処理の対応表(テーブル駆動)
TYPES = [
    ("新規作成", _ask_new_document),
    ("既存更新", _ask_update_document),
]

_SECTION_OPTIONS = [
    "背景・目的",
    "要件定義",
    "アーキテクチャ・構成図",
    "API仕様",
    "データベース設計",
    "シーケンス図・処理フロー",
    "エラーハンドリング",
    "テスト方針",
]


def _ask_sections():
    """記載してほしい項目を文章化して返す(0件ならAIの判断に委ねる文にする、戻るならBACK)"""
    indexes = menu.select_multiple("設計書に記載してほしい項目を選択してください (複数選択可)", _SECTION_OPTIONS)
    if indexes is None:
        return BACK
    if not indexes:
        return "記載する項目に特に指定はない。必要と思われる項目をAI自身で判断して構成すること。"

    labels = [_SECTION_OPTIONS[i] for i in indexes]
    return f"次の項目を含めること: {'、'.join(labels)}。"


def _premise_block(sections_text: str, output_format: str, constraints: str, context: str) -> str:
    lines = ["## 前提・制約", ""]
    lines.append(f"- {sections_text}")
    lines.append(f"- 設計書は「{output_format}」の形式で作成すること。")
    if constraints:
        lines.append(f"- 次の制約・注意点を必ず守ること: {constraints}")
    if context:
        lines.append(f"- 参考情報: {context}")
    return "\n".join(lines)


def _build_prompt(mode, target_path, type_label, task_bullets, premise, strategy, github_block):
    blocks = []
    if mode == "plan":
        blocks.append(
            "# 設計書作成計画依頼\n\n"
            "以下の設計書作成について、作成計画(作業手順)を立ててください。\n"
            "**この依頼は計画立案のみが目的です。この時点では設計書の作成は行わないでください。**"
        )
    else:
        blocks.append("# 設計書作成依頼\n\n以下の設計書を作成してください。")
    blocks.append(f"## 対象\n\n- 作業ディレクトリ: `{target_path}`")
    task_action = "行うための計画を立ててください" if mode == "plan" else "行ってください"
    blocks.append(
        f"## 作業の種別と内容\n\n下記の「{type_label}」を{task_action}。\n\n"
        + "\n".join(task_bullets)
    )
    blocks.append(premise)
    blocks.append(strategy)
    if github_block:
        blocks.append(github_block)
    return "\n\n".join(blocks) + "\n"


def _ask_target(_answers):
    return directory.ask()


def _ask_type_and_details(_answers):
    labels = [label for label, _ in TYPES]
    while True:
        index = menu.select("種別を選択してください。", labels)
        if index is None:
            return BACK
        type_label, ask_type_specific = TYPES[index]
        result = ask_type_specific()
        if result is BACK:
            continue  # 種別選択に戻る
        return (type_label, result)


def _ask_sections_step(_answers):
    return _ask_sections()


def _ask_output_format(_answers):
    value = _ask("作成する設計書の形式を教えてください (例: Markdown/箇条書き中心/図を多用): ")
    return BACK if value is None else value


def _ask_constraints(_answers):
    value = _ask("制約条件・注意点があれば教えてください (なければ空Enter): ", required=False)
    return BACK if value is None else value


def _ask_context(_answers):
    value = _ask("参考情報があれば教えてください (なければ空Enter): ", required=False)
    return BACK if value is None else value


def _ask_strategy(_answers):
    return execution_strategy.ask()


def _ask_github(answers):
    target = answers["target"]
    return github.ask(target.path, target.is_git_repo)


def run(mode: str):
    banner = "計画依頼" if mode == "plan" else "実行依頼"
    print(f"\n--- 設計書作成{banner}プロンプト作成 ---")

    steps = [
        ("target", _ask_target),
        ("type_and_details", _ask_type_and_details),
        ("sections_text", _ask_sections_step),
        ("output_format", _ask_output_format),
        ("constraints", _ask_constraints),
        ("context", _ask_context),
        ("strategy", _ask_strategy),
        ("github_block", _ask_github),
    ]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return wizard.BACK

    target = answers["target"]
    type_label, task_bullets = answers["type_and_details"]
    premise = _premise_block(
        answers["sections_text"], answers["output_format"], answers["constraints"], answers["context"]
    )

    return _build_prompt(
        mode, target.path, type_label, task_bullets, premise, answers["strategy"], answers["github_block"]
    )
