"""
Wallora v1 - tiny, lightweight live wallpaper for Windows 10/11.
Engine: mpv.exe (GPU decoding). GUI: tkinter. Tray: pystray.

 1. Browse a video   -> becomes your desktop wallpaper (behind icons)
 2. Background audio -> pick an audio file, plays in an endless loop
 3. Small preview    -> shown only while the window is open

Also: Stop/Start button, Quit button, starts with Windows, tray icon,
pauses when a fullscreen app/game is running, and running the app again
simply brings this window back.
"""
import os
import sys
import json
import time
import queue
import atexit
import shutil
import ctypes
import traceback
import subprocess
import winreg
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from ctypes import wintypes

import pystray
from PIL import Image, ImageDraw

APP = "Wallora"
HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(os.environ.get("APPDATA", HERE), APP)
CFG_FILE = os.path.join(CFG_DIR, "config.json")
LOG_FILE = os.path.join(CFG_DIR, "log.txt")
MPV_LOG = os.path.join(CFG_DIR, "mpv_log.txt")
PIPE = r"\\.\pipe\wallora_ipc"
MUTEX_NAME = "walloraSingleInstance_v3"
EVENT_NAME = "walloraShowEvent_v3"
FLAGS = 0x08000000 | 0x00004000  # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY

VIDEO_TYPES = [("Video files", "*.mp4 *.mkv *.webm *.avi *.mov *.wmv *.gif"), ("All files", "*.*")]
AUDIO_TYPES = [("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac"), ("All files", "*.*")]


def log(msg):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        if os.path.isfile(LOG_FILE) and os.path.getsize(LOG_FILE) > 200_000:
            os.remove(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- WinAPI ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
k32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
]
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]

k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
k32.CreateMutexW.restype = ctypes.c_void_p
k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
k32.CreateEventW.restype = ctypes.c_void_p
k32.SetEvent.argtypes = [ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
k32.WaitForSingleObject.restype = wintypes.DWORD


def get_workerw():
    """Find the desktop layer that sits behind the icons."""
    progman = user32.FindWindowW("Progman", None)
    res = ctypes.c_size_t()
    user32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(res))

    # Windows 11 24H2+: WorkerW is a child of Progman
    w = user32.FindWindowExW(progman, None, "WorkerW", None)
    if w:
        return w

    # Windows 10 / older Windows 11: WorkerW is a top-level sibling
    found = []

    @WNDENUMPROC
    def cb(hwnd, _):
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            found.append(user32.FindWindowExW(None, hwnd, "WorkerW", None))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found and found[0] else progman


def refresh_desktop():
    """Force Windows to repaint the real wallpaper (clears a frozen last frame)."""
    try:
        user32.SystemParametersInfoW(0x0014, 0, None, 0x01 | 0x02)  # SPI_SETDESKWALLPAPER
    except Exception:
        pass


def fullscreen_app_active():
    hw = user32.GetForegroundWindow()
    if not hw:
        return False
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hw, cls, 64)
    if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return False
    r = wintypes.RECT()
    user32.GetWindowRect(hw, ctypes.byref(r))
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return r.left <= 0 and r.top <= 0 and r.right >= sw and r.bottom >= sh


def kill_stale():
    """Close any OLD wallora copy (and its mpv players) left running in the background."""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "( $_.Name -match '^pythonw?\\.exe$' -and $_.CommandLine -match 'wallora\\.py' "
        "-and $_.ProcessId -ne %d -and $_.ProcessId -ne %d ) "
        "-or ( $_.Name -eq 'mpv.exe' -and $_.CommandLine -match 'wallora_ipc|--wid=|--no-video' ) } "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    ) % (os.getpid(), os.getppid())
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       creationflags=0x08000000, timeout=25,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except Exception as e:
        log(f"kill_stale failed: {e}")


def find_mpv():
    local = os.path.join(HERE, "mpv.exe")
    if os.path.isfile(local):
        return local
    return shutil.which("mpv") or shutil.which("mpv.exe")


def set_autostart():
    """Run at every Windows login (current user only, no admin needed)."""
    py = sys.executable
    pyw = py.replace("python.exe", "pythonw.exe")
    if os.path.isfile(pyw):
        py = pyw
    cmd = f'"{py}" "{os.path.abspath(__file__)}" --autostart'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, cmd)
    except OSError as e:
        log(f"autostart failed: {e}")


def load_cfg():
    cfg = {"video": "", "audio": "", "audio_on": False, "enabled": True}
    try:
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception as e:
        log(f"save_cfg failed: {e}")


def tray_image():
    img = Image.new("RGB", (64, 64), "#1e1e2e")
    ImageDraw.Draw(img).polygon([(22, 16), (22, 48), (50, 32)], fill="#89b4fa")
    return img


