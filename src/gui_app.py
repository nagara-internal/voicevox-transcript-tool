"""ながらかいご 音声変換 — macOS GUIアプリ."""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio_combiner import combine_wav_segments, convert_to_mp3, get_wav_duration
from config_loader import get_speaker_config, load_config
from parser import parse_transcript
from synthesizer import VoicevoxSynthesizer

APP_NAME = "ながらかいご 音声変換"
VOICEVOX_URL = "https://voicevox.hiroshiba.jp/"
VOICEVOX_APP = "/Applications/VOICEVOX.app"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "VoicevoxTranscriptTool"
HISTORY_FILE = APP_SUPPORT / "history.json"

AI_PROMPT = """以下の議事録を整形してください。

【フォーマット】話者名: 発言内容（1行1発言）

【ルール】
・話者名は一貫して（施設長、ケアマネ など）
・相槌・短い反応は省略可
・1発言200文字以内（句点で分割）
・セクション区切りは「---」の行

【議事録】
（ここに議事録テキストを貼り付けてください）"""

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── カラーパレット ──────────────────────────────────────────────────────────

BG      = "#18181B"
SIDEBAR = "#0C0C0F"
CARD    = "#27272A"
CARD2   = "#3F3F46"
ACCENT  = "#818CF8"
ACCENTH = "#6366F1"
SUCCESS = "#34D399"
WARNING = "#FBBF24"
ERROR   = "#F87171"
TEXT    = "#F4F4F5"
TEXT2   = "#D4D4D8"
MUTED   = "#A1A1AA"
BORDER  = "#3F3F46"
CODEBG  = "#1A1A2E"

H1   = ("SF Pro Display", 22, "bold")
H2   = ("SF Pro Display", 17, "bold")
H3   = ("SF Pro Display", 14, "bold")
BODY = ("SF Pro Display", 13)
BOLD = ("SF Pro Display", 13, "bold")
SM   = ("SF Pro Display", 12)
MONO = ("SF Mono", 12)


# ── ユーティリティ ──────────────────────────────────────────────────────────

def resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(__file__), "..", rel)


def get_config_path() -> str:
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    p = APP_SUPPORT / "config.yaml"
    if not p.exists():
        src = resource_path("config.yaml")
        if os.path.exists(src):
            shutil.copy(src, p)
    return str(p)


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_history(records: list) -> None:
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fmt_duration(secs) -> str:
    if secs is None:
        return "--"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_size(b: int) -> str:
    if b < 1_048_576:
        return f"{b / 1024:.0f} KB"
    return f"{b / 1_048_576:.1f} MB"


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    i = 2
    while True:
        c = p.with_stem(f"{p.stem}_{i}")
        if not c.exists():
            return c
        i += 1


# ── サイドバー ──────────────────────────────────────────────────────────────

