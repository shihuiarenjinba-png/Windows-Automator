from __future__ import annotations

import json
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import (
    FieldValue,
    ProductInput,
    TrailerAsset,
    SECURITY_CONFIRM_KEYS,
    Severity,
    ValueMode,
    apply_fixed_rules,
    fields_for,
    render_markdown,
    run_queue,
    validate_product,
    file_sha256,
)
from .github_context import fetch_context
from .ollama import complete_product
from .partner_center import (
    PARTNER_CENTER_APPS_GAMES_URL,
    dryrun_uploader,
    simulate_overview_start,
)

MODE_LABELS = {
    ValueMode.FIXED: "固定（自動）",
    ValueMode.OLLAMA: "AI補完",
    ValueMode.MANUAL: "手動",
    ValueMode.BLANK: "空欄",
    ValueMode.REVIEW: "要確認",
}
LABEL_MODES = {v: k for k, v in MODE_LABELS.items()}
SECURITY_LABELS = {
    "collects_personal_data": "個人情報へアクセス・収集・送信しますか",
    "uses_external_accounts": "外部アカウント / ログインを使用しますか",
    "security_external_services": "外部API / クラウドへ通信しますか",
    "security_local_file_access": "ユーザーのファイル / フォルダへアクセスしますか",
    "security_camera": "カメラを使用しますか",
    "security_microphone": "マイクを使用しますか",
    "security_location": "位置情報を使用しますか",
    "security_restricted_capabilities": "制限付きCapabilityを宣言していますか",
    "security_non_microsoft_driver_service": "Microsoft以外のドライバー / NT Serviceに依存しますか",
}

