"""
酵素活性部位の可視化テスト（金属酵素）
========================================

pixi run test-visual-enzyme

何をテストするか:
    ヒト炭酸脱水酵素 II (1CA2 / UniProt P00918) を使って
    UniProt アノテーションから活性部位・基質結合部位を取得し、
    Zn²⁺ 配位残基が色付けされ sticks で強調されることを確認する。

    炭酸脱水酵素は活性部位に亜鉛イオンを持つ金属酵素。
    Zn²⁺ は His94, His96, His119 の3残基で配位されており、
    金属の存在で活性部位が一目でわかる。

期待する見た目:
  - マゼンタ sticks : 触媒残基 (active site) — Zn²⁺ 配位 His など
  - シアン sticks   : 基質結合残基 (binding site)
  - 金色 sphere     : 亜鉛イオン Zn²⁺
  - デフォルト色 cartoon : タンパク質本体
  - 活性部位にズームされた kawaii render
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd
from yuimol.tools import tool_color_residues
from yuimol.uniprot import fetch_uniprot_annotations

FIXTURES  = os.path.join(PROJECT_ROOT, "tests", "fixtures")
PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"
INFO_MARK = "\033[94m[INFO]\033[0m"

UNIPROT_ID = "P00918"  # Human carbonic anhydrase 2
PDB_ID     = "1CA2"
CHAIN      = "A"


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def run():
    results = []

    print("\n" + "="*55)
    print("Visual test: Lysozyme active site (1LYZ / P00698)")
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

    # 亜鉛イオンを金色 sphere で強調
    cmd.show("spheres", f"{PDB_ID} and symbol ZN")
    cmd.color("0xFFD700", f"{PDB_ID} and symbol ZN")
    cmd.set("sphere_scale", 0.6)

    # ------------------------------------------------------------------
    # UniProt アノテーション取得
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Fetching UniProt {UNIPROT_ID} ...")
    anno          = fetch_uniprot_annotations(UNIPROT_ID)
    uniprot_seq   = anno["sequence"]
    raw_annots    = anno.get("annotations", {})

    active_sites  = [f["start"] for f in raw_annots.get("Active site",  []) if f.get("start")]
    binding_sites = [f["start"] for f in raw_annots.get("Binding site", []) if f.get("start")]

    print(f"{INFO_MARK} Sequence length : {len(uniprot_seq)}")
    print(f"{INFO_MARK} Active sites     : {active_sites}")
    print(f"{INFO_MARK} Binding sites    : {binding_sites}")

    results.append(_check(
        "UniProt sequence fetched",
        len(uniprot_seq) > 100,
        f"len={len(uniprot_seq)}",
    ))
    results.append(_check(
        "Active sites found in UniProt",
        len(active_sites) >= 1,
        f"{active_sites}",
    ))

    # ------------------------------------------------------------------
    # ベース表示
    # ------------------------------------------------------------------
    cmd.show("cartoon", PDB_ID)

    # ------------------------------------------------------------------
    # 活性部位を赤 sticks で色付け
    # ------------------------------------------------------------------
    active_ok = False
    if active_sites:
        res = tool_color_residues(cmd, {
            "object_name":       PDB_ID,
            "chain":             CHAIN,
            "uniprot_positions": active_sites,
            "color":             "magenta",
            "selection_name":    "llm_active",
            "uniprot_sequence":  uniprot_seq,
        })
        if res.get("success"):
            active_ok = True
            n = cmd.count_atoms("llm_active and name CA")
            print(f"{INFO_MARK} Active site residues colored: {n}")
            print(f"{INFO_MARK}   PDB resi: {res['pymol_resi_numbers']}")
            cmd.show("sticks", "llm_active")
        else:
            print(f"{FAIL_MARK} Active site coloring: {res.get('error')}")
    results.append(_check("Active site residues colored", active_ok))

    # ------------------------------------------------------------------
    # 基質結合部位を黄 sticks で色付け
    # ------------------------------------------------------------------
    if binding_sites:
        res = tool_color_residues(cmd, {
            "object_name":       PDB_ID,
            "chain":             CHAIN,
            "uniprot_positions": binding_sites,
            "color":             "cyan",
            "selection_name":    "llm_binding",
            "uniprot_sequence":  uniprot_seq,
        })
        if res.get("success"):
            n = cmd.count_atoms("llm_binding and name CA")
            print(f"{INFO_MARK} Binding site residues colored: {n}")
            cmd.show("sticks", "llm_binding")
        else:
            print(f"{INFO_MARK} Binding site coloring skipped: {res.get('error')}")


    print(f"\n{INFO_MARK} Magenta sticks = catalytic residues (active site, Zn²⁺ coordinating His)")
    print(f"{INFO_MARK} Cyan sticks    = substrate binding residues")
    print(f"{INFO_MARK} Gold sphere    = Zn²⁺ (zinc ion)")

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
