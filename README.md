# yuimol

PyMOL 用 LLM チャットプラグイン。自然言語でタンパク質構造を操作・解析できます。

- Claude（Anthropic）とのチャットインターフェース
- UniProt REST API からアノテーション（活性部位・結合部位・翻訳後修飾・ドメインなど）を取得
- 配列アラインメントで UniProt 座標 → 構造残基番号に変換してカラーリング
- PDB / AlphaFold DB から構造をロード
- PyMOL コマンドをチャットから直接実行（`align`, `fetch`, `zoom` など）

> **PyMOL について**: [PyMOL Open Source](https://github.com/schrodinger/pymol-open-source) を conda-forge 経由で自動インストールします。商用ライセンスは不要です。

---

## Mac セットアップ

### 1. pixi をインストール

```bash
brew install pixi
```

または公式インストーラーでも可：

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

### 2. リポジトリをクローン

```bash
git clone https://github.com/mionoyui/yuimol.git
cd yuimol
```

### 3. 依存パッケージをインストール

```bash
pixi install
```

`pymol-open-source`、`anthropic`、`httpx`、`biopython` などが自動でインストールされます。brew での追加インストールは不要です。

### 4. ~/.pymolrc にプラグインを登録

```bash
echo 'from yuimol import __init_plugin__; __init_plugin__()' >> ~/.pymolrc
```

`pixi run pymol` で起動したとき、pixi 環境の Python に `yuimol` がインストールされているため、このまま動作します。

### 5. API キーを設定

```bash
mkdir -p ~/.pymol/startup/yuimol
cat > ~/.pymol/startup/yuimol/.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
EOF
```

または PyMOL 起動後にチャットパネルの **Settings** ボタンから設定できます。

### 6. PyMOL を起動

```bash
pixi run pymol
```

起動後、右側にチャットパネルが自動で開きます。

---

## 使い方

### 自然言語で操作

```
1CA2をロードして活性部位をマゼンタで表示して
1TUPをロードしてp53のがんホットスポット変異をオレンジで表示して
KRASのAlphaFold構造をpLDDTで色付けして
1BRSのタンパク質インターフェース残基を色付けして
```

### PyMOL コマンドをそのまま入力

PyMOL コマンドとして認識できる入力は LLM を経由せず即時実行されます：

```
fetch 1TUP
align 1YCR, 1TUP
show sticks, chain A
color red, resi 50+51+52
zoom 1TUP
```

### kawaii ボタン

チャットパネルの **kawaii** ボタンで高品質レイトレースレンダリングを実行します。

---

## UniProt 座標 → PDB 残基番号のマッピング

UniProt の canonical sequence と PDB 構造では残基番号が一致しないケースが多くあります。  
例えば `1TUP` は p53 の 94–292 番残基のみを含む断片構造で、PDB の残基番号は 1 から始まりません。

yuimol は以下の手順で自動的に対応付けを行います：

1. **構造の配列を抽出** — PyMOL の `iterate` で Cα 原子の残基番号とアミノ酸を取得
2. **グローバルアラインメント** — BioPython `PairwiseAligner` で構造配列と UniProt canonical sequence を整列  
   - 構造は断片である場合が多いため、構造側の末端ギャップをペナルティなしに設定
3. **位置マップを構築** — アラインメント結果から `UniProt 位置 → PyMOL resi 番号` の辞書を作成
4. **色付け** — LLM が返した UniProt 位置をマップで変換し、`cmd.color` / `cmd.select` を実行

このため LLM はアライメントを意識せず UniProt の位置番号をそのまま指定するだけで正しく動作します。

---

## モデル選択

Settings ボタンからモデルを切り替えられます。

| モデル | コスト | 用途 |
|--------|--------|------|
| `claude-haiku-4-5-20251001` | 低 | 色付け・ロード・基本操作はほぼこれで十分 |
| `claude-sonnet-4-6` | 中 | 複雑な比較・詳細な説明・デフォルト。間違いが許容できない場合はこちら |
| `claude-opus-4-6` | 高 | 最高品質の推論が必要な場合 |

設定は `~/.pymol/startup/yuimol/.env` に `YUIMOL_MODEL=...` として保存されます。

---

## UniProt アノテーション

チャットで構造を操作すると、内部で UniProt REST API からアノテーションを取得します。

**デフォルトで取得する情報：**

| type | 内容 |
|------|------|
| Active site | 触媒残基 |
| Binding site | 基質・リガンド結合残基 |
| Metal binding | 金属配位残基 |
| Modified residue | リン酸化・アセチル化などの翻訳後修飾 |
| Site | その他の機能的に重要なサイト |
| Domain / Region / Motif | 機能ドメイン・領域 |
| DNA binding | DNA 結合ドメイン |
| Disulfide bond / Cross-link | 共有結合 |

**オプション（「変異を見せて」と頼んだ場合に取得）：**

| type | 備考 |
|------|------|
| Natural variant | p53（TP53）など研究の多いタンパク質では 1,000 件超になることがある |
| Mutagenesis | 同上 |

データ量が多い場合に API コストが増えるため、変異データはデフォルト非取得にしています。

---

## 開発

### テスト

```bash
# ユニットテスト（PyMOL 不要・高速）
pixi run test

# 結合テスト（PyMOL + Claude API が必要）
pixi run test-e2e

# テスト用フィクスチャのダウンロード
pixi run download-fixtures
```

### ビジュアルテスト（直接ツール呼び出し）

構造・色付けツールの動作を目視確認します：

```bash
pixi run test-visual           # p53 残基色付け (1TUP)
pixi run test-visual-af        # KRAS AlphaFold vs PDB
pixi run test-visual-cancer    # p53 がんホットスポット
pixi run test-visual-domains   # p53 機能ドメイン
pixi run test-visual-render    # kawaii レンダリング
pixi run test-visual-enzyme    # 炭酸脱水酵素 活性部位 (1CA2)
pixi run test-visual-interface # Barnase–Barstar インターフェース (1BRS)
```

### ビジュアルテスト（LLM チャット経由）

チャットパネルを通じて LLM のツール選択・引数生成を確認します：

```bash
pixi run test-visual-llm-enzyme    # 炭酸脱水酵素 活性部位
pixi run test-visual-llm-cancer    # p53 がんホットスポット
pixi run test-visual-llm-domains   # p53 機能ドメイン
pixi run test-visual-llm-kras      # KRAS AlphaFold pLDDT vs PDB
pixi run test-visual-llm-interface # Barnase–Barstar インターフェース
```

### ファイル構成

```
yuimol/
├── __init__.py      re-export のみ
├── constants.py     SYSTEM_PROMPT, THREE_TO_ONE
├── uniprot.py       UniProt REST クライアント
├── alignment.py     配列アラインメント・位置マッピング
├── tools.py         ツール実装 + Claude tool_use スキーマ
├── agent.py         Claude エージェントループ
├── commands.py      PyMOL コマンド判定
├── gui.py           Qt チャットパネル
└── plugin.py        PyMOL プラグインエントリポイント

tests/
├── unit/            pytest（ネット不要）
├── integration/     PyMOL headless テスト
├── visual/          目視確認テスト（直接 / LLM 経由）
└── fixtures/        テスト用データキャッシュ
```

---

## ライセンス

MIT
