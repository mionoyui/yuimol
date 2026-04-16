"""
E2E smoke test: Claude <-> PyMOL integration
---------------------------------------------
ヘッドレスで実行:
    pixi run test-e2e

または:
    pymol -c -r tests/integration/test_e2e.py

テスト内容:
    Test 1 - PDB (1TUP): fetch → UniProt mapping → color
    Test 2 - AlphaFold (P04637): fetch_structure tool 経由でロードできるか
"""

import os
import sys

# プロジェクトルートを path に追加
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from pymol import cmd
from yuimol import run_agent_loop, TOOL_DISPATCH

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
PDB_ID   = "1TUP"
PROMPT   = (
    "Please color the active sites and binding sites of the loaded structure. "
    "Use get_loaded_structures first, then map the PDB ID to UniProt, "
    "fetch the annotations, and color the relevant residues."
)
PASS_MARK = "\033[92m[PASS]\033[0m"
FAIL_MARK = "\033[91m[FAIL]\033[0m"

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _check(label: str, ok: bool, detail: str = "") -> bool:
    status = PASS_MARK if ok else FAIL_MARK
    msg = f"{status} {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return ok


# ---------------------------------------------------------------------------
# テスト本体
# ---------------------------------------------------------------------------

def run_test():
    results = []

    # ------------------------------------------------------------------
    # Step 1: 構造ロード
    # ------------------------------------------------------------------
    print(f"\n=== Step 1: fetch {PDB_ID} ===")
    cmd.reinitialize()
    cmd.fetch(PDB_ID, async_=0)
    objects = cmd.get_names("objects")
    ok = any(PDB_ID.lower() in n.lower() for n in objects)
    results.append(_check(f"{PDB_ID} loaded in PyMOL", ok, f"objects={objects}"))
    if not ok:
        print("Cannot continue without a loaded structure.")
        _summarize(results)
        return

    # ------------------------------------------------------------------
    # Step 2: エージェントループ実行
    # ------------------------------------------------------------------
    print(f"\n=== Step 2: run_agent_loop ===")
    tools_called: list[str] = []

    def _on_tool(name: str, summary: str):
        tools_called.append(name)
        print(f"  [tool] {name}: {summary[:80]}")

    reply = ""
    error  = None
    try:
        reply, _ = run_agent_loop(
            user_message=PROMPT,
            history=[],
            cmd=cmd,
            tool_callback=_on_tool,
        )
    except Exception as e:
        error = e

    results.append(_check("run_agent_loop completed without exception",
                           error is None,
                           str(error) if error else ""))

    # ------------------------------------------------------------------
    # Step 3: ツール呼び出し確認
    # ------------------------------------------------------------------
    print(f"\n=== Step 3: tool calls ===")
    print(f"  tools called: {tools_called}")
    results.append(_check("At least 1 tool was called",
                           len(tools_called) >= 1,
                           f"called={tools_called}"))

    expected_tools = ["get_loaded_structures", "fetch_uniprot_by_accession", "color_residues"]
    for t in expected_tools:
        results.append(_check(f"  tool '{t}' was called", t in tools_called))

    # ------------------------------------------------------------------
    # Step 4: PyMOL セレクション確認
    # ------------------------------------------------------------------
    print(f"\n=== Step 4: PyMOL selections ===")
    selections = cmd.get_names("selections")
    llm_sels   = [s for s in selections if s.startswith("llm_")]
    print(f"  all selections: {selections}")
    print(f"  llm_* selections: {llm_sels}")
    results.append(_check("llm_* selection exists in PyMOL",
                           len(llm_sels) >= 1,
                           f"llm_selections={llm_sels}"))

    # ------------------------------------------------------------------
    # Step 4b: セレクションの中身をコンソールに表示
    # ------------------------------------------------------------------
    print(f"\n=== Step 4b: selection details ===")
    from pymol import stored
    for sel in llm_sels:
        count = cmd.count_atoms(sel)
        stored.llm_resi_list = []
        cmd.iterate(f"{sel} and name CA", "stored.llm_resi_list.append((chain, resi, resn))")
        residues_str = ", ".join(f"{ch}/{resn}{ri}" for ch, ri, resn in stored.llm_resi_list)
        print(f"  {sel}: {count} atoms, residues=[{residues_str}]")

    # ------------------------------------------------------------------
    # Step 5: Claude の返答確認
    # ------------------------------------------------------------------
    print(f"\n=== Step 5: assistant reply ===")
    print(f"  reply (first 300 chars): {reply[:300]!r}")
    results.append(_check("Assistant returned non-empty reply", len(reply.strip()) > 0))

    # ------------------------------------------------------------------
    # サマリー
    # ------------------------------------------------------------------
    _summarize(results)


def _summarize(results: list[bool]):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*40}")
    if passed == total:
        print(f"{PASS_MARK} All {total} checks passed.")
    else:
        print(f"{FAIL_MARK} {passed}/{total} checks passed.")
    print("="*40)


# ---------------------------------------------------------------------------
# Test 2: AlphaFold fetch ツール単体テスト
# ---------------------------------------------------------------------------

def run_test_alphafold():
    results = []
    ACCESSION = "P04637"  # p53

    print(f"\n{'='*40}")
    print(f"Test 2: AlphaFold fetch ({ACCESSION})")
    print(f"{'='*40}")

    cmd.reinitialize()

    print(f"\n=== Step 1: fetch_structure tool (alphafold) ===")
    fn = TOOL_DISPATCH.get("fetch_structure")
    result = fn(cmd, {"pdb_id": ACCESSION, "source": "alphafold"})
    print(f"  result: {result}")

    ok = result.get("success") is True
    results.append(_check(f"fetch_structure returned success", ok,
                           result.get("error", "")))

    print(f"\n=== Step 2: PyMOL object check ===")
    objects = cmd.get_names("objects")
    print(f"  objects: {objects}")
    af_loaded = any("AF-" in n.upper() for n in objects)
    results.append(_check("AF-* object exists in PyMOL", af_loaded,
                           f"objects={objects}"))

    _summarize(results)
    return results


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------
all_results = []
all_results += [run_test()]
all_results += [run_test_alphafold()]
