"""PKOS Windows 데스크톱 앱. python pkos_app.py"""
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from desktop_core import validate_folders, prepare_sample
from pkos_folder import FolderConverter, FolderSettings


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PKOS 자료 변환기")
        self.geometry("1040x800")
        self.minsize(840, 660)
        self.configure(bg="#f2f5fa")
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.output_path = None
        self.result_paths = {}
        self.source = tk.StringVar()
        self.output = tk.StringVar(value=str(Path.home() / "Documents" / "PKOS" / "변환결과"))
        self.mask = tk.BooleanVar(value=True)
        self.skip = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="원본 폴더를 선택하거나, 샘플로 먼저 연습해보세요.")
        self.locked = []
        self.config_path = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "PKOS" / "settings.json"
        self.load_settings()
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def load_settings(self):
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            self.source.set(data.get("source", ""))
            self.output.set(data.get("output", self.output.get()))
        except (OSError, ValueError, TypeError):
            pass

    def save_settings(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps({"source": self.source.get(), "output": self.output.get()}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f5fa")
        style.configure("TLabel", background="#f2f5fa", font=("맑은 고딕", 10))
        style.configure("TButton", font=("맑은 고딕", 10), padding=(12, 8))
        style.configure("Accent.TButton", background="#245cc7", foreground="white")
        style.map("Accent.TButton", background=[("active", "#19469c"), ("disabled", "#b6c4db")])
        style.configure("TCheckbutton", background="#f2f5fa", font=("맑은 고딕", 10))
        style.configure("Treeview", font=("맑은 고딕", 10), rowheight=28)
        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="PKOS 자료 변환기", font=("맑은 고딕", 24, "bold")).pack(anchor="w")
        ttk.Label(outer, text="폴더를 선택하면 한글·워드·PDF·엑셀·PPT를 마크다운으로 모아줍니다.").pack(anchor="w", pady=(4, 20))
        for label, var in [("1. 원본 폴더  ·  탐색기에서 복사한 경로를 붙여넣으세요", self.source), ("2. 결과를 저장할 폴더", self.output)]:
            ttk.Label(outer, text=label, font=("맑은 고딕", 11, "bold")).pack(anchor="w", pady=(5, 6))
            row = ttk.Frame(outer)
            row.pack(fill="x", pady=(0, 10))
            entry = ttk.Entry(row, textvariable=var, font=("맑은 고딕", 11))
            entry.pack(side="left", fill="x", expand=True, ipady=8)
            entry.bind("<Control-a>", lambda e: (e.widget.selection_range(0, "end"), "break")[-1])
            button = ttk.Button(row, text="찾아보기", command=lambda v=var: self.browse(v))
            button.pack(side="left", padx=(8, 0))
            self.locked.extend([entry, button])
        opts = ttk.Frame(outer)
        opts.pack(fill="x", pady=(0, 6))
        for text, var in [("개인정보 가리기", self.mask), ("이미 변환한 파일 건너뛰기", self.skip)]:
            box = ttk.Checkbutton(opts, text=text, variable=var)
            box.pack(side="left", padx=(0, 20))
            self.locked.append(box)
        ttk.Label(outer, text="원본은 그대로 보존합니다. PDF는 글자만 변환하며 그림·스캔 OCR은 지원하지 않습니다.", foreground="#596980").pack(anchor="w")
        row = ttk.Frame(outer)
        row.pack(fill="x", pady=14)
        for text, command, accent in [("샘플로 테스트", self.sample, False), ("폴더 확인", lambda: self.start("scan"), False), ("변환 시작", lambda: self.start("convert"), True)]:
            btn = ttk.Button(row, text=text, command=command, style="Accent.TButton" if accent else "TButton")
            btn.pack(side="left", padx=(0, 8))
            self.locked.append(btn)
        self.stop_button = ttk.Button(row, text="중지", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Button(row, text="사용 방법", command=self.help).pack(side="right")
        self.bar = ttk.Progressbar(outer, maximum=100)
        self.bar.pack(fill="x")
        ttk.Label(outer, textvariable=self.status, wraplength=920).pack(anchor="w", pady=(7, 12))
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True)
        results = ttk.Frame(tabs, padding=8)
        logs = ttk.Frame(tabs)
        tabs.add(results, text=" 변환 결과 ")
        tabs.add(logs, text=" 진행 내역 ")
        self.tabs = tabs
        self.table = ttk.Treeview(results, columns=("file",), show="headings", height=5)
        self.table.heading("file", text="결과 파일 · 선택하면 오른쪽에 표시")
        self.table.column("file", width=280)
        results.rowconfigure(0, weight=1)
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=3)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<<TreeviewSelect>>", self.preview)
        self.preview_text = ScrolledText(results, height=6, width=48, font=("맑은 고딕", 10), wrap="word", state="disabled")
        self.preview_text.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.log_text = ScrolledText(logs, height=6, font=("맑은 고딕", 10), wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", before=tabs, pady=(12, 0))
        self.open_folder = ttk.Button(footer, text="결과 폴더 열기", command=self.reveal_output, state="disabled")
        self.open_folder.pack(side="left")
        self.open_file = ttk.Button(footer, text="선택한 파일 열기", command=self.open_selected, state="disabled")
        self.open_file.pack(side="left", padx=8)
        ttk.Label(footer, text="PKOS · 개인지식운영체계", foreground="#596980").pack(side="right")

    def browse(self, var):
        path = filedialog.askdirectory(parent=self, title="폴더 선택", mustexist=True)
        if path:
            var.set(path)

    def help(self):
        messagebox.showinfo("사용 방법", "1. Windows 탐색기에서 원본 폴더를 엽니다.\n2. 주소 표시줄 클릭 → Ctrl+C로 경로를 복사합니다.\n3. 앱의 원본 폴더 칸에 Ctrl+V로 붙여넣습니다.\n   폴더 우클릭 → 경로로 복사의 따옴표도 처리합니다.\n4. 결과 폴더를 선택합니다. 새 폴더 경로를 입력해도 됩니다.\n5. 폴더 확인 → 변환 시작을 누릅니다.\n6. 완료 후 결과 파일을 선택해 미리 보거나 결과 폴더를 엽니다.\n\nG:\내 드라이브 경로는 Drive 데스크톱 앱에서 접근 가능해야 합니다.\n구글 문서·시트·슬라이드는 Office 파일로 내려받아 넣거나 코랩 3부를 이용하세요.\n\n개인정보 자동 가리기는 오탐·누락이 있을 수 있습니다. 결과를 확인하세요.\n원본 이름과 경로는 결과 메타데이터에 남을 수 있습니다.", parent=self)

    def sample(self):
        try:
            base = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "PKOS" / "샘플"
            src, dst = prepare_sample(base)
            self.source.set(str(src))
            self.output.set(str(dst))
            self.start("sample")
        except Exception as exc:
            messagebox.showerror("샘플 준비 실패", str(exc), parent=self)

    def set_busy(self, value):
        self.busy = value
        for widget in self.locked:
            widget.configure(state="disabled" if value else "normal")
        self.stop_button.configure(state="normal" if value else "disabled")

    def start(self, mode):
        if self.busy:
            return
        try:
            src, dst = validate_folders(self.source.get(), self.output.get())
        except ValueError as exc:
            messagebox.showerror("경로 확인", str(exc), parent=self)
            return
        self.save_settings()
        self.cancel.clear()
        self.set_busy(True)
        self.output_path = None
        self.open_folder.configure(state="disabled")
        self.open_file.configure(state="disabled")
        self.table.delete(*self.table.get_children())
        self.result_paths.clear()
        self.set_text(self.preview_text, "")
        self.set_text(self.log_text, "")
        self.bar.configure(mode="indeterminate")
        self.bar.start(12)
        self.status.set("폴더를 확인하고 있습니다…")
        self.tabs.select(1)
        mask = self.mask.get() if mode != "sample" else False
        skip = self.skip.get() if mode != "sample" else False
        def work():
            try:
                fc = FolderConverter(FolderSettings(src_dir=str(src), out_dir=str(dst), 개인정보_가리기=mask, 보고서_원본표시=False, skip_existing=skip))
                fc.log = lambda *args: self.events.put(("log", " ".join(map(str, args))))
                if mode == "scan":
                    files = fc.collect()
                    fc.scan()
                    for path in files[:200]:
                        fc.log(str(Path(path).relative_to(src)))
                    self.events.put(("scan_done", len(files)))
                else:
                    result = fc.run(progress=lambda i, n, path: self.events.put(("progress", (i, n, Path(path).name))), cancel=self.cancel)
                    paths = [Path(fc.md_path_for(f)) for f in fc.collect() if Path(fc.md_path_for(f)).exists()]
                    for name in ("INDEX.md", "_오류.md", "_개인정보_보고서.md"):
                        if (dst / name).exists():
                            paths.append(dst / name)
                    self.events.put(("done", (result, dst, paths)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", data + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "progress":
                    i, n, name = data
                    self.bar.stop()
                    self.bar.configure(mode="determinate", value=(i-1)*100/max(n, 1))
                    self.status.set(f"{i} / {n} 처리 중 · {name}")
                else:
                    self.bar.stop()
                    self.bar.configure(mode="determinate", value=0)
                    self.set_busy(False)
                    if kind == "error":
                        self.status.set("처리 중 오류가 발생했습니다. 경로와 진행 내역을 확인해주세요.")
                        messagebox.showerror("변환 오류", data, parent=self)
                    elif kind == "scan_done":
                        self.status.set(f"변환 가능한 파일 {data}개 · 진행 내역에서 목록을 확인하세요.")
                    elif kind == "done":
                        result, dst, paths = data
                        self.output_path = dst
                        self.open_folder.configure(state="normal")
                        label = "중지됨" if result["cancelled"] else "완료"
                        self.status.set(f"{label} · 변환 {result['done']}개 / 건너뜀 {result['skipped']}개 / 실패 {result['failed']}개 · {dst}")
                        self.bar.configure(value=0 if result["cancelled"] else 100)
                        for path in paths:
                            item = self.table.insert("", "end", values=(str(path.relative_to(dst)),))
                            self.result_paths[item] = path
                        if paths:
                            item = self.table.get_children()[0]
                            self.table.selection_set(item)
                        self.tabs.select(0)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def preview(self, event=None):
        selected = self.table.selection()
        if selected:
            try:
                with self.result_paths[selected[0]].open(encoding="utf-8") as f:
                    text = f.read(100001)
                if len(text) > 100000:
                    text = text[:100000] + "\n\n[긴 파일은 앞부분만 표시합니다. 파일 열기로 전체를 확인하세요.]"
                self.set_text(self.preview_text, text)
                self.open_file.configure(state="normal")
            except OSError as exc:
                self.set_text(self.preview_text, str(exc))

    def open_path(self, path):
        try:
            os.startfile(str(path))
        except OSError as exc:
            messagebox.showerror("열기 실패", str(exc), parent=self)

    def reveal_output(self):
        if self.output_path:
            self.open_path(self.output_path)

    def open_selected(self):
        selected = self.table.selection()
        if selected:
            self.open_path(self.result_paths[selected[0]])

    def stop(self):
        self.cancel.set()
        self.stop_button.configure(state="disabled")
        self.status.set("현재 파일 처리를 마친 뒤 중지합니다…")

    def close(self):
        if self.busy:
            self.stop()
            messagebox.showinfo("중지 요청", "현재 파일을 마칠 때까지 기다린 뒤 창을 닫아주세요.", parent=self)
            return
        self.save_settings()
        self.destroy()


def smoke_test(destination):
    """배포 EXE 검증용. UI·샘플 변환을 실행하고 결과를 파일로 남긴다."""
    app = App()
    app.withdraw()
    app.update()
    src, dst = prepare_sample(Path(destination) / "sample")
    fc = FolderConverter(FolderSettings(src_dir=str(src), out_dir=str(dst), 개인정보_가리기=False, verbose=False, skip_existing=False))
    result = fc.run()
    assert result["done"] == 1 and result["failed"] == 0, result
    body = (dst / fc.records[0]["md"]).read_text(encoding="utf-8")
    assert "동해물과 백두산이" in body and "무궁화 삼천리 화려강산" in body
    # 실제 배포물에 새 읽기 엔진과 개인정보 수정이 들어갔는지 함께 확인한다.
    import zipfile
    extra = Path(destination) / "odt-source"
    extra.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(extra / "검증.odt", "w") as archive:
        archive.writestr("content.xml", '<office:document-content xmlns:office="o" '
                         'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
                         '<office:body><office:text><text:h text:outline-level="1">변환 확인</text:h>'
                         '<text:p>주민등록번호: 991350-1234567</text:p>'
                         '</office:text></office:body></office:document-content>')
    odt_out = Path(destination) / "odt-result"
    odt = FolderConverter(FolderSettings(src_dir=str(extra), out_dir=str(odt_out),
                          개인정보_가리기=True, 보고서_원본표시=False, verbose=False, skip_existing=False))
    odt_result = odt.run()
    assert odt_result["done"] == 1 and odt_result["failed"] == 0, odt_result
    odt_body = (odt_out / odt.records[0]["md"]).read_text(encoding="utf-8")
    assert "변환 확인" in odt_body and "991350-1234567" not in odt_body and "******-*******" in odt_body
    app.destroy()
    Path(destination, "smoke-result.json").write_text(json.dumps(
        {"sample": result, "odt": odt_result, "privacy": True, "gui_init": True}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        smoke_test(sys.argv[2])
    else:
        App().mainloop()
