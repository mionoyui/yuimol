"""
UniProt REST クライアント
- アノテーション取得
- PDB ID → UniProt アクセッション マッピング（キャッシュ付き）
"""

import time

_uniprot_map_cache: dict[str, str] = {}


def _uniprot_get(accession: str) -> dict:
    """UniProt エントリを JSON で取得。"""
    import httpx
    resp = httpx.get(
        f"https://rest.uniprot.org/uniprotkb/{accession}",
        params={"format": "json"},
        headers={"Accept": "application/json"},
        timeout=30.0,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json()


def _uniprot_fasta(accession: str) -> str:
    """UniProt 正準配列を FASTA 形式で取得し、配列文字列のみ返す。"""
    import httpx
    resp = httpx.get(
        f"https://rest.uniprot.org/uniprotkb/{accession}.fasta",
        timeout=30.0,
        follow_redirects=True,
    )
    resp.raise_for_status()
    lines = resp.text.splitlines()
    return "".join(l for l in lines if not l.startswith(">"))


_DEFAULT_FEATURE_TYPES = {
    "Active site", "Binding site", "Region", "Domain",
    "Modified residue", "Site", "Metal binding",
    "Motif", "DNA binding", "Disulfide bond", "Cross-link",
}
_VARIANT_FEATURE_TYPES = {"Natural variant", "Mutagenesis"}


def fetch_uniprot_annotations(accession: str, include_variants: bool = False) -> dict:
    """
    UniProt エントリから活性部位・結合部位・ドメイン情報を抽出して返す。

    Parameters
    ----------
    include_variants : bool
        True のとき Natural variant と Mutagenesis も含める。
        デフォルト False（p53 など変異データが膨大なタンパク質でのコスト削減のため）。
    """
    data = _uniprot_get(accession)

    protein_name = (
        data.get("proteinDescription", {})
        .get("recommendedName", {})
        .get("fullName", {})
        .get("value", accession)
    )
    organism = (
        data.get("organism", {})
        .get("scientificName", "")
    )
    sequence = data.get("sequence", {}).get("value", "")

    allowed = _DEFAULT_FEATURE_TYPES | (_VARIANT_FEATURE_TYPES if include_variants else set())

    annotations: dict[str, list] = {}
    for feature in data.get("features", []):
        ftype = feature.get("type", "")
        if ftype not in allowed:
            continue
        loc = feature.get("location", {})
        start = loc.get("start", {}).get("value")
        end = loc.get("end", {}).get("value")
        desc = feature.get("description", "")
        ligands = [
            lig.get("name", "") for lig in feature.get("ligands", [])
        ]
        entry = {"start": start, "end": end, "description": desc}
        if ligands:
            entry["ligands"] = ligands
        annotations.setdefault(ftype, []).append(entry)

    return {
        "accession": accession,
        "protein_name": protein_name,
        "organism": organism,
        "sequence": sequence,
        "annotations": annotations,
    }


def map_pdb_to_uniprot_accession(pdb_id: str, chain: str | None = None) -> str | None:
    """
    UniProt ID Mapping API で PDB ID → UniProt アクセッションに変換。
    結果はプロセス内でキャッシュする。最大 30 秒ポーリング。
    """
    import httpx

    pdb_id = pdb_id.upper()
    cache_key = f"{pdb_id}-{chain.upper() if chain else ''}"
    if cache_key in _uniprot_map_cache:
        return _uniprot_map_cache[cache_key]

    resp = httpx.post(
        "https://rest.uniprot.org/idmapping/run",
        data={"ids": pdb_id, "from": "PDB", "to": "UniProtKB"},
        timeout=30.0,
    )
    resp.raise_for_status()
    job_id = resp.json().get("jobId")
    if not job_id:
        return None

    results_url = f"https://rest.uniprot.org/idmapping/uniprotkb/results/{job_id}"
    results = []
    for _ in range(10):
        r = httpx.get(results_url, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                break
        time.sleep(1)
    else:
        return None

    accession = None
    if chain:
        for item in results:
            from_id = item.get("from", "")
            if from_id.endswith(f"-{chain.upper()}"):
                accession = item["to"]["primaryAccession"]
                break

    if accession is None and results:
        accession = results[0]["to"]["primaryAccession"]

    if accession:
        _uniprot_map_cache[cache_key] = accession
    return accession
