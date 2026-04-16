"""
render_nice ツールの動作確認
==============================

pixi run test-visual-render

1TUP を色付けして render_nice でレンダリングし、
設定が元に戻ることを確認する。
出力: render_1tup.png（プロジェクトルートに保存）
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd
from yuimol.tools import tool_color_residues, tool_reset_colors, tool_render_nice
from yuimol.uniprot import fetch_uniprot_annotations

FIXTURES    = os.path.join(PROJECT_ROOT, "tests", "fixtures")
OUTPUT_PNG  = ""  # PNG保存なし・ray のみ
PASS_MARK   = "\033[92m[PASS]\033[0m"
FAIL_MARK   = "\033[91m[FAIL]\033[0m"
INFO_MARK   = "\033[94m[INFO]\033[0m"

BINDING_POSITIONS = [234, 237, 239, 241, 242, 243, 245, 248, 273, 277, 278, 283]
ACTIVE_POSITIONS  = [176]
PROTEIN_CHAINS    = ["A", "B", "C"]


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    results = []

    print("\n" + "="*55)
    print("Visual test: render_nice")
    print("="*55)

    cmd.reinitialize()
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    # ------------------------------------------------------------------
    # 構造ロード・色付け
    # ------------------------------------------------------------------
    cmd.load(os.path.join(FIXTURES, "1TUP.cif"), "1TUP")
    cmd.hide("everything", "solvent")
    cmd.show("cartoon", "1TUP")

    print(f"\n{INFO_MARK} Fetching UniProt P04637 ...")
    anno        = fetch_uniprot_annotations("P04637")
    uniprot_seq = anno["sequence"]

    tool_reset_colors(cmd, {})
    for chain in PROTEIN_CHAINS:
        tool_color_residues(cmd, {
            "object_name":       "1TUP",
            "chain":             chain,
            "uniprot_positions": ACTIVE_POSITIONS,
            "color":             "red",
            "selection_name":    f"llm_active_{chain}",
            "uniprot_sequence":  uniprot_seq,
        })
        tool_color_residues(cmd, {
            "object_name":       "1TUP",
            "chain":             chain,
            "uniprot_positions": BINDING_POSITIONS,
            "color":             "yellow",
            "selection_name":    f"llm_binding_{chain}",
            "uniprot_sequence":  uniprot_seq,
        })

    cmd.show("sticks", "1TUP and not polymer")
    cmd.color("green", "1TUP and not polymer")
    cmd.hide("everything", "solvent")
    cmd.zoom("1TUP", buffer=3)

    # ------------------------------------------------------------------
    # render_nice 実行前の設定を記録
    # ------------------------------------------------------------------
    try:
        r, g, b = cmd.get_setting_tuple("bg_rgb")[0]
        bg_before = "0x%02X%02X%02X" % (int(r*255), int(g*255), int(b*255))
    except Exception:
        bg_before = "unknown"
    ambient_before = cmd.get("ambient")

    # ------------------------------------------------------------------
    # render_nice 実行（restore=True で設定が元に戻るか確認）
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Running render_nice (restore check) ...")
    res = tool_render_nice(cmd, {"filename": OUTPUT_PNG, "width": 1200, "height": 900, "restore": True})
    results.append(_check("render_nice returned success", res.get("success") is True))

    # ------------------------------------------------------------------
    # 設定が元に戻っているか確認
    # ------------------------------------------------------------------
    try:
        r, g, b = cmd.get_setting_tuple("bg_rgb")[0]
        bg_after = "0x%02X%02X%02X" % (int(r*255), int(g*255), int(b*255))
    except Exception:
        bg_after = "unknown"
    ambient_after = cmd.get("ambient")
    results.append(_check("bg_color restored",  bg_after == bg_before,
                           f"{bg_before!r} → {bg_after!r}"))
    results.append(_check("ambient restored",   ambient_after == ambient_before,
                           f"{ambient_before!r} → {ambient_after!r}"))

    # ------------------------------------------------------------------
    # 最後に kawaii render（restore=False で見た目を維持、ビューポートサイズに合わせる）
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Final kawaii render ...")
    vw, vh = cmd.get_viewport()
    tool_render_nice(cmd, {"filename": OUTPUT_PNG, "width": vw, "height": vh, "restore": False})

    print(f"\n{INFO_MARK} Output: {OUTPUT_PNG}")

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
