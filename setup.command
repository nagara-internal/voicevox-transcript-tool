#!/bin/bash
# setup.command — ダブルクリックで実行するセットアップファイル

set -e

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$TOOL_DIR/.venv"
LAUNCHER_NAME="VOICEVOX変換ツール.command"
LAUNCHER_PATH="$HOME/Desktop/$LAUNCHER_NAME"

clear
echo ""
echo "======================================"
echo " ながらかいご 音声変換ツール セットアップ"
echo "======================================"
echo ""
echo "初回セットアップを開始します。数分かかる場合があります。"
echo "この画面は閉じずにお待ちください。"
echo ""

# ── Python バージョン確認 ───────────────────────────────────────────────────

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "======================================"
    echo " ❌ セットアップに失敗しました"
    echo "======================================"
    echo ""
    echo "Python 3.10以上がインストールされていません。"
    echo ""
    echo "以下のURLからPythonをダウンロードしてインストールしてください："
    echo "  https://www.python.org/downloads/"
    echo ""
    echo "インストール後、もう一度 setup.command をダブルクリックしてください。"
    echo ""
    read -p "Enterキーを押すと閉じます..."
    exit 1
fi

echo "✅ Python: $($PYTHON --version)"

# ── 仮想環境の作成 ──────────────────────────────────────────────────────────

if [ -d "$VENV_DIR" ]; then
    echo "✅ 仮想環境が既に存在します（スキップ）"
else
    echo "📦 仮想環境を作成中..."
    "$PYTHON" -m venv "$VENV_DIR"
    echo "✅ 仮想環境を作成しました"
fi

# ── 依存パッケージのインストール ────────────────────────────────────────────

echo "📦 必要なパッケージをインストール中..."
echo "   （インターネット接続が必要です。数分かかる場合があります）"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$TOOL_DIR/requirements.txt"
echo "✅ パッケージのインストール完了"

# ── デスクトップ起動ファイルの作成 ────────────────────────────────────────

echo "🖥  デスクトップに起動ファイルを作成中..."

cat > "$LAUNCHER_PATH" << LAUNCHER
#!/bin/bash
# VOICEVOX変換ツール 起動スクリプト
cd "$TOOL_DIR"
echo ""
echo "======================================"
echo " ながらかいご 音声変換ツール 起動中"
echo "======================================"
echo ""
echo "ブラウザが自動で開きます..."
echo "終了するには このウィンドウを閉じてください。"
echo ""
"$VENV_DIR/bin/streamlit" run "$TOOL_DIR/app.py" \\
    --server.port 8501 \\
    --browser.gatherUsageStats false
LAUNCHER

chmod +x "$LAUNCHER_PATH"
echo "✅ 起動ファイルを作成しました"

# ── ffmpeg 確認 ─────────────────────────────────────────────────────────────

echo ""
if command -v ffmpeg &>/dev/null; then
    echo "✅ MP3出力: 利用可能"
else
    echo "⚠  MP3出力は利用できません（WAV形式で出力されます）"
fi

# ── 完了メッセージ ──────────────────────────────────────────────────────────

echo ""
echo "======================================"
echo " ✅ セットアップ完了！"
echo "======================================"
echo ""
echo "デスクトップに「$LAUNCHER_NAME」が作成されました。"
echo ""
echo "【毎回の使い方】"
echo "  1. VOICEVOXアプリを起動する"
echo "  2. デスクトップの「$LAUNCHER_NAME」をダブルクリックする"
echo "  3. ブラウザが自動で開きます"
echo ""
read -p "Enterキーを押すと閉じます..."
