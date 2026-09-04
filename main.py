"""prompt-generator: CUIで質問に答えるだけで生成AI用プロンプトを作る静的ジェネレータ"""

from pathlib import Path

import feedback
import menu
import wizard
from genres import coding, design_doc, design_review, investigation, issue, review

GENRES = [
    ("コーディング", coding.run),
    ("コード調査", investigation.run),
    ("コードレビュー", review.run),
    ("設計書作成", design_doc.run),
    ("設計書レビュー", design_review.run),
]

# 直接実行モードでのみ選べるジャンル(計画立案モードのジャンル一覧の先頭には追加しない)。
# Issue作成は単発の軽い作業で、計画を立てさせる意味がないため。
EXECUTE_ONLY_GENRES = [
    ("Issue作成", issue.run),
]

MODE_OPTIONS = ["計画立案(まず作業計画を立てさせる)", "直接実行(その場で作業を行わせる)"]
MODE_PLAN = "plan"
MODE_EXECUTE = "execute"

OUTPUT_OPTIONS = ["ターミナルに表示", "mdファイルに出力", "両方"]


def _genres_for_mode(mode_index: int) -> list[tuple[str, object]]:
    if mode_index == 1:  # 直接実行
        return EXECUTE_ONLY_GENRES + GENRES
    return GENRES


def _ask_mode(_answers):
    index = menu.select("=== prompt-generator ===\n生成するプロンプトの種類を選択してください。", MODE_OPTIONS)
    return wizard.BACK if index is None else index


def _ask_genre(answers):
    labels = [label for label, _ in _genres_for_mode(answers["mode_index"])]
    index = menu.select("作成したいプロンプトのジャンルを選択してください。", labels)
    return wizard.BACK if index is None else index


def select_mode_and_genre() -> tuple[str, tuple[str, object]] | None:
    """モード(計画立案/直接実行)とジャンルを選ばせる

    モード選択は最初の質問で戻る先がないため、戻る操作をした場合は None を返す。
    ジャンル選択で戻る操作をした場合はモード選択からやり直しになる。
    """
    steps = [("mode_index", _ask_mode), ("genre_index", _ask_genre)]
    answers = wizard.run_named_steps(steps, allow_escape=True)
    if answers is wizard.BACK:
        return None
    mode = MODE_PLAN if answers["mode_index"] == 0 else MODE_EXECUTE
    genres = _genres_for_mode(answers["mode_index"])
    return mode, genres[answers["genre_index"]]


def ask_output_destination() -> int:
    while True:
        index = menu.select("出力先を選択してください。", OUTPUT_OPTIONS)
        if index is None:
            print("これ以上前の質問には戻れません。出力先を選び直してください。")
            continue
        return index


def show_prompt(prompt: str) -> None:
    print("\n===== 生成されたプロンプト =====")
    print(prompt)
    print("================================\n")


def show_feedback_prompt(feedback_prompt: str) -> None:
    print("\n===== 作業完了後に投げるフィードバック依頼プロンプト =====")
    print(feedback_prompt)
    print("========================================================\n")


def save_prompt(prompt: str, feedback_prompt: str) -> None:
    filename = input("保存するファイル名 (拡張子なし、Enterで既定値 'prompt'): ").strip()
    if not filename:
        filename = "prompt"
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    path = output_dir / f"{filename}.md"
    path.write_text(prompt, encoding="utf-8")
    print(f"保存しました: {path}")

    feedback_path = output_dir / f"{filename}-feedback.md"
    feedback_path.write_text(feedback_prompt, encoding="utf-8")
    print(f"保存しました: {feedback_path}")


def main() -> None:
    while True:
        selected = select_mode_and_genre()
        if selected is None:
            # モード選択は最初の質問で戻る先がないため、選び直させる
            continue
        mode, (label, handler) = selected
        if handler is None:
            print(f"「{label}」は未実装です。今後追加予定です。")
            return

        prompt = handler(mode)
        if prompt is wizard.BACK:
            continue  # モード選択・ジャンル選択に戻る
        break

    feedback_prompt = feedback.build(prompt)

    destination = ask_output_destination()
    if destination in (0, 2):
        show_prompt(prompt)
        show_feedback_prompt(feedback_prompt)
    if destination in (1, 2):
        save_prompt(prompt, feedback_prompt)


if __name__ == "__main__":
    main()
