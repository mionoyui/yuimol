"""
PyMOL 操作ツール実装 + Claude tool_use スキーマ定義
"""

import os

from .uniprot import fetch_uniprot_annotations, map_pdb_to_uniprot_accession
from .alignment import get_struct_residues, align_sequences, build_position_map


# ===========================================================================
# ツール実装
# ===========================================================================

def tool_fetch_structure(cmd, inp: dict) -> dict:
    struct_id = inp.get("pdb_id", "").strip()
    source = inp.get("source", "pdb").lower()
    if not struct_id:
        return {"error": "pdb_id is required"}

    if source == "alphafold":
        return _fetch_alphafold(cmd, struct_id)

    fetch_id = struct_id.upper()
    try:
        cmd.fetch(fetch_id, async_=0)
        cmd.hide("everything", "solvent")
        objects = cmd.get_names("objects")
        loaded = any(fetch_id.lower() in n.lower() for n in objects)
        if loaded:
            return {"success": True, "fetched_id": fetch_id, "loaded_objects": objects}
        return {"error": f"fetch completed but {fetch_id} not found in scene"}
    except Exception as e:
        return {"error": str(e)}


def _fetch_alphafold(cmd, accession: str) -> dict:
    """AlphaFold DB API でURLを取得してCIFをダウンロードし PyMOL にロード。"""
    import httpx
    import tempfile

    accession = accession.upper().removeprefix("AF-").removesuffix("-F1")

    try:
        api_resp = httpx.get(
            f"https://alphafold.ebi.ac.uk/api/prediction/{accession}",
            timeout=15.0,
            follow_redirects=True,
        )
        api_resp.raise_for_status()
        entries = api_resp.json()
    except Exception as e:
        return {"error": f"AlphaFold API error for {accession}: {e}"}

    if not entries:
        return {"error": f"No AlphaFold entry found for {accession}"}

    entry = entries[0]
    cif_url = entry.get("cifUrl") or entry.get("pdbUrl")
    object_name = entry.get("entryId", f"AF-{accession}-F1")

    if not cif_url:
        return {"error": f"No download URL in AlphaFold entry for {accession}"}

    suffix = ".cif" if "cifUrl" in entry and entry["cifUrl"] else ".pdb"
    try:
        dl_resp = httpx.get(cif_url, timeout=30.0, follow_redirects=True)
        dl_resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to download {cif_url}: {e}"}

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(dl_resp.content)
        tmp_path = f.name

    try:
        cmd.load(tmp_path, object_name)
        cmd.hide("everything", "solvent")
    except Exception as e:
        return {"error": f"cmd.load failed: {e}"}
    finally:
        os.unlink(tmp_path)

    objects = cmd.get_names("objects")
    if object_name in objects:
        return {"success": True, "fetched_id": object_name, "loaded_objects": objects}
    return {"error": f"load completed but {object_name} not found in scene"}


def tool_get_loaded_structures(cmd, _input: dict) -> dict:
    names = cmd.get_names("objects")
    structures = {}
    for name in names:
        try:
            fasta = cmd.get_fastastr(name)
            structures[name] = {"fasta": fasta}
        except Exception:
            structures[name] = {"fasta": ""}
    return {"loaded_objects": structures}


def tool_map_pdb_to_uniprot(cmd, inp: dict) -> dict:
    pdb_id = inp.get("pdb_id", "")
    chain = inp.get("chain")
    accession = map_pdb_to_uniprot_accession(pdb_id, chain)
    if accession:
        return {"pdb_id": pdb_id, "chain": chain, "uniprot_accession": accession}
    return {"error": f"Could not map {pdb_id} to UniProt"}


def tool_fetch_uniprot(cmd, inp: dict) -> dict:
    accession = inp.get("accession", "")
    include_variants = inp.get("include_variants", False)
    try:
        return fetch_uniprot_annotations(accession, include_variants=include_variants)
    except Exception as e:
        return {"error": str(e)}


