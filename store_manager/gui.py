from __future__ import annotations
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .core import ProductInput,FieldValue,ValueMode,fields_for,apply_fixed_rules

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Microsoft Store Submission Manager"); self.geometry("1024x768"); self.minsize(900,650)
        self.kind=tk.StringVar(value="app"); self.name=tk.StringVar(); self.repo=tk.StringVar(); self.package=tk.StringVar(); self.images=tk.StringVar(); self.price=tk.StringVar(value="paid"); self.price_value=tk.StringVar(); self._build()
    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=10,pady=10)
        main=ttk.Frame(nb,padding=14); review=ttk.Frame(nb,padding=14); queue=ttk.Frame(nb,padding=14)
        nb.add(main,text="登録"); nb.add(review,text="自動選択・要確認"); nb.add(queue,text="夜間キュー")
        r=ttk.Frame(main); r.pack(fill="x"); ttk.Label(r,text="製品種類",width=18).pack(side="left"); ttk.Radiobutton(r,text="アプリ",value="app",variable=self.kind).pack(side="left"); ttk.Radiobutton(r,text="ゲーム",value="game",variable=self.kind).pack(side="left")
        for label,var in (("製品名",self.name),("GitHubリポジトリ",self.repo)):
            r=ttk.Frame(main); r.pack(fill="x",pady=4); ttk.Label(r,text=label,width=18).pack(side="left"); ttk.Entry(r,textvariable=var).pack(side="left",fill="x",expand=True)
        ttk.Label(main,text="アプリ／ゲームの内容（Ollama入力）").pack(anchor="w",pady=(10,3)); self.summary=tk.Text(main,height=10,wrap="word"); self.summary.pack(fill="x")
        self._path(main,"MSIX / MSIXUPLOAD",self.package,False); self._path(main,"商品画像フォルダ",self.images,True)
        r=ttk.Frame(main); r.pack(fill="x",pady=4); ttk.Label(r,text="価格",width=18).pack(side="left"); ttk.Radiobutton(r,text="有料",value="paid",variable=self.price).pack(side="left"); ttk.Radiobutton(r,text="無料",value="free",variable=self.price).pack(side="left"); ttk.Entry(r,textvariable=self.price_value,width=18).pack(side="left",padx=8)
        r=ttk.Frame(main); r.pack(fill="x",pady=12); ttk.Button(r,text="自動準備",command=self.prepare).pack(side="left"); ttk.Button(r,text="夜間キューへ追加").pack(side="left",padx=5); ttk.Button(r,text="アップロード",state="disabled").pack(side="right")
        ttk.Label(main,text="本番アップロードはPartner Center実画面のselector確認後に有効化します。").pack(anchor="w")
        cols=("field","mode","value","source","confidence"); self.tree=ttk.Treeview(review,columns=cols,show="headings",height=24)
        for c in cols: self.tree.heading(c,text=c)
        self.tree.pack(fill="both",expand=True); ttk.Label(review,text="通常は触りません。根拠不足だけREVIEWとして残します。").pack(anchor="w")
        self.log=tk.Text(queue); self.log.pack(fill="both",expand=True); self.log.insert("end","製品単位のHOLD/ERRORは記録して次へ進みます。認証切れのみ全体停止。\n")
    def _path(self,parent,label,var,folder):
        r=ttk.Frame(parent); r.pack(fill="x",pady=4); ttk.Label(r,text=label,width=18).pack(side="left"); ttk.Entry(r,textvariable=var).pack(side="left",fill="x",expand=True); ttk.Button(r,text="参照",command=lambda:self.pick(var,folder)).pack(side="left")
    def pick(self,var,folder):
        x=filedialog.askdirectory() if folder else filedialog.askopenfilename(filetypes=[("Store packages","*.msix *.msixupload *.msixbundle *.appx *.appxupload *.appxbundle"),("All","*.*")])
        if x: var.set(x)
    def prepare(self):
        p=ProductInput(self.kind.get(),self.name.get().strip(),self.summary.get("1.0","end").strip(),self.repo.get().strip(),self.package.get().strip(),self.images.get().strip(),price_mode=self.price.get(),price_value=self.price_value.get().strip())
        for f in fields_for(p.product_type): p.fields[f.key]=FieldValue(f.key,ValueMode.OLLAMA,None,"pending")
        p.fields["description"]=FieldValue("description",ValueMode.OLLAMA,None,"pending"); apply_fixed_rules(p)
        for i in self.tree.get_children(): self.tree.delete(i)
        defs={f.key:f for f in fields_for(p.product_type)}
        for k,v in sorted(p.fields.items()): self.tree.insert("","end",values=(defs[k].label if k in defs else k,v.mode.value,v.value or "",v.source,"" if v.confidence is None else f"{v.confidence:.2f}"))
        messagebox.showinfo("自動準備","固定ルールを適用しました。Ollama/GitHub補完は同じフィールドへ反映されます。")
def main(): App().mainloop()
if __name__=="__main__": main()
