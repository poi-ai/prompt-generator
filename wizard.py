"""前後移動できる質問フローの共通ヘルパー

質問関数が特別な値 BACK を返すことで「1つ前の質問に戻りたい」という
意図を表現する。各genresファイルや directory.py / execution_strategy.py /
github.py はこのモジュールを使って、複数の質問を前後移動可能な形で
実行する。
"""

from typing import Callable

Step = tuple[str, Callable[[dict], object]]


class _Back:
    def __repr__(self) -> str:
        return "BACK"


BACK = _Back()


def run_named_steps(steps: list[Step], allow_escape: bool = False):
    """(キー, 質問関数)のリストを順に実行し、キー -> 回答の dict を返す

    質問関数はそれまでの回答を格納した dict を受け取り、回答または BACK を返す。
    BACK が返されたら1つ前のステップの回答を破棄し、そのステップからやり直す。

    先頭のステップで BACK が返された場合の扱いは allow_escape で切り替える。
    - True: これ以上前に戻れないため、呼び出し元に BACK をそのまま返して委ねる
    - False (既定): 戻る先がないため、同じ質問をやり直す
    """
    answers: dict = {}
    index = 0
    while index < len(steps):
        key, ask = steps[index]
        result = ask(answers)
        if result is BACK:
            if index == 0:
                if allow_escape:
                    return BACK
                continue
            prev_key = steps[index - 1][0]
            answers.pop(prev_key, None)
            index -= 1
            continue
        answers[key] = result
        index += 1
    return answers


def ask_sequence(questions: list[Callable[[], object]]):
    """引数なしの質問関数のリストを順に実行し、回答のリストを返す

    関連する複数の質問をまとめる関数(例: genresファイルの `_ask_xxx()`)向け。
    いずれかで BACK が返されたら1つ前の質問に戻ってやり直す。
    先頭の質問で BACK が返された場合は、そのまま BACK を返す。
    """

    def make_step(question: Callable[[], object]) -> Callable[[dict], object]:
        return lambda _answers: question()

    steps = [(str(i), make_step(q)) for i, q in enumerate(questions)]
    result = run_named_steps(steps, allow_escape=True)
    if result is BACK:
        return BACK
    return [result[str(i)] for i in range(len(questions))]
