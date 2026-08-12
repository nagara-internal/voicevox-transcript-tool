#!/bin/bash
# install.sh — text-to-mp3 音声変換ツール セットアップスクリプト

set -e

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$TOOL_DIR/.venv"
LAUNCHER_NAME="VOICEVOX変換ツール.command"
LAUNCHER_PATH="$HOME/Desktop/$LAUNCHER_NAME"

echo ""
echo "======================================"
echo " text-to-mp3 音声変換ツール セットアップ"
echo "======================================"
echo ""

# ── Python バージョン確認 ───────────────────────────────────────────────────

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.10 以上が必要です。"
    echo ""
    echo "インストール方法:"
    echo "  https://www.python.org/downloads/ からダウンロード"
    echo "  または: brew install python@3.12"
    echo ""
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

echo "📦 パッケージをインストール中（数分かかる場合があります）..."
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
echo " text-to-mp3 音声変換ツール 起動中"
echo "======================================"
echo ""
echo "ブラウザが自動で開きます..."
echo "終了するには このウィンドウを閉じるか Ctrl+C を押してください。"
echo ""
"$VENV_DIR/bin/streamlit" run "$TOOL_DIR/app.py" \\
    --server.port 8501 \\
    --browser.gatherUsageStats false
LAUNCHER

chmod +x "$LAUNCHER_PATH"
echo "✅ 起動ファイルを作成しました: $LAUNCHER_PATH"

# ── ffmpeg 確認 ─────────────────────────────────────────────────────────────

echo ""
if command -v ffmpeg &>/dev/null; then
    echo "✅ ffmpeg: インストール済み（MP3出力が使えます）"
else
    echo "⚠  ffmpeg が見つかりません。MP3ではなくWAVで出力されます。"
    echo "   MP3出力が必要な場合: brew install ffmpeg"
fi

# ── 完了メッセージ ──────────────────────────────────────────────────────────

echo ""
echo "======================================"
echo " セットアップ完了！"
echo "======================================"
echo ""
echo "使い方:"
echo "  1. VOICEVOXアプリを起動する"
echo "  2. デスクトップの「$LAUNCHER_NAME」をダブルクリックする"
echo "  3. ブラウザが自動で開きます"
echo ""
