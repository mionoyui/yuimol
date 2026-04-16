"""
PyMOL コマンド直接実行の判定ユーティリティ
"""

_PYMOL_DIRECT_COMMANDS = frozenset({
    # 構造操作
    "fetch", "load", "save", "delete", "reinitialize",
    # アラインメント・RMSD
    "align", "super", "cealign", "rms", "rms_cur", "fit",
    # 表示
    "show", "hide", "enable", "disable",
    "cartoon", "sticks", "surface", "ribbon", "lines", "spheres",
    "color", "set_color", "spectrum",
    # 視点
    "zoom", "orient", "center", "view", "rotate", "translate", "clip",
    # セレクション
    "select", "deselect",
    # 設定
    "set", "unset", "bg_color", "bg_colour",
    # 出力
    "png", "ray", "mpng",
    # その他
    "symexp", "create", "copy", "split_states",
    "remove", "h_add", "h_fill",
    "label", "distance", "angle", "dihedral",
    "isomesh", "isosurface", "volume",
    "run", "log",
})

# 自然言語と被りやすいコマンド：カンマ区切りの PyMOL 構文があるときだけ直接実行
_AMBIGUOUS_COMMANDS = frozenset({"color", "select", "label", "show", "hide", "set"})


def is_pymol_command(text: str) -> bool:
    """
    入力がPyMOLコマンドかどうかを判定する。
    - 先頭の単語が既知コマンドリストに含まれる → True
    - ただし曖昧なコマンド（color, select など）はカンマがある場合のみ True
    """
    stripped = text.strip()
    if not stripped:
        return False
    first = stripped.split()[0].lower().rstrip(",")
    if first not in _PYMOL_DIRECT_COMMANDS:
        return False
    if first in _AMBIGUOUS_COMMANDS and "," not in stripped:
        return False
    return True
