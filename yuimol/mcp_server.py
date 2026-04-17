"""
yuimol MCP サーバー

XML-RPC サーバー（pymol -R で起動）に接続し、
Claude Code からコマンドを直接実行できるようにする。

ツール一覧:
  run_pymol_command        : 任意の PyMOL コマンド実行
  fetch_structure          : PDB / AlphaFold から構造をロード
  get_loaded_structures    : ロード済みオブジェクト一覧
  fetch_uniprot_annotations: UniProt アノテーション取得
  color_residues_uniprot   : UniProt 座標 → PDB 残基番号マッピングして色付け
  show_annotation_summary  : 色付け結果と UniProt アノテーションをパネルに表示
  color_by_plddt           : AlphaFold pLDDT カラースキーム適用
  reset_colors             : 色・選択リセット

使い方:
    1. XML-RPC モードで起動: pixi run yuimol
    2. MCP サーバーを起動: yuimol-mcp (Claude Code が自動起動)
"""

import json
import os
import xmlrpc.client
from fastmcp import FastMCP

from yuimol.uniprot import fetch_uniprot_annotations as _fetch_uniprot_annotations
from yuimol.alignment import align_sequences, build_position_map
from yuimol.constants import THREE_TO_ONE

# セッション内の色付け履歴（show_annotation_summary で使用）
_colored_log: list[dict] = []

PYMOL_XMLRPC_URL = "http://localhost:9123/RPC2"
_CONN_ERROR = (
    "Error: yuimolが起動していないか XML-RPC が有効になっていません。"
    "`pixi run yuimol` で起動してください。"
)

mcp = FastMCP("yuimol")


def _proxy() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(PYMOL_XMLRPC_URL)


def _run_script_in_pymol(proxy: xmlrpc.client.ServerProxy, script: str) -> None:
    """一時スクリプトファイルを経由して PyMOL 内で Python を実行する。"""
    script_path = f"/tmp/yuimol_script_{os.getpid()}.py"
    with open(script_path, "w") as f:
        f.write(script)
    try:
        proxy.do(f"run {script_path}")
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def _log_to_panel(proxy: xmlrpc.client.ServerProxy, text: str, role: str = "tool") -> None:
    """yuimol チャットパネルにログメッセージを表示する（スレッドセーフ）。"""
    try:
        safe = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        proxy.do(f"/import yuimol.gui as _g; _g.log_from_mcp('{safe}', '{role}')")
    except Exception:
        pass