def tool_color_residues(cmd, inp: dict) -> dict:
    object_name = inp.get("object_name", "")
    chain = inp.get("chain")
    uniprot_positions: list[int] = inp.get("uniprot_positions", [])
    color = inp.get("color", "red")
    selection_name = inp.get("selection_name", "llm_highlight")
    uniprot_sequence: str = inp.get("uniprot_sequence", "")

    if not object_name or not uniprot_positions:
        return {"error": "object_name and uniprot_positions are required"}

    if not uniprot_sequence:
        return {"error": "uniprot_sequence is required for position mapping"}

    struct_residues = get_struct_residues(cmd, object_name, chain)
    if not struct_residues:
        return {"error": f"No CA atoms found in {object_name}" + (f" chain {chain}" if chain else "")}

    struct_seq = "".join(aa for _, aa in struct_residues)

    aln = align_sequences(struct_seq, uniprot_sequence)
    if aln is None:
        return {"error": "Sequence alignment failed"}

    pos_map = build_position_map(struct_residues, aln)

    mapped_resis = [pos_map[p] for p in uniprot_positions if p in pos_map]
    missing = [p for p in uniprot_positions if p not in pos_map]

    if not mapped_resis:
        return {
            "error": "None of the specified positions are present in the structure",
            "missing_from_structure": missing,
        }

    resi_str = "+".join(str(r) for r in sorted(set(mapped_resis)))
    chain_part = f" and chain {chain}" if chain else ""
    sele_expr = f'("{object_name}"){chain_part} and resi {resi_str}'

    cmd.select(selection_name, sele_expr)
    cmd.color(color, selection_name)

    return {
        "success": True,
        "colored_count": len(mapped_resis),
        "selection_name": selection_name,
        "pymol_resi_numbers": sorted(set(mapped_resis)),
        "missing_from_structure": missing,
        "note": f"Colored {len(mapped_resis)} residues as '{color}'",
    }


def tool_run_pymol_command(cmd, inp: dict) -> dict:
    """
    任意の PyMOL コマンドを実行し、実行後のシーン状態を返す。
    align など結果値を返すコマンドは Python API 経由で取得する。
    """
    command = inp.get("command", "").strip()
    if not command:
        return {"error": "command is required"}

    tokens = command.split()
    cmd_name = tokens[0].lower() if tokens else ""

    if cmd_name in ("align", "super", "cealign"):
        args = [t.strip().rstrip(",") for t in tokens[1:] if t.strip().rstrip(",")]
        try:
            if cmd_name == "align" and len(args) >= 2:
                result_vals = cmd.align(args[0], args[1])
                return {"command": command, "rmsd": round(result_vals[0], 3),
                        "atoms": result_vals[1], "objects": cmd.get_names("objects")}
            elif cmd_name == "super" and len(args) >= 2:
                result_vals = cmd.super(args[0], args[1])
                return {"command": command, "rmsd": round(result_vals[0], 3),
                        "atoms": result_vals[1], "objects": cmd.get_names("objects")}
            elif cmd_name == "cealign" and len(args) >= 2:
                result_vals = cmd.cealign(args[0], args[1])
                return {"command": command, "rmsd": round(result_vals.get("RMSD", 0), 3),
                        "objects": cmd.get_names("objects")}
        except Exception as e:
            return {"error": str(e), "command": command}

    if cmd_name == "rms_cur":
        args = [t.strip().rstrip(",") for t in tokens[1:] if t.strip().rstrip(",")]
        try:
            rmsd = cmd.rms_cur(*args[:2]) if len(args) >= 2 else cmd.rms_cur()
            return {"command": command, "rmsd": round(rmsd, 3)}
        except Exception as e:
            return {"error": str(e), "command": command}

    try:
        cmd.do(command)
    except Exception as e:
        return {"error": str(e), "command": command}

    return {
        "command": command,
        "output": "(done)",
        "objects": cmd.get_names("objects"),
        "selections": cmd.get_names("selections"),
    }


def tool_color_by_plddt(cmd, inp: dict) -> dict:
    """
    AlphaFold 公式 pLDDT カラースキームを適用する。
    pLDDT 値は B 因子カラムに格納されている。

    >= 90 : 0x0053D6 (濃青  / very high confidence)
    70-90 : 0x65CBF3 (水色  / confident)
    50-70 : 0xFFDB13 (黄    / low confidence)
    <  50 : 0xFF7D45 (橙    / very low confidence)
    """
    object_name = inp.get("object_name", "all")

    cmd.color("0x0053D6", object_name)
    cmd.color("0x65CBF3", f"({object_name}) and b < 90")
    cmd.color("0xFFDB13", f"({object_name}) and b < 70")
    cmd.color("0xFF7D45", f"({object_name}) and b < 50")

    return {
        "success": True,
        "object_name": object_name,
        "scheme": {
            ">=90": "#0053D6 (very high)",
            "70-90": "#65CBF3 (confident)",
            "50-70": "#FFDB13 (low)",
            "<50":  "#FF7D45 (very low)",
        },
    }


