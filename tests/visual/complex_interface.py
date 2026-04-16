"""
タンパク質複合体インターフェースの可視化テスト
==============================================

pixi run test-visual-interface

何をテストするか:
    Barnase–Barstar 複合体 (1BRS) のインターフェース残基を
    距離カットオフ (4.0 Å) で選択し色付けして、相互作用面を可視化する。

    Barnase は RNase（酵素）、Barstar はその天然阻害剤。
    この複合体は ka ~ 10^14 M-1s-1 という超高速会合の教科書的例。

Chain A = Barnase  (UniProt P00648, 110 残基)
Chain D = Barstar  (UniProt P11540,  89 残基)

期待する見た目:
  - オレンジ sticks  : Barnase 側インターフェース残基
  - シアン sticks    : Barstar 側インターフェース残基
  - 白 cartoon       : Barnase 本体（半透明）
  - グレー cartoon   : Barstar 本体（半透明）
  - インターフェース中央にズームされた kawaii render
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

PDB_ID        = "1BRS"
CUTOFF        = 4.0   # Å — インターフェース判定距離
CHAIN_BARNASE = "A"
CHAIN_BARSTAR = "D"


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    results = []

    print("\n" + "="*55)
    print("Visual test: Barnase–Barstar interface (1BRS)")
    print("="*55)

    cmd.reinitialize()
    cmd.bg_color("black")
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    # ------------------------------------------------------------------
    # 構造ロード
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Fetching {PDB_ID} ...")
    cmd.fetch(PDB_ID, async_=0)
    cmd.hide("everything", "solvent")
    results.append(_check(f"{PDB_ID} loaded", PDB_ID in cmd.get_names("objects")))

    chains = cmd.get_chains(PDB_ID)
    print(f"{INFO_MARK} Chains in structure: {chains}")

    # チェーン存在確認（なければ最初の2チェーンにフォールバック）
    protein_chains = [c for c in sorted(chains) if c.strip()]
    if CHAIN_BARNASE in protein_chains and CHAIN_BARSTAR in protein_chains:
        c1, c2 = CHAIN_BARNASE, CHAIN_BARSTAR
        label1, label2 = "Barnase", "Barstar"
    else:
        c1, c2 = protein_chains[0], protein_chains[1]
        label1, label2 = f"Chain {c1}", f"Chain {c2}"
        print(f"{INFO_MARK} Expected A/D not found — using {c1}/{c2}")

    results.append(_check(f"{label1} chain ({c1}) present", c1 in protein_chains))
    results.append(_check(f"{label2} chain ({c2}) present", c2 in protein_chains))

    # ------------------------------------------------------------------
    # ベース表示（半透明 cartoon）
    # ------------------------------------------------------------------
    cmd.show("cartoon", PDB_ID)
    cmd.color("white",    f"{PDB_ID} and chain {c1}")
    cmd.color("0x888888", f"{PDB_ID} and chain {c2}")
    cmd.set("cartoon_transparency", 0.35, PDB_ID)

    # ------------------------------------------------------------------
    # インターフェース残基を距離で選択
    # ------------------------------------------------------------------
    sel_if1 = f"iface_{c1}"
    sel_if2 = f"iface_{c2}"
    cmd.select(sel_if1, f"byres ({PDB_ID} and chain {c1} and polymer within {CUTOFF} of ({PDB_ID} and chain {c2}))")
    cmd.select(sel_if2, f"byres ({PDB_ID} and chain {c2} and polymer within {CUTOFF} of ({PDB_ID} and chain {c1}))")

    n1 = cmd.count_atoms(f"{sel_if1} and name CA")
    n2 = cmd.count_atoms(f"{sel_if2} and name CA")
    print(f"{INFO_MARK} {label1} interface: {n1} residues (≤ {CUTOFF} Å from {label2})")
    print(f"{INFO_MARK} {label2} interface: {n2} residues (≤ {CUTOFF} Å from {label1})")

    results.append(_check(f"{label1} interface residues found", n1 >= 5, f"{n1} residues"))
    results.append(_check(f"{label2} interface residues found", n2 >= 5, f"{n2} residues"))

    # ------------------------------------------------------------------
    # 色付け & sticks
    # ------------------------------------------------------------------
    cmd.set("cartoon_transparency", 0.0)
    cmd.color("0xFF8C00", sel_if1)   # dark orange — Barnase
    cmd.color("0x00CED1", sel_if2)   # dark turquoise — Barstar
    cmd.show("sticks", f"{sel_if1} or {sel_if2}")

    # ------------------------------------------------------------------
    # インターフェース中央にズーム
    # ------------------------------------------------------------------
    cmd.zoom(f"{sel_if1} or {sel_if2}", buffer=4)

    print(f"\n{INFO_MARK} Orange sticks  = {label1} interface residues")
    print(f"{INFO_MARK} Cyan sticks    = {label2} interface residues")
    print(f"{INFO_MARK} White cartoon  = {label1} backbone")
    print(f"{INFO_MARK} Gray cartoon   = {label2} backbone")
    print(f"{INFO_MARK} Cutoff         = {CUTOFF} Å")

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
