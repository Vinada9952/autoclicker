import sys
import threading
import time

import pyautogui
import keyboard as kb
import tkinter as tk
from tkinter import ttk
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
# État partagé
# ---------------------------------------------------------------------------
auto_clicker_active = False
repetition_presses = 50
delay_ms = 1
hotkey_str = "caps lock"
registered_hotkey = None

# Modes disponibles
MODE_AUTO = "auto"    # clic continu tant que actif (autoclicker classique)
MODE_BURST = "burst"  # salve de N clics à chaque clic souris
MODE_HOLD = "hold"    # spam de clics tant que le bouton est maintenu

MODES = [MODE_AUTO, MODE_BURST, MODE_HOLD]
MODE_LABELS = {
    MODE_AUTO: "Auto Clicker classique (continu)",
    MODE_BURST: "Salve au clic",
    MODE_HOLD: "Maintien enfoncé",
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

# Référence vers l'app pour synchroniser l'UI depuis les hotkeys.
app_instance = None


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
            pyautogui.leftClick()
            time.sleep(max(delay_ms, 1) / 1000)
        else:
            time.sleep(0.05)


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
class AutoClickerApp:
    def __init__(self, root):
        global app_instance
        app_instance = self

        self.root = root
        root.title("Auto Clicker")
        root.configure(bg=BG)
        root.geometry("360x520")
        root.resizable(False, False)

        self._build_style()
        self._build_ui()
        self._refresh_hotkey(hotkey_str)
        self._register_mode_hotkey()
        self._sync_mode_combobox()

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

        header = ttk.Frame(self.root, style="TFrame")
        header.pack(fill="x", padx=pad, pady=(pad, 6))
        ttk.Label(header, text="Auto Clicker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Clique n'importe où pour lancer la répétition",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        # --- Statut ---------------------------------------------------
        status_panel = ttk.Frame(self.root, style="Panel.TFrame")
        status_panel.pack(fill="x", padx=pad, pady=10)

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

        # --- Mode -------------------------------------------------------
        mode_frame = ttk.Frame(self.root, style="TFrame")
        mode_frame.pack(fill="x", padx=pad, pady=(6, 0))
        ttk.Label(mode_frame, text="Mode").pack(anchor="w")

        self.mode_var = tk.StringVar(value=MODE_LABELS[click_mode])
        self.mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=list(MODE_LABELS.values()),
            state="readonly",
            style="TCombobox",
        )
        self.mode_combo.pack(fill="x", pady=(4, 4))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        self.mode_hint = ttk.Label(mode_frame, text="", style="Dim.TLabel", wraplength=320)
        self.mode_hint.pack(anchor="w", pady=(0, 6))

        ttk.Label(
            mode_frame,
            text=f"Changer de mode : {MODE_HOTKEY.upper()}",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        # --- Paramètres -------------------------------------------------
        form = ttk.Frame(self.root, style="TFrame")
        form.pack(fill="x", padx=pad, pady=6)

        ttk.Label(form, text="Nombre de clics par déclenchement (mode Salve)").pack(anchor="w")
        self.rep_var = tk.StringVar(value=str(repetition_presses))
        rep_entry = ttk.Entry(form, textvariable=self.rep_var)
        rep_entry.pack(fill="x", pady=(4, 12))
        rep_entry.bind("<FocusOut>", self._apply_params)
        rep_entry.bind("<Return>", self._apply_params)

        ttk.Label(form, text="Délai entre chaque clic (ms)").pack(anchor="w")
        self.delay_var = tk.StringVar(value=str(delay_ms))
        delay_entry = ttk.Entry(form, textvariable=self.delay_var)
        delay_entry.pack(fill="x", pady=(4, 12))
        delay_entry.bind("<FocusOut>", self._apply_params)
        delay_entry.bind("<Return>", self._apply_params)

        # --- Raccourci ----------------------------------------------------
        hk_frame = ttk.Frame(self.root, style="TFrame")
        hk_frame.pack(fill="x", padx=pad, pady=(6, 0))
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

        # --- Bas de fenêtre ------------------------------------------------
        self.error_label = ttk.Label(self.root, text="", style="Dim.TLabel", foreground=RED)
        self.error_label.pack(padx=pad, pady=(10, 0), anchor="w")

        ttk.Label(
            self.root,
            text="Ferme la fenêtre pour quitter",
            style="Dim.TLabel",
        ).pack(side="bottom", pady=12)

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
        auto_clicker_active = not auto_clicker_active
        if not auto_clicker_active:
            # On coupe proprement les modes en cours (maintien / salves).
            for b in holding:
                holding[b] = False
        self._refresh_status()

    def _refresh_status(self):
        if auto_clicker_active:
            self.status_dot.itemconfig(self.dot_id, fill=GREEN)
            self.status_label.configure(text="Activé")
        else:
            self.status_dot.itemconfig(self.dot_id, fill=RED)
            self.status_label.configure(text="Désactivé")

    # --- Mode ------------------------------------------------------------
    def _on_mode_selected(self, event=None):
        global click_mode
        label = self.mode_var.get()
        click_mode = LABEL_TO_MODE.get(label, click_mode)
        for b in holding:
            holding[b] = False
        self._sync_mode_combobox()

    def _sync_mode_combobox(self):
        self.mode_var.set(MODE_LABELS[click_mode])
        hints = {
            MODE_AUTO: "Clique en continu (clic gauche) tant que l'auto clicker est activé.",
            MODE_BURST: "Envoie une salve de N clics à chaque clic de souris.",
            MODE_HOLD: "Spam de clics tant que le bouton de la souris est maintenu enfoncé.",
        }
        self.mode_hint.configure(text=hints[click_mode])

    def cycle_mode(self):
        global click_mode
        idx = MODES.index(click_mode)
        click_mode = MODES[(idx + 1) % len(MODES)]
        for b in holding:
            holding[b] = False
        self._sync_mode_combobox()

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