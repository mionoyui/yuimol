"""
KRAS: AlphaFold pLDDT vs PDB 実験構造
========================================

pixi run test-visual-af

何をテストするか:
    AF-P01116-F1（KRAS 全長 189残基）と 4OBE（KRAS G12D/GDP 複合体）を
    重ね合わせ、pLDDT スコアと実験構造の対応を目視確認する。

    KRASのGTPaseドメイン（1-166）は高 pLDDT で PDB とよく重なるが、
    C末端のHVR（Hypervariable Region, 167-189）は膜局在シグナルを含む
    天然変性領域で pLDDT が低く、PDB に対応残基がない。

期待する見た目:
    - 青（pLDDT > 80）: GTPaseドメイン → 白い 4OBE とピッタリ重なる
    - 赤（pLDDT < 50）: HVR/C末端テール → 4OBE の外にはみ出る
    - Switch I (30-40) / Switch II (60-76) は中程度の pLDDT
    - RMSD < 2.0 Å ならアライメント良好
"""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd, stored
from yuimol.tools import tool_color_by_plddt

FIXTURES = os.path.join(PROJECT_ROOT, "tests", "fixtures")
PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"
INFO_MARK = "\033[94m[INFO]\033[0m"


def _check(label, ok, detail=""):
    print(f"{PASS_MARK if ok else FAIL_MARK} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def _ensure_fixtures():
    """必要な fixture ファイルがなければダウンロードする。"""
    import httpx

    def _dl(url, dest, label):
        if os.path.exists(dest):
            return
        print(f"{INFO_MARK} Downloading {label} ...", end="", flush=True)
        r = httpx.get(url, timeout=30.0, follow_redirects=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f" done ({len(r.content) // 1024} KB)")

    # 4OBE (KRAS PDB)
    _dl(
        "https://files.rcsb.org/download/4OBE.cif",
        os.path.join(FIXTURES, "4OBE.cif"),
        "4OBE.cif (KRAS PDB)",
    )

    # AF-P01116-F1 (KRAS AlphaFold)
    af_dest = os.path.join(FIXTURES, "AF-P01116-F1.cif")
    if not os.path.exists(af_dest):
        print(f"{INFO_MARK} Downloading AF-P01116-F1.cif ...", end="", flush=True)
        api = httpx.get(
            "https://alphafold.ebi.ac.uk/api/prediction/P01116",
            timeout=15.0, follow_redirects=True,
        )
        api.raise_for_status()
        cif_url = api.json()[0]["cifUrl"]
        r = httpx.get(cif_url, timeout=30.0, follow_redirects=True)
        r.raise_for_status()
        with open(af_dest, "wb") as f:
            f.write(r.content)
        print(f" done ({len(r.content) // 1024} KB)")


def run():
    results = []

    print("\n" + "="*55)
    print("Visual test: KRAS — AlphaFold pLDDT vs PDB")
    print("="*55)

    cmd.reinitialize()
    cmd.bg_color("black")
    cmd.viewport(1200, 900)
    cmd.set("fetch_path", FIXTURES)

    # ------------------------------------------------------------------
    # Step 1: ロード
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Loading structures ...")
    _ensure_fixtures()
    cmd.load(os.path.join(FIXTURES, "4OBE.cif"), "KRAS_PDB")
    cmd.hide("everything", "solvent")
    results.append(_check("4OBE (KRAS PDB) loaded", "KRAS_PDB" in cmd.get_names("objects")))

    cmd.load(os.path.join(FIXTURES, "AF-P01116-F1.cif"), "KRAS_AF")
    cmd.hide("everything", "solvent")
    results.append(_check("AF-P01116-F1 (KRAS AF) loaded", "KRAS_AF" in cmd.get_names("objects")))

    # ------------------------------------------------------------------
    # Step 2: super でアライメント（chain A 同士）
    # ------------------------------------------------------------------
    print(f"\n{INFO_MARK} Superimposing KRAS_AF onto KRAS_PDB ...")
    try:
        vals = cmd.super("KRAS_AF", "KRAS_PDB and chain A")
        rmsd, atoms = round(vals[0], 3), vals[1]
        results.append(_check("RMSD < 2.0 Å", rmsd < 2.0, f"RMSD={rmsd} Å, {atoms} atoms"))
        print(f"{INFO_MARK} RMSD = {rmsd} Å  ({atoms} atom pairs)")
    except Exception as e:
        results.append(_check("super completed", False, str(e)))

    # ------------------------------------------------------------------
    # Step 3: GTPase ドメイン vs HVR の pLDDT 比較
    # ------------------------------------------------------------------
    stored.b_values = []
    cmd.iterate("KRAS_AF and name CA and resi 1-166", "stored.b_values.append(b)")
    gtpase_mean = round(sum(stored.b_values) / len(stored.b_values), 1) if stored.b_values else 0

    stored.b_values = []
    cmd.iterate("KRAS_AF and name CA and resi 167-189", "stored.b_values.append(b)")
    hvr_mean = round(sum(stored.b_values) / len(stored.b_values), 1) if stored.b_values else 0

    print(f"{INFO_MARK} pLDDT mean  GTPase domain (1-166) : {gtpase_mean}")
    print(f"{INFO_MARK} pLDDT mean  HVR           (167-189): {hvr_mean}")
    results.append(_check(
        "GTPase pLDDT > HVR pLDDT",
        gtpase_mean > hvr_mean,
        f"GTPase={gtpase_mean} vs HVR={hvr_mean}",
    ))

    # ------------------------------------------------------------------
    # Step 4: 色付け
    #   KRAS_AF : pLDDT スペクトル（赤=低信頼 → 青=高信頼）
    #   KRAS_PDB: 白 cartoon（半透明）
    #   GDP/Mg²⁺: 黄 sticks
    # ------------------------------------------------------------------
    cmd.show("cartoon", "all")
    cmd.color("white", "KRAS_PDB and polymer")
    cmd.set("cartoon_transparency", 0.35, "KRAS_PDB")

    # AlphaFold 公式 pLDDT カラースキーム（tools.py の共通実装を使用）
    tool_color_by_plddt(cmd, {"object_name": "KRAS_AF"})

    # GDP・Mg²⁺ を強調
    cmd.show("sticks", "KRAS_PDB and not polymer")
    cmd.color("0xFFDB13", "KRAS_PDB and not polymer")

    cmd.zoom("all", buffer=5)
    cmd.orient("KRAS_AF")

    print(f"\n{INFO_MARK} 0x0053D6 (濃青)  pLDDT >= 90 : GTPase domain → PDB とよく重なる")
    print(f"{INFO_MARK} 0x65CBF3 (水色)  pLDDT 70-90 : confident")
    print(f"{INFO_MARK} 0xFFDB13 (黄)    pLDDT 50-70 : low confidence")
    print(f"{INFO_MARK} 0xFF7D45 (橙)    pLDDT < 50  : HVR tail → PDB の外にはみ出る")
    print(f"{INFO_MARK} White (半透明)   = 4OBE 実験構造")
    print(f"{INFO_MARK} Yellow sticks    = GDP + Mg²⁺")

    _summarize(results)
    return results


def _summarize(results):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"{PASS_MARK if passed == total else FAIL_MARK} {passed}/{total} checks passed.")
    print("="*55 + "\n")


run()
