"""GitHubのIssue・PRに関する質問(gitリポジトリの場合のみ使う)

回答は選択肢のまま出力せず、意図が伝わる説明文としてプロンプトに埋め込む。

Issue番号は1問の数値入力に統合している(0=新規作成, -1=使わない, 正の数=既存Issue)。
新規作成の場合、GitHub側で番号が採番されるまで実際の番号は分からないため、
ブランチ名・コミットメッセージは「新規作成したIssueの番号を使う」という
指示にとどめ、こちらで決め打ちした番号を書かないようにしている。
"""

import subprocess

import menu
import wizard
from wizard import BACK

_PR_OPTIONS = ["作成する", "作成しない"]
_BRANCH_OPTIONS = ["カレントブランチ", "その他(自由入力)"]
_RECORD_OPTIONS = ["記録する", "記録しない"]
_COMMIT_PUSH_OPTIONS = ["コミット・プッシュ両方行う", "コミットのみ行う(プッシュはしない)", "どちらも行わない"]
_COMMIT_PUSH_QUESTION = "作業完了後、変更をコミット・プッシュしますか?"

_COMMIT_PUSH_BOTH = 0
_COMMIT_PUSH_COMMIT_ONLY = 1
_COMMIT_PUSH_NEITHER = 2

_ISSUE_NONE = -1
_ISSUE_NEW = 0


def public_record_notice_lines() -> list[str]:
    """Issue作成・Issueへのコメント記録・コミット・PR作成など、内容が公開リポジトリに
    残る操作を行う場合に追加する注意事項を返す
    """
    return [
        "- コミットメッセージ・PR本文・Issueコメントなど、リポジトリに残る記録に、"
        "個人のアカウントに繋がるセッションURLを含めないこと。",
        "- 依頼内容にファイルパスや添付ファイルの情報が含まれる場合、ユーザー名・端末名・"
        "内部システム名など個人情報や攻撃のヒントになり得る情報はそのまま転記せず、"
        "一般化した表現に置き換えて記載すること。",
    ]


def _ask_issue_number():
    while True:
        value = menu.ask_text(
            "Issue番号を入力してください (新規作成する場合は0、Issueを使わない場合は-1): "
        )
        if value is None:
            return BACK
        value = value.lstrip("#")
        if value.lstrip("-").isdigit():
            number = int(value)
            if number >= _ISSUE_NONE:
                return number
        print("0以上の整数、新規作成なら0、使わないなら-1を入力してください。")


def _branch_override_note(branch_name: str) -> str:
    return (
        f"作業開始時点で `claude/` 等、ツール側が自動生成したブランチ上にいる場合は、"
        f"そのブランチ上で作業を進めず、ローカルで破棄したうえで `{branch_name}` ブランチを"
        f"新規作成し、そちらを作業ブランチとすること。"
    )


def _current_branch_override_note() -> str:
    return (
        "作業開始時点で `claude/` 等、ツール側が自動生成したブランチにチェックアウトされている"
        "場合は、そのブランチ上で作業を進めず、ローカルで破棄したうえでセッション開始前に"
        "チェックアウトされていた元のブランチに戻り、新しいブランチは作らずそのブランチ上で"
        "直接作業すること。"
    )


def _ask_branch_without_issue():
    while True:
        index = menu.select("対象ブランチを選択してください。", _BRANCH_OPTIONS)
        if index is None:
            return BACK
        if index == 0:
            return f"現在のブランチ(カレントブランチ)上で作業すること。\n- {_current_branch_override_note()}"
        name = menu.ask_text("ブランチ名を入力してください: ")
        if name is None:
            continue  # ブランチ選択に戻る
        return f"`{name}` ブランチ上で作業すること。\n- {_branch_override_note(name)}"


