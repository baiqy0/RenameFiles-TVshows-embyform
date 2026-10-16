# -*- coding: utf-8 -*-
"""
批量重命名 v5 —— ops5.5 审美版（浅色奶油 / 深色暖夜 双主题，右上角开关切换）

在 v4 的基础上：
  * 界面按「奶油暖底 + 陶土色点缀 + 衬线斜体标题 + 等宽编号标签 + 胶囊按钮」重做
  * 深色模式走暖夜色调（不是纯黑），右上角胶囊开关一键切换，选择会记住
  * 重命名前先预览（旧名 -> 新名），冲突标红，安全第一
  * 新增「撤销上一批」，改错了能一键改回来
  * 修掉两个 v4 的隐患：目标文件已存在时会被静默覆盖；文件夹也会被误当成文件改名

重命名规则与 v4 完全一致：{剧名}{集数格式}{集号:03d}{字幕后缀}.{后缀}

打包成 exe（在本文件所在目录执行，cmd / PowerShell 都可以）：
  python -m venv .build/venv
  .build/venv/Scripts/python.exe -m pip install pyinstaller
  .build/venv/Scripts/python.exe make_ico.py
  .build/venv/Scripts/python.exe -m PyInstaller --onefile --windowed --name "批量重命名_v5" --icon icon.ico --distpath dist --workpath .build/work --specpath .build 批量重命名_v5.py
产物：dist/批量重命名_v5.exe
"""

import math
import os
import re
import tkinter as tk
from tkinter import filedialog

# ------------------------------------------------------------------
# 主题：ops5.5 那套「奶油纸感 + 陶土色 + 衬线斜体 + 等宽标签」的审美
# 浅色 = 奶油暖底；深色 = 暖夜（刻意不用纯黑，保持纸感的暖度）
# ------------------------------------------------------------------
THEMES = {
    "light": dict(
        bg="#F5F4ED",      # 暖象牙白（画布底色）
        card="#FFFFFF",    # 卡片 / 预览列表
        ink="#1F1E1B",     # 主文字（暖黑）
        ink2="#6B675E",    # 次要文字
        muted="#9B968A",   # 标签灰
        line="#E3E0D6",    # 分隔线 / 边框
        under="#C9C4B8",   # 输入框下划线
        accent="#D97757",  # 陶土色（品牌点缀色）
        accent_d="#C56A4B",
        accent_s="#F3E3DC",
        ok="#5F7F62",
        warn="#B5462F",
        cream_tx="#FFF9F2",
        thumb="#D8D4C8",
        ghost_hover="#EDEAE0",
        pill_off_bg="#ECE9DF",
        pill_off_fg="#BDB8AB",
    ),
    "dark": dict(
        bg="#211F1C",
        card="#2B2925",
        ink="#EDEBE3",
        ink2="#B4AFA3",
        muted="#8A857A",
        line="#3C3A35",
        under="#4C4A43",
        accent="#D97757",
        accent_d="#C56A4B",
        accent_s="#4A3830",
        ok="#7FA882",
        warn="#D9705A",
        cream_tx="#FFF9F2",
        thumb="#4C4A43",
        ghost_hover="#33322D",
        pill_off_bg="#2C2B26",
        pill_off_fg="#5F5C52",
    ),
}

_theme_name = "light"
T = THEMES["light"]

ICON_CREAM = "#F5F4ED"   # 任务栏图标永远用奶油底（品牌标记，不随主题变）

WIN_TITLE = "批量重命名 v5"


def set_theme(name, persist=False):
    """切换当前主题；persist=True 时把选择写进 %APPDATA%，下次启动生效。"""
    global _theme_name, T
    if name not in THEMES:
        return
    _theme_name = name
    T = THEMES[name]
    if persist:
        try:
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            with open(os.path.join(base, "RenamerTheme"), "w", encoding="utf-8") as f:
                f.write(name)
        except Exception:
            pass


