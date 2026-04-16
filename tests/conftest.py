"""
pytest 共通フィクスチャ
"""

import json
import os
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture_path(name: str) -> str:
    """fixtures/ 以下のファイルパスを返す。"""
    return os.path.join(FIXTURES_DIR, name)


def fixture_exists(name: str) -> bool:
    return os.path.exists(fixture_path(name))


# ---------------------------------------------------------------------------
# PyMOL cmd モック（unit tests 用）
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cmd():
    """
    PyMOL cmd オブジェクトの最小モック。
    unit tests では実際の PyMOL を使わずにこれを渡す。
    """
    cmd = MagicMock()
    cmd.get_names.return_value = []
    cmd.get_fastastr.return_value = ""
    cmd.count_atoms.return_value = 0
    return cmd


# ---------------------------------------------------------------------------
# UniProt フィクスチャデータ
# ---------------------------------------------------------------------------

@pytest.fixture
def p53_uniprot_data():
    """
    P04637 (p53) の UniProt JSON 最小スタブ。
    ユニットテストは常にこのスタブを使う（実ファイルの有無に関わらず）。
    実データを使うテストは TestFetchUniprotAnnotationsWithFixture を使うこと。
    """
    # 最小スタブ（ネットワーク不要・内容固定）
    return {
        "primaryAccession": "P04637",
        "proteinDescription": {
            "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}
        },
        "organism": {"scientificName": "Homo sapiens"},
        "sequence": {"value": "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP"},
        "features": [
            {
                "type": "Active site",
                "location": {"start": {"value": 176}, "end": {"value": 176}},
                "description": "Proton acceptor",
                "ligands": [],
            },
            {
                "type": "Binding site",
                "location": {"start": {"value": 238}, "end": {"value": 238}},
                "description": "DNA binding",
                "ligands": [{"name": "DNA"}],
            },
        ],
    }
