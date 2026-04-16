"""
LLM ビジュアルテスト共通ヘルパー
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

FIXTURES   = os.path.join(PROJECT_ROOT, "tests", "fixtures")
PASS_MARK  = "\033[92m[PASS]\033[0m"
FAIL_MARK  = "\033[91m[FAIL]\033[0m"
INFO_MARK  = "\033[94m[INFO]\033[0m"
TIMEOUT_MS = 120_000


def check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


def run_llm_visual_test(title: str, prompt: str, checks_fn, bg="black"):
    """
    チャットパネル経由で LLM にプロンプトを送り、
    LLM 応答完了後に checks_fn(results) で検証する。

    Parameters
    ----------
    title     : テスト表示名
    prompt    : チャットに送る自然言語プロンプト
    checks_fn : (results: list) -> None  応答後に実行する検証関数
    bg        : 背景色（デフォルト black）
    """
    from pymol import cmd
    from pymol.Qt import QtCore, QtWidgets
    from yuimol.plugin import send_chat_message, _panel_ref

    results = []

    print("\n" + "="*55)
    print(f"Visual test (LLM): {title}")
    print("="*55)

    cmd.reinitialize()
    cmd.bg_color(bg)
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    app = QtWidgets.QApplication.instance()

    # パネルが開くのを待つ
    deadline = QtCore.QDeadlineTimer(3000)
    while _panel_ref[0] is None and not deadline.hasExpired():
        app.processEvents()

    results.append(check("Chat panel opened", _panel_ref[0] is not None))
    if _panel_ref[0] is None:
        summarize(results)
        return results

    # プロンプト送信
    print(f"\n{INFO_MARK} Prompt: {prompt}")
    send_chat_message(prompt)

    # 応答待ち
    print(f"{INFO_MARK} Waiting for LLM (up to {TIMEOUT_MS//1000}s) ...")
    deadline = QtCore.QDeadlineTimer(TIMEOUT_MS)
    while not deadline.hasExpired():
        app.processEvents()
        worker = _panel_ref[0]._worker
        if worker is None or not worker.isRunning():
            break

    results.append(check("LLM responded in time", not deadline.hasExpired()))

    # ユーザー定義の検証
    checks_fn(results)

    summarize(results)
    return results
