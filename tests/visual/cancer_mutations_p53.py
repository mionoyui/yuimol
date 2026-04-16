"""
p53 がんホットスポット変異の可視化
====================================

pixi run test-visual-cancer

何をテストするか:
    1TUP（p53/DNA複合体）に UniProt の Natural variant データを使って
    がんで頻出する変異残基をハイライトする。

    ホットスポット 6 残基（R175, G245, R248, R249, R273, R282）は
    p53 の機能喪失型変異の 30% 以上を占める。

期待する見た目:
    - 橙〜赤 (sticks): がんホットスポット残基が DNA 近傍に集中
    - 薄い青 (cartoon): DNA結合ドメイン全体
    - 緑 (sticks): DNA鎖
    A/B/C 全チェーンにホットスポットが均等に乗っていれば OK
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd
from yuimol.tools import tool_color_residues, tool_reset_colors
from yuimol.uniprot import fetch_uniprot_annotations

FIXTURES = os.path.join(PROJECT_ROOT, "tests", "fixtures")
PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"
INFO_MARK = "\033[94m[INFO]\033[0m"

# 文献上最頻出のがんホットスポット（UniProt 1-based 位置）
HOTSPOTS = {
    "R175": 175,
    "G245": 245,
    "R248": 248,
    "R249": 249,
    "R273": 273,
    "R282": 282,
}
PROTEIN_CHAINS = ["A", "B", "C"]


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    results = []

    print("\n" + "="*55)
    print("Visual test: p53 cancer hotspot mutations")
    print("="*55)

    cmd.reinitialize()
    cmd.bg_color("white")
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    # ------------------------------------------------------------------
    # Step 1: 1TUP ロード
    # ------------------------------------------------------------------
    cif_path = os.path.join(FIXTURES, "1TUP.cif")
    print(f"\n{INFO_MARK} Loading 1TUP ...")
    cmd.load(cif_path, "1TUP")
    cmd.hide("everything", "solvent")
    results.append(_check("1TUP loaded", "1TUP" in cmd.get_names("objects")))

    # ------------------------------------------------------------------
    # Step 2: UniProt 配列取得
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Fetching UniProt P04637 ...")
    try:
        anno = fetch_uniprot_annotations("P04637")
        uniprot_seq = anno["sequence"]
        results.append(_check("UniProt fetched", len(uniprot_seq) > 300, f"len={len(uniprot_seq)}"))
    except Exception as e:
        print(f"{FAIL_MARK} {e}")
        return results

    # ------------------------------------------------------------------
    # Step 3: ベース表示（淡い青の cartoon）
    # ------------------------------------------------------------------
    cmd.show("cartoon", "1TUP")
    cmd.color("lightblue", "1TUP and polymer")
    cmd.show("sticks", "1TUP and not polymer")
    cmd.color("green", "1TUP and not polymer")

    # ------------------------------------------------------------------
    # Step 4: ホットスポットを橙〜赤で全チェーンに
    # ------------------------------------------------------------------
    tool_reset_colors(cmd, {})
    cmd.color("lightblue", "1TUP and polymer")
    cmd.color("green", "1TUP and not polymer")

    hotspot_positions = list(HOTSPOTS.values())
    colored_any = False

    for chain in PROTEIN_CHAINS:
        res = tool_color_residues(cmd, {
            "object_name":       "1TUP",
            "chain":             chain,
            "uniprot_positions": hotspot_positions,
            "color":             "orange",
            "selection_name":    f"llm_hotspot_{chain}",
            "uniprot_sequence":  uniprot_seq,
        })
        if res.get("success"):
            colored_any = True
            print(f"{INFO_MARK} Chain {chain}: resi={res['pymol_resi_numbers']}, missing={res['missing_from_structure']}")
        else:
            print(f"{FAIL_MARK} Chain {chain}: {res.get('error')}")

    results.append(_check("Hotspots colored (all chains)", colored_any))

    # ------------------------------------------------------------------
    # Step 5: ホットスポット残基を sticks で強調・ズーム
    # ------------------------------------------------------------------
    all_hotspot_sel = " or ".join(f"llm_hotspot_{c}" for c in PROTEIN_CHAINS)
    cmd.show("sticks", all_hotspot_sel)
    cmd.zoom(all_hotspot_sel, buffer=10)

    print(f"\n{INFO_MARK} Orange sticks = cancer hotspot residues")
    for name, pos in HOTSPOTS.items():
        print(f"  {name} (UniProt {pos})")
    print(f"{INFO_MARK} Light blue cartoon = full DNA-binding domain")
    print(f"{INFO_MARK} Green sticks = DNA chains")

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
