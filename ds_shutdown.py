# -*- coding: utf-8 -*-
"""定时电源工具 - 支持定时关机 / 重启 / 睡眠 / 休眠 / 注销 / 锁屏。

功能：
- 两种定时方式：倒计时（时/分/秒）与指定时刻（如今天 23:30，自动跨天）。
- 六种动作：关机 / 重启 / 睡眠 / 休眠 / 注销 / 锁屏。
  · 关机、重启用 Windows 自带的 shutdown /t 定时（程序退出也照样执行）。
  · 睡眠 / 休眠 / 注销 / 锁屏没有系统延时，由本程序计时，到点执行（需保持运行）。
- 关机前提醒：可提前 30 秒 / 1 分钟 / 5 分钟弹窗，可「延后 5 分钟 / 立即执行 / 取消」。
- 自动记住上次的设置（动作、模式、数值、窗口大小）。
- 苹果风格浅色 UI、抗锯齿圆角、高 DPI 清晰、支持拖动边框等比缩放。

测试模式：设置环境变量 DSH_TEST_MODE=1 后运行，只记录将要执行的命令，不真正执行。
"""
import ctypes
import datetime
import json
import os
import subprocess
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageTk
    _HAS_PIL = True
except Exception:  # 没有 Pillow 时退化成多边形圆角
    _HAS_PIL = False

APP_NAME = "定时关机"
TEST_MODE = os.environ.get("DSH_TEST_MODE") == "1"

# ---------- 动作定义 ----------
ACTIONS = [
    ("shutdown", "关机"),
    ("restart", "重启"),
    ("sleep", "睡眠"),
    ("hibernate", "休眠"),
    ("logoff", "注销"),
    ("lock", "锁屏"),
]
ACTION_LABEL = dict(ACTIONS)
# 只有关机/重启支持 shutdown.exe 的 /t 延时
NATIVE_DELAY = {"shutdown", "restart"}

# ---------- 苹果风配色（浅色） ----------
BG = "#F2F2F7"
CARD = "#FFFFFF"
BORDER = "#E5E5EA"
TEXT = "#1D1D1F"
TEXT_DIM = "#8E8E93"
FIELD_BG = "#F2F2F7"
PILL_BG = "#E9E9EB"
ACCENT = "#007AFF"
DANGER = "#FF3B30"
GREEN = "#34C759"
ORANGE = "#FF9500"
DISABLED_BG = "#E9E9EB"
DISABLED_FG = "#C7C7CC"

# ---------- 设置文件 ----------
def _settings_candidates():
    """优先存到 %LOCALAPPDATA%，不可写时回退到程序同目录。"""
    paths = []
    base = os.environ.get("LOCALAPPDATA")
    if base:
        paths.append(os.path.join(base, "DSShutdown", "settings.json"))
    paths.append(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "settings.json"))
    return paths


SETTINGS_FILE = _settings_candidates()[0]


def load_settings():
    for path in _settings_candidates():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def save_settings(data):
    for path in _settings_candidates():
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path
        except Exception:
            continue
    return None


def _mix(hex_color, mix_color, ratio):
    """把两个十六进制颜色按比例混合（用于 hover/按下变暗）。"""
    hex_color = hex_color.lstrip("#")
    mix_color = mix_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    mr = int(mix_color[0:2], 16)
    mg = int(mix_color[2:4], 16)
    mb = int(mix_color[4:6], 16)
    r = int(r * (1 - ratio) + mr * ratio)
    g = int(g * (1 - ratio) + mg * ratio)
    b = int(b * (1 - ratio) + mb * ratio)
    return "#%02x%02x%02x" % (r, g, b)


def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """在 Canvas 上画一个圆角矩形（无抗锯齿，仅作无 Pillow 时的回退）。"""
    points = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
              x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
              x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
              x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kw)


_SS = 4  # 超采样倍数：先按 4 倍画、再用 LANCZOS 缩回，得到抗锯齿的细腻边缘


