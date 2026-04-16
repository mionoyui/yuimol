"""
yuimol.uniprot のユニットテスト（HTTP モック使用）
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from yuimol.uniprot import fetch_uniprot_annotations

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load_fixture_or_none(name: str):
    path = os.path.join(FIXTURES_DIR, name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


class TestFetchUniprotAnnotations:
    def test_extracts_active_site(self, p53_uniprot_data):
        """Active site アノテーションが正しく抽出される。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = p53_uniprot_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = fetch_uniprot_annotations("P04637")

        assert result["accession"] == "P04637"
        assert "Active site" in result["annotations"]
        sites = result["annotations"]["Active site"]
        assert any(s["start"] == 176 for s in sites)

    def test_extracts_binding_site(self, p53_uniprot_data):
        """Binding site アノテーションが正しく抽出される。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = p53_uniprot_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = fetch_uniprot_annotations("P04637")

        assert "Binding site" in result["annotations"]

    def test_returns_sequence(self, p53_uniprot_data):
        """sequence フィールドが返される。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = p53_uniprot_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = fetch_uniprot_annotations("P04637")

        assert len(result["sequence"]) > 0

    def test_unknown_feature_type_ignored(self, p53_uniprot_data):
        """不明な feature type は無視される。"""
        p53_uniprot_data["features"].append({
            "type": "Unknown type",
            "location": {"start": {"value": 1}, "end": {"value": 1}},
            "description": "should be ignored",
        })
        mock_resp = MagicMock()
        mock_resp.json.return_value = p53_uniprot_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = fetch_uniprot_annotations("P04637")

        assert "Unknown type" not in result["annotations"]


@pytest.mark.skipif(
    not os.path.exists(os.path.join(FIXTURES_DIR, "P04637_uniprot.json")),
    reason="fixture file not downloaded (run: pixi run download-fixtures)",
)
class TestFetchUniprotAnnotationsWithFixture:
    """fixtures/ に実際のAPIレスポンスがある場合のみ実行するテスト。"""

    def test_p53_protein_name(self):
        data = _load_fixture_or_none("P04637_uniprot.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = fetch_uniprot_annotations("P04637")

        assert "p53" in result["protein_name"].lower() or "tumor" in result["protein_name"].lower()
