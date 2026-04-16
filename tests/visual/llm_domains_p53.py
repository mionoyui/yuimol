"""
LLM: p53 機能ドメインの色分け（AlphaFold 全長）
================================================

pixi run test-visual-llm-domains

LLM に p53 AlphaFold 構造をロードさせ、ドメインごとに色分けさせる。
"""

import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "tests", "visual"))
from _llm_helper import run_llm_visual_test, check

PROMPT = (
    "ヒトp53（UniProt P04637）のAlphaFold構造をロードして、"
    "TAD（1-67）、プロリンリッチ（68-98）、DNA結合ドメイン（102-292）、"
    "リンカー（293-324）、四量体化ドメイン（325-356）、制御ドメイン（357-393）を"
    "それぞれ異なる色で表示して。"
)


def checks(results):
    from pymol import cmd
    objects  = cmd.get_names("objects")
    llm_sels = [s for s in cmd.get_names("selections") if s.startswith("llm_")]

    results.append(check("p53 AF structure loaded", len(objects) > 0,    f"{objects}"))
    results.append(check("llm_ selections made",    len(llm_sels) >= 3,  f"{llm_sels}"))


run_llm_visual_test("p53 domain coloring (AlphaFold)", PROMPT, checks, bg="black")
