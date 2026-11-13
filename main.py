# -*- coding: utf-8 -*-
"""PDF 工具箱 · 图形界面（多语言）"""
import os
import sys
import json
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pdf_engine as E
import license as LIC
import i18n as I

try:
    import pdf2docx  # noqa: F401
    HAS_PDF2WORD = True
except Exception:
    HAS_PDF2WORD = False

RED = "#D93025"
DARK = "#202124"
GRAY = "#5f6368"
BG = "#f5f6f8"

# (id, 名称key, 分组key, 说明key, 是否多选)
TOOLS = [
    ("merge",     "tool.merge",     "group.organize", "tool.merge.d",     True),
    ("split",     "tool.split",     "group.organize", "tool.split.d",     False),
    ("extract",   "tool.extract",   "group.organize", "tool.extract.d",   False),
    ("delete",    "tool.delete",    "group.organize", "tool.delete.d",    False),
    ("reorder",   "tool.reorder",   "group.organize", "tool.reorder.d",   False),
    ("rotate",    "tool.rotate",    "group.organize", "tool.rotate.d",    False),
    ("toimg",     "tool.toimg",     "group.convert",  "tool.toimg.d",     False),
    ("fromimg",   "tool.fromimg",   "group.convert",  "tool.fromimg.d",   True),
    ("toword",    "tool.toword",    "group.convert",  "tool.toword.d",    False),
    ("totext",    "tool.totext",    "group.convert",  "tool.totext.d",    False),
    ("office2pdf", "tool.office2pdf", "group.convert", "tool.office2pdf.d", True),
    ("compress",  "tool.compress",  "group.optimize", "tool.compress.d",  False),
    ("repair",    "tool.repair",    "group.optimize", "tool.repair.d",    False),
    ("pageno",    "tool.pageno",    "group.edit",     "tool.pageno.d",    False),
    ("crop",      "tool.crop",      "group.edit",     "tool.crop.d",      False),
    ("redact",    "tool.redact",    "group.edit",     "tool.redact.d",    False),
    ("compare",   "tool.compare",   "group.edit",     "tool.compare.d",   True),
    ("encrypt",   "tool.encrypt",   "group.secure",   "tool.encrypt.d",   False),
    ("decrypt",   "tool.decrypt",   "group.secure",   "tool.decrypt.d",   False),
    ("watermark", "tool.watermark", "group.secure",   "tool.watermark.d", False),
]

GROUPS = ["group.organize", "group.convert", "group.optimize", "group.edit", "group.secure"]