class Sidebar(ctk.CTkFrame):
    ITEMS = [
        ("convert", "変換する", "✨"),
        ("guide",   "使い方",   "📖"),
        ("history", "履歴",     "🕐"),
    ]

    def __init__(self, parent, on_navigate):
        super().__init__(parent, width=192, fg_color=SIDEBAR, corner_radius=0)
        self.on_navigate = on_navigate
        self._btns: dict = {}
        self._build()

    def _build(self):
        self.pack_propagate(False)

        logo = ctk.CTkFrame(self, fg_color="transparent")
        logo.pack(fill="x", padx=20, pady=(28, 0))
        ctk.CTkLabel(logo, text="🎙", font=("SF Pro Display", 36),
                     text_color=ACCENT).pack()
        ctk.CTkLabel(logo, text="ながらかいご\n音声変換",
                     font=("SF Pro Display", 12, "bold"),
                     text_color=TEXT, justify="center").pack(pady=(4, 0))

        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=20, pady=20)

        for key, label, icon in self.ITEMS:
            btn = ctk.CTkButton(
                self, text=f"  {icon}  {label}",
                anchor="w", height=40,
                font=BODY, corner_radius=10,
                fg_color="transparent",
                hover_color=CARD,
                text_color=MUTED,
                command=lambda k=key: self._click(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._btns[key] = btn

    def _click(self, key: str):
        self._set_active(key)
        self.on_navigate(key)

    def _set_active(self, key: str):
        for k, btn in self._btns.items():
            if k == key:
                btn.configure(fg_color=CARD2, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=MUTED)


# ── セットアップ画面 ────────────────────────────────────────────────────────

class SetupView(ctk.CTkFrame):
    """VOICEVOX インストール前の初回セットアップ誘導画面."""

    def __init__(self, parent, on_connected):
        super().__init__(parent, fg_color=BG)
        self.on_connected = on_connected
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                        scrollbar_button_color=CARD2)
        scroll.pack(fill="both", expand=True)

        hero = ctk.CTkFrame(scroll, fg_color="transparent")
        hero.pack(fill="x", padx=64, pady=(48, 8))
        ctk.CTkLabel(hero, text="🎙", font=("SF Pro Display", 60)).pack()
        ctk.CTkLabel(hero, text=APP_NAME, font=H1, text_color=TEXT).pack(pady=(8, 0))
        ctk.CTkLabel(
            hero,
            text="まず VOICEVOX（無料の音声合成ソフト）をインストールして\nこのアプリと連携させましょう ✨",
            font=BODY, text_color=MUTED, wraplength=520, justify="center",
        ).pack(pady=(8, 0))

        steps = [
            {
                "num": "1",
                "title": "VOICEVOXをダウンロード",
                "icon": "⬇️",
                "desc": "公式サイトから macOS 版を無料でダウンロードできます。",
                "btn": "ダウンロードページを開く →",
                "accent": True,
                "cmd": self._open_download,
                "note": (
                    "💡  ダウンロードした .dmg ファイルを開いて、\n"
                    "    VOICEVOX のアイコンを Applications フォルダへドラッグしてください"
                ),
            },
            {
                "num": "2",
                "title": "VOICEVOXを起動する",
                "icon": "🚀",
                "desc": "Launchpad または Finder の「アプリケーション」から VOICEVOX を起動してください。",
                "btn": "VOICEVOXを起動する →",
                "accent": False,
                "cmd": self._launch,
                "note": (
                    "⚠️  「開発元を確認できません」と表示された場合:\n"
                    "    Applications の VOICEVOX を右クリック →「開く」→「開く」"
                ),
            },
            {
                "num": "3",
                "title": "接続を確認する",
                "icon": "🔗",
                "desc": "VOICEVOX が起動したら、下のボタンで接続を確認します。成功すると変換画面に移動します！",
                "btn": "接続を確認する →",
                "accent": True,
                "cmd": self._check,
                "note": None,
            },
        ]

        for s in steps:
            self._step_card(scroll, s)

        self._status = ctk.CTkLabel(scroll, text="", font=BODY, text_color=ERROR)
        self._status.pack(pady=(8, 48))

    def _step_card(self, parent, s: dict):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=64, pady=6)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=20)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        badge = ctk.CTkLabel(
            top, text=s["num"],
            font=("SF Pro Display", 14, "bold"),
            text_color="white", width=32, height=32,
            fg_color=ACCENT, corner_radius=16,
        )
        badge.pack(side="left", padx=(0, 16))

        texts = ctk.CTkFrame(top, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True, padx=(0, 16))

        title_row = ctk.CTkFrame(texts, fg_color="transparent")
        title_row.pack(fill="x", anchor="w")
        ctk.CTkLabel(title_row, text=s["icon"] + "  ",
                     font=("SF Pro Display", 16)).pack(side="left")
        ctk.CTkLabel(title_row, text=s["title"],
                     font=("SF Pro Display", 15, "bold"), text_color=TEXT,
                     anchor="w").pack(side="left")

        ctk.CTkLabel(
            texts, text=s["desc"],
            font=SM, text_color=MUTED, anchor="w", justify="left", wraplength=380,
        ).pack(fill="x", pady=(4, 0))

        fg = ACCENT if s["accent"] else CARD2
        hv = ACCENTH if s["accent"] else BORDER
        ctk.CTkButton(
            top, text=s["btn"], height=38, font=SM, corner_radius=10,
            fg_color=fg, hover_color=hv, command=s["cmd"],
        ).pack(side="right")

        if s.get("note"):
            note_wrap = ctk.CTkFrame(inner, fg_color=CODEBG, corner_radius=10)
            note_wrap.pack(fill="x", pady=(14, 0))
            ctk.CTkLabel(
                note_wrap, text=s["note"],
                font=SM, text_color=TEXT2,
                anchor="w", justify="left", wraplength=500,
            ).pack(padx=16, pady=12, anchor="w")

    def _open_download(self):
        webbrowser.open(VOICEVOX_URL)

    def _launch(self):
        if os.path.exists(VOICEVOX_APP):
            subprocess.Popen(["open", VOICEVOX_APP])
        else:
            self._status.configure(
                text="VOICEVOX が見つかりません。まずステップ 1 でダウンロードしてください",
                text_color=WARNING,
            )

    def _check(self):
        self._status.configure(text="接続確認中…", text_color=MUTED)
        self.update()
        if VoicevoxSynthesizer().check_connection():
            self._status.configure(text="✅  接続成功！変換画面へ移動します…", text_color=SUCCESS)
            self.after(600, self.on_connected)
        else:
            self._status.configure(
                text="❌  接続できません。VOICEVOX が完全に起動してから再度お試しください",
                text_color=ERROR,
            )


