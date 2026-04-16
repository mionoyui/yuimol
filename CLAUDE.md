# CLAUDE.md — yuimol 開発ガイドライン

## プロジェクト概要

PyMOL 用 LLM チャットプラグイン。自然言語でタンパク質構造を操作・解析する。

- パッケージ名: `yuimol`（旧称 `pymol_llm` — コード内に残っていたら `yuimol` に修正）
- PyMOL プラグインとして `~/.pymolrc` から自動ロード
- `pixi` で環境管理（brew など System-level の依存なし）

---

## ビルド・テスト

```bash
pixi run test                      # ユニットテスト（PyMOL 不要）
pixi run test-visual-enzyme        # 目視確認テスト（直接ツール呼び出し）
pixi run test-visual-llm-enzyme    # LLM チャット経由テスト
```

ビジュアルテストは PyMOL ウィンドウが開いて目視確認する。LLM テストは実際に Claude API を呼ぶのでコストがかかる。

---

## アーキテクチャ方針

### スレッドモデル

PyMOL の `cmd.*` はメインスレッドからしか安全に呼べない。  
`ChatWorker`（QThread）がエージェントループを実行し、ツール呼び出しが必要になると `tool_request` シグナルを emit してブロック。メインスレッドの `ChatPanel` がツールを実行して結果を返す。

### エージェントループ（agent.py）

- system prompt と tool definitions に `cache_control: ephemeral` を付与してプロンプトキャッシュを有効化
- モデルは `run_agent_loop(model=...)` で外部から指定可能。デフォルト `claude-sonnet-4-6`

### UniProt → PDB 位置マッピング（alignment.py）

1. PyMOL の `iterate` で Cα 残基番号を取得
2. BioPython `PairwiseAligner`（global モード）で UniProt canonical sequence とアラインメント
3. 構造は断片が多いため `end_insertion_score = 0.0` で末端ギャップをペナルティなしに設定
4. アラインメント結果から `UniProt位置 → PyMOL resi` の辞書を構築

LLM は UniProt 位置番号をそのまま指定すれば良い。PDB 番号への変換は `tool_color_residues` が自動で行う。

---

## コーディング規約

### LLM ツール

- 新しいツール実装は `tools.py` に追加し、`TOOL_DEFINITIONS` と `TOOL_DISPATCH` にも登録する
- LLM に渡すデータは最小限に。UniProt のアノテーションは `_DEFAULT_FEATURE_TYPES` で絞っている
- `Natural variant` / `Mutagenesis` はデフォルト非取得（p53 など 100KB 超になるため）。ユーザーが変異を明示的に求めたときだけ `include_variants=True` を渡す

### SYSTEM_PROMPT（constants.py）

- `NEVER use run_pymol_command to color by resi` — 必ず `color_residues` ツールを使う
- `NEVER call render_nice` — "render" / "レンダリング" / "ray" / "画像を保存" と明示された場合のみ呼ぶ
- LLM には UniProt 位置をそのまま渡させる。PDB 番号への変換は自動

### GUI（gui.py）

- Settings ボタンで API キーとモデルを設定。`~/.pymol/startup/yuimol/.env` に保存
- render ボタンのラベルは `kawaii`（英字）
- kawaii render 後は設定を元に戻さない（見た目を維持）

---

## ビジュアルテスト方針

- zoom はしない（デフォルト表示で確認）
- テスト末尾で kawaii render を実行しない（ボタンで別途実行）。ただし `render_nice.py` は `restore=False` の動作確認が目的のため例外
- 全テストで `cmd.set("fetch_path", FIXTURES)` を設定する（CIF がルートに散らばらないよう）
- インターフェース残基は `byres` で残基全体を選択する

---

## 色の規約

| 用途 | 色 |
|------|----|
| 活性部位 | マゼンタ |
| 結合部位 | シアン |
| インターフェース A 鎖 | オレンジ |
| インターフェース B 鎖 | シアン |
| 金属イオン（Zn²⁺ など） | 金色 (gold) |

---

## 応答スタイル

- 要約・まとめを末尾に追加しない
- 簡潔に