def _hex_to_rgb(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _rounded_pil(w, h, radius, fill, bg, outline=None, outline_width=0):
    """生成抗锯齿的圆角矩形 PIL 图像（4 倍超采样后 LANCZOS 缩小）。"""
    if not _HAS_PIL:
        return None
    w = max(1, int(w))
    h = max(1, int(h))
    radius = max(0, min(int(radius), min(w, h) // 2))
    W, H = w * _SS, h * _SS
    img = Image.new("RGB", (W, H), _hex_to_rgb(bg))
    d = ImageDraw.Draw(img)
    box = [0, 0, W - 1, H - 1]
    if outline and outline_width > 0:
        d.rounded_rectangle(box, radius=radius * _SS, fill=_hex_to_rgb(fill),
                            outline=_hex_to_rgb(outline),
                            width=max(1, int(outline_width * _SS)))
    else:
        d.rounded_rectangle(box, radius=radius * _SS, fill=_hex_to_rgb(fill))
    return img.resize((w, h), Image.LANCZOS)


def _rounded_photo(w, h, radius, fill, bg, outline=None, outline_width=0):
    """把抗锯齿圆角矩形包成 Tk PhotoImage（无 PIL 时返回 None）。"""
    img = _rounded_pil(w, h, radius, fill, bg, outline, outline_width)
    if img is None:
        return None
    return ImageTk.PhotoImage(img)


def _enable_dpi_awareness():
    """让程序感知高 DPI，避免被 Windows 拉伸而模糊（4K 屏幕必需）。"""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def log(msg: str):
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsh_test.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


# ---------- 动作执行 ----------
def _run(cmd):
    log("EXEC: " + subprocess.list2cmdline(cmd))
    if TEST_MODE:
        return True
    try:
        subprocess.run(cmd, check=True, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except subprocess.CalledProcessError as e:
        log("ERR: " + str(e))
        return False
    except Exception as e:
        log("ERR: " + repr(e))
        return False


def schedule_native(action, seconds, force):
    """用 shutdown.exe 的 /t 定时（仅关机、重启支持）。"""
    if action not in NATIVE_DELAY:
        return False
    cmd = ["shutdown", "/s" if action == "shutdown" else "/r",
           "/t", str(max(1, int(seconds)))]
    if force:
        cmd.append("/f")
    return _run(cmd)


def abort_native():
    """取消系统层面的关机/重启倒计时。"""
    log("EXEC: shutdown /a")
    if TEST_MODE:
        return True
    try:
        subprocess.run(["shutdown", "/a"], check=True, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except subprocess.CalledProcessError as e:
        if e.returncode == 1116:   # 没有正在进行的关机
            return True
        log("ERR(shutdown /a): " + str(e))
        return False
    except Exception as e:
        log("ERR(shutdown /a): " + repr(e))
        return False


def run_action_now(action, force=False):
    """立即执行指定动作。"""
    if action in NATIVE_DELAY:
        cmd = ["shutdown", "/s" if action == "shutdown" else "/r", "/t", "0"]
        if force:
            cmd.append("/f")
        return _run(cmd)
    if action == "hibernate":
        return _run(["shutdown", "/h"])
    if action == "logoff":
        return _run(["shutdown", "/l"])
    if action == "lock":
        log("EXEC: LockWorkStation()")
        if TEST_MODE:
            return True
        try:
            return bool(ctypes.windll.user32.LockWorkStation())
        except Exception as e:
            log("ERR(lock): " + repr(e))
            return False
    if action == "sleep":
        log("EXEC: SetSuspendState(False, True, False)")
        if TEST_MODE:
            return True
        try:
            fn = ctypes.windll.powrprof.SetSuspendState
            fn.argtypes = [ctypes.c_bool, ctypes.c_bool, ctypes.c_bool]
            fn.restype = ctypes.c_bool
            return bool(fn(False, True, False))
        except Exception as e:
            log("ERR(sleep): " + repr(e))
            return _run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    return False


class Card(tk.Canvas):
    """圆角白色卡片：抗锯齿圆角底图 + 内部承载内容的 Frame。"""

    def __init__(self, master, width, height, parent_bg=BG, bg=CARD,
                 radius=20, border=BORDER, border_width=1):
        super().__init__(master, width=width, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self._card_img = _rounded_photo(width, height, radius, bg, parent_bg,
                                        outline=border, outline_width=border_width)
        if self._card_img is not None:
            self.create_image(0, 0, anchor="nw", image=self._card_img)
        else:
            _round_rect(self, 0, 0, width - 1, height - 1, radius, fill=bg,
                        outline=border, width=border_width, tags="cardbg")
        self.body = tk.Frame(self, bg=bg)
        inset = min(radius, 12)
        self.create_window(inset, inset, anchor="nw", window=self.body,
                           width=width - 2 * inset, height=height - 2 * inset)


class PillButton(tk.Canvas):
    """胶囊按钮：支持 hover / 按下 / 禁用 / 选中（分段选择）状态。"""

    def __init__(self, master, text, command, fill=ACCENT, fg="#FFFFFF",
                 parent_bg=BG, font=None, padx=26, pady=12,
                 sel_fill=None, sel_fg="#FFFFFF"):
        self.command = command
        self._fill = fill
        self._fg = fg
        self._sel_fill = sel_fill
        self._sel_fg = sel_fg
        self._selected = False
        self._enabled = True
        self._locked = False
        self._hovered = False
        self._font = font if font is not None else \
            tkfont.Font(family="Microsoft YaHei UI", size=12, weight="bold")
        tw = self._font.measure(text)
        th = self._font.metrics("linespace")
        w = tw + 2 * padx
        h = th + 2 * pady
        self._bw, self._bh = w, h
        self._text = text
        self._parent_bg = parent_bg
        self._imgs = {}
        super().__init__(master, width=w, height=h, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        if _HAS_PIL:
            self._bg_item = self.create_image(0, 0, anchor="nw",
                                              image=self._img(fill))
        else:
            self._bg_item = None
            _round_rect(self, 0, 0, w, h, h // 2, fill=fill, outline=fill,
                        tags="bg")
        self.create_text(w / 2, h / 2, text=text, fill=fg,
                         font=self._font, tags="txt")
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    # --- 绘制 ---
    def _img(self, fill):
        if fill not in self._imgs:
            self._imgs[fill] = _rounded_photo(self._bw, self._bh,
                                              self._bh // 2, fill,
                                              self._parent_bg)
        return self._imgs[fill]

    def _paint(self, fill):
        if self._bg_item is not None:
            self.itemconfig(self._bg_item, image=self._img(fill))
        else:
            self.delete("bg")
            _round_rect(self, 0, 0, self._bw, self._bh, self._bh // 2,
                        fill=fill, outline=fill, tags="bg")
            if self.find_withtag("txt"):
                self.tag_raise("txt")

    def _base_fill(self):
        if self._selected and self._sel_fill:
            return self._sel_fill
        return self._fill

    def _base_fg(self):
        if self._selected and self._sel_fill:
            return self._sel_fg
        return self._fg

    def _refresh(self):
        self._paint(self._base_fill())
        self.itemconfig("txt", fill=self._base_fg())

    # --- 交互 ---
    def _on_enter(self, _e):
        self._hovered = True
        if self._enabled and not self._locked:
            self._paint(_mix(self._base_fill(), "#000000", 0.06))

    def _on_leave(self, _e):
        self._hovered = False
        if self._enabled:
            self._refresh()

    def _on_press(self, _e):
        if not self._enabled or self._locked:
            return
        self._paint(_mix(self._base_fill(), "#000000", 0.14))
        if self.command:
            self.command()

    def _on_release(self, _e):
        if self._enabled:
            self._refresh()

    # --- 外部状态 ---
    def set_selected(self, selected: bool):
        self._selected = bool(selected)
        self._refresh()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if enabled:
            self.config(cursor="hand2")
            self._refresh()
        else:
            self.config(cursor="arrow")
            self._paint(DISABLED_BG)
            self.itemconfig("txt", fill=DISABLED_FG)

    def set_locked(self, locked: bool):
        """锁定点击但不改变外观（运行中禁止切换动作/模式）。"""
        self._locked = bool(locked)
        self.config(cursor="arrow" if locked else "hand2")


class App:
    BASE_W = 460
    BASE_H = 700
    MIN_RATIO = 0.7
    MAX_RATIO = 2.6
    RESIZE_DELAY = 70

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_NAME)
        root.configure(bg=BG)

        self.dpi = max(1.0, root.winfo_fpixels("1i") / 96.0)

        # ---------- 载入上次设置 ----------
        st = load_settings()
        self.action = st.get("action", "shutdown")
        if self.action not in ACTION_LABEL:
            self.action = "shutdown"
        self.mode = st.get("mode", "countdown")
        if self.mode not in ("countdown", "clock"):
            self.mode = "countdown"
        try:
            self.warn_seconds = int(st.get("warn", 60))
        except Exception:
            self.warn_seconds = 60

        self.var_h = tk.StringVar(value=str(st.get("h", "0")))
        self.var_m = tk.StringVar(value=str(st.get("m", "30")))
        self.var_s = tk.StringVar(value=str(st.get("s", "0")))
        self.var_th = tk.StringVar(value=str(st.get("th", "23")))
        self.var_tm = tk.StringVar(value=str(st.get("tm", "0")))
        self.var_force = tk.BooleanVar(value=bool(st.get("force", False)))

        try:
            self.cs = float(st.get("zoom", 1.0))
        except Exception:
            self.cs = 1.0
        self.cs = max(self.MIN_RATIO, min(self.cs, self.MAX_RATIO))

        # ---------- 运行状态 ----------
        self.remaining = 0
        self.running = False
        self._tick_job = None
        self._resize_job = None
        self._warned = False
        self._warn_dialog = None
        self._force_used = False

        self._status_text = "未设置"
        self._status_color = TEXT_DIM
        self._time_color = TEXT

        self.content = None
        self.lbl_status = None
        self.lbl_time = None

        root.resizable(True, True)
        root.minsize(self._px(self.BASE_W * self.MIN_RATIO),
                     self._px(self.BASE_H * self.MIN_RATIO))
        root.geometry("%dx%d" % (self._px(self.BASE_W), self._px(self.BASE_H)))

        self.var_th.trace_add("write", self._on_time_var)
        self.var_tm.trace_add("write", self._on_time_var)

        self._build()
        self._update_preview()
        root.bind("<Configure>", self._on_configure)

    # ---------- 尺寸换算 ----------
    def _px(self, v) -> int:
        return int(round(v * self.dpi * self.cs))

    def _pt(self, v) -> int:
        return max(1, int(round(v * self.cs)))

    # ---------- 设置持久化 ----------
    def _save_settings(self):
        save_settings({
            "action": self.action,
            "mode": self.mode,
            "h": self.var_h.get(), "m": self.var_m.get(), "s": self.var_s.get(),
            "th": self.var_th.get(), "tm": self.var_tm.get(),
            "force": bool(self.var_force.get()),
            "warn": self.warn_seconds,
            "zoom": round(self.cs, 3),
        })

    # ---------- 缩放 ----------
    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(self.RESIZE_DELAY, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w <= 1 or h <= 1:
            return
        cs = min(w / (self.BASE_W * self.dpi), h / (self.BASE_H * self.dpi))
        cs = max(self.MIN_RATIO, min(cs, self.MAX_RATIO))
        if abs(cs - self.cs) < 0.015:
            return
        self.cs = cs
        self._build()
        self.root.geometry("%dx%d" % (w, h))
        self._save_settings()

    # ---------- 界面 ----------
    def _build(self):
        if self.content is not None:
            self.content.destroy()

        W = self._px(self.BASE_W)
        M = self._px(18)
        card_w = W - 2 * M

        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True)
        self.content = outer
        inner = tk.Frame(outer, bg=BG)
        inner.pack(expand=True)

        # 标题
        tk.Label(inner, text=APP_NAME, bg=BG, fg=TEXT,
                 font=("Microsoft YaHei UI", self._pt(21), "bold")).pack(
            pady=(self._px(22), self._px(2)))
        tk.Label(inner, text="关机 · 重启 · 睡眠 · 休眠 · 注销 · 锁屏", bg=BG,
                 fg=TEXT_DIM, font=("Microsoft YaHei UI", self._pt(10))).pack()

        # 状态
        self.lbl_status = tk.Label(inner, text=self._status_text, bg=BG,
                                   fg=self._status_color,
                                   font=("Microsoft YaHei UI", self._pt(10), "bold"))
        self.lbl_status.pack(pady=(self._px(12), self._px(8)))

        # 大倒计时卡片
        timer_card = Card(inner, card_w, self._px(140), radius=self._px(22))
        timer_card.pack(padx=M)
        self.lbl_time = tk.Label(timer_card.body, text="00:00:00", bg=CARD,
                                 fg=self._time_color,
                                 font=("Segoe UI Light", self._pt(46)))
        self.lbl_time.pack(expand=True)

        # 动作选择
        act_row = tk.Frame(inner, bg=BG)
        act_row.pack(pady=(self._px(14), 0))
        self._action_btns = {}
        for key, label in ACTIONS:
            b = PillButton(act_row, label, lambda k=key: self._set_action(k),
                           fill=PILL_BG, fg=TEXT, parent_bg=BG,
                           font=tkfont.Font(family="Microsoft YaHei UI",
                                            size=self._pt(10)),
                           padx=self._px(9), pady=self._px(7),
                           sel_fill=ACCENT, sel_fg="#FFFFFF")
            b.pack(side="left", padx=self._px(3))
            b.set_selected(key == self.action)
            self._action_btns[key] = b

        # 定时方式
        mode_row = tk.Frame(inner, bg=BG)
        mode_row.pack(pady=(self._px(10), 0))
        self._mode_btns = {}
        for key, label in (("countdown", "倒计时"), ("clock", "指定时刻")):
            b = PillButton(mode_row, label, lambda k=key: self._set_mode(k),
                           fill=PILL_BG, fg=TEXT, parent_bg=BG,
                           font=tkfont.Font(family="Microsoft YaHei UI",
                                            size=self._pt(10)),
                           padx=self._px(16), pady=self._px(7),
                           sel_fill=TEXT, sel_fg="#FFFFFF")
            b.pack(side="left", padx=self._px(3))
            b.set_selected(key == self.mode)
            self._mode_btns[key] = b

        # 输入卡片
        in_card = Card(inner, card_w, self._px(96), radius=self._px(22))
        in_card.pack(padx=M, pady=(self._px(10), 0))
        if self.mode == "countdown":
            self._build_count_fields(in_card.body)
        else:
            self._build_clock_fields(in_card.body)

        # 强制关闭（仅关机/重启有效）
        self.chk_force = tk.Checkbutton(
            inner, text="强制关闭所有程序（不提示保存）",
            variable=self.var_force, bg=BG, fg=TEXT_DIM,
            activebackground=BG, activeforeground=TEXT, selectcolor=CARD,
            font=("Microsoft YaHei UI", self._pt(9)),
            highlightthickness=0, bd=0, command=self._on_force_toggle)
        self.chk_force.pack(pady=(self._px(10), 0))

        # 关机前提醒
        warn_row = tk.Frame(inner, bg=BG)
        warn_row.pack(pady=(self._px(8), 0))
        tk.Label(warn_row, text="提前提醒", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft YaHei UI", self._pt(9))).pack(
            side="left", padx=(0, self._px(8)))
        self._warn_btns = {}
        for secs, label in ((0, "不提醒"), (30, "30 秒"), (60, "1 分钟"),
                            (300, "5 分钟")):
            b = PillButton(warn_row, label, lambda s=secs: self._set_warn(s),
                           fill=PILL_BG, fg=TEXT, parent_bg=BG,
                           font=tkfont.Font(family="Microsoft YaHei UI",
                                            size=self._pt(9)),
                           padx=self._px(9), pady=self._px(5),
                           sel_fill=GREEN, sel_fg="#FFFFFF")
            b.pack(side="left", padx=self._px(3))
            b.set_selected(secs == self.warn_seconds)
            self._warn_btns[secs] = b

        # 快捷时长（仅倒计时模式）
        if self.mode == "countdown":
            quick = tk.Frame(inner, bg=BG)
            quick.pack(pady=(self._px(12), 0))
            for label, secs in (("15 分钟", 900), ("30 分钟", 1800),
                                ("1 小时", 3600), ("2 小时", 7200)):
                PillButton(quick, label, lambda s=secs: self._apply_preset(s),
                           fill=PILL_BG, fg=TEXT, parent_bg=BG,
                           font=tkfont.Font(family="Microsoft YaHei UI",
                                            size=self._pt(10)),
                           padx=self._px(12), pady=self._px(7)).pack(
                    side="left", padx=self._px(4))

        # 主操作按钮
        btns = tk.Frame(inner, bg=BG)
        btns.pack(pady=(self._px(16), 0))
        self.btn_start = PillButton(btns, "开始" + ACTION_LABEL[self.action],
                                    self.on_start, fill=ACCENT, fg="#FFFFFF",
                                    parent_bg=BG,
                                    font=tkfont.Font(family="Microsoft YaHei UI",
                                                     size=self._pt(13),
                                                     weight="bold"),
                                    padx=self._px(28), pady=self._px(13))
        self.btn_start.pack(side="left", padx=self._px(6))
        self.btn_cancel = PillButton(btns, "取消", self.on_cancel,
                                     fill=PILL_BG, fg=DANGER, parent_bg=BG,
                                     font=tkfont.Font(family="Microsoft YaHei UI",
                                                      size=self._pt(13),
                                                      weight="bold"),
                                     padx=self._px(28), pady=self._px(13))
        self.btn_cancel.pack(side="left", padx=self._px(6))

        # 底部提示
        tk.Label(inner, text="按 Esc 快速取消 · 拖动窗口边角可缩放界面",
                 bg=BG, fg=TEXT_DIM,
                 font=("Microsoft YaHei UI", self._pt(9))).pack(
            pady=(self._px(14), self._px(18)))

        self._sync_state()

    def _build_count_fields(self, parent):
        for col in range(3):
            parent.columnconfigure(col, weight=1, uniform="f")
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        specs = ((self.var_h, "小时"), (self.var_m, "分钟"), (self.var_s, "秒"))
        for col, (var, label) in enumerate(specs):
            ent = tk.Entry(parent, textvariable=var, width=3, justify="center",
                           font=("Segoe UI Light", self._pt(20)),
                           bg=FIELD_BG, fg=TEXT, insertbackground=ACCENT,
                           relief="flat", highlightthickness=0, bd=0)
            ent.grid(row=0, column=col, pady=(self._px(6), 0),
                     ipady=self._px(4))
            tk.Label(parent, text=label, bg=CARD, fg=TEXT_DIM,
                     font=("Microsoft YaHei UI", self._pt(10))).grid(
                row=1, column=col, pady=(0, self._px(4)))

    def _build_clock_fields(self, parent):
        for col in range(2):
            parent.columnconfigure(col, weight=1, uniform="c")
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        specs = ((self.var_th, "时"), (self.var_tm, "分"))
        for col, (var, label) in enumerate(specs):
            ent = tk.Entry(parent, textvariable=var, width=3, justify="center",
                           font=("Segoe UI Light", self._pt(20)),
                           bg=FIELD_BG, fg=TEXT, insertbackground=ACCENT,
                           relief="flat", highlightthickness=0, bd=0)
            ent.grid(row=0, column=col, pady=(self._px(6), 0),
                     ipady=self._px(4))
            tk.Label(parent, text=label, bg=CARD, fg=TEXT_DIM,
                     font=("Microsoft YaHei UI", self._pt(10))).grid(
                row=1, column=col, pady=(0, self._px(4)))

    # ---------- 状态刷新 ----------
    def _sync_state(self):
        if self.lbl_time is not None:
            self.lbl_time.config(text=self._format(self.remaining),
                                 fg=self._time_color)
        if self.lbl_status is not None:
            self.lbl_status.config(text=self._status_text, fg=self._status_color)
        self._sync_buttons()

    def _sync_buttons(self):
        if getattr(self, "btn_start", None) is not None:
            self.btn_start.set_enabled(not self.running)
            self.btn_cancel.set_enabled(self.running)
        for b in getattr(self, "_action_btns", {}).values():
            b.set_locked(self.running)
        for b in getattr(self, "_mode_btns", {}).values():
            b.set_locked(self.running)
        if getattr(self, "chk_force", None) is not None:
            usable = self.action in NATIVE_DELAY
            self.chk_force.config(state="normal" if usable else "disabled",
                                  fg=TEXT_DIM if usable else DISABLED_FG)

    def _on_force_toggle(self):
        self._save_settings()

    def _on_time_var(self, *_a):
        try:
            self._update_preview()
        except Exception:
            pass

    def _update_preview(self):
        """未运行时把状态行当作预览（指定时刻模式下显示目标时间）。"""
        if self.running or self.lbl_status is None:
            return
        if self.mode != "clock":
            # 从指定时刻模式切回来时，清掉目标时间预览
            if self._status_text.startswith("将于 ") or \
                    self._status_text.startswith("请输入"):
                self._set_state("未设置", TEXT_DIM)
            return
        try:
            _secs, target = self._clock_target()
            today = datetime.date.today()
            day = "今天" if target.date() == today else "明天"
            self._set_state("将于 %s %02d:%02d %s" %
                            (day, target.hour, target.minute,
                             ACTION_LABEL[self.action]), TEXT_DIM)
        except Exception:
            self._set_state("请输入 0-23 时、0-59 分", DANGER)

    # ---------- 选择项 ----------
    def _set_action(self, key):
        self.action = key
        for k, b in self._action_btns.items():
            b.set_selected(k == key)
        self.btn_start._text = "开始" + ACTION_LABEL[key]
        self.btn_start.delete("txt")
        self.btn_start.create_text(self.btn_start._bw / 2,
                                   self.btn_start._bh / 2,
                                   text=self.btn_start._text,
                                   fill=self.btn_start._base_fg(),
                                   font=self.btn_start._font, tags="txt")
        self._sync_buttons()
        self._update_preview()
        self._save_settings()

    def _set_mode(self, key):
        if key == self.mode:
            return
        self.mode = key
        self._build()
        self._update_preview()
        self._save_settings()

    def _set_warn(self, secs):
        self.warn_seconds = secs
        for k, b in self._warn_btns.items():
            b.set_selected(k == secs)
        self._save_settings()

    def _apply_preset(self, secs: int):
        self.var_h.set(str(secs // 3600))
        self.var_m.set(str((secs % 3600) // 60))
        self.var_s.set(str(secs % 60))
        self._save_settings()

    # ---------- 状态 ----------
    def _set_state(self, text: str, color: str):
        self._status_text = text
        self._status_color = color
        if self.lbl_status is not None:
            self.lbl_status.config(text=text, fg=color)

    def _format(self, s: int) -> str:
        s = max(0, int(s))
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return "%02d:%02d:%02d" % (h, m, sec)

    # ---------- 计算目标 ----------
    def _clock_target(self):
        """返回 (距目标秒数, 目标 datetime)；时刻已过则算到明天。"""
        try:
            th = int(float(self.var_th.get()))
            tm = int(float(self.var_tm.get()))
        except ValueError:
            raise ValueError("时间必须是数字")
        if not (0 <= th <= 23) or not (0 <= tm <= 59):
            raise ValueError("时间超出范围（时 0-23，分 0-59）")
        now = datetime.datetime.now()
        target = now.replace(hour=th, minute=tm, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return int(round((target - now).total_seconds())), target

    def _compute_seconds(self):
        if self.mode == "clock":
            return self._clock_target()
        def num(v, name):
            try:
                return max(0, int(float(v)))
            except ValueError:
                raise ValueError("%s必须是数字" % name)
        total = num(self.var_h.get(), "小时") * 3600 + \
            num(self.var_m.get(), "分钟") * 60 + \
            num(self.var_s.get(), "秒")
        return total, None

    # ---------- 开始 / 取消 / 结束 ----------
    def on_start(self):
        try:
            total, target = self._compute_seconds()
        except ValueError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        if total <= 0:
            messagebox.showwarning(APP_NAME, "请设置大于 0 的时间")
            return

        force = self.var_force.get() if self.action in NATIVE_DELAY else False

        if self.running and self.action in NATIVE_DELAY:
            abort_native()

        self._force_used = force
        self.remaining = total
        self._warned = False

        if self.action in NATIVE_DELAY:
            if not schedule_native(self.action, total, force):
                messagebox.showerror(APP_NAME, "发起失败，请检查系统权限后重试")
                return

        self.running = True
        self._time_color = TEXT
        label = ACTION_LABEL[self.action]
        if target is not None:
            today = datetime.date.today()
            day = "今天" if target.date() == today else "明天"
            desc = "%s %02d:%02d" % (day, target.hour, target.minute)
        else:
            desc = self._format(total)
        note = "" if self.action in NATIVE_DELAY else "（本程序需保持运行）"
        self._set_state("已设置 · %s 后%s%s" % (desc, label, note), ORANGE)
        self._sync_state()
        self._tick()

    def on_cancel(self):
        if not self.running:
            self._close_warn_dialog()
            return
        self.running = False
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        if self.action in NATIVE_DELAY:
            abort_native()
        self._close_warn_dialog()
        self.remaining = 0
        self._time_color = TEXT
        self._set_state("已取消%s" % ACTION_LABEL[self.action], TEXT_DIM)
        self._sync_state()

    def _finish(self):
        self.running = False
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        self._close_warn_dialog()
        label = ACTION_LABEL[self.action]
        self._time_color = DANGER
        self._set_state("正在%s…" % label, DANGER)
        if self.action not in NATIVE_DELAY:
            run_action_now(self.action, self._force_used)
        self._sync_state()

    def _execute_now(self):
        self._close_warn_dialog()
        self.running = False
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        if self.action in NATIVE_DELAY:
            abort_native()
        self.remaining = 0
        self._time_color = DANGER
        self._set_state("正在%s…" % ACTION_LABEL[self.action], DANGER)
        run_action_now(self.action, self._force_used)
        self._sync_state()

    def _postpone(self, seconds):
        self.remaining += seconds
        self._warned = False
        if self.action in NATIVE_DELAY:
            abort_native()
            schedule_native(self.action, max(1, self.remaining), self._force_used)
        self._close_warn_dialog()
        self._set_state("已延后 · %s 后%s" %
                        (self._format(self.remaining),
                         ACTION_LABEL[self.action]), ORANGE)
        self._sync_state()

    # ---------- 倒计时 ----------
    def _tick(self):
        if not self.running:
            return
        self.lbl_time.config(text=self._format(self.remaining))
        if self.remaining <= 0:
            self.lbl_time.config(fg=DANGER)
            self._finish()
            return
        if self.remaining <= 10:
            self._time_color = DANGER
            self.lbl_time.config(fg=DANGER)
        if (self.warn_seconds > 0 and not self._warned
                and self.remaining <= self.warn_seconds):
            self._warned = True
            self._show_warn_dialog()
        self.remaining -= 1
        self._tick_job = self.root.after(1000, self._tick)

    # ---------- 提醒弹窗 ----------
    def _show_warn_dialog(self):
        if self._warn_dialog is not None:
            return
        label = ACTION_LABEL[self.action]
        dlg = tk.Toplevel(self.root)
        dlg.title("即将" + label)
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        self._warn_dialog = dlg

        tk.Label(dlg, text="距离%s还有 %s" % (label, self._format(self.warn_seconds)),
                 bg=BG, fg=TEXT,
                 font=("Microsoft YaHei UI", self._pt(15), "bold")).pack(
            padx=self._px(30), pady=(self._px(22), self._px(4)))
        tk.Label(dlg, text="可以延后 5 分钟，或立即执行",
                 bg=BG, fg=TEXT_DIM,
                 font=("Microsoft YaHei UI", self._pt(10))).pack(
            pady=(0, self._px(16)))

        row = tk.Frame(dlg, bg=BG)
        row.pack(padx=self._px(20), pady=(0, self._px(20)))
        big = tkfont.Font(family="Microsoft YaHei UI", size=self._pt(11),
                          weight="bold")
        PillButton(row, "延后 5 分钟", lambda: self._postpone(300), fill=ACCENT,
                   fg="#FFFFFF", parent_bg=BG, font=big, padx=self._px(14),
                   pady=self._px(9)).pack(side="left", padx=self._px(4))
        PillButton(row, "立即" + label, self._execute_now, fill=PILL_BG, fg=TEXT,
                   parent_bg=BG, font=big, padx=self._px(14),
                   pady=self._px(9)).pack(side="left", padx=self._px(4))
        PillButton(row, "取消", self.on_cancel, fill=PILL_BG, fg=DANGER,
                   parent_bg=BG, font=big, padx=self._px(14),
                   pady=self._px(9)).pack(side="left", padx=self._px(4))

        dlg.protocol("WM_DELETE_WINDOW", lambda: None)
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() -
                                       dlg.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() -
                                       dlg.winfo_reqheight()) // 3
        dlg.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _close_warn_dialog(self):
        if self._warn_dialog is not None:
            try:
                self._warn_dialog.destroy()
            except Exception:
                pass
            self._warn_dialog = None


def main():
    _enable_dpi_awareness()
    root = tk.Tk()
    auto_close = os.environ.get("DSH_AUTO_CLOSE_MS")
    if auto_close:
        try:
            root.after(int(auto_close), root.destroy)
        except ValueError:
            pass
    app = App(root)

    def on_esc(_event):
        if app.running:
            app.on_cancel()

    root.bind("<Escape>", on_esc)

    def on_close():
        if app.running:
            if messagebox.askokcancel(
                    APP_NAME,
                    "定时任务仍在进行，确定要关闭本程序吗？\n"
                    "（关机/重启仍会按设定执行；睡眠/休眠/注销/锁屏将不会执行）"):
                app._save_settings()
                root.destroy()
        else:
            app._save_settings()
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)

    if TEST_MODE:
        app._set_state("【测试模式】不会真正执行", ORANGE)

    root.mainloop()


if __name__ == "__main__":
    main()