def _ask_no_issue_rest():
    """Issueを使わない場合の残り質問(ブランチ・コミット/プッシュ)を進め、本文を返す

    戻る操作でIssue番号の質問まで戻したい場合は wizard.BACK を返す。
    """

    def ask_branch(_answers):
        return _ask_branch_without_issue()

    def ask_commit_push(_answers):
        index = menu.select(_COMMIT_PUSH_QUESTION, _COMMIT_PUSH_OPTIONS)
        return BACK if index is None else index

    steps = [
        ("branch", ask_branch),
        ("commit_push_index", ask_commit_push),
    ]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return BACK

    lines = ["## バージョン管理", "", "- " + answers["branch"]]

    commit_push_index = answers["commit_push_index"]
    if commit_push_index == _COMMIT_PUSH_NEITHER:
        lines.append("- 作業完了後のコミット・プッシュは不要。")
    else:
        if commit_push_index == _COMMIT_PUSH_BOTH:
            lines.append("- 作業完了後、変更をコミットしたうえでプッシュすること。")
        else:
            lines.append("- 作業完了後、変更をコミットすること(リモートへのプッシュは不要)。")
        lines.extend(public_record_notice_lines())

    return "\n".join(lines)


def _list_remote_branches(directory: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", directory, "branch", "-r"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    branches = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name or "->" in name:
            continue
        branches.append(name)
    return branches


def _ask_merge_target(directory: str):
    branches = _list_remote_branches(directory)
    if not branches:
        value = menu.ask_text("マージ先のブランチ名を入力してください: ")
        return BACK if value is None else value
    index = menu.select("マージ先のブランチを選択してください。", branches)
    return BACK if index is None else branches[index]


def _issue_and_branch_lines(issue_number: int) -> list[str]:
    """Issue番号に応じた説明文を返す(新規作成時は番号を決め打ちしない、コミットメッセージ規約は含まない)"""
    if issue_number == _ISSUE_NEW:
        return [
            "- GitHubに新しいIssueを作成し、その内容に沿って作業すること。",
            "- 作成したIssueの番号を、以降のブランチ名・コミットメッセージ・Issueへの記録に使用すること。",
            "- 作成したIssueの番号を用いて `#<Issue番号>` という名前のブランチを作成し、そのブランチ上で作業すること。",
            f"- {_branch_override_note('#<Issue番号>')}",
        ]
    return [
        f"- 既存の Issue #{issue_number} に沿って作業すること。",
        f"- 作業前に `gh issue view {issue_number}` を実行し、Issueの内容を必ず確認すること。"
        "実行できない・失敗した場合は、推測で進めず、Issueの内容についてユーザーに確認すること。",
        f"- `#{issue_number}` という名前のブランチを作成し、そのブランチ上で作業すること。",
        f"- {_branch_override_note(f'#{issue_number}')}",
    ]


def _commit_message_line(issue_number: int) -> str:
    """コミットメッセージ規約の説明文を返す(新規作成時は番号を決め打ちしない)"""
    if issue_number == _ISSUE_NEW:
        return "- コミットメッセージは必ず作成したIssueの番号から始めること(例: `#<Issue番号> 〇〇を実装`)。"
    return f"- コミットメッセージは必ず `#{issue_number}` から始めること(例: `#{issue_number} 〇〇を実装`)。"


def _ask_rest_with_issue(directory_path: str, issue_number: int):
    """既存/新規Issue使用時の残り質問(記録可否・コミット/プッシュ・PR作成可否)を進め、本文を返す

    戻る操作でIssue番号の質問まで戻したい場合は wizard.BACK を返す。
    """

    def ask_record(_answers):
        index = menu.select("修正/実装内容をIssueに記録しますか?", _RECORD_OPTIONS)
        return BACK if index is None else index

    def ask_commit_push(_answers):
        index = menu.select(_COMMIT_PUSH_QUESTION, _COMMIT_PUSH_OPTIONS)
        return BACK if index is None else index

    def ask_pr(answers):
        # プッシュしない場合はPRを作成できないため質問自体を出さない
        if answers["commit_push_index"] != _COMMIT_PUSH_BOTH:
            return None
        index = menu.select("タスク完了時にPRを作成しますか?", _PR_OPTIONS)
        return BACK if index is None else index

    def ask_merge_target(answers):
        if answers.get("pr_index") != 0:
            return ""
        return _ask_merge_target(directory_path)

    steps = [
        ("record_index", ask_record),
        ("commit_push_index", ask_commit_push),
        ("pr_index", ask_pr),
        ("merge_target", ask_merge_target),
    ]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return BACK

    lines = ["## GitHub / バージョン管理", ""]
    lines += _issue_and_branch_lines(issue_number)
    if answers["record_index"] == 0:
        lines.append("- 作業完了後、実装/修正した内容を Issue にコメントとして記録すること。")

    commit_push_index = answers["commit_push_index"]
    if commit_push_index == _COMMIT_PUSH_NEITHER:
        lines.append("- 作業完了後のコミット・プッシュは不要。")
    else:
        lines.append(_commit_message_line(issue_number))
        if commit_push_index == _COMMIT_PUSH_BOTH:
            lines.append("- 作業完了後、変更をコミットしたうえでプッシュすること。")
            if answers["pr_index"] == 0:
                lines.append(f"- 作業完了後、`{answers['merge_target']}` をマージ先とする Pull Request を作成すること。")
            else:
                lines.append("- Pull Request の作成は不要。")
        else:
            lines.append("- 作業完了後、変更をコミットすること(リモートへのプッシュは不要)。")

    if issue_number == _ISSUE_NEW or answers["record_index"] == 0 or commit_push_index != _COMMIT_PUSH_NEITHER:
        lines.extend(public_record_notice_lines())

    return "\n".join(lines)


def ask(directory_path: str, is_git_repo: bool):
    """コード変更を伴う作業向け。GitHub/バージョン管理の説明文ブロックを返す

    gitリポジトリでない場合は空文字を返す。戻る操作をした場合は wizard.BACK を返す。
    """
    if not is_git_repo:
        return ""

    while True:
        issue_number = _ask_issue_number()
        if issue_number is BACK:
            return wizard.BACK

        if issue_number == _ISSUE_NONE:
            rest = _ask_no_issue_rest()
            if rest is BACK:
                continue  # Issue番号の質問に戻る
            return rest

        rest = _ask_rest_with_issue(directory_path, issue_number)
        if rest is BACK:
            continue  # Issue番号の質問に戻る
        return rest


def ask_investigation(is_git_repo: bool, result_label: str = "調査結果"):
    """コード変更を伴わない作業向けの軽量版(ブランチ・コミット規約・PR関連は聞かない)

    gitリポジトリでない、またはIssueを使わない場合は空文字を返す。
    戻る操作をした場合は wizard.BACK を返す。
    """
    if not is_git_repo:
        return ""

    while True:
        issue_number = _ask_issue_number()
        if issue_number is BACK:
            return wizard.BACK

        if issue_number == _ISSUE_NONE:
            return ""

        index = menu.select(f"{result_label}をIssueに記録しますか?", _RECORD_OPTIONS)
        if index is None:
            continue  # Issue番号の質問に戻る

        lines = ["## GitHub / Issue", ""]
        if issue_number == _ISSUE_NEW:
            lines.append("- GitHubに新しいIssueを作成し、その内容に沿って作業すること。")
        else:
            lines.append(f"- 既存の Issue #{issue_number} に沿って作業すること。")
            lines.append(
                f"- 作業前に `gh issue view {issue_number}` を実行し、Issueの内容を必ず確認すること。"
                "実行できない・失敗した場合は、推測で進めず、Issueの内容についてユーザーに確認すること。"
            )
        if index == 0:
            lines.append(f"- 作業完了後、{result_label}を Issue にコメントとして記録すること。")

        if issue_number == _ISSUE_NEW or index == 0:
            lines.extend(public_record_notice_lines())

        return "\n".join(lines)