def load_theme():
    """读回上次选择的主题，没有记录就用浅色（v4 用户的老审美）。"""
    try:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        with open(os.path.join(base, "RenamerTheme"), encoding="utf-8") as f:
            v = f.read().strip()
        if v in THEMES:
            return v
    except Exception:
        pass
    return "light"


# ------------------------------------------------------------------
# 纯逻辑部分（不依赖界面，方便单独测试）
# ------------------------------------------------------------------
def natural_key(name):
    """自然排序键：让 ep2 排在 ep10 前面（v4 的 sorted 会把 ep10 排前面）。"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def scan_files(folder, ext):
    """按自然顺序返回文件夹内指定后缀的文件名列表（只看文件，跳过文件夹）。"""
    ext = ext.strip().lstrip(".")
    if not folder or not ext or not os.path.isdir(folder):
        return []
    out = []
    for n in os.listdir(folder):
        if n.lower().endswith("." + ext.lower()) and os.path.isfile(os.path.join(folder, n)):
            out.append(n)
    return sorted(out, key=natural_key)


def build_pairs(folder, series, prefix, start, suffix, ext):
    """
    根据输入生成重命名计划。
    返回 (pairs, rows)：
      pairs -- 需要执行的 (旧路径, 新路径)
      rows  -- 预览用 (旧名, 新名, 状态, 备注)，状态 ok / skip / conflict
    """
    ext = ext.strip().lstrip(".")
    names = scan_files(folder, ext)
    srcs = {os.path.join(folder, n) for n in names}
    pairs, rows = [], []
    seen_dst = set()
    for i, name in enumerate(names):
        new_name = "%s%s%03d%s.%s" % (series, prefix, start + i, suffix, ext)
        src = os.path.join(folder, name)
        dst = os.path.join(folder, new_name)
        if dst == src:
            rows.append((name, new_name, "skip", "名称未变"))
            continue
        if os.path.exists(dst) and dst not in srcs:
            # 目标已存在、且这个已存在的文件不在本次批量里 -> 真正的冲突，不能动
            rows.append((name, new_name, "conflict", "目标已存在"))
            continue
        if dst in seen_dst:
            rows.append((name, new_name, "conflict", "批量内重名"))
            continue
        seen_dst.add(dst)
        pairs.append((src, dst))
        rows.append((name, new_name, "ok", ""))
    return pairs, rows


def safe_rename(pairs):
    """
    按 pairs 执行重命名。
    如果出现「新名字正好是别人旧名字」的链式情况（比如 001.mp4 -> 002.mp4，
    而 002.mp4 本身也要被改名），先全部改成临时名、再改成终名，
    否则直接 rename 会把还没改名的文件覆盖掉（v4 就会丢数据）。
    """
    srcs = {s for s, _ in pairs}
    if any(d in srcs for _, d in pairs):
        tmp_pairs = []
        for i, (src, dst) in enumerate(pairs):
            tmp = "%s.__renamer_tmp_%d__" % (src, i)
            os.rename(src, tmp)
            tmp_pairs.append((tmp, dst))
        for tmp, dst in tmp_pairs:
            os.rename(tmp, dst)
    else:
        for src, dst in pairs:
            os.rename(src, dst)


def _short(s, n=44):
    return s if len(s) <= n else s[: n - 10] + "..." + s[-9:]


# ------------------------------------------------------------------
# 字体
# ------------------------------------------------------------------
F_DISP   = ("Georgia", 21, "italic")   # 大标题：衬线斜体
F_MONO   = ("Consolas", 9)             # 分区标签：等宽
F_MONO_S = ("Consolas", 8)
F_BODY   = ("Segoe UI", 10)            # 正文
F_BODY_B = ("Segoe UI", 10, "bold")
F_LIST   = ("Consolas", 9)             # 预览列表
F_STATUS = ("Segoe UI", 9)


# ------------------------------------------------------------------
# 绘制小工具
# ------------------------------------------------------------------
def _round_pts(x0, y0, x1, y1, r, n=16):
    """圆角矩形的多边形顶点（Tk 的 Canvas 没有圆角矩形原语，用多边形近似）。"""
    pts = []
    corners = ((x1 - r, y0 + r, -90, 0), (x1 - r, y1 - r, 0, 90),
               (x0 + r, y1 - r, 90, 180), (x0 + r, y0 + r, 180, 270))
    for cx, cy, a0, a1 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.extend((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_star(canv, cx, cy, r, color, width=2):
    """六角星（和图标同款）：三条过中心的直线。"""
    canv.delete("all")
    for a in (90, 150, 30):
        rad = math.radians(a)
        dx, dy = r * math.cos(rad), r * math.sin(rad)
        canv.create_line(cx - dx, cy - dy, cx + dx, cy + dy,
                         fill=color, width=width, capstyle=tk.ROUND)


def draw_card_bg(canv):
    """预览卡片的圆角底。"""
    canv.delete("bg")
    w = max(canv.winfo_width(), 50)
    h = max(canv.winfo_height(), 50)
    pts = _round_pts(1, 1, w - 1, h - 1, 14)
    canv.create_polygon(pts, fill=T["card"], outline=T["line"], width=1, tags="bg")
    canv.tag_lower("bg")


def icon_pixels(size=64):
    """
    现画一个图标：奶油圆角方块 + 陶土色六角星。
    返回 (r, g, b, a) 二维列表，.ico 和运行时图标都用它，不依赖任何图片文件。
    """
    bgc = (0xF5, 0xF4, 0xED, 255)
    fgc = (0xD9, 0x77, 0x57, 255)
    cx = cy = (size - 1) / 2.0
    r_corner = size * 0.22
    half = size / 2.0 - size * 0.04
    thick = max(2.0, size * 0.10)   # 星芒粗细
    spoke = size * 0.30             # 星芒半长
    lines = [math.radians(a) for a in (90, 150, 30)]
    px = []
    for y in range(size):
        row = []
        for x in range(size):
            dx = abs(x - cx) - (half - r_corner)
            dy = abs(y - cy) - (half - r_corner)
            if dx > 0 and dy > 0 and dx * dx + dy * dy > r_corner * r_corner:
                row.append((0, 0, 0, 0))          # 圆角外 -> 透明
                continue
            on = False
            for a in lines:
                dist = abs(-math.sin(a) * (x - cx) + math.cos(a) * (y - cy))
                along = math.cos(a) * (x - cx) + math.sin(a) * (y - cy)
                if dist <= thick / 2.0 and abs(along) <= spoke:
                    on = True
                    break
            row.append(fgc if on else bgc)
        px.append(row)
    return px


def make_photo_icon(size=64):
    """把 icon_pixels 变成 tk.PhotoImage，用于任务栏 / 标题栏图标。"""
    px = icon_pixels(size)
    rows = []
    for row in px:
        rows.append("{" + " ".join("#%02x%02x%02x" % p[:3] if p[3] else ICON_CREAM
                                   for p in row) + "}")
    img = tk.PhotoImage(width=size, height=size)
    img.put(" ".join(rows))
    return img


# ------------------------------------------------------------------
# Windows 小优化：标题栏颜色跟着主题走、高 DPI 下不模糊
# ------------------------------------------------------------------
def blend_titlebar(win, hexrgb, dark=False):
    """
    Win11：标题栏/边框染成主题底色；Win10（19041+）深色模式可用沉浸式暗色标题栏。
    都不支持就安静跳过。
    """
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        rgb = int(hexrgb[1:], 16)
        colorref = ((rgb & 0xFF) << 16) | (rgb & 0xFF00) | ((rgb >> 16) & 0xFF)
        c = ctypes.c_uint(colorref)
        flag = ctypes.c_int(1 if dark else 0)
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(flag), 4)   # 沉浸式明暗
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(c), 4)     # 标题栏颜色
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(c), 4)     # 边框颜色
    except Exception:
        pass


def enable_dpi_awareness():
    """高缩放下字号不发糊。"""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDpiAware()
        except Exception:
            pass


# ------------------------------------------------------------------
# 自定义控件
# ------------------------------------------------------------------
class PillButton(tk.Canvas):
    """胶囊按钮：Canvas 画圆角矩形，支持 悬停 / 按下 / 禁用 三种状态。"""

    def __init__(self, master, text, command=None, kind="ghost", w=120, h=34):
        try:
            pbg = master.cget("bg")
        except Exception:
            pbg = T["bg"]
        super().__init__(master, width=w, height=h, bg=pbg, highlightthickness=0, bd=0)
        self.text = text
        self.command = command
        self.kind = kind
        self._state = "normal"
        self._enabled = True
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._set_state("hover"))
        self.bind("<Leave>", lambda e: self._set_state("normal"))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _palette(self):
        if not self._enabled:
            return {"bg": T["pill_off_bg"], "fg": T["pill_off_fg"], "border": None}
        if self.kind == "primary":
            bg = T["accent"] if self._state == "normal" else T["accent_d"]
            return {"bg": bg, "fg": T["cream_tx"], "border": None}
        bg = T["ghost_hover"] if self._state == "hover" else T["bg"]
        fg = T["ink"] if self._state == "hover" else T["ink2"]
        bd = T["under"] if self._state == "hover" else T["line"]
        return {"bg": bg, "fg": fg, "border": bd}

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 10)
        h = max(self.winfo_height(), 10)
        p = self._palette()
        pts = _round_pts(1.5, 1.5, w - 1.5, h - 1.5, h / 2.0 - 1.0)
        if p["border"]:
            self.create_polygon(pts, fill=p["bg"], outline=p["border"], width=1)
        else:
            self.create_polygon(pts, fill=p["bg"], outline="")
        self.create_text(w / 2.0, h / 2.0, text=self.text, fill=p["fg"],
                         font=F_BODY_B if self.kind == "primary" else F_BODY)

    def _set_state(self, s):
        if not self._enabled:
            return
        self._state = s
        self._draw()

    def _on_press(self, _):
        if self._enabled:
            self._state = "hover"
            self._draw()

    def _on_release(self, e):
        if not self._enabled:
            return
        self._state = "normal"
        self._draw()
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        if inside and self.command:
            self.command()

    def set_enabled(self, on):
        self._enabled = bool(on)
        self._state = "normal"
        self.configure(cursor="hand2" if on else "")
        self._draw()


class ToggleSwitch(tk.Canvas):
    """右上角的小胶囊开关：深色 / 浅色切换。"""

    W, H = 46, 24

    def __init__(self, master, command=None):
        try:
            pbg = master.cget("bg")
        except Exception:
            pbg = T["bg"]
        super().__init__(master, width=self.W, height=self.H, bg=pbg,
                         highlightthickness=0, bd=0)
        self.command = command
        self._on = (_theme_name == "dark")
        self._role = "toggle"
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.draw()

    def _click(self, _):
        self._on = not self._on
        self.draw()
        if self.command:
            self.command()

    def sync(self):
        self._on = (_theme_name == "dark")
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.W, self.H
        r = h / 2.0
        track = T["accent"] if self._on else T["under"]
        pts = _round_pts(1, 1, w - 1, h - 1, r)
        self.create_polygon(pts, fill=track, outline="")
        pad = 3.0
        kr = r - pad
        cx = w - pad - kr if self._on else pad + kr
        cy = h / 2.0
        self.create_oval(cx - kr, cy - kr, cx + kr, cy + kr,
                         fill=T["cream_tx"], outline="")


# ------------------------------------------------------------------
# 主界面
# ------------------------------------------------------------------
class RenamerApp:
    def __init__(self):
        self.win = tk.Tk()
        self.win.title(WIN_TITLE)
        self.win.geometry("640x730")
        self.win.minsize(600, 690)
        self.win.configure(bg=T["bg"])
        self.history = []      # 撤销栈：每次成功重命名记一笔
        self._pairs = []       # 当前预览算出来的重命名计划
        self._status_color = T["ink2"]
        self._lines = []       # [(entry, underline_frame)]，换主题时要重涂
        self._build()

        # 窗口居中
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry("+%d+%d" % (max(0, (sw - 640) // 2), max(0, (sh - 730) // 2)))

        # 标题栏 / 任务栏小图标（代码现画，不依赖图片文件）
        try:
            self.win.iconphoto(True, make_photo_icon(64))
        except Exception:
            pass

        blend_titlebar(self.win, T["bg"], dark=(_theme_name == "dark"))
        self.refresh_preview()

    # ---------------- 搭建界面 ----------------
    def _build(self):
        w = self.win

        # 头部：六角星 + 衬线斜体大标题 + 右侧主题开关
        head = tk.Frame(w, bg=T["bg"])
        head.pack(fill=tk.X, padx=36, pady=(26, 0))
        star = tk.Canvas(head, width=26, height=26, bg=T["bg"], highlightthickness=0, bd=0)
        draw_star(star, 13, 13, 8, T["accent"], 2)
        star._role = "star"
        star.pack(side=tk.LEFT)
        title = tk.Label(head, text="Renamer", font=F_DISP, bg=T["bg"], fg=T["ink"])
        title._role = "title"
        title.pack(side=tk.LEFT, padx=(9, 8))
        v5 = tk.Label(head, text="v5", font=F_MONO_S, bg=T["bg"], fg=T["muted"])
        v5._role = "muted"
        v5.pack(side=tk.LEFT, pady=(9, 0))

        right = tk.Frame(head, bg=T["bg"])
        right.pack(side=tk.RIGHT)
        lab = tk.Label(right, text="深色模式", font=F_MONO_S, bg=T["bg"], fg=T["muted"])
        lab._role = "muted"
        lab.pack(side=tk.LEFT, padx=(0, 8), pady=(3, 0))
        self.toggle = ToggleSwitch(right, command=self.switch_theme)
        self.toggle.pack(side=tk.LEFT)

        sub = tk.Label(w, text="批 量 重 命 名  ·  BATCH RENAME TOOL",
                       font=F_MONO_S, bg=T["bg"], fg=T["muted"])
        sub._role = "muted"
        sub.pack(anchor=tk.W, padx=71, pady=(3, 0))
        div = tk.Frame(w, height=1, bg=T["line"])
        div._role = "divider"
        div.pack(fill=tk.X, padx=36, pady=(14, 0))

        body = tk.Frame(w, bg=T["bg"])
        body.pack(fill=tk.X, padx=36, pady=(16, 0))

        # 01 文件夹路径
        self._field_label(body, "01", "文件夹路径")
        row = tk.Frame(body, bg=T["bg"])
        row.pack(fill=tk.X, pady=(4, 0))
        left = tk.Frame(row, bg=T["bg"])
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.e_folder = self._entry(left)
        self._entry_line(left, self.e_folder)
        PillButton(row, "浏览", self.on_browse, "ghost", 72, 28).pack(
            side=tk.RIGHT, padx=(10, 0), pady=(0, 2))
        self._gap(body)

        # 02 ~ 06
        self.e_series = self._field(body, "02", "剧名")
        self.e_prefix = self._field(body, "03", "集数格式", "(-S01E / -E)")
        self.e_ext    = self._field(body, "04", "文件后缀", "(mp4 / nfo / srt)")
        self.e_start  = self._field(body, "05", "起始编号")
        self.e_suffix = self._field(body, "06", "字幕后缀", "(.chs / .eng)")

        # 两个贴心的默认值
        self.e_ext.insert(0, "mp4")
        self.e_start.insert(0, "1")

        # 07 预览卡片
        ph = tk.Frame(body, bg=T["bg"])
        ph.pack(fill=tk.X, pady=(2, 6))
        lab7 = self._field_label(ph, "07", "预览")
        self.count_var = tk.StringVar(value="...")
        cnt = tk.Label(lab7, textvariable=self.count_var, font=F_MONO_S,
                       bg=T["bg"], fg=T["muted"])
        cnt._role = "muted"
        cnt.pack(side=tk.RIGHT)

        self.card = tk.Canvas(body, bg=T["bg"], highlightthickness=0, height=168)
        self.card._role = "card"
        self.card.pack(fill=tk.X)
        self.lb = tk.Listbox(self.card, bd=0, highlightthickness=0, bg=T["card"],
                             fg=T["ink"], font=F_LIST, activestyle="none",
                             exportselection=False, selectbackground=T["accent_s"],
                             selectforeground=T["ink"])
        self.sb = tk.Scrollbar(self.card, bd=0, highlightthickness=0, width=10,
                               bg=T["thumb"], troughcolor=T["card"],
                               activebackground=T["accent"], command=self.lb.yview)
        self.lb.configure(yscrollcommand=self.sb.set)
        self.lb_win = self.card.create_window(12, 12, window=self.lb, anchor="nw")
        self.sb_win = self.card.create_window(0, 12, window=self.sb, anchor="nw", height=144)
        self.card.bind("<Configure>", self._on_card_configure)
        draw_card_bg(self.card)

        # 主按钮 + 状态行
        self.run_btn = PillButton(body, "批量重命名", self.on_run, "primary", 200, 38)
        self.run_btn.pack(fill=tk.X, pady=(14, 0))

        st = tk.Frame(body, bg=T["bg"])
        st.pack(fill=tk.X, pady=(12, 0))
        self.status_var = tk.StringVar(value="准备好了")
        self.status_lbl = tk.Label(st, textvariable=self.status_var, font=F_STATUS,
                                   bg=T["bg"], fg=T["ink2"])
        self.status_lbl._role = "status"
        self.status_lbl.pack(side=tk.LEFT)
        self.undo_btn = PillButton(st, "<- 撤销上一批", self.on_undo, "ghost", 118, 26)
        self.undo_btn.pack(side=tk.RIGHT)

        # 保留 v4 的经典提示
        ps = tk.Label(w, text="PS：确保你的文件能修改文件扩展名",
                      font=F_MONO_S, bg=T["bg"], fg=T["warn"])
        ps._role = "ps"
        ps.pack(anchor=tk.W, padx=36, pady=(12, 14))

    # ---------------- 主题切换 ----------------
    def switch_theme(self, name=None):
        if name is None:
            name = "dark" if _theme_name == "light" else "light"
        set_theme(name, persist=True)
        self._apply_theme()
        self._status("已切换到%s模式" % ("深色" if name == "dark" else "浅色"), T["ink2"])
        blend_titlebar(self.win, T["bg"], dark=(name == "dark"))

    def _iter_widgets(self, wd):
        yield wd
        for c in wd.winfo_children():
            yield from self._iter_widgets(c)

    def _apply_theme(self):
        """遍历所有控件重涂颜色（Canvas 画的元素各自重画）。"""
        self.win.configure(bg=T["bg"])
        focus = self.win.focus_get()
        for wd in self._iter_widgets(self.win):
            if isinstance(wd, PillButton):
                wd._draw()
                continue
            if isinstance(wd, ToggleSwitch):
                wd.draw()
                continue
            if isinstance(wd, tk.Canvas):
                if getattr(wd, "_role", None) == "star":
                    draw_star(wd, 13, 13, 8, T["accent"], 2)
                elif getattr(wd, "_role", None) == "card":
                    draw_card_bg(wd)
                else:
                    wd.configure(bg=T["bg"])
            elif isinstance(wd, tk.Label):
                role = getattr(wd, "_role", None)
                if role == "title":
                    fg = T["ink"]
                elif role == "status":
                    fg = self._status_color
                elif role == "ps":
                    fg = T["warn"]
                elif role == "field_idx":
                    fg = T["accent"]
                else:
                    fg = T["muted"]
                wd.configure(bg=T["bg"], fg=fg)
            elif isinstance(wd, tk.Entry):
                wd.configure(bg=T["bg"], fg=T["ink"], insertbackground=T["accent"],
                             selectbackground=T["accent_s"], selectforeground=T["ink"])
            elif isinstance(wd, tk.Listbox):
                wd.configure(bg=T["card"], fg=T["ink"],
                             selectbackground=T["accent_s"], selectforeground=T["ink"])
            elif isinstance(wd, tk.Scrollbar):
                wd.configure(bg=T["thumb"], troughcolor=T["card"],
                             activebackground=T["accent"])
            elif isinstance(wd, tk.Frame):
                role = getattr(wd, "_role", None)
                if role == "divider":
                    wd.configure(bg=T["line"])
                elif role != "underline":
                    wd.configure(bg=T["bg"])
        # 下划线：焦点所在的那条用陶土色
        for e, line in self._lines:
            line.configure(bg=T["accent"] if e is focus else T["under"])
        self.toggle.sync()
        self.refresh_preview()

    # ---------------- 小组件工厂 ----------------
    def _field_label(self, parent, idx, label, hint=""):
        lab = tk.Frame(parent, bg=T["bg"])
        lab.pack(fill=tk.X)
        i = tk.Label(lab, text=idx, font=F_MONO, bg=T["bg"], fg=T["accent"])
        i._role = "field_idx"
        i.pack(side=tk.LEFT)
        t = tk.Label(lab, text="  " + label, font=F_MONO, bg=T["bg"], fg=T["muted"])
        t._role = "muted"
        t.pack(side=tk.LEFT)
        if hint:
            h = tk.Label(lab, text=hint, font=F_MONO_S, bg=T["bg"], fg=T["muted"])
            h._role = "muted"
            h.pack(side=tk.RIGHT)
        return lab

    def _entry(self, parent):
        e = tk.Entry(parent, bd=0, relief=tk.FLAT, highlightthickness=0, bg=T["bg"],
                     fg=T["ink"], font=F_BODY, insertbackground=T["accent"],
                     selectbackground=T["accent_s"], selectforeground=T["ink"])
        e.pack(fill=tk.X, pady=(4, 0))
        for ev in ("<KeyRelease>", "<<Paste>>", "<<Cut>>"):
            e.bind(ev, lambda _e: self.refresh_preview())
        return e

    def _entry_line(self, parent, entry):
        line = tk.Frame(parent, height=1, bg=T["under"])
        line._role = "underline"
        line.pack(fill=tk.X)
        entry.bind("<FocusIn>", lambda _e: line.configure(bg=T["accent"]))
        entry.bind("<FocusOut>", lambda _e: line.configure(bg=T["under"]))
        self._lines.append((entry, line))

    def _field(self, parent, idx, label, hint=""):
        self._field_label(parent, idx, label, hint)
        e = self._entry(parent)
        self._entry_line(parent, e)
        self._gap(parent)
        return e

    def _gap(self, parent, h=10):
        tk.Frame(parent, height=h, bg=T["bg"]).pack()

    # ---------------- 预览卡片 ----------------
    def _on_card_configure(self, e):
        draw_card_bg(self.card)
        w, h = e.width, e.height
        self.card.coords(self.lb_win, 12, 12)
        self.card.itemconfigure(self.lb_win, width=w - 30, height=h - 24)
        self.card.coords(self.sb_win, w - 14, 12)
        self.card.itemconfigure(self.sb_win, height=h - 24)

    # ---------------- 逻辑 ----------------
    def refresh_preview(self):
        """任何输入变化都实时重算预览。"""
        folder = self.e_folder.get().strip()
        self.lb.delete(0, tk.END)
        self._pairs = []
        if not folder or not os.path.isdir(folder):
            self.count_var.set("等待选择文件夹 ...")
            self._sync_buttons()
            return
        ext = self.e_ext.get().strip().lstrip(".")
        names = scan_files(folder, ext)
        if not ext:
            self.count_var.set("请填写文件后缀")
            self._sync_buttons()
            return
        try:
            start = int(self.e_start.get().strip())
        except ValueError:
            self.count_var.set("共 %d 个文件 · 起始编号需为整数" % len(names))
            for n in names[:300]:
                self.lb.insert(tk.END, _short(n))
            self._sync_buttons()
            return
        pairs, rows = build_pairs(folder, self.e_series.get(), self.e_prefix.get(),
                                  start, self.e_suffix.get(), ext)
        self._pairs = pairs
        n_conflict = sum(1 for r in rows if r[2] == "conflict")
        self.count_var.set("共 %d 个文件%s" % (
            len(names), (" · %d 个冲突" % n_conflict) if n_conflict else ""))
        for name, new_name, st, note in rows[:300]:
            if st == "ok":
                self.lb.insert(tk.END, "%s  ->  %s" % (_short(name), _short(new_name)))
                self.lb.itemconfig(tk.END, fg=T["ink"])
            elif st == "skip":
                self.lb.insert(tk.END, "%s  ·  名称未变" % _short(name))
                self.lb.itemconfig(tk.END, fg=T["muted"])
            else:
                self.lb.insert(tk.END, "%s  ->  %s   × %s" % (_short(name), _short(new_name), note))
                self.lb.itemconfig(tk.END, fg=T["warn"])
        if len(rows) > 300:
            self.lb.insert(tk.END, "... 其余 %d 个从略" % (len(rows) - 300))
            self.lb.itemconfig(tk.END, fg=T["muted"])
        self._sync_buttons()

    def _sync_buttons(self):
        self.run_btn.set_enabled(bool(self._pairs))
        self.undo_btn.set_enabled(bool(self.history))

    def _status(self, msg, color=None):
        if color is None:
            color = T["ink2"]
        self._status_color = color
        self.status_var.set("*  " + msg)
        self.status_lbl.configure(fg=color)

    def on_browse(self):
        path = filedialog.askdirectory()
        if path:
            self.e_folder.delete(0, tk.END)
            self.e_folder.insert(0, path)
            self.refresh_preview()

    def on_run(self):
        folder = self.e_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            self._status("请先选择有效的文件夹", T["warn"])
            return
        try:
            start = int(self.e_start.get().strip())
        except ValueError:
            self._status("起始编号需要是整数", T["warn"])
            return
        ext = self.e_ext.get().strip().lstrip(".")
        if not ext:
            self._status("请填写文件后缀（如 mp4）", T["warn"])
            return
        pairs, rows = build_pairs(folder, self.e_series.get(), self.e_prefix.get(),
                                  start, self.e_suffix.get(), ext)
        if not pairs:
            self._status("没有需要重命名的文件", T["ink2"])
            return
        bad = [r for r in rows if r[2] == "conflict"]
        if bad:
            self._status("存在 %d 个冲突，已中止（见预览标红项）" % len(bad), T["warn"])
            return
        try:
            safe_rename(pairs)
        except OSError as e:
            self._status("重命名失败：%s" % e, T["warn"])
            return
        self.history.append(pairs)
        self._status("已重命名 %d 个文件" % len(pairs), T["ok"])
        self.refresh_preview()

    def on_undo(self):
        if not self.history:
            return
        pairs = self.history.pop()
        try:
            safe_rename([(dst, src) for src, dst in reversed(pairs)])
        except OSError as e:
            self._status("撤销失败：%s" % e, T["warn"])
            return
        self._status("已撤销 %d 个文件" % len(pairs), T["ok"])
        self.refresh_preview()


def main():
    enable_dpi_awareness()
    set_theme(load_theme())
    app = RenamerApp()
    app.win.mainloop()


if __name__ == "__main__":
    main()