def tool_render_nice(cmd, inp: dict) -> dict:
    """
    高品質レンダリングを行う。

    オリジナル設定をベースに微調整:
      - ambient: 0.8 → 0.85（少し明るく柔らかく）
      - ray_trace_gain: 0.05 → 0.03（アウトライン控えめ）

    restore=True（デフォルト）のとき設定を元に戻す。
    restore=False のときは kawaii な見た目を維持する。
    """
    filename = inp.get("filename", "render.png")
    width    = inp.get("width",    1200)
    height   = inp.get("height",   900)
    restore  = inp.get("restore",  True)

    # ------------------------------------------------------------------
    # 現在の設定を保存
    # ------------------------------------------------------------------
    SAVE_KEYS = [
        "opaque_background", "depth_cue", "ray_trace_mode", "ray_trace_color",
        "antialias", "ambient", "cartoon_oval_width", "cartoon_oval_length",
        "ray_trace_gain", "specular", "light_count", "reflect",
    ]
    saved = {k: cmd.get(k) for k in SAVE_KEYS}
    try:
        r, g, b = cmd.get_setting_tuple("bg_rgb")[0]
        saved_bg = "0x%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))
    except Exception:
        saved_bg = "black"

    try:
        # ------------------------------------------------------------------
        # レンダリング設定を適用
        # ------------------------------------------------------------------
        cmd.do("bg_color white")
        cmd.set("opaque_background",  1)
        cmd.set("depth_cue",          0)
        cmd.set("ray_trace_mode",     1)
        cmd.set("ray_trace_color",    "0x404040")
        cmd.set("antialias",          4)
        cmd.set("ambient",            0.85)
        cmd.set("cartoon_oval_width", 0.3)
        cmd.set("cartoon_oval_length",1.3)
        cmd.set("ray_trace_gain",     0.03)
        cmd.set("specular",           0.02)
        cmd.set("light_count",        6)
        cmd.set("reflect",            0.05)

        cmd.ray(width, height)
        if filename:
            cmd.png(filename, dpi=150)

    finally:
        if restore:
            cmd.do(f"bg_color {saved_bg if saved_bg else 'black'}")
            for k, v in saved.items():
                try:
                    cmd.set(k, v)
                except Exception:
                    pass

    return {"success": True, "filename": filename, "width": width, "height": height}


def tool_reset_colors(cmd, inp: dict) -> dict:
    object_name = inp.get("object_name", "all")
    cmd.color("atomic", object_name)
    for name in cmd.get_names("selections"):
        if name.startswith("llm_"):
            cmd.delete(name)
    return {"success": True, "reset": object_name}


# ===========================================================================
# Claude tool_use スキーマ + ディスパッチテーブル
# ===========================================================================

