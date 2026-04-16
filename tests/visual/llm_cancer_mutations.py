"""
LLM: p53 がんホットスポット変異の可視化
========================================

pixi run test-visual-llm-cancer

LLM に 1TUP をロードさせ、がんホットスポット変異残基を色付けさせる。
"""

import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "tests", "visual"))
from _llm_helper import run_llm_visual_test, check

PROMPT = (
    "1TUPをロードして、全てのchainのp53のがんホットスポット変異残基を"
    "オレンジ色でstick表示にして。"
)


def checks(results):
    from pymol import cmd
    objects    = cmd.get_names("objects")
    selections = cmd.get_names("selections")
    llm_sels   = [s for s in selections if s.startswith("llm_")]

    results.append(check("1TUP loaded",          any("1TUP" in o.upper() for o in objects), f"{objects}"))
    results.append(check("llm_ selections made", len(llm_sels) > 0,                         f"{llm_sels}"))


run_llm_visual_test("p53 cancer hotspot mutations (1TUP)", PROMPT, checks, bg="white")
