"""進め方(サブエージェント活用・フェーズ分け)に関する質問(全ジャンル共通)

コンテキスト長の増加による精度低下やトークン制限への到達を防ぐ目的で、
どのジャンルの計画依頼でも共通して聞く。回答は選択肢のまま出力せず、
意図が伝わる説明文としてプロンプトに埋め込む。
"""

import menu
import wizard
from wizard import BACK

_PHASE_POLICY_OPTIONS = [
    "フェーズに分割し、各フェーズの区切りで一旦立ち止まる",
    "フェーズに分割するが、区切りでの確認は不要",
    "フェーズ分割はせず、一気に進める",
]

_PHASE_DESCRIPTIONS = [
    "作業は複数のフェーズに分割し、各フェーズの区切りで一旦作業を止め、"
    "結果を報告して確認を得てから次のフェーズに進むこと。",
    "作業は複数のフェーズに分割して進めること。"
    "各フェーズの区切りで停止する必要はなく、そのまま次のフェーズに進んでよい。",
    "フェーズ分割はせず、一連の作業として一気に進めること。",
]

_FACT_CHECK_OPTIONS = ["行う", "行わない"]

# ダブルチェックや「複数体が同時に動く」ことを前提にした質問は、この体数未満では意味を成さないため出さない
_MULTI_AGENT_THRESHOLD = 2

_REPORT_TIMING_OPTIONS = ["1体完了するごとに報告させる", "すべて完了してから一括で報告させる"]
_REPORT_TIMING_BATCH = 1


def _ask_max_agents(_answers):
    while True:
        value = menu.ask_text("サブエージェントの累計起動数の上限を入力してください (活用しない場合は0): ")
        if value is None:
            return BACK
        if value.isdigit():
            return int(value)
        print("0以上の整数を入力してください。")


def _ask_phase_index(_answers):
    index = menu.select("作業のフェーズ分け方針を選んでください。", _PHASE_POLICY_OPTIONS)
    return BACK if index is None else index


def _ask_fact_check(answers):
    """ファクトチェック・ダブルチェックを行うか選ばせる

    ダブルチェックには担当箇所ごとに独立した2体が要るため、
    サブエージェント最大起動数が2体未満の場合は質問自体を出さない。
    """
    if answers["max_agents"] < _MULTI_AGENT_THRESHOLD:
        return None
    index = menu.select(
        "実装・調査を行う担当箇所ごとに、独立したサブエージェントによる"
        "ファクトチェック・ダブルチェックを行いますか?",
        _FACT_CHECK_OPTIONS,
    )
    return BACK if index is None else index


def _ask_report_timing(answers):
    """サブエージェント完了時の報告タイミングを選ばせる

    複数体が同時に動くことを前提にした質問のため、サブエージェント最大起動数が
    2体未満の場合は質問自体を出さない。
    """
    if answers["max_agents"] < _MULTI_AGENT_THRESHOLD:
        return None
    index = menu.select(
        "サブエージェントが複数完了する場合、報告のタイミングをどうしますか?",
        _REPORT_TIMING_OPTIONS,
    )
    return BACK if index is None else index


def ask(involves_code_editing: bool = False):
    """進め方(サブエージェント/フェーズ分け/ファクトチェック)の説明文ブロックを返す

    involves_code_editing: 実際にコードを編集するジャンル(コーディング)からの
    呼び出しかどうか。同一ファイルへの同時編集を避けるためのタスク振り分けの
    指示は、コード編集を伴わないジャンル(調査・レビュー・設計書系)では
    ノイズになるため、このフラグが立っている場合のみ出力する。

    戻る操作をした場合は wizard.BACK を返す。
    """
    steps = [
        ("max_agents", _ask_max_agents),
        ("phase_index", _ask_phase_index),
        ("fact_check_index", _ask_fact_check),
        ("report_timing_index", _ask_report_timing),
    ]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return BACK

    max_agents = answers["max_agents"]
    phase_index = answers["phase_index"]
    fact_check_enabled = max_agents >= _MULTI_AGENT_THRESHOLD and answers["fact_check_index"] == 0
    batch_report_enabled = (
        max_agents >= _MULTI_AGENT_THRESHOLD and answers["report_timing_index"] == _REPORT_TIMING_BATCH
    )

    lines = ["## 進め方", ""]
    if max_agents == 0:
        lines.append("- サブエージェントは起動せず、メインエージェントのみで作業を完了させること。")
    else:
        lines.append(
            "- メインエージェントのコンテキスト長が伸びることで作業の精度が下がるのを防ぐため、"
            "個々のタスクはサブエージェントに委譲し、メインエージェントは計画立案・タスクの分割・"
            "最終結果のまとめに専念すること。"
        )
        if batch_report_enabled:
            lines.append(
                "- 複数のサブエージェントを起動する場合、個々のサブエージェントが完了するたびに"
                "逐次報告するのではなく、すべてのサブエージェントの完了を待ってから、"
                "結果をまとめて一括で報告すること。"
            )
        if fact_check_enabled:
            lines.append(
                "- 1体のサブエージェントだけに任せると見落とし・誤りに気づけないため、"
                "実装・調査を行うすべての担当箇所において、必ず独立した2体のサブエージェントに"
                "同じ内容を実装・調査させ、双方の結果を突き合わせること(ファクトチェック・ダブルチェック)。"
            )
            lines.append(
                "- 突き合わせた結果に不一致や矛盾があった場合は、その箇所についてさらに独立した"
                "第三者の検証用サブエージェントを追加で起動し、裏取り調査を行ったうえで"
                "どちらの内容が正しいかを確定させ、最終結果に反映すること。"
            )
        if involves_code_editing and max_agents >= _MULTI_AGENT_THRESHOLD:
            lines.append(
                "- 複数のサブエージェントが同時に実装作業を行う場合、同一ファイルを複数の"
                "サブエージェントが同時に編集することがないよう、担当ファイル・担当範囲が"
                "重複しないようにタスクを割り振ること。"
            )
        lines.append(
            "- 対象の規模に対してサブエージェント数やフェーズ分割が過剰だと判断した場合は、"
            "独断で減らさず、その旨をユーザーに報告して確認を得てから着手すること。"
        )
        lines.append(
            f"- ただしトークン制限による作業の中断を防ぐため、起動するサブエージェントは"
            f"累計で最大 {max_agents} 体までとすること。"
        )
    lines.append(f"- {_PHASE_DESCRIPTIONS[phase_index]}")

    return "\n".join(lines)