TEXT_LABELS = {
    "description": "Store説明文",
    "whats_new": "更新内容",
    "features": "主な機能",
    "support_url": "サポートURL",
    "privacy_policy_url": "プライバシーポリシー",
    "certification_notes": "認定担当者向けメモ",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Microsoft Store Auto Upload")
        self.geometry("1060x760")
        self.minsize(940, 680)

        self.kind = tk.StringVar(value="app")
        self.submission_kind = tk.StringVar(value="update")
        self.name = tk.StringVar()
        self.repo = tk.StringVar()
        self.package = tk.StringVar()
        self.images = tk.StringVar()
        self.price = tk.StringVar(value="paid")
        self.price_value = tk.StringVar()
        self.status_text = tk.StringVar(value="入力待ち")
        self.package_status = tk.StringVar(value="未選択")
        self.images_status = tk.StringVar(value="未選択")
        self.security_status = tk.StringVar(value="未確認")
        self.preset_status = tk.StringVar(value="アプリ用固定ルール")
        self.result_summary_text = tk.StringVar(value="未実行")
        self.review_only = tk.BooleanVar(value=True)
        self.ollama_url = tk.StringVar(value="http://127.0.0.1:11434/api/generate")
        self.ollama_model = tk.StringVar(value="qwen3:8b")
        self.github_token = tk.StringVar()
        self.hero_art = tk.StringVar()
        self.trailers: list[TrailerAsset] = []

        self.current_product: ProductInput | None = None
        self._last_kind = self.kind.get()
        self.queue: list[ProductInput] = []
        self.last_report = None

        self._configure_styles()
        self._build()
        self.kind.trace_add("write", lambda *_: self._refresh_preset_status())
        self.submission_kind.trace_add("write", lambda *_: self._refresh_preset_status())
        self._refresh_preset_status()

    def _configure_styles(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Lead.TLabel", font=("Segoe UI", 10))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 9))
        style.configure("Quiet.TButton", padding=(11, 7))
        style.configure("Treeview", rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build(self):
        header = ttk.Frame(self, padding=(20, 14, 20, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Microsoft Store Auto Upload", style="Title.TLabel").pack(side="left")
        tk.Label(
            header,
            text="安全モード / 本番書込 OFF",
            bg="#E8F1FF",
            fg="#174A8B",
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        ttk.Label(
            self,
            text="必要な情報だけ入力してください。選択問題・Store項目は裏側で自動処理します。",
            style="Lead.TLabel",
            padding=(20, 0, 20, 8),
        ).pack(fill="x")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.main_tab = ttk.Frame(self.notebook, padding=18)
        self.queue_tab = ttk.Frame(self.notebook, padding=18)
        self.review_tab = ttk.Frame(self.notebook, padding=18)
        self.notebook.add(self.main_tab, text="アップロード")
        self.notebook.add(self.queue_tab, text="夜間キュー")
        self.notebook.add(self.review_tab, text="要確認")

        self._build_main()
        self._build_queue()
        self._build_review()

        footer = ttk.Frame(self, padding=(20, 4, 20, 12))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_text, font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(footer, text="詳細設定", command=self.open_settings, style="Quiet.TButton").pack(side="right")

    def _build_main(self):
        tab = self.main_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)

        top = ttk.LabelFrame(tab, text=" 製品 ", style="Section.TLabelframe", padding=12)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=0)

        ttk.Label(top, text="種類", width=16).grid(row=0, column=0, sticky="w", pady=5)
        row = ttk.Frame(top)
        row.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(row, text="アプリ", variable=self.kind, value="app").pack(side="left")
        ttk.Radiobutton(row, text="ゲーム", variable=self.kind, value="game").pack(side="left", padx=(18, 0))
        ttk.Label(top, textvariable=self.preset_status, foreground="#1769AA").grid(row=0, column=2, sticky="e", padx=(20,0))

        ttk.Label(top, text="処理", width=16).grid(row=1, column=0, sticky="w", pady=5)
        row = ttk.Frame(top)
        row.grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(row, text="既存製品を更新", variable=self.submission_kind, value="update").pack(side="left")
        ttk.Radiobutton(row, text="新規製品", variable=self.submission_kind, value="new").pack(side="left", padx=(18, 0))

        ttk.Label(top, text="製品名", width=16).grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(top, textvariable=self.name).grid(row=2, column=1, sticky="ew", pady=5)

        files = ttk.LabelFrame(tab, text=" ファイル ", style="Section.TLabelframe", padding=12)
        files.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        files.columnconfigure(1, weight=1)
        self._path_row(files, 0, "MSIX / MSIXUPLOAD", self.package, False, self.package_status)
        self._path_row(files, 1, "商品画像フォルダ", self.images, True, self.images_status)

        security = ttk.LabelFrame(tab, text=" セキュリティ確認（必須） ", style="Section.TLabelframe", padding=12)
        security.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        security.columnconfigure(1, weight=1)
        ttk.Label(
            security,
            text="プライバシー・権限・外部通信などを確認します。AI候補だけでは完了扱いになりません。",
            foreground="#5B6470",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(security, textvariable=self.security_status, font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(security, text="セキュリティ設定を確認…", command=self.open_security_settings, style="Primary.TButton").grid(row=1, column=1, sticky="e", pady=(8, 0))

        body = ttk.LabelFrame(tab, text=" アプリ / ゲームの内容 ", style="Section.TLabelframe", padding=12)
        body.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)
        ttk.Label(
            body,
            text="できること・用途・外部サービス・課金・データ利用など。空欄のStore入力はOllama補完対象です。",
            foreground="#5B6470",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.summary = tk.Text(body, height=8, wrap="word", font=("Segoe UI", 10))
        self.summary.grid(row=1, column=0, sticky="nsew")

        bottom = ttk.Frame(tab)
        bottom.grid(row=4, column=0, sticky="ew")
        ttk.Label(bottom, text="価格").pack(side="left")
        ttk.Radiobutton(bottom, text="有料", value="paid", variable=self.price).pack(side="left", padx=(10, 3))
        ttk.Radiobutton(bottom, text="無料", value="free", variable=self.price).pack(side="left", padx=3)
        ttk.Entry(bottom, textvariable=self.price_value, width=17).pack(side="left", padx=(8, 16))

        ttk.Button(bottom, text="① 自動準備", command=self.prepare, style="Primary.TButton").pack(side="left")
        ttk.Button(bottom, text="② 軽くシミュレーション", command=self.simulate_start, style="Quiet.TButton").pack(side="left", padx=6)
        ttk.Button(bottom, text="③ 夜間キューへ", command=self.add_to_queue, style="Quiet.TButton").pack(side="left")
        self.upload_btn = ttk.Button(bottom, text="アップロード開始", state="disabled", style="Primary.TButton")
        self.upload_btn.pack(side="right")

        links = ttk.Frame(tab)
        links.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(links, text="開始画面:", foreground="#5B6470").pack(side="left")
        ttk.Button(
            links,
            text="Partner Center Apps and games",
            command=lambda: webbrowser.open(PARTNER_CENTER_APPS_GAMES_URL),
        ).pack(side="left", padx=6)
        ttk.Label(
            links,
            text="実画面selector確認完了までは自動書込しません。",
            foreground="#5B6470",
        ).pack(side="right")


    def _refresh_preset_status(self):
        kind=self.kind.get()
        kind_label="アプリ" if kind=="app" else "ゲーム"
        mode_label="既存更新" if self.submission_kind.get()=="update" else "新規"
        self.preset_status.set(f"{kind_label}用固定ルール / {mode_label}")

        if self._last_kind != kind:
            # Product-type-specific answers must never leak between app and game.
            self.current_product=None
            self.security_status.set("未確認")
            if hasattr(self, "review_summary"):
                self.review_summary.configure(text="まだ準備されていません")
            self._last_kind=kind

        # Materialize the fixed preset immediately in memory, not only as a label.
        try:
            p=self._build_product()
            apply_fixed_rules(p)
            self.current_product=p
            self.render_review()
            self.status_text.set(f"{kind_label}用固定ルールを適用済み")
        except Exception:
            self.status_text.set(f"{kind_label}用固定ルールを選択")

    def _build_queue(self):
        top = ttk.Frame(self.queue_tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="夜間キュー", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.queue_summary = ttk.Label(top, text="0件")
        self.queue_summary.pack(side="left", padx=16)
        ttk.Label(top, text="製品単位のHOLD/ERRORは次へ進む", foreground="#5B6470").pack(side="right")

        cols = ("no", "name", "kind", "package", "status")
        self.queue_tree = ttk.Treeview(self.queue_tab, columns=cols, show="headings", height=18)
        for c, text, width in (
            ("no", "#", 42),
            ("name", "製品", 250),
            ("kind", "種類", 85),
            ("package", "パッケージ", 420),
            ("status", "状態", 120),
        ):
            self.queue_tree.heading(c, text=text)
            self.queue_tree.column(c, width=width, anchor="w")
        self.queue_tree.tag_configure("hold", background="#FFF4D6")
        self.queue_tree.tag_configure("ready", background="#EAF5EA")
        self.queue_tree.tag_configure("done", background="#EAF5EA")
        self.queue_tree.tag_configure("error", background="#FDECEC")
        self.queue_tree.tag_configure("unknown", background="#EEF1F5")
        self.queue_tree.pack(fill="both", expand=True)

        summary = ttk.LabelFrame(self.queue_tab, text=" 総合結果 ", style="Section.TLabelframe", padding=10)
        summary.pack(fill="x", pady=(10,0))
        ttk.Label(summary, textvariable=self.result_summary_text, font=("Segoe UI", 12, "bold")).pack(side="left")

        buttons = ttk.Frame(self.queue_tab)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="選択を削除", command=self.remove_queue_item).pack(side="left")
        ttk.Button(buttons, text="保存", command=self.save_queue).pack(side="left", padx=6)
        ttk.Button(buttons, text="読み込む", command=self.load_queue).pack(side="left")
        ttk.Button(buttons, text="全体事前確認", command=self.run_preflight, style="Primary.TButton").pack(side="right")

        self.queue_report = tk.Text(self.queue_tab, height=10, wrap="word", font=("Consolas", 9))
        self.queue_report.pack(fill="x")
        self.queue_report.insert("end", "ここではMicrosoftへ書き込まず、全製品の進行可否だけ確認します。\n")

    def _build_review(self):
        top = ttk.Frame(self.review_tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="要確認", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.review_summary = ttk.Label(top, text="まだ準備されていません")
        self.review_summary.pack(side="left", padx=16)
        ttk.Checkbutton(top, text="要確認だけ", variable=self.review_only, command=self.render_review).pack(side="right")

        ttk.Label(
            self.review_tab,
            text="通常は触りません。必要な行だけダブルクリックして修正します。選択問題は既定候補からのみ変更できます。",
            foreground="#5B6470",
        ).pack(fill="x", pady=(0, 8))

        cols = ("label", "mode", "value", "source", "confidence")
        self.review_tree = ttk.Treeview(self.review_tab, columns=cols, show="headings", height=18)
        for c, text, width in (
            ("label", "Store項目", 230),
            ("mode", "処理", 110),
            ("value", "値", 360),
            ("source", "根拠", 120),
            ("confidence", "確信度", 80),
        ):
            self.review_tree.heading(c, text=text)
            self.review_tree.column(c, width=width, anchor="w")
        self.review_tree.tag_configure("review", background="#FFF4D6")
        self.review_tree.tag_configure("fixed", background="#EAF5EA")
        self.review_tree.pack(fill="both", expand=True)
        self.review_tree.bind("<Double-1>", self.edit_selected_field)

        self.rationale = tk.Text(self.review_tab, height=5, wrap="word", state="disabled")
        self.rationale.pack(fill="x", pady=(8, 0))
        self.review_tree.bind("<<TreeviewSelect>>", self.show_rationale)

    def _path_row(self, parent, row, label, var, folder, status_var):
        ttk.Label(parent, text=label, width=16).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=6, padx=6)
        ttk.Button(parent, text="参照", command=lambda: self.pick(var, folder, status_var)).grid(row=row, column=2)
        ttk.Label(parent, textvariable=status_var, width=10).grid(row=row, column=3, padx=(8, 0))

    def pick(self, var, folder, status_var):
        if folder:
            selected = filedialog.askdirectory()
        else:
            selected = filedialog.askopenfilename(
                filetypes=[
                    ("Store packages", "*.msix *.msixupload *.msixbundle *.appx *.appxupload *.appxbundle"),
                    ("All files", "*.*"),
                ]
            )
        if selected:
            var.set(selected)
            status_var.set("選択済み" if Path(selected).exists() else "要確認")
            if var is self.package:
                self.security_status.set("再確認が必要")
                if self.current_product:
                    self.current_product.security_package_sha256=""
                    for key in SECURITY_CONFIRM_KEYS:
                        if key in self.current_product.fields:
                            self.current_product.fields[key].confirmed=False

    def _build_product(self):
        p = ProductInput(
            self.kind.get(),
            self.name.get().strip(),
            self.summary.get("1.0", "end").strip(),
            self.repo.get().strip(),
            self.package.get().strip(),
            self.images.get().strip(),
            price_mode=self.price.get(),
            price_value=self.price_value.get().strip(),
            trailers=[TrailerAsset(t.video_path,t.title,t.thumbnail_path) for t in self.trailers],
            hero_art_path=self.hero_art.get().strip(),
            security_package_sha256=self.current_product.security_package_sha256 if self.current_product and self.current_product.product_type == self.kind.get() else "",
            submission_kind=self.submission_kind.get(),
        )
        if self.current_product and self.current_product.product_type == p.product_type:
            p.fields = {k: FieldValue(**{
                "key": v.key,
                "mode": v.mode,
                "value": v.value,
                "source": v.source,
                "confidence": v.confidence,
                "rationale": v.rationale,
                "confirmed": v.confirmed,
            }) for k, v in self.current_product.fields.items()}
        for f in fields_for(p.product_type):
            p.fields.setdefault(f.key, FieldValue(f.key, ValueMode.OLLAMA, None, "pending"))
        p.fields.setdefault("description", FieldValue("description", ValueMode.OLLAMA, None, "pending"))
        return p

    def prepare(self, show_review=True):
        p = self._build_product()
        apply_fixed_rules(p)
        self.current_product = p
        findings = validate_product(p)
        holds = sum(1 for f in findings if f.severity in {Severity.HOLD, Severity.FATAL})
        self.status_text.set(f"自動準備完了 / 要確認 {holds}件" if holds else "自動準備完了 / 事前チェックOK")
        self.render_review()
        if show_review:
            self.notebook.select(self.review_tab)
        return p

    def simulate_start(self):
        p = self.prepare(show_review=False)
        sim = simulate_overview_start(
            p.product_name,
            self.submission_kind.get(),
            visible_products=(),
        )
        lines = [
            "Partner Center開始シミュレーション",
            "",
            f"開始URL: {sim.start_url}",
            f"対象: {sim.product_name or '(未入力)'}",
            f"処理: {'新規' if sim.mode == 'new' else '既存更新'}",
            "",
            *[f"✓ {x}" for x in sim.actions],
        ]
        if sim.safe_to_continue:
            lines += ["", "結果: ここまでは安全に進行可能。実画面では製品名の完全一致を確認してから開きます。"]
        else:
            lines += ["", f"結果: HOLD — {sim.hold_reason}"]
        messagebox.showinfo("軽いシミュレーション", "\n".join(lines))
        self.status_text.set("開始画面のシミュレーション完了")

    def ollama_fill(self):
        p = self.prepare(show_review=False)
        if not p.app_summary.strip():
            messagebox.showwarning("内容が必要です", "アプリ / ゲームの内容を入力してください。")
            return
        settings = self._settings_values()
        self.status_text.set("Ollama補完中…")

        def worker():
            try:
                ctx = fetch_context(p.repository, settings["token"]) if settings["token"] and p.repository else ""
                complete_product(p, ctx, url=settings["url"], model=settings["model"])
                self.after(0, lambda: self._ollama_done(p, None))
            except Exception as exc:
                self.after(0, lambda: self._ollama_done(p, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _ollama_done(self, p, error):
        if error:
            self.status_text.set("Ollama補完エラー")
            messagebox.showerror("Ollama補完", str(error))
            return
        self.current_product = p
        self.render_review()
        self.status_text.set("Ollama補完完了")
        self.notebook.select(self.review_tab)

    def add_to_queue(self):
        p = self.prepare(show_review=False)
        if not p.product_name:
            messagebox.showwarning("製品名", "製品名を入力してください。")
            return

        new_key=(p.store_product_id.strip().casefold() if p.store_product_id.strip() else f"{p.product_type}:{p.product_name.strip().casefold()}")
        for existing in self.queue:
            existing_key=(existing.store_product_id.strip().casefold() if existing.store_product_id.strip() else f"{existing.product_type}:{existing.product_name.strip().casefold()}")
            if existing_key==new_key:
                messagebox.showwarning("重複", "同じ製品がすでに夜間キューにあります。")
                return

        self.queue.append(ProductInput.from_dict(p.to_dict()))
        self.render_queue()
        self.notebook.select(self.queue_tab)
        self.status_text.set(f"夜間キューへ追加 / {len(self.queue)}件")

    def render_queue(self):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        for i, p in enumerate(self.queue, 1):
            findings = validate_product(p)
            hold = any(f.severity in {Severity.HOLD, Severity.FATAL} for f in findings)
            self.queue_tree.insert(
                "",
                "end",
                iid=str(i - 1),
                values=(i, p.product_name, "ゲーム" if p.product_type == "game" else "アプリ", Path(p.package_path).name if p.package_path else "未選択", "要確認" if hold else "準備OK"),
                tags=("hold" if hold else "ready",),
            )
        self.queue_summary.configure(text=f"{len(self.queue)}件")

    def remove_queue_item(self):
        selected = self.queue_tree.selection()
        for index in sorted((int(x) for x in selected), reverse=True):
            if 0 <= index < len(self.queue):
                self.queue.pop(index)
        self.render_queue()

    def save_queue(self):
        if not self.queue:
            messagebox.showinfo("夜間キュー", "保存する製品がありません。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="store-night-queue.json")
        if path:
            Path(path).write_text(json.dumps([p.to_dict() for p in self.queue], ensure_ascii=False, indent=2), encoding="utf-8")

    def load_queue(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.queue = [ProductInput.from_dict(x) for x in json.loads(Path(path).read_text(encoding="utf-8"))]
            self.render_queue()
        except Exception as exc:
            messagebox.showerror("夜間キュー", str(exc))

    def run_preflight(self):
        if not self.queue:
            messagebox.showinfo("夜間キュー", "事前確認する製品がありません。")
            return
        self.last_report = run_queue(self.queue, dryrun_uploader)
        text = render_markdown(self.last_report)
        self.queue_report.delete("1.0", "end")
        self.queue_report.insert("1.0", text)

        # Reflect the actual result on each queued row.
        label_map={"DONE":"成功","DRAFT_SAVED":"下書き保存","HOLD":"HOLD","UNKNOWN":"不明","ERROR":"失敗","AUTH_ERROR":"認証失敗"}
        tag_map={"DONE":"done","DRAFT_SAVED":"done","HOLD":"hold","UNKNOWN":"unknown","ERROR":"error","AUTH_ERROR":"error"}
        for index,result in enumerate(self.last_report.results):
            iid=str(index)
            if not self.queue_tree.exists(iid):
                continue
            values=list(self.queue_tree.item(iid,"values"))
            if len(values)>=5:
                values[4]=label_map.get(result.status,result.status)
            self.queue_tree.item(iid,values=values,tags=(tag_map.get(result.status,"unknown"),))

        summary=self.last_report.summary()
        if summary["mode"]=="single":
            self.result_summary_text.set(f"実行結果: {summary['label']}")
            self.status_text.set(f"1件の処理結果 / {summary['label']}")
        else:
            self.result_summary_text.set(
                f"総件数 {summary['total']}件   下書き保存 {summary['draft_saved']}件   Dry Run成功 {summary['dry_run_done']}件   HOLD {summary['hold']}件   "
                f"失敗 {summary['failed']}件   不明 {summary['unknown']}件"
            )
            self.status_text.set(
                f"総合結果 / 下書き保存 {summary['draft_saved']}件・Dry Run成功 {summary['dry_run_done']}件・HOLD {summary['hold']}件・"
                f"失敗 {summary['failed']}件・不明 {summary['unknown']}件"
            )

    def render_review(self):
        for item in self.review_tree.get_children():
            self.review_tree.delete(item)
        p = self.current_product
        if not p:
            self.review_summary.configure(text="まだ準備されていません")
            return
        defs = {f.key: f for f in fields_for(p.product_type)}
        counts = {m: 0 for m in ValueMode}
        for key, fv in sorted(p.fields.items()):
            counts[fv.mode] += 1
            if self.review_only.get() and fv.mode != ValueMode.REVIEW:
                continue
            label = defs[key].label if key in defs else TEXT_LABELS.get(key, key)
            value = ", ".join(map(str, fv.value)) if isinstance(fv.value, list) else ("" if fv.value is None else str(fv.value))
            confidence = "" if fv.confidence is None else f"{fv.confidence:.0%}"
            tag = "review" if fv.mode == ValueMode.REVIEW else ("fixed" if fv.mode == ValueMode.FIXED else "")
            self.review_tree.insert("", "end", iid=key, values=(label, MODE_LABELS[fv.mode], value, fv.source or "—", confidence), tags=(tag,) if tag else ())
        self.review_summary.configure(text=f"要確認 {counts[ValueMode.REVIEW]} / AI {counts[ValueMode.OLLAMA]} / 固定 {counts[ValueMode.FIXED]}")

    def show_rationale(self, _event=None):
        selected = self.review_tree.selection()
        text = ""
        if selected and self.current_product:
            fv = self.current_product.fields.get(selected[0])
            if fv:
                text = fv.rationale or "補足理由はありません。"
        self.rationale.configure(state="normal")
        self.rationale.delete("1.0", "end")
        self.rationale.insert("1.0", text)
        self.rationale.configure(state="disabled")

    def edit_selected_field(self, _event=None):
        selected = self.review_tree.selection()
        if not selected or not self.current_product:
            return
        key = selected[0]
        fv = self.current_product.fields[key]
        defs = {f.key: f for f in fields_for(self.current_product.product_type)}
        field_def = defs.get(key)

        win = tk.Toplevel(self)
        win.title("項目を修正")
        win.geometry("500x400")
        win.transient(self)
        win.grab_set()
        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)

        label = field_def.label if field_def else TEXT_LABELS.get(key, key)
        ttk.Label(body, text=label, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(body, text="選択問題はMicrosoft側の候補からだけ選択できます。", foreground="#5B6470").pack(anchor="w", pady=(2, 12))

        mode_var = tk.StringVar(value=MODE_LABELS[fv.mode])
        ttk.Combobox(body, textvariable=mode_var, state="readonly", values=tuple(MODE_LABELS.values())).pack(fill="x", pady=(0, 12))

        if field_def and field_def.max_selections == 1:
            value_var = tk.StringVar(value="" if fv.value is None else str(fv.value))
            widget = ttk.Combobox(body, textvariable=value_var, state="readonly", values=field_def.choices)
            widget.pack(fill="x")
            read_value = lambda: value_var.get() or None
        elif field_def and field_def.max_selections > 1:
            widget = tk.Listbox(body, selectmode="multiple", exportselection=False, height=10)
            for option in field_def.choices:
                widget.insert("end", option)
            current = fv.value if isinstance(fv.value, list) else []
            for i, option in enumerate(field_def.choices):
                if option in current:
                    widget.selection_set(i)
            widget.pack(fill="both", expand=True)
            read_value = lambda: [widget.get(i) for i in widget.curselection()]
        else:
            widget = tk.Text(body, height=9, wrap="word")
            widget.insert("1.0", "" if fv.value is None else str(fv.value))
            widget.pack(fill="both", expand=True)
            read_value = lambda: widget.get("1.0", "end").strip() or None

        def save():
            mode = LABEL_MODES[mode_var.get()]
            value = None if mode in {ValueMode.BLANK, ValueMode.OLLAMA} else read_value()
            self.current_product.fields[key] = FieldValue(
                key,
                mode,
                value,
                "manual-ui" if mode == ValueMode.MANUAL else fv.source,
                1.0 if mode == ValueMode.MANUAL else fv.confidence,
                "ユーザーがUIで変更" if mode == ValueMode.MANUAL else fv.rationale,
            )
            self.render_review()
            win.destroy()

        ttk.Button(body, text="反映", command=save, style="Primary.TButton").pack(anchor="e", pady=(10, 0))



    def open_security_settings(self):
        if not self.package.get().strip() or not Path(self.package.get().strip()).is_file():
            messagebox.showwarning("セキュリティ確認", "先にMSIX / MSIXUPLOADを選択してください。")
            return

        p=self._build_product()
        win=tk.Toplevel(self)
        win.title("セキュリティ確認（必須）")
        win.geometry("760x650")
        win.transient(self)
        win.grab_set()

        body=ttk.Frame(win,padding=18)
        body.pack(fill="both",expand=True)
        ttk.Label(body,text="セキュリティ・プライバシー確認",font=("Segoe UI",14,"bold")).pack(anchor="w")
        ttk.Label(
            body,
            text="すべて必須です。AIが候補を作成していても、ここで確認済みにしない限りアップロード準備完了にはなりません。",
            foreground="#5B6470",
            wraplength=700,
        ).pack(anchor="w",pady=(3,12))

        form=ttk.Frame(body)
        form.pack(fill="both",expand=True)
        form.columnconfigure(0,weight=1)
        values={}
        for row,key in enumerate(SECURITY_CONFIRM_KEYS):
            ttk.Label(form,text=SECURITY_LABELS[key],wraplength=500).grid(row=row,column=0,sticky="w",pady=5)
            current=p.fields.get(key)
            var=tk.StringVar(value=str(current.value) if current and current.value in {"yes","no"} else "")
            values[key]=var
            ttk.Combobox(form,textvariable=var,state="readonly",values=("yes","no"),width=12).grid(row=row,column=1,sticky="e",pady=5)

        privacy_var=tk.StringVar(value=str(p.fields.get("privacy_policy_url").value) if p.fields.get("privacy_policy_url") and p.fields.get("privacy_policy_url").value else "")
        privacy_row=len(SECURITY_CONFIRM_KEYS)
        ttk.Label(form,text="プライバシーポリシーURL（個人情報=Yesの場合必須）",wraplength=500).grid(row=privacy_row,column=0,sticky="w",pady=5)
        ttk.Entry(form,textvariable=privacy_var,width=38).grid(row=privacy_row,column=1,sticky="e",pady=5)

        ttk.Separator(body).pack(fill="x",pady=10)
        ttk.Label(
            body,
            text="この確認は現在選択されているパッケージのSHA-256に紐づきます。MSIXを変更すると再確認が必要です。",
            foreground="#5B6470",
        ).pack(anchor="w")

        def save():
            missing=[SECURITY_LABELS[k] for k,v in values.items() if v.get() not in {"yes","no"}]
            if missing:
                messagebox.showwarning("未回答","すべてのセキュリティ項目を回答してください。",parent=win)
                return
            if values["collects_personal_data"].get()=="yes" and not privacy_var.get().strip():
                messagebox.showwarning("プライバシーポリシー","個人情報を扱う場合はURLが必要です。",parent=win)
                return
            for key,var in values.items():
                p.fields[key]=FieldValue(
                    key=key,
                    mode=ValueMode.MANUAL,
                    value=var.get(),
                    source="security-ui",
                    confidence=1.0,
                    rationale="必須セキュリティ確認",
                    confirmed=True,
                )
            if privacy_var.get().strip():
                p.fields["privacy_policy_url"]=FieldValue(
                    key="privacy_policy_url",
                    mode=ValueMode.MANUAL,
                    value=privacy_var.get().strip(),
                    source="security-ui",
                    confidence=1.0,
                    rationale="必須セキュリティ確認",
                    confirmed=True,
                )
            p.security_package_sha256=file_sha256(p.package_path)
            self.current_product=p
            self.security_status.set("確認済み")
            self.render_review()
            win.destroy()

        ttk.Button(body,text="確認済みにする",command=save,style="Primary.TButton").pack(anchor="e",pady=(12,0))

    def open_trailer_settings(self):
        win = tk.Toplevel(self)
        win.title("動画設定（任意）")
        win.geometry("760x500")
        win.transient(self)
        win.grab_set()

        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="動画は任意です", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            body,
            text="何も追加しなければStoreへ動画を送りません。必要な製品だけ追加してください。",
            foreground="#5B6470",
        ).pack(anchor="w", pady=(2, 10))

        cols=("video","title","thumb")
        tree=ttk.Treeview(body,columns=cols,show="headings",height=10)
        for c,text,width in (("video","動画",250),("title","タイトル",220),("thumb","サムネイル",220)):
            tree.heading(c,text=text)
            tree.column(c,width=width,anchor="w")
        tree.pack(fill="both",expand=True)

        def refresh():
            for x in tree.get_children():
                tree.delete(x)
            for i,t in enumerate(self.trailers):
                tree.insert("", "end", iid=str(i), values=(Path(t.video_path).name if t.video_path else "", t.title, Path(t.thumbnail_path).name if t.thumbnail_path else ""))

        def add():
            video=filedialog.askopenfilename(parent=win,filetypes=[("Trailer video","*.mp4 *.mov"),("All files","*.*")])
            if not video:
                return
            thumb=filedialog.askopenfilename(parent=win,title="サムネイルPNGを選択",filetypes=[("PNG","*.png"),("All files","*.*")])
            if not thumb:
                return
            title_win=tk.Toplevel(win)
            title_win.title("動画タイトル")
            title_win.geometry("420x150")
            title_win.transient(win)
            title_win.grab_set()
            frm=ttk.Frame(title_win,padding=14)
            frm.pack(fill="both",expand=True)
            title_var=tk.StringVar(value=Path(video).stem)
            ttk.Label(frm,text="タイトル").pack(anchor="w")
            ttk.Entry(frm,textvariable=title_var).pack(fill="x",pady=6)
            def save_title():
                if not title_var.get().strip():
                    messagebox.showwarning("動画","タイトルを入力してください。",parent=title_win)
                    return
                self.trailers.append(TrailerAsset(video,title_var.get().strip(),thumb))
                title_win.destroy()
                refresh()
            ttk.Button(frm,text="追加",command=save_title,style="Primary.TButton").pack(anchor="e",pady=6)

        def remove():
            indexes=sorted((int(x) for x in tree.selection()),reverse=True)
            for i in indexes:
                if 0<=i<len(self.trailers):
                    self.trailers.pop(i)
            refresh()

        buttons=ttk.Frame(body)
        buttons.pack(fill="x",pady=8)
        ttk.Button(buttons,text="動画を追加",command=add).pack(side="left")
        ttk.Button(buttons,text="選択を削除",command=remove).pack(side="left",padx=6)

        hero=ttk.LabelFrame(body,text="ゲームで動画を使う場合のみ",padding=10)
        hero.pack(fill="x",pady=(8,0))
        hero.columnconfigure(1,weight=1)
        ttk.Label(hero,text="16:9 Super hero art").grid(row=0,column=0,sticky="w")
        ttk.Entry(hero,textvariable=self.hero_art).grid(row=0,column=1,sticky="ew",padx=6)
        ttk.Button(hero,text="参照",command=lambda:self._pick_hero(win)).grid(row=0,column=2)
        ttk.Label(hero,text="動画を使わない場合は空欄で構いません。",foreground="#5B6470").grid(row=1,column=0,columnspan=3,sticky="w",pady=(5,0))

        def close():
            if hasattr(self,"media_status"):
                self.media_status.configure(text=f"{len(self.trailers)}本設定" if self.trailers else "使用しない")
            win.destroy()
        ttk.Button(body,text="完了",command=close,style="Primary.TButton").pack(anchor="e",pady=(10,0))
        refresh()

    def _pick_hero(self,parent):
        path=filedialog.askopenfilename(parent=parent,filetypes=[("PNG","*.png"),("All files","*.*")])
        if path:
            self.hero_art.set(path)

    def _settings_values(self):
        return {"url": self.ollama_url.get().strip(), "model": self.ollama_model.get().strip() or "qwen3:8b", "token": self.github_token.get().strip()}

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("詳細設定")
        win.geometry("620x300")
        win.transient(self)
        body = ttk.Frame(win, padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="GitHubリポジトリ").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(body, textvariable=self.repo).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(body, text="Ollama URL").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(body, textvariable=self.ollama_url).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(body, text="Ollama model").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(body, textvariable=self.ollama_model).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(body, text="GitHub token").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(body, textvariable=self.github_token, show="•").grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Label(body, text="動画（任意）").grid(row=4, column=0, sticky="w", pady=6)
        media_row = ttk.Frame(body)
        media_row.grid(row=4, column=1, sticky="ew", pady=6)
        self.media_status = ttk.Label(media_row, text=f"{len(self.trailers)}本設定" if self.trailers else "使用しない")
        self.media_status.pack(side="left")
        ttk.Button(media_row, text="動画設定…", command=self.open_trailer_settings).pack(side="right")
        ttk.Label(body, text="動画は完全に任意です。未設定なら動画関連のチェックもアップロードも行いません。", foreground="#5B6470").grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(body, text="トークンは保存せず、GitHub読取だけに使用します。Ollamaには渡しません。", foreground="#5B6470").grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(body, text="Ollamaで現在の空欄を補完", command=lambda: (win.destroy(), self.ollama_fill()), style="Primary.TButton").grid(row=7, column=1, sticky="e", pady=(16, 0))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