# ------------------------------------------------------------------- App ---
class wallora:
    COMMON = ["--no-terminal", "--no-osc", "--no-osd-bar", "--no-border",
              "--no-input-default-bindings", "--input-media-keys=no", "--no-input-cursor",
              "--loop-file=inf", "--hwdec=auto-safe", "--vo=gpu", "--panscan=1.0",
              "--no-audio", "--framedrop=vo", "--stop-screensaver=no", "--keep-open=yes"]

    def __init__(self, autostart, event):
        self.event = event
        self.mpv = find_mpv()
        self.cfg = load_cfg()
        self.wall = self.audio = self.prev = None
        self.paused = False
        self.q = queue.Queue()
        self.tick_n = 0
        self.quitting = False

        self.root = tk.Tk()
        self.root.title(APP)
        self.sc = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.root.geometry(f"{int(370 * self.sc)}x{int(520 * self.sc)}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.build_ui()

        self.tray = pystray.Icon(
            APP, tray_image(), APP,
            menu=pystray.Menu(
                pystray.MenuItem("Open", lambda i, it: self.q.put("show"), default=True),
                pystray.MenuItem(
                    lambda item: "Stop wallpaper" if self.cfg.get("enabled", True) else "Start wallpaper",
                    lambda i, it: self.q.put("toggle")),
                pystray.MenuItem("Quit", lambda i, it: self.q.put("quit")),
            ),
        )
        self.tray.run_detached()
        atexit.register(self.kill_all)

        if not self.mpv:
            self.root.after(400, lambda: messagebox.showwarning(
                APP, "mpv.exe was not found.\n\nDownload it from mpv.io (Windows builds), put "
                     "mpv.exe in the same folder as wallora.py, then start wallora again."))
        if autostart:
            self.root.withdraw()
            self.root.after(5000, self.apply_all)  # let Explorer finish loading
        else:
            self.root.after(300, self.apply_all)
            self.root.after(700, self.start_preview)
        self.root.after(500, self.tick)

    # ---- UI
    def build_ui(self):
        pad = {"padx": 12}
        ttk.Label(self.root, text="1. Wallpaper video").pack(anchor="w", pady=(12, 2), **pad)
        row = ttk.Frame(self.root)
        row.pack(fill="x", **pad)
        self.v_var = tk.StringVar(value=self.cfg.get("video", ""))
        ttk.Entry(row, textvariable=self.v_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self.pick_video).pack(side="left", padx=(6, 0))

        ttk.Label(self.root, text="2. Background audio (loops)").pack(anchor="w", pady=(14, 2), **pad)
        row = ttk.Frame(self.root)
        row.pack(fill="x", **pad)
        self.a_var = tk.StringVar(value=self.cfg.get("audio", ""))
        ttk.Entry(row, textvariable=self.a_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self.pick_audio).pack(side="left", padx=(6, 0))
        self.audio_on = tk.BooleanVar(value=self.cfg.get("audio_on", False))
        ttk.Checkbutton(self.root, text="Play background audio", variable=self.audio_on,
                        command=self.toggle_audio).pack(anchor="w", pady=(6, 0), **pad)

        ttk.Label(self.root, text="3. Preview").pack(anchor="w", pady=(14, 2), **pad)
        self.pv = tk.Frame(self.root, bg="black", width=int(336 * self.sc), height=int(189 * self.sc))
        self.pv.pack(**pad)
        self.pv.pack_propagate(False)

        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status).pack(anchor="w", pady=(10, 0), **pad)

        row = ttk.Frame(self.root)
        row.pack(fill="x", pady=(6, 0), **pad)
        self.toggle_btn = ttk.Button(row, command=self.toggle_wall)
        self.toggle_btn.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Quit app", command=self.quit).pack(side="left", padx=(6, 0))

        ttk.Label(self.root, foreground="gray",
                  text="Closing this window keeps the wallpaper running\n(tray icon, bottom-right).").pack(
            anchor="w", pady=(8, 0), **pad)
        self.update_btn()

    def update_btn(self):
        on = self.cfg.get("enabled", True)
        self.toggle_btn.config(text="Stop wallpaper" if on else "Start wallpaper")
        if not self.mpv:
            self.status.set("Status: mpv.exe not found")
        elif not on:
            self.status.set("Status: stopped")
        elif not self.cfg.get("video"):
            self.status.set("Status: no video selected")
        elif self.wall and self.wall.poll() is None:
            self.status.set("Status: wallpaper running" + (" (paused: fullscreen app)" if self.paused else ""))
        else:
            self.status.set("Status: starting…")

    # ---- processes
    def run(self, args):
        return subprocess.Popen([self.mpv, *args], creationflags=FLAGS,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

    def start_wall(self):
        self.stop(self.wall)
        self.wall = None
        v = self.cfg.get("video")
        if not self.cfg.get("enabled", True):
            return
        if not (self.mpv and v and os.path.isfile(v)):
            return
        self.paused = False
        try:
            self.wall = self.run([f"--wid={get_workerw()}", f"--input-ipc-server={PIPE}",
                                  f"--log-file={MPV_LOG}", "--msg-level=all=error", *self.COMMON, v])
        except Exception as e:
            log(f"start_wall failed: {e}")

    def start_preview(self):
        self.stop(self.prev)
        self.prev = None
        v = self.cfg.get("video")
        if not (self.mpv and v and os.path.isfile(v)) or self.root.state() == "withdrawn":
            return
        self.root.update_idletasks()
        try:
            self.prev = self.run([f"--wid={self.pv.winfo_id()}", *self.COMMON, v])
        except Exception as e:
            log(f"start_preview failed: {e}")

    def start_audio(self):
        self.stop(self.audio)
        self.audio = None
        a = self.cfg.get("audio")
        if self.mpv and self.cfg.get("enabled", True) and self.cfg.get("audio_on") and a and os.path.isfile(a):
            try:
                self.audio = self.run(["--no-video", "--no-terminal", "--loop-file=inf",
                                       "--no-input-default-bindings", a])
            except Exception as e:
                log(f"start_audio failed: {e}")

    @staticmethod
    def stop(p):
        try:
            if p and p.poll() is None:
                p.terminate()
        except Exception:
            pass

    def kill_all(self):
        for p in (self.wall, self.audio, self.prev):
            self.stop(p)

    def apply_all(self):
        self.start_wall()
        self.start_audio()
        self.update_btn()

    # ---- actions
    def pick_video(self):
        p = filedialog.askopenfilename(title="Choose wallpaper video", filetypes=VIDEO_TYPES)
        if p:
            self.cfg["video"] = p
            self.cfg["enabled"] = True
            self.v_var.set(p)
            save_cfg(self.cfg)
            self.apply_all()
            self.start_preview()

    def pick_audio(self):
        p = filedialog.askopenfilename(title="Choose background audio", filetypes=AUDIO_TYPES)
        if p:
            self.cfg["audio"] = p
            self.a_var.set(p)
            self.audio_on.set(True)
            self.cfg["audio_on"] = True
            save_cfg(self.cfg)
            self.start_audio()
        else:
            self.audio_on.set(bool(self.cfg.get("audio")) and self.cfg.get("audio_on", False))

    def toggle_audio(self):
        self.cfg["audio_on"] = self.audio_on.get()
        if self.cfg["audio_on"] and not self.cfg.get("audio"):
            self.pick_audio()
            return
        save_cfg(self.cfg)
        self.start_audio()

    def toggle_wall(self):
        if self.cfg.get("enabled", True):
            self.cfg["enabled"] = False
            save_cfg(self.cfg)
            self.stop(self.wall)
            self.wall = None
            self.stop(self.audio)
            self.audio = None
            self.root.after(500, refresh_desktop)  # clear the frozen last frame
        else:
            if not self.cfg.get("video"):
                self.pick_video()
                return
            self.cfg["enabled"] = True
            save_cfg(self.cfg)
            self.apply_all()
        self.update_btn()

    def hide(self):
        self.stop(self.prev)  # preview costs nothing while hidden
        self.prev = None
        self.root.withdraw()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        self.update_btn()
        self.root.after(250, self.start_preview)

    def quit(self):
        if self.quitting:
            return
        self.quitting = True
        self.kill_all()
        time.sleep(0.3)
        refresh_desktop()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    # ---- background housekeeping (very cheap, every 0.5s)
    def tick(self):
        if self.quitting:
            return
        try:
            while True:
                m = self.q.get_nowait()
                if m == "show":
                    self.show()
                elif m == "toggle":
                    self.toggle_wall()
                elif m == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass

        # a second launch (e.g. the .bat) asks this instance to show its window
        if self.event and k32.WaitForSingleObject(self.event, 0) == 0:
            self.show()

        self.tick_n += 1
        if self.tick_n % 4 == 0 and self.wall and self.wall.poll() is None:
            fs = fullscreen_app_active()
            if fs != self.paused:
                self.paused = fs
                try:
                    with open(PIPE, "wb", buffering=0) as f:
                        f.write((json.dumps({"command": ["set_property", "pause", fs]}) + "\n").encode())
                except OSError:
                    pass
        # restart the wallpaper if it died (e.g. Explorer restarted)
        if (self.tick_n % 10 == 0 and self.cfg.get("enabled", True) and self.cfg.get("video")
                and (self.wall is None or self.wall.poll() is not None)
                and os.path.isfile(self.cfg["video"])):
            self.start_wall()
        if self.tick_n % 4 == 0 and self.root.state() != "withdrawn":
            self.update_btn()

        self.root.after(500, self.tick)


def main():
    mutex = k32.CreateMutexW(None, False, MUTEX_NAME)  # keep reference alive
    already_running = ctypes.get_last_error() == 183
    ev = k32.CreateEventW(None, False, False, EVENT_NAME)
    if already_running:
        k32.SetEvent(ev)  # tell the running copy to open its window
        return

    kill_stale()  # removes any older wallora version still running hidden
    set_autostart()
    app = wallora(autostart="--autostart" in sys.argv, event=ev)
    app.root.mainloop()
    del mutex


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        log("FATAL:\n" + err)
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror(APP, f"wallora crashed:\n\n{err[-800:]}\n\nLog: {LOG_FILE}")
        except Exception:
            pass