if not HAS_PDF2WORD:
    TOOLS = [t for t in TOOLS if t[0] != "toword"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(I.t("app.title"))
        self.geometry("1040x780")
        self.minsize(940, 700)
        self.configure(bg=BG)
        self.files = []
        self.msgq = queue.Queue()
        self.worker = None
        self.cur = "merge"
        self.lic = {"ok": True, "paid": False, "trial_left": LIC.TRIAL_TOTAL, "msg": ""}
        self._build()
        self.after(100, self._poll)
        self._select("merge")
        self.after(300, self._lic_check)

    # ---------- 布局 ----------
    def _build(self):
        head = tk.Frame(self, bg=RED, height=76)
        head.pack(fill="x")
        head.pack_propagate(False)

        self.lbl_lic = tk.Label(head, text=I.t("lic.checking"), bg=RED, fg="#ffd9d6",
                                font=("Microsoft YaHei UI", 9))
        self.lbl_lic.pack(side="right", padx=8)
        self.btn_act = tk.Button(head, text=I.t("btn.activate"), command=self._open_pay,
                                 bg="#ffffff", fg=RED, relief="flat",
                                 font=("Microsoft YaHei UI", 9), padx=10, pady=2, cursor="hand2")
        self.btn_act.pack(side="right", padx=4)

        # 语言选择
        self.lang_var = tk.StringVar(value=I.LANG_NAMES[I.current()])
        lang_box = ttk.Combobox(head, textvariable=self.lang_var, width=11, state="readonly",
                                values=list(I.LANG_NAMES.values()))
        lang_box.pack(side="right", padx=8, pady=18)
        lang_box.bind("<<ComboboxSelected>>", self._on_lang)

        tk.Label(head, text=I.t("app.title"), bg=RED, fg="white",
                 font=("Microsoft YaHei UI", 17, "bold")).pack(side="left", padx=16)
        tk.Label(head, text=I.t("app.subtitle"), bg=RED, fg="#ffd9d6",
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=4)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg="white", width=200)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        self.toolbtns = {}
        for g in GROUPS:
            tk.Label(left, text=I.t(g), bg="white", fg=GRAY,
                     font=("Microsoft YaHei UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 3))
            for tid, nk, gk, dk, multi in TOOLS:
                if gk != g:
                    continue
                b = tk.Label(left, text="  " + I.t(nk), bg="white", fg=DARK, anchor="w",
                             font=("Microsoft YaHei UI", 10), cursor="hand2", pady=5)
                b.pack(fill="x", padx=6)
                b.bind("<Button-1>", lambda e, t=tid: self._select(t))
                b.bind("<Enter>", lambda e, w=b: w.configure(bg="#f1f3f4"))
                b.bind("<Leave>", lambda e, w=b: w.configure(bg="white"))
                self.toolbtns[tid] = b

        self.right = tk.Frame(body, bg=BG)
        self.right.pack(side="left", fill="both", expand=True, padx=14, pady=10)

        self.lbl_title = tk.Label(self.right, text="", bg=BG, fg=DARK,
                                  font=("Microsoft YaHei UI", 14, "bold"), anchor="w")
        self.lbl_title.pack(fill="x")
        self.lbl_desc = tk.Label(self.right, text="", bg=BG, fg=GRAY,
                                 font=("Microsoft YaHei UI", 9), anchor="w")
        self.lbl_desc.pack(fill="x", pady=(2, 8))

        self.filebox = tk.Frame(self.right, bg="white", highlightbackground="#e0e0e0", highlightthickness=1)
        self.filebox.pack(fill="x")
        bar = tk.Frame(self.filebox, bg="white")
        bar.pack(fill="x", padx=10, pady=7)
        self.btn_pick = tk.Button(bar, text=I.t("file.pick"), command=self._pick, bg=RED, fg="white",
                                  relief="flat", font=("Microsoft YaHei UI", 9), padx=14, pady=3, cursor="hand2")
        self.btn_pick.pack(side="left")
        tk.Button(bar, text=I.t("file.clear"), command=self._clear, bg="#eceff1", fg=DARK,
                  relief="flat", font=("Microsoft YaHei UI", 9), padx=10, pady=3,
                  cursor="hand2").pack(side="left", padx=5)
        tk.Button(bar, text=I.t("file.up"), command=lambda: self._move(-1), bg="#eceff1", fg=DARK,
                  relief="flat", font=("Microsoft YaHei UI", 9), padx=8, pady=3,
                  cursor="hand2").pack(side="left", padx=2)
        tk.Button(bar, text=I.t("file.down"), command=lambda: self._move(1), bg="#eceff1", fg=DARK,
                  relief="flat", font=("Microsoft YaHei UI", 9), padx=8, pady=3,
                  cursor="hand2").pack(side="left", padx=2)
        self.lbl_count = tk.Label(bar, text=I.t("file.none"), bg="white", fg=GRAY,
                                  font=("Microsoft YaHei UI", 9))
        self.lbl_count.pack(side="right")

        self.listbox = tk.Listbox(self.filebox, height=5, relief="flat", bg="white", fg=DARK,
                                  font=("Consolas", 9), highlightthickness=0,
                                  selectbackground="#fce8e6", selectforeground=DARK)
        self.listbox.pack(fill="x", padx=10, pady=(0, 10))

        self.param = tk.Frame(self.right, bg="white", highlightbackground="#e0e0e0", highlightthickness=1)
        self.param.pack(fill="x", pady=8)
        self.param_inner = tk.Frame(self.param, bg="white")
        self.param_inner.pack(fill="x", padx=12, pady=9)

        act = tk.Frame(self.right, bg=BG)
        act.pack(fill="x")
        self.btn_run = tk.Button(act, text=I.t("btn.run"), command=self._run, bg=RED, fg="white",
                                 relief="flat", font=("Microsoft YaHei UI", 11, "bold"),
                                 padx=28, pady=7, cursor="hand2")
        self.btn_run.pack(side="left")
        self.pbar = ttk.Progressbar(act, mode="determinate", length=320)
        self.pbar.pack(side="left", padx=12)
        self.lbl_status = tk.Label(act, text=I.t("status.ready"), bg=BG, fg=GRAY,
                                   font=("Microsoft YaHei UI", 9))
        self.lbl_status.pack(side="left")

        self.log = tk.Text(self.right, height=6, bg="#fafafa", fg="#333", relief="flat",
                           font=("Consolas", 8), wrap="word")
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self.log.configure(state="disabled")

    # ---------- 语言 ----------
    def _on_lang(self, evt=None):
        name = self.lang_var.get()
        code = next((k for k, v in I.LANG_NAMES.items() if v == name), None)
        if not code or code == I.current():
            return
        I.save_lang(code)
        if messagebox.askokcancel(I.t("lang.title"), I.t("lang.prompt") + "\n\nRestart now?"):
            self._restart()
        else:
            self.lbl_lic.configure(text=I.t("lic.checking"))

    def _restart(self):
        try:
            self.destroy()
        except Exception:
            pass
        os.execl(sys.executable, sys.executable, *sys.argv)

    # ---------- 交互 ----------
    def _select(self, tid):
        for k, b in self.toolbtns.items():
            b.configure(bg=RED if k == tid else "white", fg="white" if k == tid else DARK)
        self.cur = tid
        meta = [t for t in TOOLS if t[0] == tid][0]
        self.lbl_title.configure(text=I.t(meta[1]))
        self.lbl_desc.configure(text=I.t(meta[3]))
        self.files = []
        self._refresh_list()
        for w in self.param_inner.winfo_children():
            w.destroy()
        self._build_params(tid)

    def _build_params(self, tid):
        p = self.param_inner
        self.vars = {}

        def make_row(label, key, default="", hint=""):
            f = tk.Frame(p, bg="white")
            f.pack(fill="x", pady=3)
            tk.Label(f, text=label, bg="white", fg=DARK, width=15, anchor="w",
                     font=("Microsoft YaHei UI", 9)).pack(side="left")
            v = tk.StringVar(value=default)
            self.vars[key] = v
            ttk.Entry(f, textvariable=v, width=28).pack(side="left")
            if hint:
                tk.Label(f, text=hint, bg="white", fg=GRAY,
                         font=("Microsoft YaHei UI", 8)).pack(side="left", padx=8)

        def make_combo(label, key, values, default=None):
            f = tk.Frame(p, bg="white")
            f.pack(fill="x", pady=3)
            tk.Label(f, text=label, bg="white", fg=DARK, width=15, anchor="w",
                     font=("Microsoft YaHei UI", 9)).pack(side="left")
            v = tk.StringVar(value=default or values[0])
            self.vars[key] = v
            c = ttk.Combobox(f, textvariable=v, values=values, state="readonly", width=24)
            c.pack(side="left")
            return c

        def make_check(label, key, default=True):
            f = tk.Frame(p, bg="white")
            f.pack(fill="x", pady=3)
            v = tk.BooleanVar(value=default)
            self.vars[key] = v
            tk.Checkbutton(f, text=label, variable=v, bg="white", fg=DARK, activebackground="white",
                           font=("Microsoft YaHei UI", 9)).pack(side="left")

        def tip(text):
            tk.Label(p, text=text, bg="white", fg=GRAY, font=("Microsoft YaHei UI", 8),
                     wraplength=660, justify="left").pack(anchor="w", pady=(5, 0))

        if tid == "split":
            make_combo(I.t("param.split.mode"), "mode",
                       [I.t("param.split.bypage"), I.t("param.split.custom")], I.t("param.split.bypage"))
            make_row(I.t("param.split.n"), "n", "1", I.t("param.split.hint"))
        elif tid == "extract":
            make_row(I.t("param.extract"), "expr", "1-3,5", I.t("param.extract.hint"))
        elif tid == "delete":
            make_row(I.t("param.delete"), "expr", "1", I.t("param.delete.hint"))
        elif tid == "reorder":
            make_row(I.t("param.reorder"), "expr", "3,1,2,4-", I.t("param.reorder.hint"))
        elif tid == "rotate":
            make_row(I.t("param.rotate.pages"), "expr", "", I.t("param.rotate.hint"))
            make_combo(I.t("param.rotate.angle"), "angle", ["90", "180", "270"])
        elif tid == "compress":
            make_combo(I.t("param.compress.level"), "level",
                       [I.t("param.compress.l1"), I.t("param.compress.l2"), I.t("param.compress.l3")],
                       I.t("param.compress.l2"))
        elif tid == "toimg":
            make_combo(I.t("param.img.fmt"), "fmt", ["png", "jpg"])
            make_row(I.t("param.img.dpi"), "dpi", "150", I.t("param.img.dpi.hint"))
            make_row(I.t("param.img.pages"), "expr", "", I.t("param.img.pages.hint"))
        elif tid == "fromimg":
            make_combo(I.t("param.fromimg.size"), "size",
                       [I.t("param.fromimg.s1"), I.t("param.fromimg.s2")], I.t("param.fromimg.s2"))
        elif tid == "encrypt":
            make_row(I.t("param.enc.pwd"), "pwd", "", I.t("param.enc.pwd.hint"))
            make_row(I.t("param.enc.owner"), "owner", "", I.t("param.enc.owner.hint"))
        elif tid == "decrypt":
            make_row(I.t("param.dec.pwd"), "pwd", "", I.t("param.dec.pwd.hint"))
        elif tid == "watermark":
            make_row(I.t("param.wm.text"), "text", "POLICE  EVIDENCE")
            make_row(I.t("param.wm.size"), "size", "36")
            make_check(I.t("param.wm.pageno"), "pageno", True)
        elif tid == "pageno":
            make_combo(I.t("param.pageno.pos"), "pos",
                       [I.t("param.pos.bc"), I.t("param.pos.br"), I.t("param.pos.bl"),
                        I.t("param.pos.tc"), I.t("param.pos.tr")], I.t("param.pos.bc"))
            make_combo(I.t("param.pageno.fmt"), "fmt",
                       [I.t("param.fmt.1"), I.t("param.fmt.2"), I.t("param.fmt.3"), I.t("param.fmt.4")],
                       I.t("param.fmt.1"))
            make_row(I.t("param.pageno.size"), "size", "12")
            make_row(I.t("param.pageno.start"), "start", "1")
        elif tid == "crop":
            make_row(I.t("param.crop.t"), "top", "0", I.t("param.crop.hint"))
            make_row(I.t("param.crop.b"), "bottom", "0")
            make_row(I.t("param.crop.l"), "left", "0")
            make_row(I.t("param.crop.r"), "right", "0")
            tip(I.t("param.crop.tip"))
        elif tid == "redact":
            make_row(I.t("param.redact.kw"), "kw", "", I.t("param.redact.hint"))
            tip(I.t("param.redact.tip"))
        elif tid == "compare":
            tip(I.t("param.compare.tip"))
        elif tid == "repair":
            tip(I.t("param.repair.tip"))
        else:
            tk.Label(p, text=I.t("param.none"), bg="white", fg=GRAY,
                     font=("Microsoft YaHei UI", 9)).pack(anchor="w")

        out_row = tk.Frame(p, bg="white")
        out_row.pack(fill="x", pady=(6, 0))
        tk.Label(out_row, text=I.t("param.outdir"), bg="white", fg=DARK, width=15, anchor="w",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        v = tk.StringVar(value="")
        self.vars["outdir"] = v
        ttk.Entry(out_row, textvariable=v, width=28).pack(side="left")
        tk.Button(out_row, text=I.t("param.browse"), command=self._pick_outdir, bg="#eceff1",
                  relief="flat", font=("Microsoft YaHei UI", 8), padx=8,
                  cursor="hand2").pack(side="left", padx=5)
        tk.Label(out_row, text=I.t("param.outdir.hint"), bg="white", fg=GRAY,
                 font=("Microsoft YaHei UI", 8)).pack(side="left")

    def _pick_outdir(self):
        d = filedialog.askdirectory(title=I.t("param.outdir"))
        if d:
            self.vars["outdir"].set(d)

    def _pick(self):
        multi = [t for t in TOOLS if t[0] == self.cur][0][4]
        if self.cur == "fromimg":
            fs = filedialog.askopenfilenames(
                filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All", "*.*")])
        elif self.cur == "office2pdf":
            fs = filedialog.askopenfilenames(
                filetypes=[("Office", "*.docx *.doc *.xlsx *.xls *.pptx *.ppt *.rtf *.csv"),
                           ("All", "*.*")])
        elif multi:
            fs = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        else:
            fs = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
            fs = [fs] if fs else []
        if not fs:
            return
        if multi:
            self.files.extend([f for f in fs if f not in self.files])
        else:
            self.files = list(fs)[:1]
        self._refresh_list()

    def _clear(self):
        self.files = []
        self._refresh_list()

    def _move(self, d):
        i = self.listbox.curselection()
        if not i:
            return
        i = i[0]
        j = i + d
        if 0 <= j < len(self.files):
            self.files[i], self.files[j] = self.files[j], self.files[i]
            self._refresh_list()
            self.listbox.selection_set(j)

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for k, f in enumerate(self.files, 1):
            sz = os.path.getsize(f) / 1048576 if os.path.exists(f) else 0
            self.listbox.insert("end", "%02d  [%6.2f MB]  %s" % (k, sz, os.path.basename(f)))
        self.lbl_count.configure(text=(I.t("file.count", n=len(self.files)) if self.files else I.t("file.none")))

    # ---------- 授权 ----------
    def _lic_check(self):
        def work():
            try:
                r = LIC.checkin()
            except Exception as e:
                r = {"ok": True, "paid": False, "trial_left": LIC.TRIAL_TOTAL, "msg": str(e)[:40]}
            self.msgq.put(("lic", r))
        threading.Thread(target=work, daemon=True).start()

    def _set_lic(self, r):
        self.lic = r
        if r.get("paid"):
            self.lbl_lic.configure(text=I.t("lic.paid"), fg="#c8f7c5")
            try:
                self.btn_act.pack_forget()
            except Exception:
                pass
            return
        left = int(r.get("trial_left", 0) or 0)
        if r.get("ok"):
            self.lbl_lic.configure(text=I.t("lic.trial", n=left), fg="#ffd9d6")
        else:
            self.lbl_lic.configure(text=I.t("lic.used"), fg="#ffe082")

    def _open_pay(self, reason=""):
        short = LIC.short_code()
        win = tk.Toplevel(self)
        win.title(I.t("pay.title"))
        win.geometry("470x640")
        win.configure(bg="white")
        win.transient(self)
        win.grab_set()

        tk.Label(win, text=I.t("pay.title"), bg="white", fg=DARK,
                 font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(14, 3))
        if reason:
            tk.Label(win, text=reason, bg="white", fg="#c62828",
                     font=("Microsoft YaHei UI", 9)).pack()

        box = tk.Frame(win, bg="#fafafa", highlightbackground="#e0e0e0", highlightthickness=1)
        box.pack(fill="x", padx=18, pady=10)
        tk.Label(box, text=I.t("pay.machine"), bg="#fafafa", fg=GRAY,
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=(7, 0))

        mid_row = tk.Frame(box, bg="#fafafa")
        mid_row.pack(fill="x", padx=10)
        tk.Label(mid_row, text=short, bg="#fafafa", fg=DARK,
                 font=("Consolas", 15, "bold")).pack(side="left")

        def copy_mid():
            try:
                self.clipboard_clear()
                self.clipboard_append(LIC.machine_code())
                btn_copy.configure(text="已复制")
                win.after(1200, lambda: btn_copy.configure(text="复制完整码"))
            except Exception:
                pass

        btn_copy = tk.Button(mid_row, text="复制完整码", command=copy_mid, bg="#e8f0fe", fg="#1a73e8",
                             relief="flat", font=("Microsoft YaHei UI", 8), padx=8, pady=1,
                             cursor="hand2")
        btn_copy.pack(side="left", padx=10)

        tk.Label(box, text=I.t("pay.price", p=66), bg="#fafafa", fg=RED,
                 font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", padx=10, pady=(5, 7))

        def _res(name):
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            p = os.path.join(base, name)
            return p if os.path.exists(p) else os.path.join(
                os.path.dirname(os.path.abspath(sys.argv[0])), name)

        qr = _res("pay_qr.png")
        if os.path.exists(qr):
            try:
                from PIL import Image, ImageTk
                im = Image.open(qr)
                im.thumbnail((150, 150))
                self._qr_img = ImageTk.PhotoImage(im)
                tk.Label(win, image=self._qr_img, bg="white").pack(pady=(0, 2))
                tk.Label(win, text=I.t("pay.scan"), bg="white", fg=GRAY,
                         font=("Microsoft YaHei UI", 8)).pack()
            except Exception:
                pass

        tk.Label(win, text=I.t("pay.steps", p=66), bg="white", fg=GRAY,
                 font=("Microsoft YaHei UI", 9), justify="left").pack(padx=18, anchor="w", pady=(4, 0))

        # 邮箱输入 + 提交授权申请
        ef = tk.Frame(win, bg="white")
        ef.pack(fill="x", padx=18, pady=(4, 0))
        tk.Label(ef, text=I.t("pay.email_label"), bg="white", fg=DARK,
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        email_var = tk.StringVar()
        email_ent = ttk.Entry(ef, textvariable=email_var, width=26)
        email_ent.pack(side="left", padx=8)
        email_ent.focus_set()
        tk.Label(ef, text=I.t("pay.email_hint"), bg="white", fg=GRAY,
                 font=("Microsoft YaHei UI", 8)).pack(side="left")

        msg = tk.Label(win, text="", bg="white", fg=GRAY, font=("Microsoft YaHei UI", 9),
                       wraplength=420, justify="left")
        msg.pack(pady=(6, 0))

        def do_apply():
            email = email_var.get().strip()
            if not email:
                msg.configure(text=I.t("pay.email_empty"), fg="#c62828")
                return
            if "@" not in email or "." not in email.split("@")[-1]:
                msg.configure(text=I.t("pay.email_bad"), fg="#c62828")
                return
            msg.configure(text=I.t("pay.submitting"), fg=GRAY)
            btn_apply.configure(state="disabled")
            win.update_idletasks()
            try:
                r = LIC.apply_license(email)
            except Exception as e:
                r = {"ok": False, "msg": str(e)[:60]}
            if r.get("ok"):
                if r.get("paid"):
                    msg.configure(text=I.t("pay.already"), fg="#2e7d32")
                    self.after(800, win.destroy)
                    self._lic_check()
                else:
                    msg.configure(text=r.get("msg") or I.t("pay.submitted"), fg="#2e7d32")
                    btn_apply.configure(text="已提交 ✓", state="disabled", bg="#c8e6c9")
            else:
                msg.configure(text=r.get("msg") or "提交失败", fg="#c62828")
                btn_apply.configure(state="normal")

        bf = tk.Frame(win, bg="white")
        bf.pack(pady=10)
        btn_apply = tk.Button(bf, text=I.t("pay.submit_btn"), command=do_apply, bg=RED, fg="white",
                              relief="flat", font=("Microsoft YaHei UI", 10, "bold"),
                              padx=24, pady=6, cursor="hand2")
        btn_apply.pack(side="left", padx=5)
        tk.Button(bf, text=I.t("pay.close"), command=win.destroy, bg="#eceff1", fg=DARK,
                  relief="flat", font=("Microsoft YaHei UI", 10), padx=18, pady=6,
                  cursor="hand2").pack(side="left")

        
    # ---------- 执行 ----------
    def _log(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _progress(self, a, b, name=""):
        self.msgq.put(("p", a, b, name))

    def _poll(self):
        try:
            while True:
                m = self.msgq.get_nowait()
                if m[0] == "p":
                    _, a, b, name = m
                    self.pbar["maximum"] = max(1, b)
                    self.pbar["value"] = a
                    self.lbl_status.configure(text="%s/%s  %s" % (a, b, name))
                elif m[0] == "log":
                    self._log(m[1])
                elif m[0] == "lic":
                    self._set_lic(m[1])
                elif m[0] == "done":
                    self.btn_run.configure(state="normal", text=I.t("btn.run"))
                    self.pbar["value"] = 0
                    self.lbl_status.configure(text=m[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _run(self):
        if not self.files:
            messagebox.showwarning(I.t("app.title"), I.t("msg.pick_first"))
            return
        try:
            feat = I.t([t for t in TOOLS if t[0] == self.cur][0][1])
            c = LIC.consume(feat)
        except Exception:
            c = {"ok": True, "paid": bool(self.lic.get("paid")),
                 "trial_left": self.lic.get("trial_left", 0)}
        if not c.get("ok"):
            self._set_lic({"ok": False, "paid": False, "trial_left": c.get("trial_left", 0)})
            self._open_pay(c.get("msg", ""))
            return
        self._set_lic({"ok": True, "paid": c.get("paid"), "trial_left": c.get("trial_left", 0)})
        outdir = self.vars.get("outdir").get().strip() or None
        self.btn_run.configure(state="disabled", text=I.t("btn.running"))
        self._log("———— " + I.t([t for t in TOOLS if t[0] == self.cur][0][1]) + " ————")

        def work():
            try:
                r = self._dispatch(outdir)
                self.msgq.put(("log", str(r)))
                self.msgq.put(("done", I.t("status.done")))
            except Exception as e:
                self.msgq.put(("log", str(e)))
                self.msgq.put(("done", I.t("status.failed")))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _dispatch(self, outdir):
        t = self.cur
        src = self.files[0]
        v = self.vars

        def g(k, d=""):
            return v[k].get() if k in v else d

        if t == "merge":
            out = os.path.join(outdir or os.path.dirname(src), "merged.pdf")
            E.merge_pdfs(self.files, out, self._progress)
            return "%d → %s" % (len(self.files), out)

        if t == "split":
            od = outdir or os.path.join(os.path.dirname(src),
                                        os.path.splitext(os.path.basename(src))[0] + "_split")
            mode = "ranges" if g("mode").startswith(I.t("param.split.custom")[:4]) else "pages_per"
            made = E.split_pdf(src, od, mode, g("n", "1"), self._progress)
            return "%d → %s" % (len(made), od)

        if t == "extract":
            out = E._out_path(src, outdir, "_extract")
            _, n = E.extract_pages(src, out, g("expr"), self._progress)
            return "%d pages → %s" % (n, out)

        if t == "delete":
            out = E._out_path(src, outdir, "_deleted")
            _, n = E.delete_pages(src, out, g("expr"), self._progress)
            return "%d pages → %s" % (n, out)

        if t == "reorder":
            out = E._out_path(src, outdir, "_reordered")
            _, n = E.reorder_pages(src, out, g("expr"), self._progress)
            return "%d pages → %s" % (n, out)

        if t == "rotate":
            out = E._out_path(src, outdir, "_rotated")
            E.rotate_pages(src, out, g("expr"), g("angle", "90"), self._progress)
            return out

        if t == "compress":
            lv = g("level")
            level = "light" if lv == I.t("param.compress.l1") else ("strong" if lv == I.t("param.compress.l3") else "medium")
            out = E._out_path(src, outdir, "_compressed")
            E.compress_pdf(src, out, level, self._progress)
            a, b = os.path.getsize(src), os.path.getsize(out)
            return "%.2f MB → %.2f MB (-%d%%)\n%s" % (a / 1048576, b / 1048576, (1 - b / a) * 100, out)

        if t == "toimg":
            od = outdir or os.path.join(os.path.dirname(src),
                                        os.path.splitext(os.path.basename(src))[0] + "_img")
            made = E.pdf_to_images(src, od, g("fmt", "png"), g("dpi", "150"), g("expr"), self._progress)
            return "%d → %s" % (len(made), od)

        if t == "fromimg":
            out = os.path.join(outdir or os.path.dirname(src), "images.pdf")
            size = "a4" if g("size") == I.t("param.fromimg.s2") else "auto"
            E.images_to_pdf(self.files, out, size, self._progress)
            return out

        if t == "toword":
            out = E._out_path(src, outdir, "", ".docx")
            E.pdf_to_word(src, out, self._progress)
            return out

        if t == "totext":
            out = E._out_path(src, outdir, "", ".txt")
            E.pdf_to_text(src, out, self._progress)
            return out

        if t == "office2pdf":
            done, fail = [], []
            for k, f in enumerate(self.files, 1):
                out = os.path.join(outdir or os.path.dirname(f),
                                   os.path.splitext(os.path.basename(f))[0] + ".pdf")
                try:
                    E.office_to_pdf(f, out)
                    done.append(out)
                    self._log("  [%d/%d] %s OK" % (k, len(self.files), os.path.basename(f)))
                except Exception as e:
                    fail.append("%s: %s" % (os.path.basename(f), e))
                self._progress(k, len(self.files), os.path.basename(f))
            msg = "OK %d" % len(done)
            if fail:
                msg += " / FAIL " + str(len(fail)) + ": " + "; ".join(fail[:3])
            return msg

        if t == "pageno":
            pos_map = {
                I.t("param.pos.bc"): "bottom_center", I.t("param.pos.br"): "bottom_right",
                I.t("param.pos.bl"): "bottom_left", I.t("param.pos.tc"): "top_center",
                I.t("param.pos.tr"): "top_right",
            }
            fmt_map = {I.t("param.fmt.1"): "p", I.t("param.fmt.2"): "x/y",
                       I.t("param.fmt.3"): "dash", I.t("param.fmt.4"): "num"}
            out = E._out_path(src, outdir, "_pageno")
            _, n = E.add_pageno(src, out, pos_map.get(g("pos"), "bottom_center"),
                                fmt_map.get(g("fmt"), "p"), int(g("size", "12") or 12),
                                int(g("start", "1") or 1), 36, self._progress)
            return "%d pages → %s" % (n, out)

        if t == "crop":
            out = E._out_path(src, outdir, "_cropped")
            E.crop_pdf(src, out, float(g("top", "0") or 0), float(g("right", "0") or 0),
                       float(g("bottom", "0") or 0), float(g("left", "0") or 0), self._progress)
            return out

        if t == "redact":
            out = E._out_path(src, outdir, "_redacted")
            _, hits = E.redact_pdf(src, out, g("kw"), (0, 0, 0), 2, self._progress)
            return "%d → %s" % (hits, out)

        if t == "compare":
            if len(self.files) < 2:
                raise RuntimeError(I.t("msg.need_two"))
            out = os.path.join(outdir or os.path.dirname(self.files[0]),
                               "compare_" + os.path.splitext(os.path.basename(self.files[1]))[0] + ".pdf")
            _, diffs = E.compare_pdf(self.files[0], self.files[1], out, 100, self._progress)
            if diffs:
                return "%d diff page(s): %s → %s" % (len(diffs), ",".join(map(str, diffs[:15])), out)
            return "identical structure → %s" % out

        if t == "repair":
            out = E._out_path(src, outdir, "_repaired")
            _, n = E.repair_pdf(src, out, self._progress)
            return "%d pages → %s" % (n, out)

        if t == "encrypt":
            out = E._out_path(src, outdir, "_encrypted")
            E.encrypt_pdf(src, out, g("pwd"), g("owner"))
            return out

        if t == "decrypt":
            out = E._out_path(src, outdir, "_decrypted")
            E.decrypt_pdf(src, out, g("pwd"))
            return out

        if t == "watermark":
            out = E._out_path(src, outdir, "_watermark")
            E.add_watermark(src, out, g("text"), 0.25, int(g("size", "36") or 36), 0,
                            "center", bool(v["pageno"].get() if "pageno" in v else True),
                            self._progress)
            return out

        raise RuntimeError("unknown tool")


def ask_language_first_run():
    """首次运行时让用户选语言"""
    s = I._settings_path()
    if os.path.exists(s):
        try:
            with open(s, encoding="utf-8") as f:
                if json.load(f).get("lang"):
                    return
        except Exception:
            pass
    win = tk.Tk()
    win.title("Language / 语言")
    win.geometry("380x300")
    win.configure(bg="white")
    win.resizable(False, False)
    tk.Label(win, text="请选择界面语言\nSelect interface language",
             bg="white", fg=DARK, font=("Microsoft YaHei UI", 11, "bold")).pack(pady=16)
    chosen = {"code": I.DEFAULT_LANG}
    for code, name in I.LANG_NAMES.items():
        def pick(c=code):
            chosen["code"] = c
            win.destroy()
        tk.Button(win, text=name, command=pick, bg="#f1f3f4", fg=DARK, relief="flat",
                  font=("Microsoft YaHei UI", 10), width=24, pady=4,
                  cursor="hand2").pack(pady=2)
    win.mainloop()
    I.save_lang(chosen["code"])


if __name__ == "__main__":
    try:
        import ctypes
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)
    except Exception:
        pass

    if "--selftest" in sys.argv:
        E.selftest()
        sys.exit(0)

    if "--check" in sys.argv:
        I.load_lang()
        app = App()
        app.after(600, app.destroy)
        app.mainloop()
        print("GUI OK lang=" + I.current())
        sys.exit(0)

    I.load_lang()
    ask_language_first_run()
    I.load_lang()
    App().mainloop()