# ── ガイドビュー ────────────────────────────────────────────────────────────

class GuideView(ctk.CTkScrollableFrame):
    """使い方マニュアルページ."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=BG, scrollbar_button_color=CARD2)
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=52, pady=(36, 20))
        ctk.CTkLabel(hdr, text="📖 使い方ガイド", font=H1, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(hdr, text="VOICEVOXのセットアップからテキスト書き方まで全部わかります",
                     font=BODY, text_color=MUTED).pack(anchor="w", pady=(4, 0))

        self._about()
        self._voicevox()
        self._text_format()
        self._ai_prompt()
        self._output()
        self._faq()

        ctk.CTkFrame(self, height=48, fg_color="transparent").pack()

    def _section(self, emoji: str, title: str):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=52, pady=6)

        sh = ctk.CTkFrame(card, fg_color="transparent")
        sh.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(sh, text=f"{emoji}  {title}", font=H2, text_color=TEXT).pack(anchor="w")
        ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(fill="x", padx=24, pady=(12, 0))

        c = ctk.CTkFrame(card, fg_color="transparent")
        c.pack(fill="x", padx=24, pady=(16, 24))
        return c

    def _para(self, p, text: str, color=None):
        ctk.CTkLabel(p, text=text, font=BODY, text_color=color or TEXT2,
                     anchor="w", justify="left", wraplength=620).pack(fill="x", pady=(2, 4))

    def _h3(self, p, text: str):
        ctk.CTkLabel(p, text=text, font=H3, text_color=TEXT,
                     anchor="w").pack(fill="x", pady=(14, 4))

    def _code(self, p, text: str, height: int = None):
        h = height or max(48, text.count("\n") * 20 + 36)
        box = ctk.CTkTextbox(p, height=h, fg_color=CODEBG, font=MONO,
                             text_color=TEXT2, corner_radius=10, state="normal")
        box.pack(fill="x", pady=(4, 8))
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _bullet(self, p, icon: str, text: str):
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=icon, font=SM, width=24).pack(side="left")
        ctk.CTkLabel(row, text=text, font=BODY, text_color=TEXT2,
                     anchor="w", justify="left", wraplength=580).pack(
            side="left", fill="x", expand=True)

    def _note(self, p, text: str):
        box = ctk.CTkFrame(p, fg_color=CODEBG, corner_radius=10)
        box.pack(fill="x", pady=(6, 4))
        ctk.CTkLabel(box, text=text, font=SM, text_color=TEXT2,
                     anchor="w", justify="left", wraplength=560).pack(
            padx=16, pady=12, anchor="w")

    def _div(self, p):
        ctk.CTkFrame(p, height=1, fg_color=BORDER).pack(fill="x", pady=10)

    def _about(self):
        c = self._section("🎙", "このアプリについて")
        self._para(c, "議事録テキスト（話者名: 発言内容 形式）を VOICEVOX の音声に変換して MP3 ファイルを自動生成するツールです。")
        self._para(c, "ながらかいごのマニュアル動画・研修素材の音声制作にお使いください。")
        self._div(c)
        for icon, text in [
            ("1️⃣", "議事録テキストを .txt ファイルで用意する"),
            ("2️⃣", "「変換する」画面でファイルを選択する"),
            ("3️⃣", "MP3 が自動生成されてデスクトップに保存される"),
        ]:
            self._bullet(c, icon, text)

    def _voicevox(self):
        c = self._section("📥", "VOICEVOXのセットアップ")
        self._para(c, "VOICEVOX は無料の日本語テキスト読み上げソフトです。このアプリが VOICEVOX と連携して音声を生成します。")

        self._h3(c, "Step 1 — ダウンロード")
        self._bullet(c, "1.", "ブラウザで https://voicevox.hiroshiba.jp/ を開く")
        self._bullet(c, "2.", "「ダウンロード」ボタンをクリック")
        self._bullet(c, "3.", "macOS 版を選択してダウンロード")
        ctk.CTkButton(
            c, text="ダウンロードページを開く →", height=36, width=220,
            font=SM, corner_radius=10, fg_color=ACCENT, hover_color=ACCENTH,
            command=lambda: webbrowser.open(VOICEVOX_URL),
        ).pack(anchor="w", pady=(8, 0))

        self._h3(c, "Step 2 — インストール")
        self._bullet(c, "4.", "ダウンロードした .dmg ファイルをダブルクリック")
        self._bullet(c, "5.", "VOICEVOX のアイコンを「Applications」フォルダへドラッグ")
        self._note(c, "💡  Applications フォルダへのドラッグは、.dmg を開いたウィンドウ内の矢印に従ってください")

        self._h3(c, "Step 3 — 初回起動")
        self._bullet(c, "6.", "Launchpad または Finder の「アプリケーション」から VOICEVOX を起動")
        self._note(c, (
            "⚠️  「開発元を確認できません」と表示された場合の対処:\n"
            "   1. Finder でアプリケーションフォルダを開く\n"
            "   2. VOICEVOX を右クリック（2本指クリック）→「開く」を選択\n"
            "   3. ダイアログが出たら「開く」を押す\n"
            "   → 2回目以降は通常どおり起動できます"
        ))

        self._h3(c, "Step 4 — 接続確認")
        self._para(c, "VOICEVOX が起動したら、このアプリの「変換する」ページを開いてください。自動で接続が確認されます。")

    def _text_format(self):
        c = self._section("📝", "テキストファイルの書き方")
        self._para(c, "テキストファイルはどこに保存しても OK です（デスクトップ・書類フォルダ など）。変換時にファイル選択ダイアログが開きます。")

        self._h3(c, "基本フォーマット")
        self._code(c, "話者名: 発言内容\n話者名：発言内容  ← 全角コロン（：）でもOK")

        self._h3(c, "記述例")
        self._code(c, (
            "# 4月スタッフミーティング\n\n"
            "施設長: 本日はお集まりいただきありがとうございます。\n"
            "ケアマネ: よろしくお願いします。\n"
            "介護士A: 先月の利用者様の件から報告いたします。\n"
            "前回から体調が安定しており、食事量も増えています。\n\n"
            "---\n\n"
            "施設長: では次の議題に移りましょう。"
        ), height=160)

        self._h3(c, "特殊記法")
        self._bullet(c, "📌", "--- の行 → セクション区切り（2 秒の無音を挿入）")
        self._bullet(c, "📌", "# で始まる行 → コメント（読み上げをスキップ）")
        self._bullet(c, "📌", "空行 → スキップ")
        self._bullet(c, "📌", "コロンなし行 → 直前の話者の発言の続きとして処理")
        self._bullet(c, "📌", "200文字超の発言 → 句点（。）で自動分割して合成")

        self._note(c, "💡  文字コードは UTF-8 で保存してください（macOS のテキストエディットはデフォルトで UTF-8）")

    def _ai_prompt(self):
        c = self._section("🤖", "AIプロンプトで簡単に整形")
        self._para(c, "ChatGPT や Claude に議事録を貼り付けてプロンプトと一緒に送ると、フォーマットを自動整形できます。")
        for icon, text in [
            ("1.", "「変換する」画面の「AIプロンプトをコピー」ボタンを押す"),
            ("2.", "ChatGPT または Claude のチャットを開く"),
            ("3.", "コピーしたプロンプトを貼り付け、続けて議事録テキストを貼る"),
            ("4.", "送信すると整形済みテキストが返ってくる"),
            ("5.", "テキストエディタに貼り付けて .txt として保存し、このアプリで変換"),
        ]:
            self._bullet(c, icon, text)

    def _output(self):
        c = self._section("💾", "出力ファイルについて")
        self._bullet(c, "📁", "保存先: デスクトップ（~/Desktop/）")
        self._bullet(c, "📄", "ファイル名: 入力した .txt と同じ名前（例: meeting.txt → meeting.mp3）")
        self._bullet(c, "🔢", "同名ファイルがある場合: meeting_2.mp3 のように連番が付きます")
        self._bullet(c, "🎵", "フォーマット: MP3（ffmpeg が未インストールの場合は WAV）")
        self._div(c)
        self._para(c, "設定ファイル（config.yaml）で話者名と VOICEVOX キャラクターのマッピングを変更できます。", MUTED)
        self._bullet(c, "📍", f"設定ファイルの場所: {APP_SUPPORT}/config.yaml")

    def _faq(self):
        c = self._section("❓", "よくある質問")
        faqs = [
            ("変換に時間がかかる",
             "VOICEVOX は CPU で処理するため、100 行で 5〜10 分程度かかります。変換中は VOICEVOX を終了しないでください。"),
            ("「接続できません」と表示される",
             "VOICEVOX が完全に起動してから再試行してください。VOICEVOX のウィンドウが表示されるまで少し待ってから「変換する」を開いてください。"),
            ("声（キャラクター）を変えたい",
             f"設定ファイル（{APP_SUPPORT}/config.yaml）の speaker_id を変更してください。ID 一覧は VOICEVOX アプリの設定画面で確認できます。"),
            ("新しい話者を追加したい",
             "config.yaml に話者名と speaker_id を追記してください。話者名は議事録のコロン前と完全一致させる必要があります。"),
            ("MP3 ではなく WAV で出力される",
             "ffmpeg がインストールされていない場合、WAV 形式で出力されます。brew install ffmpeg でインストールできます。"),
        ]
        for i, (q, a) in enumerate(faqs):
            if i > 0:
                self._div(c)
            ctk.CTkLabel(c, text=f"Q: {q}", font=BOLD, text_color=TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(c, text=f"A: {a}", font=BODY, text_color=TEXT2,
                         anchor="w", justify="left", wraplength=600).pack(fill="x", pady=(2, 0))


# ── 変換ビュー ──────────────────────────────────────────────────────────────

RULES_TEXT = """話者名: 発言内容
（半角コロン : または全角コロン ：）

