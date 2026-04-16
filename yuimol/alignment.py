"""
配列アラインメント・位置マッピング
"""

from .constants import THREE_TO_ONE

try:
    from Bio.Align import PairwiseAligner
    HAS_BIOPYTHON = True
except ImportError:
    HAS_BIOPYTHON = False


def get_struct_residues(cmd, object_name: str, chain: str | None) -> list[tuple[int, str]]:
    """
    PyMOL オブジェクトから (resi番号, 1文字アミノ酸) のリストを返す。
    cmd.iterate + stored 名前空間を使用（PyMOL全バージョン互換）。
    """
    from pymol import stored
    stored.llm_residues = []

    sel = f"({object_name}) and name CA"
    if chain:
        sel += f" and chain {chain}"

    cmd.iterate(
        sel,
        "stored.llm_residues.append((int(resi), resn))",
    )

    return sorted(
        (resi, THREE_TO_ONE.get(resn, "X"))
        for resi, resn in stored.llm_residues
    )


def align_sequences(struct_seq: str, uniprot_seq: str):
    """
    BioPython PairwiseAligner で全体アラインメント。
    なければフォールバックで単純比較を返す。
    Returns object with .seqA (aligned struct) and .seqB (aligned uniprot).
    """
    if HAS_BIOPYTHON:
        aligner = PairwiseAligner()
        aligner.mode = "global"
        aligner.match_score = 2
        aligner.mismatch_score = -1
        aligner.open_gap_score = -10
        aligner.extend_gap_score = -0.5
        # 構造は UniProt 全長の断片である場合が多い。
        # 構造側（target）の末端ギャップを無コストにすることで、
        # 断片が全長配列の正しい位置にアラインされる。
        try:
            aligner.end_insertion_score = 0.0   # BioPython >= 1.84 の新 API
        except AttributeError:
            aligner.target_end_gap_score = 0.0  # 旧 API フォールバック
        alns = aligner.align(struct_seq, uniprot_seq)
        aln = next(iter(alns), None)
        if aln is None:
            return None

        fasta = aln.format("fasta")
        lines = [l for l in fasta.splitlines() if not l.startswith(">")]
        if len(lines) < 2:
            return None

        class _Aln:
            seqA = lines[0]  # struct (target)
            seqB = lines[1]  # uniprot (query)

        return _Aln()
    else:
        class _FakeAln:
            seqA = struct_seq
            seqB = uniprot_seq
        return _FakeAln()


def build_position_map(
    struct_residues: list[tuple[int, str]],
    alignment,
) -> dict[int, int]:
    """
    アラインメント結果から uniprot_1based_pos → pymol_resi の辞書を返す。
    """
    aligned_struct = alignment.seqA
    aligned_uniprot = alignment.seqB

    pos_map: dict[int, int] = {}
    struct_idx = 0
    uniprot_pos = 0

    for s_char, u_char in zip(aligned_struct, aligned_uniprot):
        if u_char != "-":
            uniprot_pos += 1
        if s_char != "-":
            if u_char != "-" and struct_idx < len(struct_residues):
                resi_num = struct_residues[struct_idx][0]
                pos_map[uniprot_pos] = resi_num
            struct_idx += 1

    return pos_map
