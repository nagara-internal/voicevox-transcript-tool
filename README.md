# voicevox-transcript-tool

議事録テキスト（`話者名: 発言内容` 形式）を読み込み、VOICEVOXでずんだもん・四国めたん等のキャラクター音声に変換してMP3を出力するCLIツールです。  
ながらかいご マニュアル動画の音声素材生成用に作られています。

---

## 目次

1. [前提条件](#前提条件)
2. [セットアップ](#セットアップ)
3. [議事録テキストの用意](#議事録テキストの用意)
4. [config.yaml の設定](#configyaml-の設定)
5. [実行方法](#実行方法)
6. [Claude Code での使い方](#claude-code-での使い方)
7. [コマンドオプション一覧](#コマンドオプション一覧)
8. [ディレクトリ構成](#ディレクトリ構成)
9. [トラブルシューティング](#トラブルシューティング)
10. [クレジット](#クレジット)

---

## 前提条件

| ツール | バージョン | 備考 |
|--------|-----------|------|
| Python | 3.10以上 | `python --version` で確認 |
| Docker | 任意 | VOICEVOXをDockerで起動する場合 |
| ffmpeg | 任意 | MP3出力に必要。WAV出力のみなら不要 |

> **Dockerを使う場合はVOICEVOXのインストール不要です（推奨）**

---

## セットアップ

### 1. リポジトリをclone

```bash
git clone git@github.com:nagara-internal/voicevox-transcript-tool.git
cd voicevox-transcript-tool
```

### 2. Python依存パッケージをインストール

```bash
pip install -r requirements.txt
```

インストールされるパッケージ：

| パッケージ | 用途 |
|-----------|------|
| requests | VOICEVOX APIへのHTTPリクエスト |
| pyyaml | config.yaml の読み込み |
| tqdm | 合成進捗のプログレスバー表示 |

### 3. ffmpegをインストール（MP3出力する場合）

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 4. VOICEVOXを起動する

**Dockerを使う場合（推奨）：**

```bash
docker run -d --rm --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-latest
```

起動確認（バージョン番号が返ってくればOK）：

```bash
curl http://localhost:50021/version
```

**VOICEVOXアプリを使う場合：**

[https://voicevox.hiroshiba.jp/](https://voicevox.hiroshiba.jp/) からダウンロードしてアプリを起動してください。  
起動するとAPIが `http://localhost:50021` で自動的に立ち上がります。

> `generate.sh` を使う場合は、VOICEVOXが起動していなければDockerで自動起動します。

---

## 議事録テキストの用意

### ファイルの置き場所

```
voicevox-transcript-tool/
└── samples/          ← ここに .txt ファイルを置く（推奨）
    └── my_meeting.txt
```

任意のパスでも指定可能です。

### テキストの書き方

UTF-8のテキストファイルに `話者名: 発言内容` の形式で記載します。  
コロンは **半角（:）でも全角（：）でも両方OK** です。

```text
# 4月スタッフミーティング
# コメント行（#で始まる行）はスキップされます

施設長: 本日はお忙しいところお集まりいただきありがとうございます。
ケアマネ：よろしくお願いいたします。
介護士A: 先月の利用者様の様子について報告いたします。
前回から体調が安定しており、食事量も増えています。
# ↑ コロンなしの行は直前の話者の発言として扱われます

---
# ↑ --- はセクション区切り。前後に2秒の無音が入ります

施設長: では次の議題に移ります。
```

### 書き方ルール

| 記法 | 意味 |
|------|------|
| `話者名: テキスト` | 発言（半角コロン） |
| `話者名：テキスト` | 発言（全角コロン） |
| コロンなしの行 | 直前の話者の発言の続き |
| `---` | セクション区切り（2秒の無音を挿入） |
| `# コメント` | コメント行（スキップ） |
| 空行 | スキップ |

> 200文字を超える発言は句点（。）で自動分割して合成されます。

---

## config.yaml の設定

リポルートの `config.yaml` で **話者名とVOICEVOXキャラクターのマッピング** を設定します。  
**議事録の話者名と config.yaml のキーを一致させる必要があります。**

```yaml
# VOICEVOX API設定
voicevox:
  base_url: "http://localhost:50021"
  timeout: 30

# 話者マッピング
speakers:
  施設長:
    speaker_id: 3      # ずんだもん（ノーマル）
    speed_scale: 1.0   # 話速（1.0が標準、1.2で20%速く）
    pitch_scale: 0.0   # ピッチ（0.0が標準）
  ケアマネ:
    speaker_id: 2      # 四国めたん（ノーマル）
    speed_scale: 1.0
    pitch_scale: 0.0
  介護士A:
    speaker_id: 8      # 春日部つむぎ（ノーマル）
    speed_scale: 1.0
    pitch_scale: 0.0

# config にない話者名が出てきたときに使われるデフォルト
default_speaker:
  speaker_id: 3
  speed_scale: 1.0
  pitch_scale: 0.0

# 音声生成設定
audio:
  silence_between_lines: 0.8      # 発言間の無音（秒）
  silence_between_sections: 2.0   # --- セクション区切りの無音（秒）
  sample_rate: 24000               # VOICEVOXのデフォルトサンプルレート
  output_format: "mp3"             # "mp3" または "wav"
  mp3_quality: 2                   # 0=最高品質 〜 9=最低品質
```

### 主なVOICEVOXキャラクターID

```bash
# 利用可能な全キャラクターをVOICEVOXから取得する
python src/main.py --list-speakers
```

よく使うキャラクター（環境によってIDが異なる場合があります）：

| ID | キャラクター | スタイル |
|----|-------------|---------|
| 3  | ずんだもん | ノーマル |
| 1  | ずんだもん | あまあま |
| 7  | ずんだもん | ツンツン |
| 0  | 四国めたん | ノーマル |
| 2  | 四国めたん | あまあま |
| 8  | 春日部つむぎ | ノーマル |
| 10 | 雨晴はう | ノーマル |
| 13 | 青山龍星 | ノーマル |

---

## 実行方法

### generate.sh を使う（最も簡単）

```bash
# ファイルを指定して実行
./generate.sh samples/my_meeting.txt

# 出力先を指定
./generate.sh samples/my_meeting.txt -o output/demo.mp3
```

> VOICEVOXが起動していない場合、Dockerで自動起動してから実行します。

### python コマンドで直接実行

```bash
# 基本
python src/main.py samples/my_meeting.txt

# 出力先を指定
python src/main.py samples/my_meeting.txt -o output/my_demo.mp3

# config.yaml を別ファイルで指定
python src/main.py samples/my_meeting.txt -c custom_config.yaml

# テキストを直接渡す
python src/main.py -t '施設長: こんにちは。本日もよろしくお願いします。'

# パイプで渡す
echo '施設長: テスト発言です。' | python src/main.py
cat samples/my_meeting.txt | python src/main.py -o output/test.mp3
```

### 実行前の確認コマンド

```bash
# 話者一覧を確認（VOICEVOXが起動している必要あり）
python src/main.py --list-speakers

# 音声合成せずにパース結果・話者マッピングだけ確認（dry-run）
python src/main.py samples/my_meeting.txt --dry-run
```

dry-run の出力例：
```
📝 パース結果:

  [  1] ✅ 施設長 (ID:3): 本日はお忙しいところお集まりいただきありがとうございます...
  [  2] ✅ ケアマネ (ID:2): よろしくお願いいたします。まず前回の経過を共有させて...
  [  3] ⚠️ 新人スタッフ (ID:3): はじめまして。（config未設定→デフォルト話者を使用）

📊 合計: 45 エントリ
   話者: 3 名 (ケアマネ, 施設長, 新人スタッフ)

⚠ 以下の話者はconfig.yamlにマッピングがありません（デフォルト話者を使用）:
   - 新人スタッフ
```

> ✅ = config.yaml にマッピングあり  
> ⚠️ = マッピングなし（デフォルト話者で代替）

---

## Claude Code での使い方

Claude Code（AIアシスタント）と一緒に使うと、議事録テキストの準備からMP3生成まで会話しながら進められます。

### 初めての指示の出し方

リポをcloneしてプロジェクトフォルダをClaude Codeで開き、以下のように指示してください：

---

**ステップ1: セットアップの確認を依頼する**

```
voicevox-transcript-toolのセットアップをして。
Dockerでの起動から依存パッケージのインストールまで全部やって。
```

---

**ステップ2: 議事録テキストを用意して変換を依頼する**

議事録テキストを `samples/` フォルダに `.txt` ファイルとして用意してから：

```
samples/meeting_0530.txt の議事録を音声に変換して。
話者は「施設長」「ケアマネ」「介護士A」の3人。
施設長はずんだもん、ケアマネは四国めたん、介護士Aは春日部つむぎにして。
出力先は output/0530_demo.mp3 にして。
```

---

**ステップ3: サンプル議事録の生成を依頼する（テキストがない場合）**

```
ながらかいごのデモ用に、サービス担当者会議の議事録テキストを作って。
話者は施設長・ケアマネ・介護士の3人、10〜15発言ずつ、
samples/service_meeting_demo.txt に保存して。
```

保存されたら変換を依頼：

```
samples/service_meeting_demo.txt を音声に変換して。
config.yamlの話者設定も議事録に合わせて更新して。
```

---

**ステップ4: 複数議事録をまとめて変換する**

```
samples/ フォルダにある全 .txt ファイルを順番にMP3に変換して。
output/ フォルダにファイル名を合わせて保存して。
```

---

**話者を追加したいとき**

```
config.yaml に「看護師」という話者を追加して。
VOICEVOXの雨晴はう（ノーマル）を使って、話速は1.1にして。
```

---

**うまくいかないとき**

```
python src/main.py samples/meeting.txt --dry-run を実行して
パース結果と話者マッピングを確認して。
```

---

## コマンドオプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `input` | 議事録テキストファイルのパス | - |
| `-t`, `--text` | 議事録テキストを直接指定 | - |
| `-o`, `--output` | 出力ファイルパス | `output/meeting_audio.mp3` |
| `-c`, `--config` | config.yaml のパス | `config.yaml` |
| `--list-speakers` | 利用可能な話者一覧を表示して終了 | - |
| `--dry-run` | 音声合成せずにパース結果を表示 | - |

---

## ディレクトリ構成

```
voicevox-transcript-tool/
├── README.md              # このファイル
├── config.yaml            # 話者マッピング・音声設定（編集して使う）
├── generate.sh            # 実行ショートカット（Docker自動起動つき）
├── requirements.txt       # Pythonパッケージ
├── samples/               # 議事録テキストを置くフォルダ
│   ├── sample_transcript1_スタッフミーティング.txt
│   ├── sample_transcript2_サービス担当者会議.txt
│   └── ...
├── output/                # 生成されたMP3ファイルの出力先（.gitignoreで除外）
└── src/                   # ソースコード
    ├── main.py            # CLIエントリーポイント
    ├── parser.py          # 議事録テキストのパース
    ├── synthesizer.py     # VOICEVOX APIクライアント
    ├── audio_combiner.py  # WAVセグメント結合・MP3変換
    └── config_loader.py   # config.yaml の読み込み
```

---

## トラブルシューティング

### `❌ VOICEVOXが起動していません` と表示される

VOICEVOXが起動していないか、ポートが違います。

```bash
# Docker で起動
docker run -d --rm --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-latest

# 起動確認
curl http://localhost:50021/version
```

### `ModuleNotFoundError` が出る

```bash
pip install -r requirements.txt
```

`src/` 配下から実行する場合はルートディレクトリから実行してください：

```bash
# NG
cd src && python main.py

# OK
python src/main.py samples/transcript.txt
```

### MP3が生成されない（WAVになる）

ffmpegがインストールされていません。

```bash
brew install ffmpeg     # macOS
sudo apt install ffmpeg # Ubuntu
```

### 生成が遅い（CPUモード）

VOICEVOXのCPUモードでは1発言あたり数秒かかります。  
50発言で数分、200発言で10〜20分程度が目安です。  
GPUモードのDockerイメージを使うと大幅に高速化できます：

```bash
docker run -d --rm --name voicevox -p 50021:50021 voicevox/voicevox_engine:nvidia-latest
```

### `⚠ 以下の話者はconfig.yamlにマッピングがありません` と表示される

議事録の話者名と config.yaml のキーが一致していません。  
`--dry-run` で確認してから config.yaml を更新してください。

```bash
python src/main.py samples/transcript.txt --dry-run
```

---

## クレジット

本ツールは [VOICEVOX](https://voicevox.hiroshiba.jp/) の音声合成エンジンを使用しています。  
生成した音声ファイルを利用する際は、使用したキャラクターに応じてクレジット表記が必要です。

```
VOICEVOX:ずんだもん
VOICEVOX:四国めたん
（使用したキャラクター名を記載）
```

各キャラクターの利用規約は [VOICEVOX公式サイト](https://voicevox.hiroshiba.jp/) をご確認ください。