TOOL_DEFINITIONS = [
    {
        "name": "fetch_structure",
        "description": (
            "Download and load a structure into PyMOL. "
            "Supports RCSB PDB (4-character PDB ID, e.g. '1TUP') and "
            "AlphaFold DB (UniProt accession with source='alphafold', e.g. 'P04637'). "
            "Use this when the user asks to load or fetch a structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pdb_id": {
                    "type": "string",
                    "description": "PDB ID (e.g. '1TUP') or UniProt accession for AlphaFold (e.g. 'P04637')",
                },
                "source": {
                    "type": "string",
                    "enum": ["pdb", "alphafold"],
                    "description": "Structure source: 'pdb' for RCSB PDB (default), 'alphafold' for AlphaFold DB",
                },
            },
            "required": ["pdb_id"],
        },
    },
    {
        "name": "get_loaded_structures",
        "description": (
            "Returns the list of objects currently loaded in PyMOL with their "
            "FASTA sequences. Call this first to understand what is in the scene."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "map_pdb_to_uniprot",
        "description": (
            "Given a PDB ID (e.g. '1TUP'), find the corresponding UniProt accession "
            "using the UniProt ID Mapping API. Optionally specify a chain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string", "description": "4-character PDB ID"},
                "chain": {"type": "string", "description": "PDB chain ID (optional)"},
            },
            "required": ["pdb_id"],
        },
    },
    {
        "name": "fetch_uniprot_by_accession",
        "description": (
            "Fetch protein annotations from UniProt by accession (e.g. 'P04637' for p53). "
            "Returns active sites, binding sites, domains, regions, and the canonical sequence. "
            "Natural variants and mutagenesis data are excluded by default (can be large). "
            "Set include_variants=true only when the user explicitly asks about variants or mutations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "accession": {"type": "string", "description": "UniProt accession ID, e.g. P04637"},
                "include_variants": {
                    "type": "boolean",
                    "description": "Include Natural variant and Mutagenesis data (default: false). Only set true when the user asks about variants or mutations.",
                },
            },
            "required": ["accession"],
        },
    },
    {
        "name": "color_residues",
        "description": (
            "Color specific residues in PyMOL. Provide UniProt canonical sequence "
            "positions; the plugin automatically aligns them to structure residue numbers. "
            "Always call reset_colors before applying a new color scheme."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {"type": "string", "description": "PyMOL object name (from get_loaded_structures)"},
                "chain": {"type": "string", "description": "PDB chain ID (optional, e.g. 'A')"},
                "uniprot_positions": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Residue positions in UniProt canonical sequence (1-based)",
                },
                "color": {"type": "string", "description": "PyMOL color name (e.g. red, green, yellow, cyan, magenta)"},
                "selection_name": {"type": "string", "description": "Name for the PyMOL selection (use prefix 'llm_', e.g. 'llm_active_sites')"},
                "uniprot_sequence": {"type": "string", "description": "UniProt canonical sequence string (from fetch_uniprot_by_accession)"},
            },
            "required": ["object_name", "uniprot_positions", "color", "selection_name", "uniprot_sequence"],
        },
    },
    {
        "name": "run_pymol_command",
        "description": (
            "Execute any PyMOL command directly (e.g. align, super, cealign, rms_cur, "
            "select, show, hide, zoom, color, rotate, save, set, etc.). "
            "Returns output text and RMSD values where applicable. "
            "Use this for direct PyMOL manipulations that don't require UniProt data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "PyMOL command string exactly as you would type in the PyMOL console. "
                        "Examples: 'align 1YCR, 1TUP', 'show sticks, resi 50', "
                        "'select binding_site, resi 100+101+102', 'zoom 1TUP'"
                    ),
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "reset_colors",
        "description": (
            "Reset all colors to element-based coloring (atomic) and delete "
            "all llm_* selections created by this plugin. Call before applying new highlights."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {"type": "string", "description": "PyMOL object name to reset, or 'all' (default)"},
            },
            "required": [],
        },
    },
    {
        "name": "render_nice",
        "description": (
            "Render the current PyMOL scene with high-quality ray tracing settings and save as PNG. "
            "Applies a curated render preset (soft lighting, smooth cartoons, cream background), "
            "saves the image, then restores all settings to their previous values. "
            "Use when the user asks to render, save an image, or take a screenshot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output PNG filename (default: 'render.png')",
                },
                "width":  {"type": "integer", "description": "Image width in pixels (default: 1200)"},
                "height": {"type": "integer", "description": "Image height in pixels (default: 900)"},
            },
            "required": [],
        },
    },
    {
        "name": "color_by_plddt",
        "description": (
            "Color an AlphaFold structure by pLDDT confidence score using the official AlphaFold color scheme. "
            "pLDDT is stored in the B-factor column. "
            "Use this when the user asks to color by pLDDT, confidence, or requests AlphaFold-style coloring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "PyMOL object name to color (e.g. 'AF-P01116-F1'). Defaults to 'all'.",
                },
            },
            "required": [],
        },
    },
]

TOOL_DISPATCH = {
    "fetch_structure":          tool_fetch_structure,
    "get_loaded_structures":    tool_get_loaded_structures,
    "run_pymol_command":        tool_run_pymol_command,
    "map_pdb_to_uniprot":       tool_map_pdb_to_uniprot,
    "fetch_uniprot_by_accession": tool_fetch_uniprot,
    "color_residues":           tool_color_residues,
    "reset_colors":             tool_reset_colors,
    "color_by_plddt":           tool_color_by_plddt,
    "render_nice":              tool_render_nice,
}
