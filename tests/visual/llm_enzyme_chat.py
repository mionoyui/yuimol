"""
LLM 自然言語 → チャット経由 → ツール実行 → 描画 テスト
=========================================================

pixi run test-visual-llm-enzyme

何をテストするか:
    チャットパネルに自然言語で依頼を送り、LLM がツールを呼んで
    描画まで完結するかを確認する。

    既存の test-visual-enzyme は直接ツールを呼ぶ単体テスト。
    こちらはチャットパネル経由の E2E テスト。

確認ポイント:
    - チャット欄にプロンプトが表示される
    - LLM がツールを呼んで 1CA2 をロードする
    - 活性部位が色付けされて llm_ セレクションが作られる
    - 描画結果を目で確認できる
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd

FIXTURES  = os.path.join(PROJECT_ROOT, "tests", "fixtures")
PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"
INFO_MARK = "\033[94m[INFO]\033[0m"

PROMPT = "1CA2（炭酸脱水酵素II）をロードして、活性部位の残基をマゼンダ、基質結合部位をシアンでそれぞれstick表示にして。"

TIMEOUT_MS = 120_000  # LLM 応答待ち最大 2 分


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    from pymol.Qt import QtCore, QtWidgets
    from yuimol.plugin import send_chat_message, _panel_ref

    results = []

    print("\n" + "="*55)
    print("Visual test: LLM chat → enzyme active site")
    print("="*55)

    cmd.reinitialize()
    cmd.bg_color("black")
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    # ------------------------------------------------------------------
    # チャットパネルが開くのを待つ
    # ------------------------------------------------------------------
    app = QtWidgets.QApplication.instance()

    deadline = QtCore.QDeadlineTimer(3000)
    while _panel_ref[0] is None and not deadline.hasExpired():
        app.processEvents()

    results.append(_check("Chat panel opened", _panel_ref[0] is not None))
    if _panel_ref[0] is None:
        _summarize(results)
        return results

    # ------------------------------------------------------------------
    # プロンプトをチャット経由で送信
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Sending via chat panel: {PROMPT}")
    send_chat_message(PROMPT)

    # ------------------------------------------------------------------
    # LLM 応答が完了するまでイベントループを回す
    # ------------------------------------------------------------------
    print(f"{INFO_MARK} Waiting for LLM response (up to {TIMEOUT_MS//1000}s) ...")
    deadline = QtCore.QDeadlineTimer(TIMEOUT_MS)

    while not deadline.hasExpired():
        app.processEvents()
        worker = _panel_ref[0]._worker
        if worker is None or not worker.isRunning():
            break

    timed_out = deadline.hasExpired()
    results.append(_check("LLM responded in time", not timed_out))

    # ------------------------------------------------------------------
    # 結果確認
    # ------------------------------------------------------------------
    objects = cmd.get_names("objects")
    loaded = any("1ca2" in o.lower() for o in objects)
    results.append(_check("1CA2 loaded by LLM", loaded, f"objects={objects}"))

    selections = cmd.get_names("selections")
    llm_sels = [s for s in selections if s.startswith("llm_")]
    results.append(_check(
        "llm_ selections created",
        len(llm_sels) > 0,
        f"{llm_sels}",
    ))

    if llm_sels:
        total_atoms = sum(cmd.count_atoms(s) for s in llm_sels)
        results.append(_check(
            "Colored residues have atoms",
            total_atoms > 0,
            f"{total_atoms} atoms in {llm_sels}",
        ))

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
