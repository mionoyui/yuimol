"""
テスト用フィクスチャファイルの事前ダウンロードスクリプト

使い方:
    pixi run download-fixtures
    # または
    python tests/fixtures/download.py

ダウンロードされるファイル（.gitignore で除外済み）:
    1TUP.cif               - p53/DNA複合体 (RCSB PDB)
    AF-P04637-F1.cif       - p53 AlphaFold構造
    P04637_uniprot.json    - p53 UniProtアノテーション
    4OBE.cif               - KRAS G12D/GDP 複合体 (RCSB PDB)
    AF-P01116-F1.cif       - KRAS AlphaFold構造
"""

import json
import os
import sys

FIXTURES_DIR = os.path.dirname(__file__)


def download(url: str, dest: str, label: str):
    import httpx

    if os.path.exists(dest):
        print(f"  [skip] {label} (already exists)")
        return
    print(f"  [download] {label} ...", end="", flush=True)
    r = httpx.get(url, timeout=30.0, follow_redirects=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f" done ({len(r.content) // 1024} KB)")


def main():
    print("Downloading test fixtures to:", FIXTURES_DIR)

    # 1TUP (p53/DNA, PDB)
    download(
        "https://files.rcsb.org/download/1TUP.cif",
        os.path.join(FIXTURES_DIR, "1TUP.cif"),
        "1TUP.cif (RCSB PDB)",
    )

    # p53 AlphaFold（API でダウンロード URL を取得してから落とす）
    af_dest = os.path.join(FIXTURES_DIR, "AF-P04637-F1.cif")
    if os.path.exists(af_dest):
        print("  [skip] AF-P04637-F1.cif (already exists)")
    else:
        print("  [download] AF-P04637-F1.cif (AlphaFold DB) ...", end="", flush=True)
        import httpx
        api = httpx.get(
            "https://alphafold.ebi.ac.uk/api/prediction/P04637",
            timeout=15.0, follow_redirects=True,
        )
        api.raise_for_status()
        cif_url = api.json()[0]["cifUrl"]
        r = httpx.get(cif_url, timeout=30.0, follow_redirects=True)
        r.raise_for_status()
        with open(af_dest, "wb") as f:
            f.write(r.content)
        print(f" done ({len(r.content) // 1024} KB)")

    # p53 UniProt アノテーション
    dest_json = os.path.join(FIXTURES_DIR, "P04637_uniprot.json")
    if not os.path.exists(dest_json):
        import httpx
        print("  [download] P04637_uniprot.json (UniProt) ...", end="", flush=True)
        r = httpx.get(
            "https://rest.uniprot.org/uniprotkb/P04637",
            params={"format": "json"},
            headers={"Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )
        r.raise_for_status()
        with open(dest_json, "w") as f:
            json.dump(r.json(), f)
        print(f" done")
    else:
        print("  [skip] P04637_uniprot.json (already exists)")

    # 4OBE (KRAS G12D/GDP, PDB)
    download(
        "https://files.rcsb.org/download/4OBE.cif",
        os.path.join(FIXTURES_DIR, "4OBE.cif"),
        "4OBE.cif (KRAS G12D, RCSB PDB)",
    )

    # KRAS AlphaFold (P01116)
    af_kras_dest = os.path.join(FIXTURES_DIR, "AF-P01116-F1.cif")
    if os.path.exists(af_kras_dest):
        print("  [skip] AF-P01116-F1.cif (already exists)")
    else:
        print("  [download] AF-P01116-F1.cif (AlphaFold DB) ...", end="", flush=True)
        import httpx
        api = httpx.get(
            "https://alphafold.ebi.ac.uk/api/prediction/P01116",
            timeout=15.0, follow_redirects=True,
        )
        api.raise_for_status()
        cif_url = api.json()[0]["cifUrl"]
        r = httpx.get(cif_url, timeout=30.0, follow_redirects=True)
        r.raise_for_status()
        with open(af_kras_dest, "wb") as f:
            f.write(r.content)
        print(f" done ({len(r.content) // 1024} KB)")

    print("Done.")


if __name__ == "__main__":
    sys.exit(main() or 0)
