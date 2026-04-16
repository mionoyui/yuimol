"""
LLM: Barnase–Barstar 複合体インターフェース
============================================

pixi run test-visual-llm-interface

LLM に 1BRS をロードさせ、2タンパク質のインターフェース残基を色付けさせる。
"""

import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "tests", "visual"))
from _llm_helper import run_llm_visual_test, check

PROMPT = (
    "1BRS（BarnaseとBarstarの複合体）をロードして、"
    "2つのタンパク質間のインターフェース残基をそれぞれ異なる色で"
    "stick表示にして。"
)


def checks(results):
    from pymol import cmd
    objects  = cmd.get_names("objects")
    llm_sels = [s for s in cmd.get_names("selections") if s.startswith("llm_")]

    results.append(check("1BRS loaded",            any("1BRS" in o.upper() for o in objects), f"{objects}"))
    results.append(check("Interface colored",       len(objects) > 0))


run_llm_visual_test("Barnase–Barstar interface (1BRS)", PROMPT, checks, bg="black")
