"""
yuimol.alignment のユニットテスト（PyMOL不要・ネット不要）
"""

import pytest
from yuimol.alignment import align_sequences, build_position_map


def test_align_sequences_identical():
    seq = "ACDEFGHIKLM"
    aln = align_sequences(seq, seq)
    assert aln is not None
    assert "-" not in aln.seqA
    assert "-" not in aln.seqB


def test_align_sequences_with_gap():
    # struct に欠損残基がある場合（structが短い）
    struct_seq  = "ACDFG"   # E が欠損
    uniprot_seq = "ACDEFG"
    aln = align_sequences(struct_seq, uniprot_seq)
    assert aln is not None
    # アラインメント後の長さは同じになる
    assert len(aln.seqA) == len(aln.seqB)


def test_build_position_map_perfect():
    """完全一致のとき UniProt位置 → PyMOL resi が1:1で対応する。"""
    struct_residues = [(10, "A"), (11, "C"), (12, "D")]

    class _Aln:
        seqA = "ACD"
        seqB = "ACD"

    pos_map = build_position_map(struct_residues, _Aln())
    assert pos_map == {1: 10, 2: 11, 3: 12}


def test_build_position_map_with_struct_gap():
    """構造側にギャップがある（UniProt残基が構造に存在しない）場合。"""
    struct_residues = [(10, "A"), (12, "D")]  # C(11) が欠損

    class _Aln:
        seqA = "A-D"   # struct にギャップ
        seqB = "ACD"   # uniprot は完全

    pos_map = build_position_map(struct_residues, _Aln())
    # UniProt pos 1(A)→10, pos 2(C)→マップなし, pos 3(D)→12
    assert pos_map[1] == 10
    assert 2 not in pos_map
    assert pos_map[3] == 12


def test_build_position_map_with_uniprot_gap():
    """UniProt側にギャップ（構造に余分な残基）がある場合。"""
    struct_residues = [(10, "A"), (11, "X"), (12, "D")]

    class _Aln:
        seqA = "AXD"
        seqB = "A-D"   # uniprot にギャップ

    pos_map = build_position_map(struct_residues, _Aln())
    # UniProt pos 1(A)→10, pos 2(D)→12  (X は uniprot 側にないので pos_map に入らない)
    assert pos_map[1] == 10
    assert pos_map[2] == 12


def test_align_fragment_to_full_sequence():
    """
    1TUP のような断片構造（UniProt 全長の途中だけ）を全長配列にアラインしたとき、
    UniProt の位置が正しくマッピングされる。
    target_end_gap_score = 0.0 なしだと末端ペナルティでズレが生じる。
    """
    # UniProt 全長を模した配列（10残基のN末端 + 5残基の断片領域 + 10残基のC末端）
    full_seq   = "AAAAAAAAAA" "CDEFG" "AAAAAAAAAA"  # 25 残基
    # 構造は中央の断片のみ（resi 101-105 として PyMOL に入っている想定）
    frag_seq   = "CDEFG"
    struct_residues = [(101, "C"), (102, "D"), (103, "E"), (104, "F"), (105, "G")]

    aln = align_sequences(frag_seq, full_seq)
    assert aln is not None
    assert len(aln.seqA) == len(aln.seqB)

    pos_map = build_position_map(struct_residues, aln)

    # UniProt の 11〜15 番目が構造の resi 101〜105 に対応するはず
    assert pos_map.get(11) == 101
    assert pos_map.get(12) == 102
    assert pos_map.get(13) == 103
    assert pos_map.get(14) == 104
    assert pos_map.get(15) == 105