例:
  施設長: 本日はお集まりいただきありがとうございます。
  ケアマネ: よろしくお願いします。

■ 特殊記法
  # で始まる行  → コメント（スキップ）
  --- の行      → セクション区切り（2秒の無音）
  空行          → スキップ
  コロンなし行  → 直前の話者の続き
  200文字超     → 句点で自動分割"""


class ConvertView(ctk.CTkFrame):
    def __init__(self, parent, config_path: str, on_history_update, on_guide):
        super().__init__(parent, fg_color=BG)
        self.config_path = config_path
        self.on_history_update = on_history_update
        self.on_guide = on_guide
        self._q: queue.Queue = queue.Queue()
        self._selected = None
        self._result = None
        self._total = 0
        self._frames: dict = {}
        self._build()
        self._show(0)
        self._poll()

    def _build(self):
        self._build_step0()
        self._build_step1()
        self._build_step2()
        self._build_step3()

    def _build_step0(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        self._frames[0] = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", padx=52, pady=(36, 4))
        ctk.CTkLabel(hdr, text="テキストの書き方", font=H1, text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            hdr, text="📖 詳細ガイド", height=32, width=120,
            font=SM, corner_radius=8,
            fg_color=CARD2, hover_color=BORDER, text_color=MUTED,
            command=self.on_guide,
        ).pack(side="right")

        ctk.CTkLabel(
            f,
            text="このフォーマットの .txt ファイルが必要です。AIプロンプトで議事録を簡単に整形できます。",
            font=BODY, text_color=MUTED, anchor="w", justify="left",
        ).pack(fill="x", padx=52, pady=(0, 14))

        rules = ctk.CTkTextbox(f, height=220, fg_color=CARD, corner_radius=14,
                               font=MONO, text_color=TEXT2, state="normal")
        rules.pack(fill="x", padx=52)
        rules.insert("1.0", RULES_TEXT)
        rules.configure(state="disabled")

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(fill="x", padx=52, pady=(18, 0))

        ctk.CTkButton(
            btn_row, text="📋  AIプロンプトをコピー",
            height=42, font=BODY, corner_radius=10,
            fg_color=CARD2, hover_color=BORDER, text_color=TEXT,
            command=self._copy_prompt,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="ファイルを選択する  →",
            height=42, font=BOLD, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENTH,
            command=lambda: self._show(1),
        ).pack(side="right")

    def _build_step1(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        self._frames[1] = f

        ctk.CTkLabel(f, text="ファイルを選択してください",
                     font=H1, text_color=TEXT).pack(pady=(52, 4))
        ctk.CTkLabel(f, text="UTF-8 の .txt ファイルを選択すると変換を開始できます",
                     font=BODY, text_color=MUTED).pack(pady=(0, 24))

        self._dz = ctk.CTkFrame(f, fg_color=CARD, corner_radius=20,
                                height=180, border_width=2, border_color=BORDER)
        self._dz.pack(fill="x", padx=52)
        self._dz.pack_propagate(False)

        dz_inner = ctk.CTkFrame(self._dz, fg_color="transparent")
        dz_inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(dz_inner, text="📄", font=("SF Pro Display", 40)).pack()
        self._dz_title = ctk.CTkLabel(dz_inner, text="クリックしてファイルを選択",
                                      font=("SF Pro Display", 14), text_color=MUTED)
        self._dz_title.pack(pady=(8, 2))
        self._dz_sub = ctk.CTkLabel(dz_inner, text=".txt ファイルのみ",
                                    font=SM, text_color=MUTED)
        self._dz_sub.pack()

        for w in [self._dz, dz_inner]:
            w.bind("<Button-1>", lambda e: self._pick_file())
        for child in dz_inner.winfo_children():
            child.bind("<Button-1>", lambda e: self._pick_file())
        self._dz.bind("<Enter>", lambda e: self._dz.configure(border_color=ACCENT))
        self._dz.bind("<Leave>", lambda e: self._dz.configure(border_color=BORDER))

        self._file_label = ctk.CTkLabel(f, text="", font=BODY, text_color=SUCCESS)
        self._file_label.pack(pady=(14, 0))

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(pady=(20, 0))

        ctk.CTkButton(
            btn_row, text="← ルールを確認",
            height=42, font=BODY, corner_radius=10,
            fg_color=CARD2, hover_color=BORDER,
            command=lambda: self._show(0),
        ).pack(side="left", padx=8)

        self._convert_btn = ctk.CTkButton(
            btn_row, text="音声に変換する  🎵",
            height=42, font=BOLD, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENTH,
            state="disabled",
            command=self._start_convert,
        )
        self._convert_btn.pack(side="left", padx=8)

    def _build_step2(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        self._frames[2] = f

        ctk.CTkLabel(f, text="🎙 変換中...", font=H1, text_color=TEXT).pack(pady=(52, 4))
        self._converting_label = ctk.CTkLabel(f, text="", font=BODY, text_color=MUTED)
        self._converting_label.pack()

        self._progress_bar = ctk.CTkProgressBar(f, height=6, corner_radius=3,
                                                 fg_color=CARD, progress_color=ACCENT)
        self._progress_bar.pack(fill="x", padx=52, pady=(20, 4))
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(f, text="", font=SM, text_color=MUTED)
        self._progress_label.pack()

        self._log_box = ctk.CTkTextbox(f, height=240, font=MONO,
                                       fg_color=CARD, corner_radius=14,
                                       text_color=MUTED, state="disabled")
        self._log_box.pack(fill="x", padx=52, pady=(14, 0))

    def _build_step3(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        self._frames[3] = f

        ctk.CTkLabel(f, text="✅", font=("SF Pro Display", 60)).pack(pady=(48, 8))
        ctk.CTkLabel(f, text="変換完了！", font=H1, text_color=TEXT).pack()

        result_card = ctk.CTkFrame(f, fg_color=CARD, corner_radius=16,
                                   border_width=1, border_color=BORDER)
        result_card.pack(fill="x", padx=52, pady=(24, 0))

        inner = ctk.CTkFrame(result_card, fg_color="transparent")
        inner.pack(fill="x", padx=28, pady=24)

        self._res_name = ctk.CTkLabel(inner, text="", font=H3, text_color=TEXT, anchor="w")
        self._res_name.pack(fill="x")

        self._res_dur = ctk.CTkLabel(inner, text="",
                                     font=("SF Pro Display", 28, "bold"),
                                     text_color=ACCENT, anchor="w")
        self._res_dur.pack(fill="x", pady=(6, 2))

        self._res_meta = ctk.CTkLabel(inner, text="", font=SM, text_color=MUTED,
                                      anchor="w", justify="left", wraplength=560)
        self._res_meta.pack(fill="x")

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(pady=(24, 0))

        ctk.CTkButton(
            btn_row, text="📂  Finder で開く",
            height=44, font=("SF Pro Display", 14, "bold"), corner_radius=12,
            fg_color=SUCCESS, hover_color="#25A17A",
            command=self._open_finder,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="別のファイルを変換",
            height=44, font=BODY, corner_radius=12,
            fg_color=CARD2, hover_color=BORDER,
            command=self._reset,
        ).pack(side="left", padx=8)

    def _show(self, step: int):
        for f in self._frames.values():
            f.pack_forget()
        self._frames[step].pack(fill="both", expand=True)

    def _copy_prompt(self):
        self.clipboard_clear()
        self.clipboard_append(AI_PROMPT)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="文字起こしファイルを選択",
            filetypes=[("テキストファイル", "*.txt"), ("すべて", "*.*")],
        )
        if path:
            self._selected = path
            name = Path(path).name
            self._dz_title.configure(text=f"✅  {name}", text_color=SUCCESS)
            self._dz_sub.configure(text="クリックして変更", text_color=MUTED)
            self._file_label.configure(text=f"選択中: {name}")
            self._convert_btn.configure(state="normal")

    def _start_convert(self):
        if not self._selected:
            return
        self._show(2)
        stem = Path(self._selected).stem
        self._converting_label.configure(text=f"「{stem}」を変換しています…")
        self._progress_bar.configure(mode="indeterminate")
        self._progress_bar.start()
        self._progress_label.configure(text="")
        self._clear_log()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            config = load_config(self.config_path)
            entries = parse_transcript(self._selected)
            total = len(entries)
            self._total = total
            self._q.put(("log", f"📝  {total} エントリを読み込みました"))
            self._q.put(("mode_determinate", total))

            synth = VoicevoxSynthesizer(
                base_url=config["voicevox"]["base_url"],
                timeout=config["voicevox"]["timeout"],
            )
            audio_cfg = config["audio"]
            stem = Path(self._selected).stem
            out_path = unique_path(Path.home() / "Desktop" / f"{stem}.mp3")

            segments = []
            failed = 0
            for i, entry in enumerate(entries):
                if entry["type"] == "section_break":
                    segments.append({"wav_data": [], "type": "section_break"})
                    self._q.put(("progress", i + 1, f"--- セクション区切り ({i+1}/{total})"))
                    continue

                speaker = entry["speaker"]
                text = entry["text"]
                sc = get_speaker_config(config, speaker)
                self._q.put(("progress", i + 1, f"{speaker}  ({i+1}/{total})"))

                try:
                    wav_parts = synth.synthesize_long_text(
                        text=text,
                        speaker_id=sc["speaker_id"],
                        speed_scale=sc.get("speed_scale", 1.0),
                        pitch_scale=sc.get("pitch_scale", 0.0),
                    )
                    segments.append({"wav_data": wav_parts, "type": "line"})
                    short = text[:45] + ("…" if len(text) > 45 else "")
                    self._q.put(("log", f"  ✓  {speaker}: {short}"))
                except Exception as e:
                    failed += 1
                    self._q.put(("log", f"  ⚠  スキップ [{speaker}]: {e}"))

            self._q.put(("log", "🔗  音声ファイルを結合中..."))
            wav_tmp = str(out_path.with_suffix(".wav"))
            combine_wav_segments(
                segments=segments,
                output_path=wav_tmp,
                silence_between_lines=audio_cfg["silence_between_lines"],
                silence_between_sections=audio_cfg["silence_between_sections"],
                sample_rate=audio_cfg["sample_rate"],
            )
            duration = get_wav_duration(wav_tmp)
            final = str(out_path)
            if convert_to_mp3(wav_tmp, final, audio_cfg.get("mp3_quality", 2)):
                os.remove(wav_tmp)
            else:
                final = wav_tmp
            size = os.path.getsize(final)
            self._q.put(("done", {
                "path": final,
                "name": Path(final).name,
                "stem": Path(final).stem,
                "size": size,
                "duration": duration,
                "failed": failed,
            }))
        except Exception as e:
            self._q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self._append_log(msg[1])
                elif kind == "mode_determinate":
                    self._progress_bar.stop()
                    self._progress_bar.configure(mode="determinate")
                    self._progress_bar.set(0)
                elif kind == "progress":
                    _, val, label = msg
                    if self._total:
                        self._progress_bar.set(val / self._total)
                    self._progress_label.configure(text=label)
                elif kind == "done":
                    self._progress_bar.stop()
                    self._progress_bar.set(1)
                    self._on_done(msg[1])
                elif kind == "error":
                    self._progress_bar.stop()
                    self._append_log(f"❌  エラー: {msg[1]}")
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _append_log(self, text: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", text + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _on_done(self, data: dict):
        self._result = data
        self._res_name.configure(text=f"📄  {data['name']}")
        self._res_dur.configure(text=fmt_duration(data["duration"]))
        meta_parts = [f"サイズ: {fmt_size(data['size'])}"]
        if data["failed"]:
            meta_parts.append(f"スキップ: {data['failed']} 行")
        self._res_meta.configure(text="　　".join(meta_parts) + f"\n保存先: {data['path']}")

        records = load_history()
        records.insert(0, {
            "name": data["name"],
            "stem": data["stem"],
            "path": data["path"],
            "size": data["size"],
            "duration": data["duration"],
            "date": datetime.now().isoformat(),
        })
        save_history(records[:200])
        self.on_history_update()
        self._show(3)

    def _open_finder(self):
        if self._result and os.path.exists(self._result["path"]):
            subprocess.Popen(["open", "-R", self._result["path"]])

    def _reset(self):
        self._selected = None
        self._result = None
        self._dz_title.configure(text="クリックしてファイルを選択", text_color=MUTED)
        self._dz_sub.configure(text=".txt ファイルのみ", text_color=MUTED)
        self._file_label.configure(text="")
        self._convert_btn.configure(state="disabled")
        self._show(1)


# ── 履歴ビュー ──────────────────────────────────────────────────────────────

class HistoryView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=BG)
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=52, pady=(36, 0))
        ctk.CTkLabel(header, text="変換履歴", font=H1, text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            header, text="すべて削除", height=30, width=96,
            font=SM, corner_radius=8,
            fg_color=CARD2, hover_color=ERROR, text_color=MUTED,
            command=self._clear,
        ).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                              scrollbar_button_color=CARD2)
        self._scroll.pack(fill="both", expand=True, padx=52, pady=(14, 36))
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        records = load_history()
        if not records:
            empty = ctk.CTkFrame(self._scroll, fg_color="transparent")
            empty.pack(expand=True, pady=80)
            ctk.CTkLabel(empty, text="🎵", font=("SF Pro Display", 48)).pack()
            ctk.CTkLabel(empty, text="まだ変換履歴がありません",
                         font=BODY, text_color=MUTED).pack(pady=(8, 2))
            ctk.CTkLabel(empty, text="「変換する」でファイルを選択してください",
                         font=SM, text_color=BORDER).pack()
            return

        for rec in records:
            self._add_row(rec)

    def _add_row(self, rec: dict):
        card = ctk.CTkFrame(self._scroll, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=4)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)

        ctk.CTkLabel(row, text="🎵", font=("SF Pro Display", 26), width=36).pack(side="left")

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=(12, 8))

        ctk.CTkLabel(info, text=rec.get("name", "不明"),
                     font=("SF Pro Display", 14, "bold"), text_color=TEXT,
                     anchor="w").pack(fill="x")

        meta = []
        if rec.get("duration"):
            meta.append(f"⏱ {fmt_duration(rec['duration'])}")
        if rec.get("size"):
            meta.append(f"💾 {fmt_size(rec['size'])}")
        if rec.get("date"):
            try:
                dt = datetime.fromisoformat(rec["date"])
                meta.append(f"📅 {dt.strftime('%Y/%m/%d %H:%M')}")
            except Exception:
                pass
        ctk.CTkLabel(info, text="   ".join(meta),
                     font=SM, text_color=MUTED, anchor="w").pack(fill="x")

        path = rec.get("path", "")
        if path and os.path.exists(path):
            ctk.CTkButton(
                row, text="開く", height=30, width=64,
                font=SM, corner_radius=8,
                fg_color=CARD2, hover_color=ACCENT,
                command=lambda p=path: subprocess.Popen(["open", "-R", p]),
            ).pack(side="right")
        else:
            ctk.CTkLabel(row, text="削除済", font=SM, text_color=BORDER).pack(side="right")

    def _clear(self):
        save_history([])
        self.refresh()


# ── メインアプリ ────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("900x660")
        self.minsize(800, 560)
        self.configure(fg_color=BG)
        self._config_path = get_config_path()
        self._sidebar = None
        self._convert_view = None
        self._guide_view = None
        self._history_view = None
        self._check_and_route()

    def _check_and_route(self):
        if VoicevoxSynthesizer().check_connection():
            self._show_main()
        else:
            self._show_setup()

    def _show_setup(self):
        for w in self.winfo_children():
            w.destroy()
        SetupView(self, on_connected=self._show_main).pack(fill="both", expand=True)

    def _show_main(self):
        for w in self.winfo_children():
            w.destroy()

        self._sidebar = Sidebar(self, on_navigate=self._navigate)
        self._sidebar.pack(side="left", fill="y")

        ctk.CTkFrame(self, width=1, fg_color=BORDER).pack(side="left", fill="y")

        content = ctk.CTkFrame(self, fg_color=BG)
        content.pack(side="left", fill="both", expand=True)

        self._convert_view = ConvertView(
            content, self._config_path,
            on_history_update=self._refresh_history,
            on_guide=self._nav_guide,
        )
        self._guide_view = GuideView(content)
        self._history_view = HistoryView(content)

        self._sidebar._click("convert")

    def _nav_guide(self):
        if self._sidebar:
            self._sidebar._click("guide")

    def _refresh_history(self):
        if self._history_view:
            self._history_view.refresh()

    def _navigate(self, key: str):
        for v in [self._convert_view, self._guide_view, self._history_view]:
            if v:
                v.pack_forget()
        if key == "convert" and self._convert_view:
            self._convert_view.pack(fill="both", expand=True)
        elif key == "guide" and self._guide_view:
            self._guide_view.pack(fill="both", expand=True)
        elif key == "history" and self._history_view:
            self._history_view.refresh()
            self._history_view.pack(fill="both", expand=True)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
