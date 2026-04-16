"""
アライメント修正の目視確認スクリプト
=====================================

GUI つき PyMOL で実行する（-c フラグなし）:
    pixi run test-visual

何をテストするか:
    1TUP（p53 の断片構造、UniProt 94-292 番のみ）を使って
    UniProt 座標 → PyMOL resi 番号のマッピングが正しいかを目で確認する。

    [修正前] グローバルアラインメントの末端ペナルティでオフセットがズレていた
    [修正後] target_end_gap_score=0 で断片が正しい位置にアラインされる

    Active site (赤) と Binding site (黄) が
    DNA 結合ドメインの正しい残基に乗っていれば OK。

期待する見た目:
    - 赤: 176 番（Arg176、DNA 直接接触残基の代表）
    - 黄: 234, 237, 239, 241, 242, 243, 245, 248, 273, 277, 278, 283 付近
    - DNA（HETATM）の近傍に赤・黄の残基が集中しているはず
"""

import os
import sys

# pixi run は常にプロジェクトルートをカレントディレクトリにして起動する
PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd
from yuimol.tools import tool_color_residues, tool_reset_colors

# ---------------------------------------------------------------------------
# p53 UniProt P04637 の正準配列（393 残基）
# ※ネットワーク不要にするため直接埋め込み
# ---------------------------------------------------------------------------
P53_UNIPROT_SEQ = (
    "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDP"
    "GPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYPQGLNGTVNLFRNL"
    "NKSPSSQKLMELLVNDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGQMNRRNC"
    "PILTIITLEDSSGKLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPVHGQWLDSPRTFMQ"
    "QNVVLNQLNCLKPEPIQLPEQRLNQELADGSVPPVLQFEDLESLQQLRNQSGRLALPPK"
    "QLQNPIFVQLWQFLLELLTSSPQQSQQHQQQLQQQQQQQQHQQQQQQQQQQQQQQQQQQQ"
    "QQNHQQQQ"
)
# 上記は桁合わせ用の仮配列。実際は fetch して得る。
# ここでは uniprot.py 経由でリアルに取得する。

# ---------------------------------------------------------------------------
# UniProt P04637 のアノテーション（代表的なもの）
# Active site   : 176
# Binding site  : 234,237,239,241,242,243,245,248,273,277,278,283
# 出典: UniProt P04637 Features (2024)
# ---------------------------------------------------------------------------
ACTIVE_SITE_POSITIONS  = [176]
BINDING_SITE_POSITIONS = [234, 237, 239, 241, 242, 243, 245, 248, 273, 277, 278, 283]

PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"
INFO_MARK = "\033[94m[INFO]\033[0m"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    status = PASS_MARK if ok else FAIL_MARK
    print(f"{status} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    results = []

    # ------------------------------------------------------------------
    # Step 1: ローカル CIF から 1TUP をロード
    # ------------------------------------------------------------------
    print("\n" + "="*50)
    print("Visual test: 1TUP alignment offset fix")
    print("="*50)

    cif_path = os.path.join(PROJECT_ROOT, "tests", "fixtures", "1tup.cif")
    cmd.reinitialize()
    cmd.bg_color("white")
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", os.path.join(PROJECT_ROOT, "tests", "fixtures"))

    print(f"\n{INFO_MARK} Loading {cif_path}")
    cmd.load(cif_path, "1TUP")
    objects = cmd.get_names("objects")
    ok = "1TUP" in objects
    results.append(_check("1TUP loaded", ok, f"objects={objects}"))
    if not ok:
        return results

    # ------------------------------------------------------------------
    # Step 2: UniProt 正準配列を取得
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Fetching UniProt P04637 sequence ...")
    from yuimol.uniprot import fetch_uniprot_annotations
    try:
        anno = fetch_uniprot_annotations("P04637")
        uniprot_seq = anno["sequence"]
        results.append(_check("UniProt P04637 fetched",
                               len(uniprot_seq) > 300,
                               f"len={len(uniprot_seq)}"))
        print(f"{INFO_MARK} sequence length: {len(uniprot_seq)}")
    except Exception as e:
        print(f"{FAIL_MARK} UniProt fetch failed: {e}")
        return results

    # ------------------------------------------------------------------
    # Step 3 & 4: 全タンパク質鎖（A, B, C）に Active / Binding site をカラーリング
    # アライメントは鎖ごとに独立して行う
    # ------------------------------------------------------------------
    PROTEIN_CHAINS = ["A", "B", "C"]
    tool_reset_colors(cmd, {})

    active_ok_any  = False
    binding_ok_any = False
    active_resi_check = None

    for chain in PROTEIN_CHAINS:
        print(f"\n{INFO_MARK} Chain {chain} — coloring active sites (red) ...")
        res = tool_color_residues(cmd, {
            "object_name":       "1TUP",
            "chain":             chain,
            "uniprot_positions": ACTIVE_SITE_POSITIONS,
            "color":             "red",
            "selection_name":    f"llm_active_{chain}",
            "uniprot_sequence":  uniprot_seq,
        })
        print(f"  {res}")
        if res.get("success"):
            active_ok_any = True
            if active_resi_check is None:
                active_resi_check = res.get("pymol_resi_numbers", [])

        print(f"{INFO_MARK} Chain {chain} — coloring binding sites (yellow) ...")
        res2 = tool_color_residues(cmd, {
            "object_name":       "1TUP",
            "chain":             chain,
            "uniprot_positions": BINDING_SITE_POSITIONS,
            "color":             "yellow",
            "selection_name":    f"llm_binding_{chain}",
            "uniprot_sequence":  uniprot_seq,
        })
        print(f"  {res2}")
        if res2.get("success"):
            binding_ok_any = True

    results.append(_check("Active sites colored (all chains)", active_ok_any))
    results.append(_check("Binding sites colored (all chains)", binding_ok_any))
    if active_resi_check is not None:
        results.append(_check(
            "Active site resi 176 mapped correctly",
            176 in active_resi_check,
            f"got resi={active_resi_check}",
        ))

    # ------------------------------------------------------------------
    # Step 5: 見た目を整えてズーム
    # ------------------------------------------------------------------
    all_llm = " or ".join(
        f"llm_active_{c} or llm_binding_{c}" for c in PROTEIN_CHAINS
    )
    cmd.hide("everything", "solvent")
    cmd.show("cartoon", "1TUP")
    cmd.show("sticks", all_llm)
    cmd.zoom(all_llm, buffer=8)
    cmd.orient(all_llm)

    print(f"\n{INFO_MARK} View zoomed to colored residues.")
    print(f"{INFO_MARK} Red   = Active site  (UniProt pos {ACTIVE_SITE_POSITIONS})")
    print(f"{INFO_MARK} Yellow = Binding site (UniProt pos {BINDING_SITE_POSITIONS})")
    print(f"{INFO_MARK} DNA chains should be nearby — if colors land on correct residues, alignment is correct.")

    # ------------------------------------------------------------------
    # サマリー
    # ------------------------------------------------------------------
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*50}")
    if passed == total:
        print(f"{PASS_MARK} All {total} checks passed. Inspect the view above.")
    else:
        print(f"{FAIL_MARK} {passed}/{total} checks passed.")
    print("="*50 + "\n")

    return results


run()
# PyMOL をそのまま開いておく（sys.exit しない）
