from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import (
    FieldValue,
    ProductInput,
    Severity,
    ValueMode,
    apply_fixed_rules,
    fields_for,
    render_markdown,
    run_queue,
    validate_product,
)
from .github_context import fetch_context
from .ollama import complete_product
from .partner_center import dryrun_uploader

MODE_LABELS = {
    ValueMode.FIXED: "固定（自動）",
    ValueMode.OLLAMA: "AI補完",
    ValueMode.MANUAL: "手動",
    ValueMode.BLANK: "意図的に空欄",
    ValueMode.REVIEW: "要確認",
}
LABEL_MODES = {v: k for k, v in MODE_LABELS.items()}
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
        self.title("Microsoft Store Submission Manager")
        self.geometry("1180x780")
        self.minsize(980, 680)

        self.kind = tk.StringVar(value="app")
        self.name = tk.StringVar()
        self.repo = tk.StringVar()
        self.package = tk.StringVar()
        self.images = tk.StringVar()
        self.price = tk.StringVar(value="paid")
        self.price_value = tk.StringVar()
        self.status_text = tk.StringVar(value="準備中")
        self.package_status = tk.StringVar(value="未選択")
        self.images_status = tk.StringVar(value="未選択")
        self.review_only = tk.BooleanVar(value=False)

        self.ollama_url = tk.StringVar(value="http://127.0.0.1:11434/api/generate")
        self.ollama_model = tk.StringVar(value="qwen3:8b")
        self.github_token = tk.StringVar()

        self.current_product: ProductInput | None = None
        self.queue: list[ProductInput] = []
        self.last_report = None

        self._configure_styles()
        self._build()
        self.kind.trace_add("write", lambda *_: self._refresh_kind_hint())
        self._refresh_kind_hint()

    def _configure_styles(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Quiet.TButton", padding=(10, 6))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build(self):
        header = ttk.Frame(self, padding=(18, 14, 18, 6))
        header.pack(fill="x")
        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Microsoft Store Submission Manager", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="製品内容とファイルを指定すると、選択問題とStore入力を裏側で準備します。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        self.safety_badge = tk.Label(
            header,
            text="安全モード  本番書込 OFF",
            bg="#E8F1FF",
            fg="#174A8B",
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        )
        self.safety_badge.pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(4, 8))

        self.input_tab = ttk.Frame(self.notebook, padding=16)
        self.review_tab = ttk.Frame(self.notebook, padding=16)
        self.queue_tab = ttk.Frame(self.notebook, padding=16)
        self.result_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.input_tab, text="1  製品とファイル")
        self.notebook.add(self.review_tab, text="2  自動入力・要確認")
        self.notebook.add(self.queue_tab, text="3  夜間キュー")
        self.notebook.add(self.result_tab, text="4  結果・設定")

        self._build_input_tab()
        self._build_review_tab()
        self._build_queue_tab()
        self._build_result_tab()

        footer = ttk.Frame(self, padding=(18, 4, 18, 10))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_text, style="Status.TLabel").pack(side="left")
        ttk.Label(
            footer,
            text="本番アップロードはPartner Center実画面の対応確認後に有効化",
        ).pack(side="right")

    def _build_input_tab(self):
        tab = self.input_tab
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        product = ttk.LabelFrame(tab, text=" 1. 製品 ", style="Section.TLabelframe", padding=12)
        product.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=(0, 10))
        product.columnconfigure(1, weight=1)

        ttk.Label(product, text="種類").grid(row=0, column=0, sticky="w", pady=5)
        kind_row = ttk.Frame(product)
        kind_row.grid(row=0, column=1, sticky="w", pady=5)
        ttk.Radiobutton(kind_row, text="一般アプリ", value="app", variable=self.kind).pack(side="left")
        ttk.Radiobutton(kind_row, text="ゲーム", value="game", variable=self.kind).pack(side="left", padx=(16, 0))

        ttk.Label(product, text="製品名").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(product, textvariable=self.name).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(product, text="GitHub").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(product, textvariable=self.repo).grid(row=2, column=1, sticky="ew", pady=5)
        self.kind_hint = ttk.Label(product, text="", foreground="#5B6470")
        self.kind_hint.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        package = ttk.LabelFrame(tab, text=" 2. パッケージ・画像 ", style="Section.TLabelframe", padding=12)
        package.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 10))
        package.columnconfigure(1, weight=1)
        self._path_row(package, 0, "MSIX / MSIXUPLOAD", self.package, False, self.package_status)
        self._path_row(package, 1, "商品画像フォルダ", self.images, True, self.images_status)

        content = ttk.LabelFrame(tab, text=" 3. アプリ / ゲームの内容 ", style="Section.TLabelframe", padding=12)
        content.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)
        ttk.Label(
            content,
            text="できること・使い方・外部サービス・課金・データ利用などを書いてください。空欄のStore項目はここからAIが補完します。",
            foreground="#5B6470",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.summary = tk.Text(content, height=9, wrap="word", font=("Segoe UI", 10))
        self.summary.grid(row=1, column=0, sticky="nsew")

        sale = ttk.LabelFrame(tab, text=" 4. 販売設定 ", style="Section.TLabelframe", padding=12)
        sale.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(sale, text="価格").pack(side="left")
        ttk.Radiobutton(sale, text="有料", value="paid", variable=self.price).pack(side="left", padx=(14, 4))
        ttk.Radiobutton(sale, text="無料", value="free", variable=self.price).pack(side="left", padx=4)
        ttk.Label(sale, text="希望価格 / メモ").pack(side="left", padx=(24, 6))
        ttk.Entry(sale, textvariable=self.price_value, width=24).pack(side="left")

        actions = ttk.Frame(tab)
        actions.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.prepare_btn = ttk.Button(actions, text="自動準備", command=self.prepare, style="Primary.TButton")
        self.prepare_btn.pack(side="left")
        self.ollama_btn = ttk.Button(actions, text="Ollamaで空欄を補完", command=self.ollama_fill, style="Quiet.TButton")
        self.ollama_btn.pack(side="left", padx=8)
        ttk.Button(actions, text="夜間キューへ追加", command=self.add_to_queue, style="Quiet.TButton").pack(side="left")
        self.upload_btn = ttk.Button(actions, text="下書きアップロード", state="disabled", style="Primary.TButton")
        self.upload_btn.pack(side="right")

    def _build_review_tab(self):
        top = ttk.Frame(self.review_tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="自動入力結果", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.review_summary = ttk.Label(top, text="まだ準備されていません")
        self.review_summary.pack(side="left", padx=16)
        ttk.Checkbutton(
            top,
            text="要確認だけ表示",
            variable=self.review_only,
            command=self.render_review,
        ).pack(side="right")

        ttk.Label(
            self.review_tab,
            text="普段は触る必要はありません。修正したい行だけダブルクリックしてください。選択項目はMicrosoft側の候補以外を入力できません。",
            foreground="#5B6470",
        ).pack(fill="x", pady=(0, 8))

        cols = ("label", "mode", "value", "source", "confidence")
        self.review_tree = ttk.Treeview(self.review_tab, columns=cols, show="headings", height=18)
        headings = {
            "label": "Store項目",
            "mode": "処理",
            "value": "値",
            "source": "根拠",
            "confidence": "確信度",
        }
        widths = {"label": 230, "mode": 110, "value": 360, "source": 120, "confidence": 80}
        for c in cols:
            self.review_tree.heading(c, text=headings[c])
            self.review_tree.column(c, width=widths[c], anchor="w")
        self.review_tree.tag_configure("review", background="#FFF4D6")
        self.review_tree.tag_configure("fixed", background="#EAF5EA")
        self.review_tree.pack(fill="both", expand=True)
        self.review_tree.bind("<Double-1>", self.edit_selected_field)

        self.rationale = tk.Text(self.review_tab, height=5, wrap="word", state="disabled")
        self.rationale.pack(fill="x", pady=(8, 0))
        self.review_tree.bind("<<TreeviewSelect>>", self.show_rationale)

    def _build_queue_tab(self):
        top = ttk.Frame(self.queue_tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="夜間処理キュー", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.queue_summary = ttk.Label(top, text="0件")
        self.queue_summary.pack(side="left", padx=16)
        ttk.Label(
            top,
            text="HOLD / ERRORは記録して次へ進む",
            foreground="#5B6470",
        ).pack(side="right")

        cols = ("no", "name", "kind", "package", "status")
        self.queue_tree = ttk.Treeview(self.queue_tab, columns=cols, show="headings", height=18)
        for c, text, width in (
            ("no", "#", 45),
            ("name", "製品", 250),
            ("kind", "種類", 90),
            ("package", "パッケージ", 440),
            ("status", "事前状態", 120),
        ):
            self.queue_tree.heading(c, text=text)
            self.queue_tree.column(c, width=width, anchor="w")
        self.queue_tree.tag_configure("hold", background="#FFF4D6")
        self.queue_tree.tag_configure("ready", background="#EAF5EA")
        self.queue_tree.pack(fill="both", expand=True)

        buttons = ttk.Frame(self.queue_tab)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="現在の製品を追加", command=self.add_to_queue).pack(side="left")
        ttk.Button(buttons, text="選択した製品を削除", command=self.remove_queue_item).pack(side="left", padx=6)
        ttk.Button(buttons, text="キューを保存", command=self.save_queue).pack(side="left", padx=6)
        ttk.Button(buttons, text="キューを読み込む", command=self.load_queue).pack(side="left", padx=6)
        ttk.Button(
            buttons,
            text="夜間処理を事前確認",
            command=self.run_preflight,
            style="Primary.TButton",
        ).pack(side="right")

        ttk.Label(
            self.queue_tab,
            text="ここでの事前確認はMicrosoftへ書き込みません。実アップロードは実機マッピング完了後に同じキューを使用します。",
            foreground="#5B6470",
        ).pack(anchor="w")

    def _build_result_tab(self):
        status = ttk.LabelFrame(self.result_tab, text=" 実行結果 ", style="Section.TLabelframe", padding=12)
        status.pack(fill="both", expand=True)
        self.result_text = tk.Text(status, wrap="word", font=("Consolas", 9))
        self.result_text.pack(fill="both", expand=True)
        self.result_text.insert(
            "end",
            "まだ結果はありません。\n「夜間キュー」から事前確認を実行すると、DONE / HOLD / UNKNOWN / ERRORをここに表示します。\n",
        )

        settings = ttk.LabelFrame(self.result_tab, text=" AI・GitHub設定 ", style="Section.TLabelframe", padding=12)
        settings.pack(fill="x", pady=(10, 0))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="Ollama URL").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(settings, textvariable=self.ollama_url).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(settings, text="Ollama model").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(settings, textvariable=self.ollama_model).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(settings, text="GitHub token").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(settings, textvariable=self.github_token, show="•").grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(
            settings,
            text="トークンは保存せず、GitHub読取にだけ使用します。Ollamaには渡しません。",
            foreground="#5B6470",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        buttons = ttk.Frame(self.result_tab)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="結果をMarkdown保存", command=self.save_report).pack(side="right")

    def _path_row(self, parent, row, label, var, folder, status_var):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=6, padx=6)
        ttk.Button(
            parent,
            text="参照",
            command=lambda: self.pick(var, folder, status_var),
        ).grid(row=row, column=2, pady=6)
        ttk.Label(parent, textvariable=status_var, width=10).grid(row=row, column=3, sticky="e", padx=(8, 0))

    def _refresh_kind_hint(self):
        if self.kind.get() == "game":
            text = "ゲーム：ジャンル・オンライン要素・IARC関連は裏側で処理し、根拠不足だけ要確認に残します。"
        else:
            text = "アプリ：カテゴリ・権限・データ利用などを裏側で処理し、根拠不足だけ要確認に残します。"
        if hasattr(self, "kind_hint"):
            self.kind_hint.configure(text=text)

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
            p = Path(selected)
            status_var.set("選択済み" if p.exists() else "要確認")

    def _build_product(self) -> ProductInput:
        fields = {}
        if self.current_product:
            fields = {
                k: FieldValue(
                    key=v.key,
                    mode=v.mode,
                    value=v.value,
                    source=v.source,
                    confidence=v.confidence,
                    rationale=v.rationale,
                )
                for k, v in self.current_product.fields.items()
            }
        p = ProductInput(
            self.kind.get(),
            self.name.get().strip(),
            self.summary.get("1.0", "end").strip(),
            self.repo.get().strip(),
            self.package.get().strip(),
            self.images.get().strip(),
            price_mode=self.price.get(),
            price_value=self.price_value.get().strip(),
            fields=fields,
        )
        for f in fields_for(p.product_type):
            p.fields.setdefault(f.key, FieldValue(f.key, ValueMode.OLLAMA, None, "pending"))
        p.fields.setdefault("description", FieldValue("description", ValueMode.OLLAMA, None, "pending"))
        return p

    def prepare(self, show_message=True):
        p = self._build_product()
        apply_fixed_rules(p)
        self.current_product = p
        findings = validate_product(p)
        hold_count = sum(1 for f in findings if f.severity in {Severity.HOLD, Severity.FATAL})
        self.status_text.set(
            f"自動準備完了 — 要確認 {hold_count}件" if hold_count else "自動準備完了 — 事前チェックOK"
        )
        self.render_review()
        if show_message:
            self.notebook.select(self.review_tab)
        return p

    def ollama_fill(self):
        p = self.prepare(show_message=False)
        if not p.app_summary.strip():
            messagebox.showwarning("内容が必要です", "アプリ / ゲームの内容を入力してください。")
            return

        self.status_text.set("Ollama補完中…")
        self.ollama_btn.configure(state="disabled")
        token = self.github_token.get().strip()
        model = self.ollama_model.get().strip() or "qwen3:8b"
        url = self.ollama_url.get().strip()

        def worker():
            try:
                ctx = fetch_context(p.repository, token) if token and p.repository else ""
                complete_product(p, ctx, url=url, model=model)
                self.after(0, lambda: self._ollama_done(p, None))
            except Exception as exc:
                self.after(0, lambda: self._ollama_done(p, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _ollama_done(self, p, error):
        self.ollama_btn.configure(state="normal")
        if error:
            self.status_text.set("Ollama補完エラー")
            messagebox.showerror("Ollama補完", str(error))
            return
        self.current_product = p
        self.status_text.set("Ollama補完完了")
        self.render_review()
        self.notebook.select(self.review_tab)

    def render_review(self):
        if not hasattr(self, "review_tree"):
            return
        for item in self.review_tree.get_children():
            self.review_tree.delete(item)
        p = self.current_product
        if not p:
            self.review_summary.configure(text="まだ準備されていません")
            return

        defs = {f.key: f for f in fields_for(p.product_type)}
        fixed = ai = review = manual = blank = 0
        for key, fv in sorted(p.fields.items()):
            if fv.mode == ValueMode.FIXED:
                fixed += 1
            elif fv.mode == ValueMode.OLLAMA:
                ai += 1
            elif fv.mode == ValueMode.REVIEW:
                review += 1
            elif fv.mode == ValueMode.MANUAL:
                manual += 1
            elif fv.mode == ValueMode.BLANK:
                blank += 1

            if self.review_only.get() and fv.mode != ValueMode.REVIEW:
                continue

            label = defs[key].label if key in defs else TEXT_LABELS.get(key, key)
            value = fv.value
            if isinstance(value, list):
                value = ", ".join(str(x) for x in value)
            value = "" if value is None else str(value)
            confidence = "" if fv.confidence is None else f"{fv.confidence:.0%}"
            tag = "review" if fv.mode == ValueMode.REVIEW else ("fixed" if fv.mode == ValueMode.FIXED else "")
            self.review_tree.insert(
                "",
                "end",
                iid=key,
                values=(label, MODE_LABELS[fv.mode], value, fv.source or "—", confidence),
                tags=(tag,) if tag else (),
            )
        self.review_summary.configure(
            text=f"固定 {fixed} / AI {ai} / 手動 {manual} / 空欄 {blank} / 要確認 {review}"
        )

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
        win.geometry("520x430")
        win.transient(self)
        win.grab_set()
        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)

        label = field_def.label if field_def else TEXT_LABELS.get(key, key)
        ttk.Label(body, text=label, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            body,
            text="選択問題はMicrosoft側の候補からだけ選択できます。",
            foreground="#5B6470",
        ).pack(anchor="w", pady=(2, 12))

        ttk.Label(body, text="処理方法").pack(anchor="w")
        mode_var = tk.StringVar(value=MODE_LABELS[fv.mode])
        ttk.Combobox(
            body,
            textvariable=mode_var,
            state="readonly",
            values=tuple(MODE_LABELS.values()),
        ).pack(fill="x", pady=(3, 12))

        ttk.Label(body, text="値").pack(anchor="w")
        value_holder = ttk.Frame(body)
        value_holder.pack(fill="both", expand=True, pady=(3, 8))

        if field_def and field_def.max_selections == 1:
            value_var = tk.StringVar(value="" if fv.value is None else str(fv.value))
            widget = ttk.Combobox(
                value_holder,
                textvariable=value_var,
                state="readonly",
                values=field_def.choices,
            )
            widget.pack(fill="x")
            read_value = lambda: value_var.get() or None
        elif field_def and field_def.max_selections > 1:
            widget = tk.Listbox(value_holder, selectmode="multiple", exportselection=False, height=10)
            for option in field_def.choices:
                widget.insert("end", option)
            current = fv.value if isinstance(fv.value, list) else []
            for i, option in enumerate(field_def.choices):
                if option in current:
                    widget.selection_set(i)
            widget.pack(fill="both", expand=True)
            read_value = lambda: [widget.get(i) for i in widget.curselection()]
        else:
            widget = tk.Text(value_holder, height=10, wrap="word")
            widget.insert("1.0", "" if fv.value is None else str(fv.value))
            widget.pack(fill="both", expand=True)
            read_value = lambda: widget.get("1.0", "end").strip() or None

        def save():
            mode = LABEL_MODES[mode_var.get()]
            if mode == ValueMode.BLANK:
                value = None
            elif mode == ValueMode.OLLAMA:
                value = None
            else:
                value = read_value()
            self.current_product.fields[key] = FieldValue(
                key=key,
                mode=mode,
                value=value,
                source="manual-ui" if mode == ValueMode.MANUAL else ("pending" if mode == ValueMode.OLLAMA else fv.source),
                confidence=1.0 if mode == ValueMode.MANUAL else fv.confidence,
                rationale="ユーザーがUIで変更" if mode == ValueMode.MANUAL else fv.rationale,
            )
            self.render_review()
            win.destroy()

        ttk.Button(body, text="反映", command=save, style="Primary.TButton").pack(anchor="e", pady=(8, 0))

    def add_to_queue(self):
        p = self.prepare(show_message=False)
        if not p.product_name:
            messagebox.showwarning("製品名", "製品名を入力してください。")
            return
        copy = ProductInput.from_dict(p.to_dict())
        self.queue.append(copy)
        self.render_queue()
        self.status_text.set(f"夜間キューへ追加 — {len(self.queue)}件")
        self.notebook.select(self.queue_tab)

    def render_queue(self):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        for i, p in enumerate(self.queue, 1):
            findings = validate_product(p)
            hold = any(f.severity in {Severity.HOLD, Severity.FATAL} for f in findings)
            status = "要確認" if hold else "準備OK"
            package = Path(p.package_path).name if p.package_path else "未選択"
            self.queue_tree.insert(
                "",
                "end",
                iid=str(i - 1),
                values=(i, p.product_name, "ゲーム" if p.product_type == "game" else "アプリ", package, status),
                tags=("hold" if hold else "ready",),
            )
        self.queue_summary.configure(text=f"{len(self.queue)}件")

    def remove_queue_item(self):
        selected = self.queue_tree.selection()
        if not selected:
            return
        indexes = sorted((int(x) for x in selected), reverse=True)
        for index in indexes:
            if 0 <= index < len(self.queue):
                self.queue.pop(index)
        self.render_queue()

    def save_queue(self):
        if not self.queue:
            messagebox.showinfo("夜間キュー", "保存する製品がありません。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="store-night-queue.json",
        )
        if path:
            Path(path).write_text(
                json.dumps([p.to_dict() for p in self.queue], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.status_text.set("夜間キューを保存しました")

    def load_queue(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.queue = [ProductInput.from_dict(x) for x in data]
            self.render_queue()
            self.status_text.set(f"夜間キューを読み込み — {len(self.queue)}件")
        except Exception as exc:
            messagebox.showerror("夜間キュー", str(exc))

    def run_preflight(self):
        if not self.queue:
            messagebox.showinfo("夜間キュー", "事前確認する製品がありません。")
            return
        report = run_queue(self.queue, dryrun_uploader)
        self.last_report = report
        text = render_markdown(report)
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.notebook.select(self.result_tab)
        done = sum(1 for r in report.results if r.status == "DONE")
        hold = sum(1 for r in report.results if r.status == "HOLD")
        self.status_text.set(f"夜間処理の事前確認完了 — DONE {done} / HOLD {hold}")

    def save_report(self):
        if not self.last_report:
            messagebox.showinfo("結果", "保存できる結果がまだありません。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
            initialfile="store-night-report.md",
        )
        if path:
            Path(path).write_text(render_markdown(self.last_report), encoding="utf-8")
            self.status_text.set("結果レポートを保存しました")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
