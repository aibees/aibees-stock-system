"""
clipboard_table_viewer.py
─────────────────────────
Ctrl+V 로 붙여넣기 하면 Excel 복사 내용을 테이블로 렌더링하는 tkinter GUI.

실행: python clipboard_table_viewer.py
"""

import csv
import io
import tkinter as tk
from tkinter import ttk


BG        = "#1e1e2e"
BG_HEADER = "#313244"
FG        = "#cdd6f4"
FG_DIM    = "#6c7086"
ACCENT    = "#89b4fa"
SEL_BG    = "#45475a"
FONT_BODY = ("Consolas", 11)
FONT_HEAD = ("Consolas", 11, "bold")


def parse_clipboard(text: str) -> list[list[str]]:
    """탭 구분 텍스트(Excel 복사 포맷) → 2D 리스트"""
    reader = csv.reader(io.StringIO(text.strip()), delimiter="\t")
    return [row for row in reader if any(cell.strip() for cell in row)]


class ClipboardTableViewer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Clipboard Table Viewer")
        self.root.configure(bg=BG)
        self.root.geometry("900x520")
        self.root.minsize(500, 300)

        self._build_ui()
        # bind_all: 포커스 위치 상관없이 앱 전체에서 이벤트 수신
        self.root.bind_all("<Control-v>", self._on_paste)
        self.root.bind_all("<Command-v>", self._on_paste)  # macOS

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 상단 상태바
        top = tk.Frame(self.root, bg=BG, pady=6)
        top.pack(fill="x", padx=12)

        self.status_var = tk.StringVar(value="Excel에서 셀을 복사한 뒤 Ctrl+V 하세요.")
        tk.Label(
            top, textvariable=self.status_var,
            bg=BG, fg=FG_DIM, font=("Consolas", 10)
        ).pack(side="left")

        tk.Button(
            top, text="초기화", command=self._clear,
            bg=BG_HEADER, fg=FG, relief="flat",
            font=("Consolas", 10), padx=10, cursor="hand2"
        ).pack(side="right")

        # 구분선
        tk.Frame(self.root, bg=BG_HEADER, height=1).pack(fill="x")

        # 테이블 영역
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="both", expand=True, padx=12, pady=10)

        self._style_treeview()

        self.tree = ttk.Treeview(frame, style="Custom.Treeview", show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        # 스크롤바
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(self.root, orient="horizontal", command=self.tree.xview)
        hsb.pack(fill="x", padx=12, pady=(0, 8))

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 행 홀짝 색상
        self.tree.tag_configure("odd",  background=BG)
        self.tree.tag_configure("even", background=BG_HEADER)

    def _style_treeview(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(
            "Custom.Treeview",
            background=BG,
            foreground=FG,
            fieldbackground=BG,
            font=FONT_BODY,
            rowheight=26,
        )
        s.configure(
            "Custom.Treeview.Heading",
            background=BG_HEADER,
            foreground=ACCENT,
            font=FONT_HEAD,
            relief="flat",
        )
        s.map(
            "Custom.Treeview",
            background=[("selected", SEL_BG)],
            foreground=[("selected", FG)],
        )
        s.map(
            "Custom.Treeview.Heading",
            background=[("active", SEL_BG)],
        )

    # ── 테이블 렌더링 ────────────────────────────────────────────────────────

    def _render(self, rows: list[list[str]]):
        """rows → Treeview 렌더링. 첫 행을 헤더로 사용."""
        self._clear_tree()

        if not rows:
            return

        headers = rows[0]
        data    = rows[1:]

        # 컬럼 설정
        self.tree["columns"] = headers
        for col in headers:
            self.tree.heading(col, text=col)
            # 컬럼 너비: 내용 길이 기반 자동 조정
            max_len = max(
                (len(str(r[headers.index(col)])) for r in data if headers.index(col) < len(r)),
                default=len(col),
            )
            width = min(max(max_len * 9, len(col) * 10 + 20), 280)
            self.tree.column(col, width=width, anchor="center", minwidth=60)

        # 행 삽입
        for i, row in enumerate(data):
            tag = "even" if i % 2 == 0 else "odd"
            # 컬럼 수 맞추기 (빈 셀 패딩)
            padded = row + [""] * (len(headers) - len(row))
            self.tree.insert("", "end", values=padded[: len(headers)], tags=(tag,))

        n_rows = len(data)
        n_cols = len(headers)
        self.status_var.set(f"✔  {n_rows}행 × {n_cols}열  |  첫 행을 헤더로 인식했습니다.")

    def _clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []

    def _clear(self):
        self._clear_tree()
        self.status_var.set("초기화 완료. Excel에서 셀을 복사한 뒤 Ctrl+V 하세요.")

    # ── 붙여넣기 이벤트 ──────────────────────────────────────────────────────

    def _on_paste(self, event=None):
        try:
            clip = self.root.clipboard_get()
        except tk.TclError:
            return

        rows = parse_clipboard(clip)
        if rows:
            self._render(rows)


def main():
    root = tk.Tk()
    ClipboardTableViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
