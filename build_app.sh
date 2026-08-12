#!/bin/bash
# ながらかいご 議事録→音声変換 — macOS .app + .dmg ビルドスクリプト
set -e

cd "$(dirname "$0")"

APP_NAME="ながらかいご音声変換"
DIST_DIR="dist"

echo "📦 依存パッケージを確認..."
pip install pyinstaller customtkinter -q

echo "🔨 PyInstaller でビルド中..."
pyinstaller \
    --name "$APP_NAME" \
    --windowed \
    --onedir \
    --noconfirm \
    --collect-all customtkinter \
    --add-data "config.yaml:." \
    --add-data "samples:samples" \
    --paths "src" \
    src/gui_app.py

APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/$APP_NAME.dmg"

echo ""
echo "✅ .app ビルド完了: $APP_PATH"
echo ""

# ── DMG 作成 ──────────────────────────────────────────────────────
if command -v create-dmg &>/dev/null; then
    echo "💿 create-dmg で DMG を作成中..."
    rm -f "$DMG_PATH"
    create-dmg \
        --volname "$APP_NAME" \
        --window-size 520 320 \
        --icon-size 100 \
        --icon "$APP_NAME.app" 130 160 \
        --app-drop-link 390 160 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$APP_PATH"
else
    echo "💿 hdiutil で DMG を作成中（簡易版）..."
    rm -f "$DMG_PATH"
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$APP_PATH" \
        -ov -format UDZO \
        "$DMG_PATH"
    echo ""
    echo "💡 よりきれいな DMG（アイコン配置付き）を作るには:"
    echo "   brew install create-dmg"
    echo "   ./build_app.sh を再実行してください"
fi

echo ""
echo "✅ DMG 作成完了: $DMG_PATH"
echo ""
echo "配布手順:"
echo "  1. $DMG_PATH を共有"
echo "  2. 受け取った側は DMG をダブルクリック → Applications にドラッグ"
echo "  3. VOICEVOX (https://voicevox.hiroshiba.jp/) を別途インストール・起動"
echo "  4. アプリを起動すると接続確認画面が表示される"
