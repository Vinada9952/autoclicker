import sys
import os
import json
import threading
import time
import pydirectinput
import ctypes
from ctypes import wintypes

user32=ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_=[("x",wintypes.LONG),("y",wintypes.LONG)]

INPUT_MOUSE=0
MOUSEEVENTF_LEFTDOWN=0x0002
MOUSEEVENTF_LEFTUP=0x0004
MOUSEEVENTF_RIGHTDOWN=0x0008
MOUSEEVENTF_RIGHTUP=0x0010

class MOUSEINPUT(ctypes.Structure):
    _fields_=[("dx",wintypes.LONG),("dy",wintypes.LONG),("mouseData",wintypes.DWORD),("dwFlags",wintypes.DWORD),("time",wintypes.DWORD),("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
class INPUT(ctypes.Structure):
    _fields_=[("type",wintypes.DWORD),("mi",MOUSEINPUT)]
def _send(flags):
    inp=INPUT(type=INPUT_MOUSE,mi=MOUSEINPUT(0,0,0,flags,0,None))
    user32.SendInput(1,ctypes.byref(inp),ctypes.sizeof(INPUT))
class pyautogui:
    PAUSE=0
    FAILSAFE=False
    @staticmethod
    def leftClick():
        # _send(MOUSEEVENTF_LEFTDOWN);_send(MOUSEEVENTF_LEFTUP)
        pydirectinput.mouseDown()
    time.sleep( 0.0000000001 )
    pydirectinput.mouseUp()
    @staticmethod
    def rightClick():
        # _send(MOUSEEVENTF_RIGHTDOWN);_send(MOUSEEVENTF_RIGHTUP)
        pydirectinput.mouseDown( button="right" )
        time.sleep( 0.0000000001 )
        pydirectinput.mouseUp( button="right" )
    @staticmethod
    def click(button="left"):
        (pyautogui.leftClick if button=="left" else pyautogui.rightClick)()
    @staticmethod
    def moveTo(x,y):
        user32.SetCursorPos(int(x),int(y))
    @staticmethod
    def position():
        p=POINT();user32.GetCursorPos(ctypes.byref(p));return p.x,p.y

import keyboard as kb
import tkinter as tk
from tkinter import ttk, messagebox
from pynput import mouse

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

# ---------------------------------------------------------------------------
# Thème
# ---------------------------------------------------------------------------
BG = "#0d0d0f"
BG_PANEL = "#17171b"
ACCENT = "#7c6af7"
ACCENT_HOVER = "#9384ff"
TEXT = "#e8e8ec"
TEXT_DIM = "#8a8a94"
RED = "#f76a6a"
GREEN = "#6af7a0"

# ---------------------------------------------------------------------------
# Persistance des macros (%APPDATA%/AutoClicker/macros.json)
# ---------------------------------------------------------------------------
def get_macros_path():
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    dir_path = os.path.join(appdata, "SmartAutoClicker")
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, "macros.json")


def load_macros():
    path = get_macros_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_macros(macros):
    path = get_macros_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(macros, f, ensure_ascii=False, indent=4)


# ---------------------------------------------------------------------------
# État partagé
# ---------------------------------------------------------------------------
auto_clicker_active = False
repetition_presses = 50
delay_ms = 1
hotkey_str = "caps lock"
registered_hotkey = None

# Bouton utilisé par le mode "Auto Clicker classique"
auto_click_button = "left"

# Modes disponibles
MODE_AUTO = "auto"    # clic continu tant que actif (autoclicker classique)
MODE_BURST = "burst"  # salve de N clics à chaque clic souris
MODE_HOLD = "hold"    # spam de clics tant que le bouton est maintenu
MODE_MACRO = "macro"  # exécute une macro personnalisée au clic

MODES = [MODE_AUTO, MODE_BURST, MODE_HOLD, MODE_MACRO]
MODE_LABELS = {
    MODE_AUTO: "Auto Clicker classique (continu)",
    MODE_BURST: "Salve au clic",
    MODE_HOLD: "Maintien enfoncé",
    MODE_MACRO: "Macro personnalisée",
}
LABEL_TO_MODE = {v: k for k, v in MODE_LABELS.items()}

click_mode = MODE_BURST  # comportement d'origine par défaut

MODE_HOTKEY = "alt+caps lock"
registered_mode_hotkey = None

# Un verrou par bouton : empêche deux salves de se chevaucher sur le même
# bouton, tout en laissant le clic droit et le clic gauche se déclencher
# indépendamment l'un de l'autre.
click_locks = {
    mouse.Button.left: threading.Lock(),
    mouse.Button.right: threading.Lock(),
}

# État "maintenu" par bouton, utilisé par le mode MODE_HOLD.
holding = {
    mouse.Button.left: False,
    mouse.Button.right: False,
}

# Empêche les clics simulés par pyautogui (mode maintien) d'être
# réinterprétés comme des vrais clics/relâchements par le listener pynput.
ignore_synthetic = {
    mouse.Button.left: False,
    mouse.Button.right: False,
}

# Verrou pour empêcher deux exécutions de macro simultanées.
macro_lock = threading.Lock()

# Permet d'interrompre une macro en cours (utile pour les boucles for/while).
macro_stop_flag = threading.Event()

# Référence vers l'app pour synchroniser l'UI depuis les hotkeys/listener.
app_instance = None


# ---------------------------------------------------------------------------
# Logique des modes
# ---------------------------------------------------------------------------
def run_click_burst(target_click, lock):
    """Exécute la salve de clics (mode Salve). Tourne dans son propre thread."""
    global auto_clicker_active
    delay = delay_ms / 1000
    try:
        for _ in range(repetition_presses):
            if not auto_clicker_active or click_mode != MODE_BURST:
                break
            time.sleep(delay)
            target_click()
    finally:
        lock.release()


def run_hold_clicks(target_click, button):
    """Spam de clics tant que le bouton reste maintenu (mode Maintien)."""
    delay = delay_ms / 1000
    while auto_clicker_active and click_mode == MODE_HOLD and holding.get(button):
        ignore_synthetic[button] = True
        target_click()
        ignore_synthetic[button] = False
        time.sleep(delay)


def auto_clicker_worker():
    """Boucle du mode Auto Clicker classique : clique en continu tant que
    actif, indépendamment des clics réels de l'utilisateur."""
    while True:
        if auto_clicker_active and click_mode == MODE_AUTO:
            pyautogui.click(button=auto_click_button)
            time.sleep(max(delay_ms, 1) / 1000)
        else:
            time.sleep(0.05)


def _macro_should_continue(respect_toggle):
    """Détermine si une macro (ou une boucle en son sein) doit continuer."""
    if macro_stop_flag.is_set():
        return False
    if respect_toggle and not (auto_clicker_active and click_mode == MODE_MACRO):
        return False
    return True


def _execute_block(block, respect_toggle):
    cmd = block.get("command")
    val = block.get("value")
    try:
        if cmd == "keyboard":
            kb.send(val)
        elif cmd == "mouse":
            pyautogui.click(button="left" if val == "left" else "right")
        elif cmd == "mousemove":
            x = int(val.get("x"))
            y = int(val.get("y"))
            pyautogui.moveTo(x, y)
        elif cmd == "delay":
            ms = int(val)
            time.sleep(max(ms, 0) / 1000)
        elif cmd == "for":
            count = int(val.get("count", 1))
            nested = val.get("blocks", [])
            for _ in range(count):
                if not _macro_should_continue(respect_toggle):
                    break
                run_macro(nested, respect_toggle)
        elif cmd == "while":
            condition = val.get("condition", "always")
            key = val.get("key")
            nested = val.get("blocks", [])
            while _macro_should_continue(respect_toggle):
                if condition == "key_held" and not (key and kb.is_pressed(key)):
                    break
                run_macro(nested, respect_toggle)
    except Exception:
        # Une touche/valeur invalide ne doit pas planter le thread.
        pass


def run_macro(blocks, respect_toggle=True):
    """Exécute séquentiellement les blocs d'une macro (récursif pour les boucles)."""
    for block in blocks:
        if not _macro_should_continue(respect_toggle):
            break
        _execute_block(block, respect_toggle)


def start_macro_run(blocks, respect_toggle=True):
    if not blocks:
        return
    if not macro_lock.acquire(blocking=False):
        return
    macro_stop_flag.clear()

    def _run():
        try:
            run_macro(blocks, respect_toggle)
        finally:
            macro_lock.release()

    threading.Thread(target=_run, daemon=True).start()


def stop_running_macro():
    macro_stop_flag.set()


def on_click(x, y, button, pressed):
    """Callback du listener pynput : doit rester rapide, ne jamais bloquer."""
    if not auto_clicker_active:
        return

    if click_mode == MODE_AUTO:
        # Le mode classique ne réagit pas aux clics, seulement au toggle.
        return

    if button not in (mouse.Button.left, mouse.Button.right):
        return

    if ignore_synthetic.get(button):
        # Clic généré par nos propres salves (mode Maintien) : on l'ignore.
        return

    target_click = pyautogui.leftClick if button == mouse.Button.left else pyautogui.rightClick

    if click_mode == MODE_BURST:
        if not pressed:
            return
        lock = click_locks[button]
        if not lock.acquire(blocking=False):
            # Une salve est déjà en cours pour ce bouton : on ignore ce clic
            # plutôt que d'empiler les salves.
            return
        threading.Thread(
            target=run_click_burst, args=(target_click, lock), daemon=True
        ).start()

    elif click_mode == MODE_HOLD:
        if pressed:
            if holding[button]:
                return
            holding[button] = True
            threading.Thread(
                target=run_hold_clicks, args=(target_click, button), daemon=True
            ).start()
        else:
            holding[button] = False


mouse_listener = mouse.Listener(on_click=on_click)
mouse_listener.start()

threading.Thread(target=auto_clicker_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Interface graphique
# ---------------------------------------------------------------------------
BLOCK_TYPE_KEYBOARD = "Appuyer sur touche du clavier"
BLOCK_TYPE_MOUSE = "Appuyer sur touche de la souris"
BLOCK_TYPE_MOUSEMOVE = "Déplacer la souris"
BLOCK_TYPE_DELAY = "Attendre (ms)"
BLOCK_TYPE_FOR = "Répéter x fois"
BLOCK_TYPE_WHILE = "Répéter indéfiniment"
BLOCK_TYPES = [
    BLOCK_TYPE_KEYBOARD,
    BLOCK_TYPE_MOUSE,
    BLOCK_TYPE_MOUSEMOVE,
    BLOCK_TYPE_DELAY,
    BLOCK_TYPE_FOR,
    BLOCK_TYPE_WHILE,
]
WHILE_COND_ALWAYS = "Toujours (jusqu'à arrêt)"
WHILE_COND_KEY_HELD = "Tant qu'une touche est maintenue"

NEW_MACRO_LABEL = "+ Nouvelle macro"


class AutoClickerApp:
    def __init__(self, root):
        global app_instance
        app_instance = self

        self.root = root
        root.title("Auto Clicker")
        root.configure(bg=BG)
        root.geometry("440x640")
        root.minsize(380, 480)
        root.resizable(True, True)

        self.macros = load_macros()
        self.current_blocks = []
        self._iid_location = {}
        self._list_parent_iid = {}

        self._build_style()
        self._build_ui()
        self._refresh_hotkey(hotkey_str)
        self._register_mode_hotkey()
        self._refresh_macro_selector()
        self._sync_mode_ui()
        self._update_mouse_position()

    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)

        style.configure(
            "TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10)
        )
        style.configure(
            "Panel.TLabel", background=BG_PANEL, foreground=TEXT, font=("Segoe UI", 10)
        )
        style.configure(
            "Dim.TLabel", background=BG, foreground=TEXT_DIM, font=("Segoe UI", 9)
        )
        style.configure(
            "Title.TLabel",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI Semibold", 15),
        )

        style.configure(
            "TEntry",
            fieldbackground=BG_PANEL,
            background=BG_PANEL,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=ACCENT,
            lightcolor=BG_PANEL,
            darkcolor=BG_PANEL,
            padding=6,
        )

        style.configure(
            "TCombobox",
            fieldbackground=BG_PANEL,
            background=BG_PANEL,
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=ACCENT,
            lightcolor=BG_PANEL,
            darkcolor=BG_PANEL,
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_PANEL)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", BG_PANEL)],
            selectforeground=[("readonly", TEXT)],
        )
        self.root.option_add("*TCombobox*Listbox.background", BG_PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#0d0d0f")

        style.configure(
            "Treeview",
            background=BG_PANEL,
            fieldbackground=BG_PANEL,
            foreground=TEXT,
            rowheight=24,
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#0d0d0f")],
        )
        style.configure(
            "Treeview.Heading",
            background=BG_PANEL,
            foreground=TEXT_DIM,
            borderwidth=0,
            font=("Segoe UI Semibold", 9),
        )

        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#0d0d0f",
            font=("Segoe UI Semibold", 10),
            borderwidth=0,
            padding=8,
        )
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])

        style.configure(
            "Ghost.TButton",
            background=BG_PANEL,
            foreground=TEXT,
            font=("Segoe UI", 9),
            borderwidth=0,
            padding=6,
        )
        style.map("Ghost.TButton", background=[("active", "#232329")])

    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = 20

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(4, weight=1)  # ligne du conteneur de mode

        # --- En-tête ----------------------------------------------------
        header = ttk.Frame(self.root, style="TFrame")
        header.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 6))
        ttk.Label(header, text="Auto Clicker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Automatisation de clics et de macros",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        # --- Statut -------------------------------------------------------
        status_panel = ttk.Frame(self.root, style="Panel.TFrame")
        status_panel.grid(row=1, column=0, sticky="ew", padx=pad, pady=10)

        inner = ttk.Frame(status_panel, style="Panel.TFrame")
        inner.pack(fill="x", padx=16, pady=14)

        self.status_dot = tk.Canvas(
            inner, width=12, height=12, bg=BG_PANEL, highlightthickness=0
        )
        self.status_dot.pack(side="left")
        self.dot_id = self.status_dot.create_oval(1, 1, 11, 11, fill=RED, outline="")

        self.status_label = ttk.Label(
            inner, text="Désactivé", style="Panel.TLabel", font=("Segoe UI Semibold", 11)
        )
        self.status_label.pack(side="left", padx=(10, 0))

        self.toggle_btn = ttk.Button(
            status_panel,
            text="Activer  (ou appuyer sur la touche)",
            style="Accent.TButton",
            command=self.toggle_active,
        )
        self.toggle_btn.pack(fill="x", padx=16, pady=(0, 14))

        # --- Sélecteur de mode ---------------------------------------------
        mode_select_frame = ttk.Frame(self.root, style="TFrame")
        mode_select_frame.grid(row=2, column=0, sticky="ew", padx=pad, pady=(6, 0))
        ttk.Label(mode_select_frame, text="Mode").pack(anchor="w")

        self.mode_var = tk.StringVar(value=MODE_LABELS[click_mode])
        self.mode_combo = ttk.Combobox(
            mode_select_frame,
            textvariable=self.mode_var,
            values=list(MODE_LABELS.values()),
            state="readonly",
            style="TCombobox",
        )
        self.mode_combo.pack(fill="x", pady=(4, 4))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        ttk.Label(
            mode_select_frame,
            text=f"Changer de mode : {MODE_HOTKEY.upper()}",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        # --- Variables partagées entre panneaux -----------------------------
        self.delay_var = tk.StringVar(value=str(delay_ms))
        self.rep_var = tk.StringVar(value=str(repetition_presses))
        self.auto_button_var = tk.StringVar(
            value="Clic gauche" if auto_click_button == "left" else "Clic droit"
        )

        # --- Conteneur des panneaux spécifiques à chaque mode ---------------
        mode_container = ttk.Frame(self.root, style="TFrame")
        mode_container.grid(row=4, column=0, sticky="nsew", padx=pad, pady=(6, 0))
        mode_container.grid_rowconfigure(0, weight=1)
        mode_container.grid_columnconfigure(0, weight=1)

        self.mode_frames = {}
        self.mode_frames[MODE_AUTO] = self._build_auto_panel(mode_container)
        self.mode_frames[MODE_BURST] = self._build_burst_panel(mode_container)
        self.mode_frames[MODE_HOLD] = self._build_hold_panel(mode_container)
        self.mode_frames[MODE_MACRO] = self._build_macro_panel(mode_container)
        for frame in self.mode_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        # --- Raccourci d'activation -----------------------------------------
        hk_frame = ttk.Frame(self.root, style="TFrame")
        hk_frame.grid(row=5, column=0, sticky="ew", padx=pad, pady=(10, 0))
        ttk.Label(hk_frame, text="Raccourci d'activation").pack(anchor="w")

        hk_row = ttk.Frame(hk_frame, style="TFrame")
        hk_row.pack(fill="x", pady=(4, 0))

        self.hotkey_label = ttk.Label(
            hk_row, text=hotkey_str.upper(), style="Panel.TLabel", font=("Segoe UI Semibold", 10)
        )
        self.hotkey_label.pack(side="left", ipadx=10, ipady=6)
        self.hotkey_label.configure(background=BG_PANEL)

        self.rebind_btn = ttk.Button(
            hk_row, text="Changer", style="Ghost.TButton", command=self.start_rebind
        )
        self.rebind_btn.pack(side="left", padx=(10, 0))

        # --- Bas de fenêtre --------------------------------------------------
        self.error_label = ttk.Label(self.root, text="", style="Dim.TLabel", foreground=RED)
        self.error_label.grid(row=6, column=0, sticky="ew", padx=pad, pady=(8, 0))

        ttk.Label(
            self.root,
            text="Ferme la fenêtre pour quitter",
            style="Dim.TLabel",
        ).grid(row=7, column=0, pady=12)

    # ------------------------------------------------------------------
    # Panneau : Auto Clicker classique
    # ------------------------------------------------------------------
    def _build_auto_panel(self, parent):
        frame = ttk.Frame(parent, style="TFrame")

        ttk.Label(frame, text="Bouton à cliquer").pack(anchor="w", pady=(8, 0))
        combo = ttk.Combobox(
            frame,
            textvariable=self.auto_button_var,
            state="readonly",
            values=["Clic gauche", "Clic droit"],
            style="TCombobox",
        )
        combo.pack(fill="x", pady=(4, 12))
        combo.bind("<<ComboboxSelected>>", self._on_auto_button_selected)

        ttk.Label(frame, text="Délai entre chaque clic (ms)").pack(anchor="w")
        entry = ttk.Entry(frame, textvariable=self.delay_var)
        entry.pack(fill="x", pady=(4, 12))
        entry.bind("<FocusOut>", self._apply_params)
        entry.bind("<Return>", self._apply_params)

        ttk.Label(
            frame,
            text="Clique en continu tant que l'auto clicker est activé.",
            style="Dim.TLabel",
            wraplength=340,
        ).pack(anchor="w")

        return frame

    def _on_auto_button_selected(self, event=None):
        global auto_click_button
        auto_click_button = "left" if self.auto_button_var.get() == "Clic gauche" else "right"

    # ------------------------------------------------------------------
    # Panneau : Salve au clic
    # ------------------------------------------------------------------
    def _build_burst_panel(self, parent):
        frame = ttk.Frame(parent, style="TFrame")

        ttk.Label(frame, text="Nombre de clics par déclenchement").pack(anchor="w", pady=(8, 0))
        rep_entry = ttk.Entry(frame, textvariable=self.rep_var)
        rep_entry.pack(fill="x", pady=(4, 12))
        rep_entry.bind("<FocusOut>", self._apply_params)
        rep_entry.bind("<Return>", self._apply_params)

        ttk.Label(frame, text="Délai entre chaque clic (ms)").pack(anchor="w")
        delay_entry = ttk.Entry(frame, textvariable=self.delay_var)
        delay_entry.pack(fill="x", pady=(4, 12))
        delay_entry.bind("<FocusOut>", self._apply_params)
        delay_entry.bind("<Return>", self._apply_params)

        ttk.Label(
            frame,
            text="Envoie une salve de N clics à chaque clic de souris (gauche ou droit).",
            style="Dim.TLabel",
            wraplength=340,
        ).pack(anchor="w")

        return frame

    # ------------------------------------------------------------------
    # Panneau : Maintien enfoncé
    # ------------------------------------------------------------------
    def _build_hold_panel(self, parent):
        frame = ttk.Frame(parent, style="TFrame")

        ttk.Label(frame, text="Délai entre chaque clic (ms)").pack(anchor="w", pady=(8, 0))
        delay_entry = ttk.Entry(frame, textvariable=self.delay_var)
        delay_entry.pack(fill="x", pady=(4, 12))
        delay_entry.bind("<FocusOut>", self._apply_params)
        delay_entry.bind("<Return>", self._apply_params)

        ttk.Label(
            frame,
            text="Spam de clics tant que le bouton de la souris (gauche ou droit) est maintenu enfoncé.",
            style="Dim.TLabel",
            wraplength=340,
        ).pack(anchor="w")

        return frame

    # ------------------------------------------------------------------
    # Panneau : Macro personnalisée
    # ------------------------------------------------------------------
    def _build_macro_panel(self, parent):
        frame = ttk.Frame(parent, style="TFrame")
        frame.grid_rowconfigure(5, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Indicateur de position de la souris
        pos_panel = ttk.Frame(frame, style="Panel.TFrame")
        pos_panel.grid(row=0, column=0, sticky="ew", pady=(8, 8))
        self.mouse_pos_label = ttk.Label(
            pos_panel, text="Position souris : -, -", style="Panel.TLabel",
            font=("Segoe UI Semibold", 10),
        )
        self.mouse_pos_label.pack(padx=12, pady=8, anchor="w")

        # Sélecteur de macro
        ttk.Label(frame, text="Macro").grid(row=1, column=0, sticky="w")
        self.macro_selector_var = tk.StringVar(value=NEW_MACRO_LABEL)
        self.macro_selector = ttk.Combobox(
            frame,
            textvariable=self.macro_selector_var,
            state="readonly",
            style="TCombobox",
        )
        self.macro_selector.grid(row=2, column=0, sticky="ew", pady=(4, 8))
        self.macro_selector.bind("<<ComboboxSelected>>", self._on_macro_selected)

        # Nom de la macro
        ttk.Label(frame, text="Nom de la macro").grid(row=3, column=0, sticky="w")
        self.macro_name_var = tk.StringVar(value="")
        name_entry = ttk.Entry(frame, textvariable=self.macro_name_var)
        name_entry.grid(row=4, column=0, sticky="ew", pady=(4, 8))

        # Liste des blocs
        tree_frame = ttk.Frame(frame, style="TFrame")
        tree_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 8))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.macro_tree = ttk.Treeview(
            tree_frame, columns=("idx", "type", "value"), show="headings", height=6
        )
        self.macro_tree.heading("idx", text="#")
        self.macro_tree.heading("type", text="Type")
        self.macro_tree.heading("value", text="Valeur")
        self.macro_tree.column("idx", width=28, anchor="center", stretch=False)
        self.macro_tree.column("type", width=180, anchor="w")
        self.macro_tree.column("value", width=90, anchor="w")
        self.macro_tree.grid(row=0, column=0, sticky="nsew")
        self.macro_tree.bind("<Double-1>", self._on_tree_double_click)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.macro_tree.yview)
        self.macro_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Boutons de gestion des blocs
        block_btns = ttk.Frame(frame, style="TFrame")
        block_btns.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(
            block_btns, text="+ Ajouter bloc", style="Accent.TButton",
            command=lambda: self.open_block_dialog()
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            block_btns, text="+ Dans la boucle", style="Ghost.TButton",
            command=self.add_block_inside_loop
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            block_btns, text="Supprimer", style="Ghost.TButton", command=self.remove_block
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            block_btns, text="▲", style="Ghost.TButton", width=3,
            command=lambda: self.move_block(-1)
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            block_btns, text="▼", style="Ghost.TButton", width=3,
            command=lambda: self.move_block(1)
        ).pack(side="left")

        # Boutons de gestion de la macro
        macro_btns = ttk.Frame(frame, style="TFrame")
        macro_btns.grid(row=7, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(
            macro_btns, text="Nouvelle", style="Ghost.TButton", command=self.new_macro
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            macro_btns, text="Enregistrer", style="Accent.TButton", command=self.save_current_macro
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            macro_btns, text="Supprimer macro", style="Ghost.TButton", command=self.delete_current_macro
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            macro_btns, text="Tester", style="Ghost.TButton", command=self.test_macro
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            macro_btns, text="Arrêter", style="Ghost.TButton", command=stop_running_macro
        ).pack(side="left")

        self.macro_error_label = ttk.Label(frame, text="", style="Dim.TLabel", foreground=RED)
        self.macro_error_label.grid(row=8, column=0, sticky="w")

        ttk.Label(
            frame,
            text=(
                "Appuie sur le raccourci d'activation (ou le bouton) pour démarrer la macro "
                "sélectionnée ; appuie de nouveau pour l'arrêter. Sélectionne une boucle puis "
                "clique « + Dans la boucle » pour ajouter des blocs à l'intérieur."
            ),
            style="Dim.TLabel",
            wraplength=340,
        ).grid(row=9, column=0, sticky="w", pady=(4, 0))

        return frame

    # -- Gestion des macros --------------------------------------------------
    def _refresh_macro_selector(self, select_name=None):
        names = [m["name"] for m in self.macros]
        self.macro_selector["values"] = names + [NEW_MACRO_LABEL]
        if select_name and select_name in names:
            self.macro_selector_var.set(select_name)
        elif not select_name:
            self.macro_selector_var.set(NEW_MACRO_LABEL)

    def _on_macro_selected(self, event=None):
        name = self.macro_selector_var.get()
        if name == NEW_MACRO_LABEL:
            self.new_macro()
            return
        macro = next((m for m in self.macros if m["name"] == name), None)
        if macro:
            self.current_blocks = [dict(b) for b in macro.get("macros", [])]
            self.macro_name_var.set(name)
            self.macro_error_label.configure(text="")
            self._refresh_macro_tree()

    def new_macro(self):
        self.current_blocks = []
        self.macro_name_var.set("")
        self.macro_error_label.configure(text="")
        self._refresh_macro_tree()
        self.macro_selector_var.set(NEW_MACRO_LABEL)

    def save_current_macro(self):
        name = self.macro_name_var.get().strip()
        if not name:
            self.macro_error_label.configure(text="Nom de macro requis.")
            return
        if not self.current_blocks:
            self.macro_error_label.configure(text="Ajoute au moins un bloc.")
            return
        existing = next((m for m in self.macros if m["name"] == name), None)
        if existing:
            existing["macros"] = [dict(b) for b in self.current_blocks]
        else:
            self.macros.append({"name": name, "macros": [dict(b) for b in self.current_blocks]})
        try:
            save_macros(self.macros)
        except OSError as e:
            self.macro_error_label.configure(text=f"Erreur d'enregistrement : {e}")
            return
        self.macro_error_label.configure(text="")
        self._refresh_macro_selector(select_name=name)

    def delete_current_macro(self):
        name = self.macro_name_var.get().strip()
        if not name or not any(m["name"] == name for m in self.macros):
            self.new_macro()
            return
        if not messagebox.askyesno("Supprimer la macro", f"Supprimer la macro « {name} » ?"):
            return
        self.macros = [m for m in self.macros if m["name"] != name]
        try:
            save_macros(self.macros)
        except OSError as e:
            self.macro_error_label.configure(text=f"Erreur d'enregistrement : {e}")
        self.new_macro()
        self._refresh_macro_selector()

    def test_macro(self):
        start_macro_run(list(self.current_blocks), respect_toggle=False)

    # -- Gestion des blocs ----------------------------------------------------
    def _block_label(self, block):
        cmd = block.get("command")
        val = block.get("value")
        if cmd == "keyboard":
            return ("Touche clavier", str(val))
        if cmd == "mouse":
            return ("Clic souris", "Gauche" if val == "left" else "Droite")
        if cmd == "mousemove":
            if isinstance(val, dict):
                return ("Déplacer souris", f"{val.get('x')}, {val.get('y')}")
            return ("Déplacer souris", str(val))
        if cmd == "delay":
            return ("Attente", f"{val} ms")
        if cmd == "for":
            count = val.get("count", 1) if isinstance(val, dict) else 1
            return ("Boucle Pour", f"× {count}")
        if cmd == "while":
            if isinstance(val, dict) and val.get("condition") == "key_held":
                return ("Boucle Tant que", f"touche « {val.get('key', '?')} » maintenue")
            return ("Boucle Tant que", "toujours (jusqu'à arrêt)")
        return (str(cmd), str(val))

    def _refresh_macro_tree(self):
        self.macro_tree.delete(*self.macro_tree.get_children())
        self._iid_location = {}
        self._list_parent_iid = {}
        self._insert_blocks(self.current_blocks, "")

    def _insert_blocks(self, blocks_list, parent_iid):
        self._list_parent_iid[id(blocks_list)] = parent_iid
        for i, block in enumerate(blocks_list):
            iid = f"{parent_iid}.{i}" if parent_iid else str(i)
            type_label, value_label = self._block_label(block)
            self.macro_tree.insert(
                parent_iid, "end", iid=iid, values=(i + 1, type_label, value_label), open=True
            )
            self._iid_location[iid] = (blocks_list, i)
            if block.get("command") in ("for", "while"):
                nested = block.setdefault("value", {}).setdefault("blocks", [])
                self._insert_blocks(nested, iid)

    def _on_tree_double_click(self, event):
        sel = self.macro_tree.selection()
        if not sel:
            return
        loc = self._iid_location.get(sel[0])
        if not loc:
            return
        self.open_block_dialog(edit_location=loc)

    def remove_block(self):
        sel = self.macro_tree.selection()
        if not sel:
            return
        loc = self._iid_location.get(sel[0])
        if not loc:
            return
        blocks_list, idx = loc
        del blocks_list[idx]
        self._refresh_macro_tree()

    def move_block(self, direction):
        sel = self.macro_tree.selection()
        if not sel:
            return
        loc = self._iid_location.get(sel[0])
        if not loc:
            return
        blocks_list, idx = loc
        new_idx = idx + direction
        if 0 <= new_idx < len(blocks_list):
            blocks_list[idx], blocks_list[new_idx] = blocks_list[new_idx], blocks_list[idx]
            parent_iid = self._list_parent_iid.get(id(blocks_list), "")
            new_iid = f"{parent_iid}.{new_idx}" if parent_iid else str(new_idx)
            self._refresh_macro_tree()
            self.macro_tree.selection_set(new_iid)

    def add_block_inside_loop(self):
        sel = self.macro_tree.selection()
        if not sel:
            self.macro_error_label.configure(text="Sélectionne une boucle pour ajouter un bloc à l'intérieur.")
            return
        loc = self._iid_location.get(sel[0])
        if not loc:
            return
        blocks_list, idx = loc
        block = blocks_list[idx]
        if block.get("command") not in ("for", "while"):
            self.macro_error_label.configure(text="Sélectionne une boucle pour ajouter un bloc à l'intérieur.")
            return
        self.macro_error_label.configure(text="")
        nested = block.setdefault("value", {}).setdefault("blocks", [])
        self.open_block_dialog(target_list=nested)

    def open_block_dialog(self, target_list=None, edit_location=None):
        editing = edit_location is not None
        if editing:
            target_list, edit_index = edit_location
            existing_block = target_list[edit_index]
        else:
            if target_list is None:
                target_list = self.current_blocks
            existing_block = None

        dialog = tk.Toplevel(self.root)
        dialog.title("Modifier le bloc" if editing else "Ajouter un bloc")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        pad = 16

        ttk.Label(dialog, text="Type de bloc").pack(anchor="w", padx=pad, pady=(pad, 4))

        default_type = BLOCK_TYPE_KEYBOARD
        if existing_block:
            cmd = existing_block.get("command")
            default_type = {
                "keyboard": BLOCK_TYPE_KEYBOARD,
                "mouse": BLOCK_TYPE_MOUSE,
                "mousemove": BLOCK_TYPE_MOUSEMOVE,
                "delay": BLOCK_TYPE_DELAY,
                "for": BLOCK_TYPE_FOR,
                "while": BLOCK_TYPE_WHILE,
            }.get(cmd, BLOCK_TYPE_KEYBOARD)

        type_var = tk.StringVar(value=default_type)
        type_combo = ttk.Combobox(
            dialog, textvariable=type_var, state="readonly", values=BLOCK_TYPES, style="TCombobox"
        )
        type_combo.pack(fill="x", padx=pad)

        value_container = ttk.Frame(dialog, style="TFrame")
        value_container.pack(fill="x", padx=pad, pady=12)

        # -- Sous-panneau clavier --
        key_frame = ttk.Frame(value_container, style="TFrame")
        ttk.Label(key_frame, text="Touche (ex: i, esc, ctrl+c)").pack(anchor="w")
        key_row = ttk.Frame(key_frame, style="TFrame")
        key_row.pack(fill="x", pady=(4, 0))
        key_var = tk.StringVar(
            value=existing_block.get("value", "")
            if existing_block and existing_block.get("command") == "keyboard"
            else ""
        )
        key_entry = ttk.Entry(key_row, textvariable=key_var)
        key_entry.pack(side="left", fill="x", expand=True)

        def capture_key():
            capture_btn.configure(text="Appuie sur une touche...")
            dialog.update()

            def capture():
                try:
                    new_key = kb.read_hotkey(suppress=False)
                except Exception:
                    new_key = key_var.get()
                dialog.after(0, lambda: _finish_capture(new_key))

            def _finish_capture(new_key):
                key_var.set(new_key)
                capture_btn.configure(text="Capturer")

            threading.Thread(target=capture, daemon=True).start()

        capture_btn = ttk.Button(key_row, text="Capturer", style="Ghost.TButton", command=capture_key)
        capture_btn.pack(side="left", padx=(6, 0))

        # -- Sous-panneau souris --
        mouse_frame = ttk.Frame(value_container, style="TFrame")
        ttk.Label(mouse_frame, text="Bouton de la souris").pack(anchor="w")
        mouse_default = "Gauche"
        if existing_block and existing_block.get("command") == "mouse":
            mouse_default = "Gauche" if existing_block.get("value") == "left" else "Droite"
        mouse_var = tk.StringVar(value=mouse_default)
        ttk.Combobox(
            mouse_frame, textvariable=mouse_var, state="readonly",
            values=["Gauche", "Droite"], style="TCombobox"
        ).pack(fill="x", pady=(4, 0))

        # -- Sous-panneau déplacement souris --
        mousemove_frame = ttk.Frame(value_container, style="TFrame")
        mm_default_x, mm_default_y = "0", "0"
        if existing_block and existing_block.get("command") == "mousemove":
            mm_val = existing_block.get("value", {})
            if isinstance(mm_val, dict):
                mm_default_x = str(mm_val.get("x", "0"))
                mm_default_y = str(mm_val.get("y", "0"))

        coords_row = ttk.Frame(mousemove_frame, style="TFrame")
        coords_row.pack(fill="x")

        x_col = ttk.Frame(coords_row, style="TFrame")
        x_col.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(x_col, text="X").pack(anchor="w")
        mm_x_var = tk.StringVar(value=mm_default_x)
        ttk.Entry(x_col, textvariable=mm_x_var).pack(fill="x", pady=(4, 0))

        y_col = ttk.Frame(coords_row, style="TFrame")
        y_col.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(y_col, text="Y").pack(anchor="w")
        mm_y_var = tk.StringVar(value=mm_default_y)
        ttk.Entry(y_col, textvariable=mm_y_var).pack(fill="x", pady=(4, 0))

        def capture_position():
            capture_pos_btn.configure(text="Déplace la souris...")
            dialog.update()

            def countdown():
                for i in range(3, 0, -1):
                    label = f"Capture dans {i}..."
                    dialog.after(0, lambda t=label: capture_pos_btn.configure(text=t))
                    time.sleep(1)
                x, y = pyautogui.position()
                dialog.after(0, lambda: _finish_capture(x, y))

            def _finish_capture(x, y):
                mm_x_var.set(str(x))
                mm_y_var.set(str(y))
                capture_pos_btn.configure(text="Capturer position (3s)")

            threading.Thread(target=countdown, daemon=True).start()

        capture_pos_btn = ttk.Button(
            mousemove_frame, text="Capturer position (3s)", style="Ghost.TButton",
            command=capture_position,
        )
        capture_pos_btn.pack(fill="x", pady=(8, 0))
        ttk.Label(
            mousemove_frame,
            text="Place le curseur où tu veux pendant le compte à rebours.",
            style="Dim.TLabel",
            wraplength=300,
        ).pack(anchor="w", pady=(4, 0))

        # -- Sous-panneau délai --
        delay_frame = ttk.Frame(value_container, style="TFrame")
        ttk.Label(delay_frame, text="Durée d'attente (ms)").pack(anchor="w")
        delay_default = "1000"
        if existing_block and existing_block.get("command") == "delay":
            delay_default = str(existing_block.get("value", "1000"))
        delay_var = tk.StringVar(value=delay_default)
        ttk.Entry(delay_frame, textvariable=delay_var).pack(fill="x", pady=(4, 0))

        # -- Sous-panneau boucle Pour --
        for_frame = ttk.Frame(value_container, style="TFrame")
        ttk.Label(for_frame, text="Nombre d'itérations").pack(anchor="w")
        for_default = "5"
        if existing_block and existing_block.get("command") == "for":
            for_default = str(existing_block.get("value", {}).get("count", 5))
        for_count_var = tk.StringVar(value=for_default)
        ttk.Entry(for_frame, textvariable=for_count_var).pack(fill="x", pady=(4, 0))
        ttk.Label(
            for_frame,
            text="Ajoute ensuite des blocs à l'intérieur via « + Dans la boucle ».",
            style="Dim.TLabel",
            wraplength=300,
        ).pack(anchor="w", pady=(6, 0))

        # -- Sous-panneau boucle Tant que --
        while_frame = ttk.Frame(value_container, style="TFrame")
        ttk.Label(while_frame, text="Condition").pack(anchor="w")
        while_default_cond = WHILE_COND_ALWAYS
        while_default_key = ""
        if existing_block and existing_block.get("command") == "while":
            wv = existing_block.get("value", {})
            if wv.get("condition") == "key_held":
                while_default_cond = WHILE_COND_KEY_HELD
                while_default_key = wv.get("key", "")
        while_condition_var = tk.StringVar(value=while_default_cond)
        while_combo = ttk.Combobox(
            while_frame, textvariable=while_condition_var, state="readonly",
            values=[WHILE_COND_ALWAYS, WHILE_COND_KEY_HELD], style="TCombobox",
        )
        while_combo.pack(fill="x", pady=(4, 8))

        while_key_frame = ttk.Frame(while_frame, style="TFrame")
        ttk.Label(while_key_frame, text="Touche à surveiller").pack(anchor="w")
        while_key_row = ttk.Frame(while_key_frame, style="TFrame")
        while_key_row.pack(fill="x", pady=(4, 0))
        while_key_var = tk.StringVar(value=while_default_key)
        ttk.Entry(while_key_row, textvariable=while_key_var).pack(side="left", fill="x", expand=True)

        def capture_while_key():
            while_capture_btn.configure(text="Appuie sur une touche...")
            dialog.update()

            def capture():
                try:
                    new_key = kb.read_hotkey(suppress=False)
                except Exception:
                    new_key = while_key_var.get()
                dialog.after(0, lambda: _finish_capture(new_key))

            def _finish_capture(new_key):
                while_key_var.set(new_key)
                while_capture_btn.configure(text="Capturer")

            threading.Thread(target=capture, daemon=True).start()

        while_capture_btn = ttk.Button(
            while_key_row, text="Capturer", style="Ghost.TButton", command=capture_while_key
        )
        while_capture_btn.pack(side="left", padx=(6, 0))

        def show_while_key_row(*_):
            if while_condition_var.get() == WHILE_COND_KEY_HELD:
                while_key_frame.pack(fill="x")
            else:
                while_key_frame.pack_forget()

        while_combo.bind("<<ComboboxSelected>>", show_while_key_row)
        show_while_key_row()

        ttk.Label(
            while_frame,
            text="Ajoute ensuite des blocs à l'intérieur via « + Dans la boucle ».",
            style="Dim.TLabel",
            wraplength=300,
        ).pack(anchor="w", pady=(6, 0))

        panels = {
            BLOCK_TYPE_KEYBOARD: key_frame,
            BLOCK_TYPE_MOUSE: mouse_frame,
            BLOCK_TYPE_MOUSEMOVE: mousemove_frame,
            BLOCK_TYPE_DELAY: delay_frame,
            BLOCK_TYPE_FOR: for_frame,
            BLOCK_TYPE_WHILE: while_frame,
        }

        def show_panel(*_):
            for panel in panels.values():
                panel.pack_forget()
            panels[type_var.get()].pack(fill="x")

        type_combo.bind("<<ComboboxSelected>>", show_panel)
        show_panel()

        error_label = ttk.Label(dialog, text="", style="Dim.TLabel", foreground=RED)
        error_label.pack(anchor="w", padx=pad)

        def confirm():
            selected_type = type_var.get()
            if selected_type == BLOCK_TYPE_KEYBOARD:
                value = key_var.get().strip()
                if not value:
                    error_label.configure(text="Indique une touche.")
                    return
                block = {"command": "keyboard", "value": value}
            elif selected_type == BLOCK_TYPE_MOUSE:
                value = "left" if mouse_var.get() == "Gauche" else "right"
                block = {"command": "mouse", "value": value}
            elif selected_type == BLOCK_TYPE_MOUSEMOVE:
                try:
                    mx = int(mm_x_var.get().strip())
                    my = int(mm_y_var.get().strip())
                except ValueError:
                    error_label.configure(text="Coordonnées invalides.")
                    return
                block = {"command": "mousemove", "value": {"x": mx, "y": my}}
            elif selected_type == BLOCK_TYPE_FOR:
                try:
                    count = int(for_count_var.get().strip())
                    if count < 1:
                        raise ValueError
                except ValueError:
                    error_label.configure(text="Nombre d'itérations invalide.")
                    return
                nested = []
                if existing_block and existing_block.get("command") == "for":
                    nested = existing_block.get("value", {}).get("blocks", [])
                block = {"command": "for", "value": {"count": count, "blocks": nested}}
            elif selected_type == BLOCK_TYPE_WHILE:
                key_held = while_condition_var.get() == WHILE_COND_KEY_HELD
                key_value = while_key_var.get().strip()
                if key_held and not key_value:
                    error_label.configure(text="Indique une touche à surveiller.")
                    return
                nested = []
                if existing_block and existing_block.get("command") == "while":
                    nested = existing_block.get("value", {}).get("blocks", [])
                value = {"condition": "key_held" if key_held else "always", "blocks": nested}
                if key_held:
                    value["key"] = key_value
                block = {"command": "while", "value": value}
            else:
                try:
                    ms = int(delay_var.get().strip())
                    if ms < 0:
                        raise ValueError
                except ValueError:
                    error_label.configure(text="Durée invalide.")
                    return
                block = {"command": "delay", "value": str(ms)}

            if editing:
                target_list[edit_index] = block
            else:
                target_list.append(block)
            self._refresh_macro_tree()
            dialog.destroy()

        btn_row = ttk.Frame(dialog, style="TFrame")
        btn_row.pack(fill="x", padx=pad, pady=(4, pad))
        ttk.Button(btn_row, text="Annuler", style="Ghost.TButton", command=dialog.destroy).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(
            btn_row, text="Modifier" if editing else "Ajouter", style="Accent.TButton", command=confirm
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Paramètres partagés (délai / nombre de clics)
    # ------------------------------------------------------------------
    def _apply_params(self, event=None):
        global repetition_presses, delay_ms
        try:
            repetition_presses = max(1, int(self.rep_var.get()))
        except ValueError:
            self.rep_var.set(str(repetition_presses))
        try:
            delay_ms = max(0, int(self.delay_var.get()))
        except ValueError:
            self.delay_var.set(str(delay_ms))
        self.error_label.configure(text="")

    def toggle_active(self):
        global auto_clicker_active
        if click_mode == MODE_MACRO:
            self.toggle_macro_run()
            return
        auto_clicker_active = not auto_clicker_active
        if not auto_clicker_active:
            # On coupe proprement les modes en cours (maintien / salves).
            for b in holding:
                holding[b] = False
        self._refresh_status()

    def toggle_macro_run(self):
        if macro_lock.locked():
            stop_running_macro()
        else:
            start_macro_run(list(self.current_blocks), respect_toggle=False)
        self._refresh_status()

    def _refresh_status(self):
        if click_mode == MODE_MACRO:
            running = macro_lock.locked()
            self.status_dot.itemconfig(self.dot_id, fill=GREEN if running else RED)
            self.status_label.configure(text="Macro en cours" if running else "Macro arrêtée")
            return
        if auto_clicker_active:
            self.status_dot.itemconfig(self.dot_id, fill=GREEN)
            self.status_label.configure(text="Activé")
        else:
            self.status_dot.itemconfig(self.dot_id, fill=RED)
            self.status_label.configure(text="Désactivé")

    # --- Mode ------------------------------------------------------------
    def _on_mode_selected(self, event=None):
        global click_mode
        previous_mode = click_mode
        label = self.mode_var.get()
        click_mode = LABEL_TO_MODE.get(label, click_mode)
        if previous_mode == MODE_MACRO and click_mode != MODE_MACRO:
            stop_running_macro()
        for b in holding:
            holding[b] = False
        self._sync_mode_ui()

    def _sync_mode_ui(self):
        self.mode_var.set(MODE_LABELS[click_mode])
        self.mode_frames[click_mode].tkraise()
        if click_mode == MODE_MACRO:
            self.toggle_btn.configure(text="Démarrer/Arrêter la macro (ou appuyer sur la touche)")
        else:
            self.toggle_btn.configure(text="Activer  (ou appuyer sur la touche)")
        self._refresh_status()

    def _update_mouse_position(self):
        if click_mode == MODE_MACRO:
            try:
                x, y = pyautogui.position()
                self.mouse_pos_label.configure(text=f"Position souris : {x}, {y}")
            except Exception:
                pass
            self._refresh_status()
        self.root.after(100, self._update_mouse_position)

    def cycle_mode(self):
        global click_mode
        previous_mode = click_mode
        idx = MODES.index(click_mode)
        click_mode = MODES[(idx + 1) % len(MODES)]
        if previous_mode == MODE_MACRO and click_mode != MODE_MACRO:
            stop_running_macro()
        for b in holding:
            holding[b] = False
        self._sync_mode_ui()

    def _register_mode_hotkey(self):
        global registered_mode_hotkey
        if registered_mode_hotkey is not None:
            try:
                kb.remove_hotkey(registered_mode_hotkey)
            except (KeyError, ValueError):
                pass
        registered_mode_hotkey = kb.add_hotkey(
            MODE_HOTKEY, lambda: self.root.after(0, self.cycle_mode)
        )

    # --- Raccourci d'activation -------------------------------------------
    def start_rebind(self):
        self.rebind_btn.configure(text="Appuie sur une touche...")
        self.hotkey_label.configure(text="...")
        self.root.update()

        def capture():
            try:
                new_key = kb.read_hotkey(suppress=False)
            except Exception:
                new_key = hotkey_str
            self.root.after(0, lambda: self._finish_rebind(new_key))

        threading.Thread(target=capture, daemon=True).start()

    def _finish_rebind(self, new_key):
        self._refresh_hotkey(new_key)
        self.rebind_btn.configure(text="Changer")

    def _refresh_hotkey(self, new_key):
        global hotkey_str, registered_hotkey
        if registered_hotkey is not None:
            try:
                kb.remove_hotkey(registered_hotkey)
            except (KeyError, ValueError):
                pass
        hotkey_str = new_key
        self.hotkey_label.configure(text=hotkey_str.upper())
        registered_hotkey = kb.add_hotkey(hotkey_str, self._toggle_from_hotkey)

    def _toggle_from_hotkey(self):
        self.root.after(0, self.toggle_active)


def main():
    root = tk.Tk()
    app = AutoClickerApp(root)

    def on_close():
        mouse_listener.stop()
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()