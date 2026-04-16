"""
yuimol.commands のユニットテスト
"""

import pytest
from yuimol.commands import is_pymol_command


@pytest.mark.parametrize("text, expected", [
    # PyMOL コマンドとして認識すべき
    ("align 1YCR, 1TUP",        True),
    ("fetch 1TUP",              True),
    ("zoom 1TUP",               True),
    ("bg_color white",          True),
    ("reinitialize",            True),
    ("color red, chain A",      True),   # カンマあり → OK
    ("show sticks, resi 50",    True),   # カンマあり → OK
    ("select site, resi 100",   True),   # カンマあり → OK
    # 自然言語として Claude に渡すべき
    ("color the active sites",  False),  # カンマなし → 自然言語
    ("select everything",       False),  # カンマなし
    ("what is p53?",            False),
    ("1YCRのRMSDを計算して",      False),
    ("show me the binding site",False),
    ("",                        False),
])
def test_is_pymol_command(text, expected):
    assert is_pymol_command(text) == expected
