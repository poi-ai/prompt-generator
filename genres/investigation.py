"""コード調査計画依頼プロンプトの質問セットと組み立て処理

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


def _ask_root_cause():
    def ask_problem():
        value = _ask("発生している問題・現象を教えてください: ")
        return BACK if value is None else value

    def ask_steps():
        value = _ask("再現手順があれば教えてください (なければ空Enter): ", required=False)
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_problem, ask_steps])
    if result is BACK:
        return BACK
    problem, steps = result

    bullets = [f"- 発生している問題・現象: {problem}"]
    if steps:
        bullets.append(f"- 再現手順: {steps}")
        bullets.append("- 上記の再現手順どおりに再現しない場合は、推測で進めず、その事実と実際に再現する条件を報告すること。")
    return bullets


def _ask_impact_scope():
    def ask_change():
        value = _ask("想定している変更内容を教えてください: ")
        return BACK if value is None else value

    def ask_scope():
        value = _ask("影響を確認したい範囲があれば教えてください (なければ空Enter): ", required=False)
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_change, ask_scope])
    if result is BACK:
        return BACK
    change, scope = result

    bullets = [f"- 想定している変更内容: {change}"]
    if scope:
        bullets.append(f"- 影響を確認したい範囲: {scope}")
    return bullets


def _ask_understanding():
    def ask_target():
        value = _ask("知りたい機能・処理を教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_target])
    if result is BACK:
        return BACK
    return [f"- 知りたい機能・処理: {result[0]}"]


def _ask_freeform():
    def ask_task():
        value = _ask("調査・確認してほしい内容を具体的に教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_task])
    if result is BACK:
        return BACK
    return [f"- 調査・確認してほしい内容: {result[0]}"]


# 種別ラベルと、その種別の調査内容を尋ねる処理の対応表(テーブル駆動)
TYPES = [
    ("原因調査", _ask_root_cause),
    ("影響範囲調査", _ask_impact_scope),
    ("仕様・実装の理解", _ask_understanding),
    ("その他(自由入力)", _ask_freeform),
]


def _premise_block(purpose: str, output_format: str, constraints: str, context: str) -> str:
    lines = ["## 前提・制約", ""]
    lines.append(f"- 調査の目的・背景: {purpose}")
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
            "# コード調査計画依頼\n\n"
            "以下の調査について、調査計画(作業手順)を立ててください。\n"
            "**この依頼は計画立案のみが目的です。この時点では実際の調査は行わないでください。**"
        )
    else:
        blocks.append("# コード調査依頼\n\n以下の調査を行ってください。")
    blocks.append(f"## 対象\n\n- 作業ディレクトリ: `{target_path}`")
    task_action = "行うための計画を立ててください" if mode == "plan" else "行ってください"
    blocks.append(
        f"## 調査の内容\n\n下記の「{type_label}」を{task_action}。\n\n"
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


def _ask_purpose(_answers):
    value = _ask("調査の目的・背景を教えてください: ")
    return BACK if value is None else value


def _ask_output_format(_answers):
    value = _ask("期待する成果物の形式を教えてください (例: サマリー/詳細レポート/箇条書きリスト): ")
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
    return github.ask_investigation(target.is_git_repo)


def run(mode: str):
    banner = "計画依頼" if mode == "plan" else "実行依頼"
    print(f"\n--- コード調査{banner}プロンプト作成 ---")

    steps = [
        ("target", _ask_target),
        ("type_and_details", _ask_type_and_details),
        ("purpose", _ask_purpose),
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
    premise = _premise_block(answers["purpose"], answers["output_format"], answers["constraints"], answers["context"])

    return _build_prompt(
        mode, target.path, type_label, task_bullets, premise, answers["strategy"], answers["github_block"]
    )
