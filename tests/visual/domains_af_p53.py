"""
p53 ドメイン構造の色分け（AlphaFold 全長）
============================================

pixi run test-visual-domains

何をテストするか:
    AF-P04637-F1（p53 全長393残基）を UniProt の Region アノテーションを使って
    機能ドメインごとに色分けする。1TUP は DNA結合ドメインのみだが、
    AlphaFold 全長構造なら N 末端・C 末端の無秩序領域も含めて確認できる。

ドメイン配色（UniProt Region より）:
    青     : 転写活性化ドメイン (TAD, 〜67)
    シアン : プロリンリッチ領域 (68〜98)
    緑     : DNA 結合ドメイン (102〜292)
    黄     : リンカー (293〜324)
    橙     : 四量体形成ドメイン (325〜356)
    赤     : 調節ドメイン (357〜393)
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd

FIXTURES = os.path.join(PROJECT_ROOT, "tests", "fixtures")
PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"
INFO_MARK = "\033[94m[INFO]\033[0m"

# UniProt P04637 の主要ドメイン（1-based, 文献値）
DOMAINS = [
    ("TAD",              1,   67,  "blue",    "Transactivation domain"),
    ("Proline-rich",    68,   98,  "cyan",    "Proline-rich region"),
    ("DNA-binding",    102,  292,  "green",   "DNA-binding domain"),
    ("Linker",         293,  324,  "yellow",  "Linker"),
    ("Tetramerization",325,  356,  "orange",  "Tetramerization domain"),
    ("Regulatory",     357,  393,  "red",     "Regulatory domain"),
]


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    results = []

    print("\n" + "="*55)
    print("Visual test: p53 domain coloring (AlphaFold full-length)")
    print("="*55)

    cmd.reinitialize()
    cmd.bg_color("black")
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    # ------------------------------------------------------------------
    # Step 1: AlphaFold 全長構造をロード
    # ------------------------------------------------------------------
    cif_af = os.path.join(FIXTURES, "AF-P04637-F1.cif")
    print(f"\n{INFO_MARK} Loading AF-P04637-F1 ...")
    cmd.load(cif_af, "AF_p53")
    cmd.hide("everything", "solvent")
    results.append(_check("AF-P04637-F1 loaded", "AF_p53" in cmd.get_names("objects")))

    # ------------------------------------------------------------------
    # Step 2: ドメインごとに色付け（PyMOL resi は UniProt と同じ）
    # ------------------------------------------------------------------
    cmd.show("cartoon", "AF_p53")
    cmd.color("white", "AF_p53")  # ベースを白に

    print(f"\n{INFO_MARK} Coloring domains ...")
    for short_name, start, end, color, description in DOMAINS:
        sel_name = f"llm_domain_{short_name.replace('-','_')}"
        sele_expr = f"AF_p53 and resi {start}-{end}"
        cmd.select(sel_name, sele_expr)
        cmd.color(color, sel_name)
        count = cmd.count_atoms(f"{sel_name} and name CA")
        ok = count > 0
        results.append(_check(f"{short_name} ({start}-{end})", ok, f"{count} CA atoms, color={color}"))
        print(f"  {color:8s} {short_name:20s} {start:4d}-{end:4d}  {description}")

    # ------------------------------------------------------------------
    # Step 3: 表示調整
    # ------------------------------------------------------------------
    cmd.hide("(hydro)")
    cmd.zoom("AF_p53", buffer=5)
    cmd.orient("AF_p53")

    print(f"\n{INFO_MARK} Full-length p53 colored by functional domain.")
    print(f"{INFO_MARK} Disordered N/C-terminal regions visible unlike in crystal structures.")

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
