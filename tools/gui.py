#!/usr/bin/env python3
"""Desktop patcher GUI for Sonic and the Secret Rings on Wii.

Supports drag-and-drop or file browsing for WBFS / ISO disc images or main.dol files.
Provides options for Classic Controller and GameCube Controller support.
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import disc
import features
import patcher
from dol import Dol
from regions import ALL_REGIONS

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BASE = TkinterDnD.Tk
    HAVE_DND = True
except ImportError:
    BASE = tk.Tk
    HAVE_DND = False


def asset_path(filename):
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        p = os.path.join(base, 'assets', filename)
        if os.path.exists(p):
            return p
        p = os.path.join(base, filename)
        if os.path.exists(p):
            return p
    return os.path.join(HERE, '..', 'assets', filename)


class SecretRingsPatcherApp(BASE):
    def __init__(self):
        super().__init__()
        self.title("Sonic and the Secret Rings Controller Patcher")
        self.geometry("580x660")
        self.minsize(540, 600)

        # State
        self.file_path = None
        self.is_disc = False
        self.region_id = None
        self.feature_vars = {}
        self.busy = False

        self._build_ui()

    def _build_ui(self):
        # 1. Header / Logo Banner
        banner_path = asset_path('logo.png')
        if os.path.exists(banner_path):
            try:
                raw_img = tk.PhotoImage(file=banner_path)
                # Logo is 937x593; subsample by 3 -> ~312x197
                sub_factor = max(1, raw_img.width() // 312)
                self.logo_img = raw_img.subsample(sub_factor, sub_factor)
                logo_lbl = tk.Label(self, image=self.logo_img)
                logo_lbl.pack(pady=(12, 4))
            except Exception:
                pass

        title_lbl = tk.Label(self, text="Sonic and the Secret Rings · Wii",
                             font=("TkDefaultFont", 12, "bold"))
        title_lbl.pack(pady=(0, 2))
        sub_lbl = tk.Label(self, text="Classic Controller & GameCube Controller Suite",
                           font=("TkDefaultFont", 10), fg="#555")
        sub_lbl.pack(pady=(0, 8))

        # 2. Options Frame
        opts_frame = tk.LabelFrame(self, text=" Controller Mode ", padx=12, pady=8)
        opts_frame.pack(fill=tk.X, padx=14, pady=4)

        self.mode_var = tk.StringVar(value='combo')
        for fkey in ('combo', 'cc', 'gc'):
            rb = tk.Radiobutton(opts_frame, text=features.TITLES[fkey], variable=self.mode_var,
                                value=fkey, font=("TkDefaultFont", 10, "bold"), anchor=tk.W)
            rb.pack(fill=tk.X, anchor=tk.W, pady=(2, 0))
            desc_lbl = tk.Label(opts_frame, text=f"    {features.DESCRIPTIONS[fkey]}",
                                font=("TkDefaultFont", 9), fg="#666", anchor=tk.W)
            desc_lbl.pack(fill=tk.X, anchor=tk.W, pady=(0, 4))

        # 3. Drop / Pick Target Area
        hint = ("Drop a .wbfs, .iso, or main.dol here\n\n(or click to browse)"
                if HAVE_DND else "Click to choose a .wbfs, .iso, or main.dol")
        self.drop_lbl = tk.Label(self, text=hint, relief="ridge", bd=2,
                                 padx=10, pady=22, cursor="hand2", font=("TkDefaultFont", 10))
        self.drop_lbl.pack(fill=tk.X, padx=14, pady=10)
        self.drop_lbl.bind("<Button-1>", lambda e: self._browse_file())

        if HAVE_DND:
            self.drop_lbl.drop_target_register(DND_FILES)
            self.drop_lbl.dnd_bind("<<Drop>>", self._on_drop)

        # Info Note
        note_lbl = tk.Label(self, text="The original disc image is kept alongside as <name>.bak",
                            font=("TkDefaultFont", 9), fg="#666")
        note_lbl.pack()

        # 4. Action Button
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=14, pady=(6, 8))

        self.patch_btn = tk.Button(btn_frame, text="Apply Patches", command=self._start_patching,
                                   font=("TkDefaultFont", 11, "bold"), state=tk.DISABLED, pady=5)
        self.patch_btn.pack(fill=tk.X)

        # 5. Output Log
        log_frame = tk.LabelFrame(self, text=" Output Log ", padx=8, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 9), height=7, bg="#F9F9F9")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if paths and not self.busy:
            self._load_file(paths[0])

    def _browse_file(self):
        if self.busy:
            return
        f = filedialog.askopenfilename(
            title="Select Sonic and the Secret Rings Disc Image or main.dol",
            filetypes=[
                ("All Supported Files", "*.wbfs;*.iso;*.dol"),
                ("Wii Disc Images", "*.wbfs;*.iso"),
                ("Executable DOL", "*.dol"),
                ("All Files", "*.*")
            ]
        )
        if f:
            self._load_file(f)

    def _load_file(self, path):
        self.file_path = path
        ext = os.path.splitext(path)[1].lower()

        if ext in ('.wbfs', '.iso'):
            self.is_disc = True
            wit_bin = disc.find_wit()
            if not wit_bin:
                self.log("Note: wit (Wiimms ISO Tool) is required to extract and rebuild disc images.")
            self.drop_lbl.config(text=f"Selected Disc:\n{os.path.basename(path)}", fg="#006600")
            self.patch_btn.config(state=tk.NORMAL)
        elif ext == '.dol':
            self.is_disc = False
            try:
                d = Dol(path)
                reg = patcher.detect_region(d)
                if reg:
                    self.region_id = reg
                    meta = ALL_REGIONS[reg]
                    self.drop_lbl.config(text=f"Detected DOL:\n{reg} - {meta['label']}", fg="#006600")
                    self.patch_btn.config(state=tk.NORMAL)
                else:
                    self.drop_lbl.config(text=f"Could not identify region for:\n{os.path.basename(path)}", fg="#990000")
                    self.patch_btn.config(state=tk.DISABLED)
            except Exception as e:
                self.drop_lbl.config(text=f"Error reading DOL:\n{e}", fg="#990000")
                self.patch_btn.config(state=tk.DISABLED)
        else:
            self.drop_lbl.config(text=f"Unsupported file type:\n{os.path.basename(path)}", fg="#990000")
            self.patch_btn.config(state=tk.DISABLED)

    def _start_patching(self):
        if not self.file_path or self.busy:
            return

        selected_mode = self.mode_var.get()
        if not selected_mode:
            messagebox.showwarning("No Mode Selected", "Please select a controller mode option.")
            return

        selected = [selected_mode]

        self.busy = True
        self.patch_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log("Starting patch process...")

        def worker():
            try:
                if self.is_disc:
                    disc.run_patch(self.file_path, self.log, self._patch_finished, which=selected)
                else:
                    d = Dol(self.file_path)
                    applied = patcher.patch(d, self.region_id, selected)
                    out_path = self.file_path.replace('.dol', '_patched.dol')
                    d.save(out_path)
                    self.log(f"Successfully applied: {', '.join(applied)}")
                    self.log(f"Saved patched DOL to: {out_path}")
                    self._patch_finished(True, out_path)
            except Exception as e:
                self.log(f"ERROR: {e}")
                self._patch_finished(False, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _patch_finished(self, success, result):
        def cb():
            self.busy = False
            self.patch_btn.config(state=tk.NORMAL)
            if success:
                messagebox.showinfo("Success", f"Patching completed successfully!\n\nTarget: {result}")
            else:
                messagebox.showerror("Patching Failed", f"An error occurred during patching:\n\n{result}")
        self.after(0, cb)


if __name__ == '__main__':
    app = SecretRingsPatcherApp()
    app.mainloop()
