"""
LLM: KRAS AlphaFold pLDDT vs PDB 重ね合わせ
============================================

pixi run test-visual-llm-kras

LLM に 4OBE と KRAS AlphaFold をロードさせ、
重ね合わせて pLDDT カラーで表示させる。
"""

import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "tests", "visual"))
from _llm_helper import run_llm_visual_test, check

PROMPT = (
    "KRAS（PDB: 4OBE）とKRASのAlphaFold予測構造（UniProt: P01116）を"
    "ロードして重ね合わせ、AlphaFold構造をpLDDTスコアで色付けして。"
    "PDB構造は白の半透明cartoonで表示して。"
)


def checks(results):
    from pymol import cmd
    objects = cmd.get_names("objects")

    has_pdb = any("4OBE" in o.upper() for o in objects)
    has_af  = any("AF" in o.upper() or "P01116" in o.upper() or "KRAS" in o.upper() for o in objects)

    results.append(check("4OBE (KRAS PDB) loaded",    has_pdb, f"{objects}"))
    results.append(check("AlphaFold structure loaded", has_af,  f"{objects}"))


run_llm_visual_test("KRAS AlphaFold pLDDT vs PDB (4OBE)", PROMPT, checks, bg="black")