def _get_struct_residues(
    proxy: xmlrpc.client.ServerProxy, object_name: str, chain: str | None
) -> list[tuple[int, str]]:
    """PyMOL から (resi番号, 1文字アミノ酸) のリストを取得する。"""
    out_path = f"/tmp/yuimol_residues_{os.getpid()}.json"

    sel = f"({object_name}) and name CA"
    if chain:
        sel += f" and chain {chain}"

    _run_script_in_pymol(
        proxy,
        f'import json\n'
        f'data = [(int(a.resi), a.resn) for a in cmd.get_model("{sel}").atom]\n'
        f'open("{out_path}", "w").write(json.dumps(data))\n',
    )

    try:
        if not os.path.exists(out_path):
            return []
        with open(out_path) as f:
            data = json.load(f)
        return sorted((int(resi), THREE_TO_ONE.get(resn, "X")) for resi, resn in data)
    finally:
        try:
            os.unlink(out_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# MCP ツール
# ---------------------------------------------------------------------------

@mcp.tool()
def run_pymol_command(command: str) -> str:
    """
    任意の PyMOL コマンドを実行する。

    Parameters
    ----------
    command : str
        PyMOL コマンド文字列。例: "fetch 1CA2", "color magenta, resi 64",
        "align 1YCR, 1TUP", "show sticks, sele"
    """
    try:
        proxy = _proxy()
        proxy.do(command)
        return f"OK: {command}"
    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def fetch_structure(pdb_id: str, source: str = "pdb") -> str:
    """
    PDB または AlphaFold DB から構造を PyMOL にロードする。

    Parameters
    ----------
    pdb_id : str
        PDB ID（例: "1CA2"）または UniProt アクセッション（AlphaFold 用、例: "P01116"）
    source : str
        "pdb"（デフォルト）または "alphafold"
    """
    try:
        proxy = _proxy()
        fetch_id = pdb_id.upper()
        if source == "alphafold":
            fetch_id = f"AF-{fetch_id}-F1"
        proxy.do(f"fetch {fetch_id}")
        proxy.do("hide everything, solvent")
        return f"OK: fetched {fetch_id}"
    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_loaded_structures() -> str:
    """
    PyMOL に現在ロードされているオブジェクト名のリストを返す。
    色付けや操作を行う前にオブジェクト名を確認するために使う。
    """
    out_path = f"/tmp/yuimol_names_{os.getpid()}.json"
    try:
        proxy = _proxy()
        _run_script_in_pymol(
            proxy,
            f'import json\n'
            f'open("{out_path}", "w").write(json.dumps(cmd.get_names("objects")))\n',
        )
        if not os.path.exists(out_path):
            return json.dumps({"objects": []})
        with open(out_path) as f:
            names = json.load(f)
        return json.dumps({"objects": names})
    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(out_path)
        except Exception:
            pass


@mcp.tool()
def fetch_uniprot_annotations(accession: str, include_variants: bool = False) -> str:
    """
    UniProt からタンパク質アノテーションを取得する。

    活性部位・結合部位・金属配位・ドメイン・翻訳後修飾などを返す。
    canonical sequence も含まれるため color_residues_uniprot に渡せる。

    Parameters
    ----------
    accession : str
        UniProt アクセッション ID（例: "P00918" for 炭酸脱水酵素 II、"P04637" for p53）
    include_variants : bool
        自然変異・変異誘発データを含める（デフォルト: False）。
        変異について調べるときのみ True にする。
    """
    try:
        data = _fetch_uniprot_annotations(accession, include_variants=include_variants)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def color_residues_uniprot(
    object_name: str,
    uniprot_accession: str,
    uniprot_positions: list[int],
    color: str,
    chain: str | None = None,
    selection_name: str = "llm_highlight",
) -> str:
    """
    UniProt の位置番号を指定して PyMOL 上の残基を色付けする。
    UniProt 座標 → PyMOL resi 番号への自動マッピングを行うため、
    PDB と UniProt の残基番号のズレを意識する必要はない。

    Parameters
    ----------
    object_name : str
        PyMOL オブジェクト名（get_loaded_structures で確認）
    uniprot_accession : str
        UniProt アクセッション ID（例: "P00918"）。配列マッピングに使用。
    uniprot_positions : list[int]
        UniProt canonical sequence における残基位置（1-based）
    color : str
        PyMOL 色名（例: "magenta", "cyan", "orange", "gold"）
    chain : str | None
        PDB チェーン ID（省略可、例: "A"）
    selection_name : str
        PyMOL セレクション名（デフォルト: "llm_highlight"、推奨プレフィックス: "llm_"）
    """
    try:
        proxy = _proxy()
    except Exception:
        return _CONN_ERROR

    try:
        # UniProt canonical sequence を取得
        uniprot_data = _fetch_uniprot_annotations(uniprot_accession)
        uniprot_sequence: str = uniprot_data.get("sequence", "")
        if not uniprot_sequence:
            return f"Error: UniProt sequence not found for {uniprot_accession}"

        # PyMOL から構造の残基情報を取得
        struct_residues = _get_struct_residues(proxy, object_name, chain)
        if not struct_residues:
            msg = f"Error: No CA atoms found in {object_name}"
            return msg + (f" chain {chain}" if chain else "")

        # アラインメントで UniProt 位置 → PyMOL resi マップを構築
        struct_seq = "".join(aa for _, aa in struct_residues)
        aln = align_sequences(struct_seq, uniprot_sequence)
        if aln is None:
            return "Error: Sequence alignment failed"
        pos_map = build_position_map(struct_residues, aln)

        mapped_resis = [pos_map[p] for p in uniprot_positions if p in pos_map]
        missing = [p for p in uniprot_positions if p not in pos_map]

        if not mapped_resis:
            return json.dumps({
                "error": "None of the specified positions are present in the structure",
                "missing_from_structure": missing,
            })

        resi_str = "+".join(str(r) for r in sorted(set(mapped_resis)))
        chain_part = f" and chain {chain}" if chain else ""
        sele_expr = f'("{object_name}"){chain_part} and resi {resi_str}'

        proxy.do(f"select {selection_name}, {sele_expr}")
        proxy.do(f"color {color}, {selection_name}")
        proxy.do(f"show sticks, {selection_name}")

        # セッション履歴に記録
        _colored_log.append({
            "object_name": object_name,
            "accession": uniprot_accession,
            "positions": set(mapped_resis),
            "uniprot_positions": set(uniprot_positions),
            "color": color,
            "selection_name": selection_name,
        })

        # チャットパネルにサマリーを表示
        mapping_preview = ", ".join(
            f"{up}→{pp}"
            for up, pp in zip(
                [p for p in uniprot_positions if p in pos_map][:6],
                [pos_map[p] for p in uniprot_positions if p in pos_map][:6],
            )
        )
        if len(mapped_resis) > 6:
            mapping_preview += " ..."
        log_lines = [f"[MCP] {object_name} ({uniprot_accession}) → {color}"]
        log_lines.append(f"  {len(mapped_resis)} residues colored as {selection_name}")
        log_lines.append(f"  UniProt→PDB: {mapping_preview}")
        if missing:
            log_lines.append(f"  not in structure: {missing[:5]}")
        _log_to_panel(proxy, "\n".join(log_lines))

        result = {
            "success": True,
            "colored_count": len(mapped_resis),
            "selection_name": selection_name,
            "pymol_resi_numbers": sorted(set(mapped_resis)),
            "missing_from_structure": missing,
            "note": f"Colored {len(mapped_resis)} residues as '{color}'",
        }
        return json.dumps(result)

    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"


# PyMOL カラー名 → CSS カラーコードの簡易マッピング
_COLOR_CSS: dict[str, str] = {
    "magenta": "#c0399a", "cyan": "#00bcd4", "orange": "#e67e22",
    "gold": "#d4ac0d", "red": "#e74c3c", "green": "#27ae60",
    "blue": "#2980b9", "yellow": "#f1c40f", "white": "#bdc3c7",
    "salmon": "#e8a09a", "pink": "#f8a8c0", "violet": "#8e44ad",
}


@mcp.tool()
def show_annotation_summary(
    uniprot_accession: str,
    object_name: str = "",
) -> str:
    """
    UniProt アノテーションと今セッションで行った色付けをまとめてチャットパネルに表示する。
    色付けしたものとそうでないものを区別して HTML テーブルで表示。
    色付けの一連の操作が完了した後に呼ぶ。

    Parameters
    ----------
    uniprot_accession : str
        UniProt アクセッション ID（例: "P00918"）
    object_name : str
        PyMOL オブジェクト名（省略可。表示のみに使用）
    """
    try:
        proxy = _proxy()
    except Exception:
        return _CONN_ERROR

    try:
        data = _fetch_uniprot_annotations(uniprot_accession)
        protein_name = data.get("protein_name", uniprot_accession)
        organism = data.get("organism", "")
        annotations = data.get("annotations", {})

        # このセッションでこのアクセッションに色付けした UniProt 位置をまとめる
        colored_entries: list[dict] = [
            e for e in _colored_log if e["accession"] == uniprot_accession
        ]
        all_colored_uniprot: set[int] = set()
        for e in colored_entries:
            all_colored_uniprot |= e["uniprot_positions"]

        # feature ごとに「色付けしたか」を判定
        colored_rows: list[tuple] = []   # (ftype, pos_str, color, sele)
        other_rows: list[tuple] = []     # (ftype, pos_str)

        for ftype, entries in annotations.items():
            for entry in entries:
                s, e_ = entry.get("start"), entry.get("end")
                if s is None:
                    continue
                feat_positions = set(range(s, (e_ or s) + 1))
                pos_str = str(s) if s == e_ else f"{s}–{e_}"
                desc = entry.get("description", "")
                if desc:
                    pos_str += f" ({desc})"

                # この feature の位置と色付け済み位置が重なるか
                overlap = feat_positions & all_colored_uniprot
                if overlap:
                    # どの color_residues_uniprot 呼び出しと対応するか
                    match = next(
                        (c for c in colored_entries if c["uniprot_positions"] & feat_positions),
                        None,
                    )
                    color = match["color"] if match else "?"
                    sele = match["selection_name"] if match else ""
                    colored_rows.append((ftype, pos_str, color, sele))
                else:
                    other_rows.append((ftype, pos_str))

        # HTML テーブルを構築
        subtitle = f"{organism} · " if organism else ""
        html_parts = [
            f'<b style="font-size:13px">{protein_name}</b>'
            f'<span style="color:#7f8c8d;font-size:11px"> {subtitle}{uniprot_accession}'
            + (f" / {object_name}" if object_name else "") + "</span><br>",
        ]

        def _dot(color: str) -> str:
            css = _COLOR_CSS.get(color.lower(), "#888")
            return f'<span style="color:{css}">&#9679;</span>'

        if colored_rows:
            html_parts.append(
                '<table style="width:100%;font-size:12px;border-collapse:collapse;margin-top:4px">'
                '<tr style="border-bottom:1px solid #3498db;color:#3498db">'
                '<td><b>Feature</b></td><td><b>Position</b></td><td><b>Color</b></td></tr>'
            )
            for ftype, pos_str, color, sele in colored_rows:
                html_parts.append(
                    f'<tr><td style="padding:2px 4px">{ftype}</td>'
                    f'<td style="padding:2px 4px;font-family:monospace">{pos_str}</td>'
                    f'<td style="padding:2px 4px">{_dot(color)} {color}</td></tr>'
                )
            html_parts.append("</table>")

        if other_rows:
            html_parts.append(
                '<div style="color:#2c3e50;font-size:11px;margin-top:6px">その他のアノテーション</div>'
                '<table style="width:100%;font-size:12px;border-collapse:collapse;color:#2c3e50">'
            )
            for ftype, pos_str in other_rows:
                html_parts.append(
                    f'<tr><td style="padding:2px 4px">{ftype}</td>'
                    f'<td style="padding:2px 4px;font-family:monospace">{pos_str}</td></tr>'
                )
            html_parts.append("</table>")

        html = "".join(html_parts)
        _log_to_panel(proxy, html, role="html")
        return json.dumps({"success": True, "colored_features": len(colored_rows), "other_features": len(other_rows)})

    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def color_by_plddt(object_name: str = "all") -> str:
    """
    AlphaFold pLDDT スコアに基づいて公式カラースキームで色付けする。
    pLDDT は B 因子カラムに格納されている。

    Parameters
    ----------
    object_name : str
        PyMOL オブジェクト名（デフォルト: "all"）
    """
    try:
        proxy = _proxy()
        proxy.do(f"color 0x0053D6, {object_name}")
        proxy.do(f"color 0x65CBF3, ({object_name}) and b < 90")
        proxy.do(f"color 0xFFDB13, ({object_name}) and b < 70")
        proxy.do(f"color 0xFF7D45, ({object_name}) and b < 50")
        return json.dumps({
            "success": True,
            "object_name": object_name,
            "scheme": {
                ">=90": "#0053D6 (very high)",
                "70-90": "#65CBF3 (confident)",
                "50-70": "#FFDB13 (low)",
                "<50": "#FF7D45 (very low)",
            },
        })
    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def reset_colors(object_name: str = "all") -> str:
    """
    色を元素ベース（atomic）にリセットし、llm_ プレフィックスのセレクションを削除する。
    新しい色付けスキームを適用する前に呼ぶ。

    Parameters
    ----------
    object_name : str
        リセット対象の PyMOL オブジェクト名（デフォルト: "all"）
    """
    try:
        proxy = _proxy()
        proxy.do(f"color atomic, {object_name}")
        _run_script_in_pymol(
            proxy,
            'for name in cmd.get_names("selections"):\n'
            '    if name.startswith("llm_"):\n'
            '        cmd.delete(name)\n',
        )
        return json.dumps({"success": True, "reset": object_name})
    except ConnectionRefusedError:
        return _CONN_ERROR
    except Exception as e:
        return f"Error: {e}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
