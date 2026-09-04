"""コーディング計画依頼プロンプトの質問セットと組み立て処理

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


def _ask_new_feature():
    def ask_content():
        content = _ask("実装したい内容(要件)を教えてください: ")
        return BACK if content is None else content

    result = wizard.ask_sequence([ask_content])
    if result is BACK:
        return BACK
    return [f"- 実装したい内容: {result[0]}"]


def _ask_modification():
    def ask_current():
        value = _ask("現在の挙動(現状)を教えてください: ")
        return BACK if value is None else value

    def ask_expected():
        value = _ask("変更後に期待する挙動を教えてください: ")
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_current, ask_expected])
    if result is BACK:
        return BACK
    current, expected = result
    return [
        f"- 現在の挙動: {current}",
        f"- 変更後に期待する挙動: {expected}",
    ]


def _ask_bugfix():
    def ask_symptom():
        value = _ask("現象(何が起きているか)を教えてください: ")
        return BACK if value is None else value

    def ask_steps():
        value = _ask("再現手順を教えてください: ")
        return BACK if value is None else value

    def ask_expected():
        value = _ask("期待する動作を教えてください: ")
        return BACK if value is None else value

    def ask_error_log():
        value = _ask("エラーメッセージ・ログがあれば教えてください (なければ空Enter): ", required=False)
        return BACK if value is None else value

    result = wizard.ask_sequence([ask_symptom, ask_steps, ask_expected, ask_error_log])
    if result is BACK:
        return BACK
    symptom, steps, expected, error_log = result

    bullets = [
        f"- 発生している現象: {symptom}",
        f"- 再現手順: {steps}",
        "- 上記の再現手順どおりに再現しない場合は、推測で進めず、その事実と実際に再現する条件を報告すること。",
        f"- 期待する動作: {expected}",
    ]
    if error_log:
        bullets.append(f"- エラーメッセージ・ログ: {error_log}")
    return bullets


# 種別ラベルと、その種別の作業内容を尋ねる処理の対応表(テーブル駆動)
TYPES = [
    ("新規機能実装", _ask_new_feature),
    ("改修", _ask_modification),
    ("バグ修正", _ask_bugfix),
]

_DOCUMENT_OPTIONS = ["README", "API仕様書", "設計書", "CHANGELOG", "その他(自由入力)"]


def _ask_documentation():
    """更新・新規作成するドキュメント名のリストを返す(なければ空リスト、戻るならBACK)"""
    indexes = menu.select_multiple("更新・新規作成するドキュメントを選択してください (複数選択可)", _DOCUMENT_OPTIONS)
    if indexes is None:
        return BACK
    if not indexes:
        return []

    labels = [_DOCUMENT_OPTIONS[i] for i in indexes]
    other_position = _DOCUMENT_OPTIONS.index("その他(自由入力)")
    if other_position in indexes:
        other_label = _ask("その他のドキュメント名を入力してください: ")
        if other_label is None:
            return BACK
        labels[labels.index("その他(自由入力)")] = other_label
    return labels


def _premise_block(mode: str, output_format: str, constraints: str, context: str) -> str:
    lines = ["## 前提・制約", ""]
    if mode == "plan":
        lines.append(
            f"- 実装フェーズでは「{output_format}」の形で成果物を出力する想定です。"
            "計画にはこの前提を織り込んでください。"
        )
    else:
        lines.append(f"- 成果物は「{output_format}」の形式で出力すること。")
    if constraints:
        lines.append(f"- 次の制約・注意点を必ず守ること: {constraints}")
    if context:
        lines.append(f"- 参考情報: {context}")
    return "\n".join(lines)


def _quality_block(keep_verification_code: bool, make_tests: bool, docs: list[str]) -> str:
    lines = ["## 品質担保", ""]
    if keep_verification_code:
        lines.append("- 実装後は必ず動作確認を行うこと。動作確認に使ったコードは成果物として残すこと。")
    else:
        lines.append("- 実装後は必ず動作確認を行うこと。動作確認に使ったコードは最終的に削除すること。")
    if make_tests:
        lines.append("- 対象の実装に対するテストコードを作成すること。")
    else:
        lines.append("- 今回はテストコードの新規作成は不要。")
    if docs:
        lines.append(f"- あわせて次のドキュメントを更新・新規作成すること: {'、'.join(docs)}")
    else:
        lines.append("- ドキュメントの更新・新規作成は不要。")
    return "\n".join(lines)


def _build_prompt(mode, target_path, type_label, task_bullets, premise, quality, strategy, github_block):
    blocks = []
    if mode == "plan":
        blocks.append(
            "# コーディング計画依頼\n\n"
            "以下の作業について、実装計画(作業手順)を立ててください。\n"
            "**この依頼は計画立案のみが目的です。この時点では実際のコード実装は行わないでください。**"
        )
    else:
        blocks.append("# コーディング実行依頼\n\n以下の作業を実装してください。")
    blocks.append(f"## 対象\n\n- 作業ディレクトリ: `{target_path}`")
    task_action = "行うための計画を立ててください" if mode == "plan" else "行ってください"
    blocks.append(
        f"## 作業の種別と内容\n\n下記の「{type_label}」を{task_action}。\n\n"
        + "\n".join(task_bullets)
    )
    blocks.append(premise)
    blocks.append(quality)
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


def _ask_output_format(_answers):
    value = _ask("実装フェーズで期待する出力形式を教えてください (例: コードのみ/説明付き/差分形式): ")
    return BACK if value is None else value


def _ask_constraints(_answers):
    value = _ask("制約条件・注意点があれば教えてください (なければ空Enter): ", required=False)
    return BACK if value is None else value


def _ask_context(_answers):
    value = _ask("参考情報・関連ファイルがあれば教えてください (なければ空Enter): ", required=False)
    return BACK if value is None else value


def _ask_keep_verification(_answers):
    index = menu.select("動作確認で使ったコードを残しますか?", ["残す", "残さない"])
    return BACK if index is None else index


def _ask_make_tests(_answers):
    index = menu.select("テストコードを作成しますか?", ["する", "しない"])
    return BACK if index is None else index


def _ask_docs(_answers):
    return _ask_documentation()


def _ask_strategy(_answers):
    return execution_strategy.ask(involves_code_editing=True)


def _ask_github(answers):
    target = answers["target"]
    return github.ask(target.path, target.is_git_repo)


def run(mode: str):
    banner = "計画依頼" if mode == "plan" else "実行依頼"
    print(f"\n--- コーディング{banner}プロンプト作成 ---")

    steps = [
        ("target", _ask_target),
        ("type_and_details", _ask_type_and_details),
        ("output_format", _ask_output_format),
        ("constraints", _ask_constraints),
        ("context", _ask_context),
        ("keep_index", _ask_keep_verification),
        ("test_index", _ask_make_tests),
        ("docs", _ask_docs),
        ("strategy", _ask_strategy),
        ("github_block", _ask_github),
    ]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return wizard.BACK

    target = answers["target"]
    type_label, task_bullets = answers["type_and_details"]
    premise = _premise_block(mode, answers["output_format"], answers["constraints"], answers["context"])
    quality = _quality_block(answers["keep_index"] == 0, answers["test_index"] == 0, answers["docs"])

    return _build_prompt(
        mode, target.path, type_label, task_bullets, premise, quality, answers["strategy"], answers["github_block"]
    )
