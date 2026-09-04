"""コードレビュー計画依頼プロンプトの質問セットと組み立て処理

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


def _ask_file_target():
    def ask_target():
        value = _ask("レビュー対象のファイル・ディレクトリを教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_target])
    if result is BACK:
        return BACK
    return [f"- レビュー対象: {result[0]}"]


def _ask_pr_target():
    def ask_target():
        value = _ask("PR番号またはコミットハッシュを教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_target])
    if result is BACK:
        return BACK
    return [f"- レビュー対象: {result[0]}"]


# レビュー対象種別ラベルと、その種別の対象を尋ねる処理の対応表(テーブル駆動)
TYPES = [
    ("ファイル・ディレクトリ指定", _ask_file_target),
    ("PR・コミットハッシュ指定", _ask_pr_target),
]

_PERSPECTIVE_OPTIONS = [
    "バグ・不具合",
    "セキュリティ",
    "パフォーマンス",
    "可読性",
    "規約準拠(コーディング規約・命名規則等)",
    "テストカバレッジ",
]


def _ask_perspectives():
    """レビュー観点を文章化して返す(0件ならAIの判断に委ねる文にする、戻るならBACK)"""
    indexes = menu.select_multiple("レビュー観点を選択してください (複数選択可)", _PERSPECTIVE_OPTIONS)
    if indexes is None:
        return BACK
    if not indexes:
        return "特にレビュー観点の指定はない。重要と思われる観点をAI自身で判断して確認すること。"

    labels = [_PERSPECTIVE_OPTIONS[i] for i in indexes]
    return f"次の観点を重点的に確認すること: {'、'.join(labels)}。"


def _premise_block(purpose: str, perspectives: str, output_format: str, constraints: str, context: str) -> str:
    lines = ["## 前提・制約", ""]
    lines.append(f"- レビューの目的・背景: {purpose}")
    lines.append(f"- {perspectives}")
    lines.append(f"- 成果物は「{output_format}」の形式でまとめること。")
    if constraints:
        lines.append(f"- 次の制約・注意点を必ず守ること: {constraints}")
    if context:
        lines.append(f"- 参考情報: {context}")
    return "\n".join(lines)


def _build_prompt(mode, target_path, type_label, task_bullets, premise, strategy, github_block):
    blocks = []
    if mode == "plan":
        blocks.append(
            "# コードレビュー計画依頼\n\n"
            "以下のレビューについて、レビュー計画(作業手順)を立ててください。\n"
            "**この依頼は計画立案のみが目的です。この時点では実際のレビューは行わないでください。**"
        )
    else:
        blocks.append("# コードレビュー実行依頼\n\n以下のレビューを行ってください。")
    blocks.append(f"## 対象\n\n- 作業ディレクトリ: `{target_path}`")
    task_action = "行うための計画を立ててください" if mode == "plan" else "行ってください"
    blocks.append(
        f"## レビューの内容\n\n下記の「{type_label}」を{task_action}。\n\n"
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
        index = menu.select("レビュー対象の種別を選択してください。", labels)
        if index is None:
            return BACK
        type_label, ask_type_specific = TYPES[index]
        result = ask_type_specific()
        if result is BACK:
            continue  # 種別選択に戻る
        return (type_label, result)


def _ask_purpose(_answers):
    value = _ask("レビューの目的・背景を教えてください: ")
    return BACK if value is None else value


def _ask_perspectives_step(_answers):
    return _ask_perspectives()


def _ask_output_format(_answers):
    value = _ask("期待する成果物の形式を教えてください (例: 指摘一覧/サマリー+詳細/優先度付きリスト): ")
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
    return github.ask_investigation(target.is_git_repo, result_label="レビュー結果")


def run(mode: str):
    banner = "計画依頼" if mode == "plan" else "実行依頼"
    print(f"\n--- コードレビュー{banner}プロンプト作成 ---")

    steps = [
        ("target", _ask_target),
        ("type_and_details", _ask_type_and_details),
        ("purpose", _ask_purpose),
        ("perspectives", _ask_perspectives_step),
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
        answers["purpose"], answers["perspectives"], answers["output_format"], answers["constraints"], answers["context"]
    )

    return _build_prompt(
        mode, target.path, type_label, task_bullets, premise, answers["strategy"], answers["github_block"]
    )
