import os
import json
import pandas as pd
import numpy as np
import io
import time
from datetime import datetime, timedelta

# --- Kivy Configuration: Force Portrait Mode ---
from kivy.config import Config
Config.set('graphics', 'orientation', 'portrait')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import platform

# --- Robust Plyer Imports ---
try:
    from plyer import toast, storagepath, permissions
    PLYER_AVAILABLE = True
except ImportError:
    print("WARNING: Plyer components could not be imported. Native features like toast notifications and file saving will be disabled.")
    PLYER_AVAILABLE = False
    def toast(message, **kwargs): pass
    class storagepath:
        @staticmethod
        def get_downloads_dir(): return '.'
    class permissions:
        WRITE_EXTERNAL_STORAGE = 'WRITE_EXTERNAL_STORAGE'
        READ_EXTERNAL_STORAGE = 'READ_EXTERNAL_STORAGE'
        @staticmethod
        def request_permissions(perms, callback=None): pass


# --- Configuration for Data Persistence ---
try:
    user_data_dir = App.get_running_app().user_data_dir
except AttributeError:
    user_data_dir = '.' 
CONFIG_DIR = os.path.join(user_data_dir, ".cwl_rechner_config")
ROSTER_FILE = os.path.join(CONFIG_DIR, "clan_roster.json")
POINTS_FILE = os.path.join(CONFIG_DIR, "point_system.json")

def save_settings(roster, points):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(ROSTER_FILE, 'w') as f: json.dump(roster, f, indent=4)
    with open(POINTS_FILE, 'w') as f: json.dump(points, f, indent=4)

def load_settings():
    default_points = {
        "ell_gt_2": 3, "ell_eq_1": 2, "ell_eq_0": 1, "ell_eq_-1": 0, "ell_lt_-2": -1,
        "atk_3s_gt_2": 6, "atk_3s_eq": 4, "atk_3s_lt_-2": 2, "atk_2s_ge_90": 4,
        "atk_2s_80_89": 3, "atk_2s_50_79": 2, "atk_1s_90_99": 2, "atk_1s_50_89": 1,
        "aktiv": 1, "bonus_100": 1, "mut_base": 1, "mut_extra": 2, "all_attacks": 2,
    }
    try:
        with open(ROSTER_FILE, 'r') as f: roster = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): roster = ["Beispielspieler 1", "Beispielspieler 2"]
    try:
        with open(POINTS_FILE, 'r') as f: points = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): points = default_points
    return roster, points

def calculate_all_points(df, point_system):
    if df.empty: return pd.DataFrame(columns=["Name", "Punkte"])
    df_calc = df.copy()
    total_points = pd.Series(0, index=df_calc.index, dtype=float)
    total_attacks = pd.Series(0, index=df_calc.index, dtype=int)
    df_calc['Eigenes_Rathaus'] = pd.to_numeric(df_calc['Eigenes_Rathaus'], errors='coerce').fillna(0)
    for i in range(1, 8):
        stars, pct, opp_rh = (pd.to_numeric(df_calc.get(c), errors='coerce') for c in [f"Tag{i}_Sterne", f"Tag{i}_Prozent", f"Tag{i}_Rathaus_Gegner"])
        attack_made = (stars.notna() | pct.notna()) & opp_rh.notna()
        total_attacks += attack_made.astype(int)
        stars = stars.fillna(-1); pct = pct.fillna(0)
        diff = opp_rh - df_calc['Eigenes_Rathaus']
        
        ell_conditions = [diff >= 2, diff == 1, diff == 0, diff == -1, diff <= -2]
        ell_choices = [point_system["ell_gt_2"], point_system["ell_eq_1"], point_system["ell_eq_0"], point_system["ell_eq_-1"], point_system["ell_lt_-2"]]
        ell_points = np.select(ell_conditions, ell_choices, default=0)

        attack_conditions = [
            (stars == 3) & (diff >= 2), (stars == 3) & (diff.between(-1, 1)), (stars == 3) & (diff <= -2),
            (stars == 2) & (pct >= 90), (stars == 2) & (pct.between(80, 89)), (stars == 2) & (pct.between(50, 79)),
            (stars == 1) & (pct.between(90, 99)), (stars == 1) & (pct.between(50, 89)),]
        attack_choices = [
            point_system["atk_3s_gt_2"], point_system["atk_3s_eq"], point_system["atk_3s_lt_-2"],
            point_system["atk_2s_ge_90"], point_system["atk_2s_80_89"], point_system["atk_2s_50_79"],
            point_system["atk_1s_90_99"], point_system["atk_1s_50_89"]]
        attack_points = np.select(attack_conditions, attack_choices, default=0)

        aktiv_points = np.where(attack_made, point_system["aktiv"], 0)
        bonus_100_points = np.where((pct == 100) & (diff >= 0), point_system["bonus_100"], 0)
        courage_conditions = [(diff >= 3) & (pct.between(30, 49)), (diff >= 3)]
        courage_choices = [point_system["mut_extra"], point_system["mut_base"]]
        mut_points = np.select(courage_conditions, courage_choices, default=0)
        
        daily_total = ell_points + attack_points + aktiv_points + bonus_100_points + mut_points
        total_points += np.where(attack_made, daily_total, 0)
        
    total_points += np.where(total_attacks >= 7, point_system["all_attacks"], 0)
    results = pd.DataFrame({"Name": df_calc["Name"], "Punkte": total_points.astype(int)})
    return results.sort_values(by=["Punkte", "Name"], ascending=[False, True]).reset_index(drop=True)

# --- Custom Styled Widgets for "De Luxe" Design ---
class HeaderLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.font_size = '22sp'; self.bold = True; self.size_hint_y = None; self.height = dp(50)
class SubheaderLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.font_size = '16sp'; self.size_hint_y = None; self.height = dp(30); self.color = (0.8, 0.8, 0.8, 1)
class TableHeaderLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.bold = True; self.size_hint_y = None; self.height = dp(40); self.size_hint_x = None; self.width = dp(100)
        with self.canvas.before: Color(0.1, 0.1, 0.1, 1); self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self.update_rect, size=self.update_rect)
    def update_rect(self, *args): self.rect.pos = self.pos; self.rect.size = self.size
class StyledTextInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.multiline = False; self.input_filter = 'int'; self.halign = 'center'; self.size_hint_y = None; self.height = dp(40); self.background_color = (0.2, 0.2, 0.2, 1); self.foreground_color = (1, 1, 1, 1); self.cursor_color = (1, 1, 1, 1); self.padding = [dp(6), dp(10), dp(6), dp(10)]; self.size_hint_x = None; self.width = dp(100)
class StyledBigTextInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.size_hint_y=None; self.height=dp(250); self.background_color=(0.15, 0.15, 0.15, 1); self.foreground_color=(1, 1, 1, 1)
class GradientButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.background_color = (0,0,0,0); self.font_size = '15sp'; self.size_hint_y = None; self.height = dp(50); self.bold = True
        with self.canvas.before: 
            self.canvas_color = Color(0.9, 0.25, 0.34, 1)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self.update_rect, size=self.update_rect, state=self.on_state)
    def update_rect(self, *args): self.rect.pos = self.pos; self.rect.size = self.size
    def on_state(self, instance, value): 
        if value == 'down': self.canvas_color.rgba = (0.8, 0.15, 0.24, 1)
        else: self.canvas_color.rgba = (0.9, 0.25, 0.34, 1)
class SecondaryButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.background_color = (0.2, 0.2, 0.2, 1); self.font_size = '15sp'; self.size_hint_y = None; self.height = dp(50)

# --- Kivy Screen Classes ---
class BaseScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10)); self.add_widget(self.layout); self.inputs = {}
    def rebuild_layout(self): self.layout.clear_widgets(); self.inputs.clear()

class Step1Screen(BaseScreen):
    def on_pre_enter(self, *args): self.rebuild_layout()
    def rebuild_layout(self):
        super().rebuild_layout(); app = App.get_running_app()
        self.layout.add_widget(HeaderLabel(text="Schritt 1: Rathäuser & Gegner"))
        self.roster = app.roster
        if not self.roster:
            self.layout.add_widget(Label(text="Bitte zuerst Mitglieder in den Einstellungen eintragen."))
            nav_bar = BoxLayout(size_hint_y=None, height=dp(50)); settings_button = GradientButton(text="Zu den Einstellungen"); settings_button.bind(on_press=lambda x: setattr(app.screen_manager, 'current', 'settings')); nav_bar.add_widget(settings_button); self.layout.add_widget(nav_bar)
            return
        if app.data_df.empty: app.data_df = app.create_new_dataframe()
        grid = GridLayout(cols=9, spacing=dp(2), size_hint_y=None, size_hint_x=None); grid.bind(minimum_height=grid.setter('height')); grid.bind(minimum_width=grid.setter('width'))
        for header_text in ["Name", "Eigenes RH"] + [f"Gegner T{i}" for i in range(1, 8)]:
            lbl = TableHeaderLabel(text=header_text)
            if header_text == "Name": lbl.width = dp(150)
            grid.add_widget(lbl)
        for index, row in app.data_df.iterrows():
            player_name = row["Name"]; self.inputs[player_name] = {}; name_lbl = Label(text=player_name, size_hint_y=None, height=dp(40), size_hint_x=None, width=dp(150)); grid.add_widget(name_lbl)
            own_th_val = "" if pd.isna(row.get("Eigenes_Rathaus")) else str(int(row.get("Eigenes_Rathaus")))
            own_th_input = StyledTextInput(text=own_th_val); self.inputs[player_name]['Eigenes_Rathaus'] = own_th_input; grid.add_widget(own_th_input)
            for i in range(1, 8):
                col_name = f'Tag{i}_Rathaus_Gegner'; opp_th_val = "" if pd.isna(row.get(col_name)) else str(int(row.get(col_name)))
                opp_th_input = StyledTextInput(text=opp_th_val); self.inputs[player_name][col_name] = opp_th_input; grid.add_widget(opp_th_input)
        scrollview = ScrollView(scroll_type=['bars'], bar_width=dp(10)); scrollview.add_widget(grid); self.layout.add_widget(scrollview)
        nav_bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10)); settings_button = SecondaryButton(text="Einstellungen"); settings_button.bind(on_press=lambda x: setattr(app.screen_manager, 'current', 'settings')); save_button = SecondaryButton(text="💾 Speichern"); save_button.bind(on_press=self.save_data); next_button = GradientButton(text="Weiter"); next_button.bind(on_press=self.go_to_step2); nav_bar.add_widget(settings_button); nav_bar.add_widget(save_button); nav_bar.add_widget(next_button); self.layout.add_widget(nav_bar)
    def save_data(self, instance): App.get_running_app().save_from_inputs(self.inputs, "Daten gespeichert!")
    def go_to_step2(self, instance): App.get_running_app().save_from_inputs(self.inputs); App.get_running_app().screen_manager.current = 'step2'

class Step2Screen(BaseScreen):
    def on_pre_enter(self, *args): self.rebuild_layout()
    def rebuild_layout(self):
        super().rebuild_layout(); app = App.get_running_app()
        self.layout.add_widget(HeaderLabel(text="Schritt 2: Sterne & Prozent"))
        self.layout.add_widget(SubheaderLabel(text="Sterne"))
        stars_grid = GridLayout(cols=8, spacing=dp(2), size_hint_y=None, size_hint_x=None); stars_grid.bind(minimum_height=stars_grid.setter('height')); stars_grid.bind(minimum_width=stars_grid.setter('width'))
        for h in ["Name"] + [f"T{i} Sterne" for i in range(1, 8)]: stars_grid.add_widget(TableHeaderLabel(text=h, width=dp(150) if h == "Name" else dp(100)))
        for _, row in app.data_df.iterrows():
            name = row['Name']; self.inputs[name] = {}; stars_grid.add_widget(Label(text=name, size_hint_y=None, height=dp(40), size_hint_x=None, width=dp(150)))
            for i in range(1, 8):
                val = "" if pd.isna(row.get(f'Tag{i}_Sterne')) else str(int(row.get(f'Tag{i}_Sterne'))); inp = StyledTextInput(text=val); self.inputs[name][f'Tag{i}_Sterne'] = inp; stars_grid.add_widget(inp)
        stars_scroll = ScrollView(size_hint_y=0.4, scroll_type=['bars'], bar_width=dp(10)); stars_scroll.add_widget(stars_grid); self.layout.add_widget(stars_scroll)
        self.layout.add_widget(SubheaderLabel(text="Prozent"))
        pct_grid = GridLayout(cols=8, spacing=dp(2), size_hint_y=None, size_hint_x=None); pct_grid.bind(minimum_height=pct_grid.setter('height')); pct_grid.bind(minimum_width=pct_grid.setter('width'))
        for h in ["Name"] + [f"T{i} %" for i in range(1, 8)]: pct_grid.add_widget(TableHeaderLabel(text=h, width=dp(150) if h == "Name" else dp(100)))
        for _, row in app.data_df.iterrows():
            name = row['Name']; pct_grid.add_widget(Label(text=name, size_hint_y=None, height=dp(40), size_hint_x=None, width=dp(150)))
            for i in range(1, 8):
                val = "" if pd.isna(row.get(f'Tag{i}_Prozent')) else str(int(row.get(f'Tag{i}_Prozent'))); inp = StyledTextInput(text=val); self.inputs[name][f'Tag{i}_Prozent'] = inp; pct_grid.add_widget(inp)
        pct_scroll = ScrollView(size_hint_y=0.4, scroll_type=['bars'], bar_width=dp(10)); pct_scroll.add_widget(pct_grid); self.layout.add_widget(pct_scroll)
        nav_bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10)); back_button = SecondaryButton(text="Zurück"); back_button.bind(on_press=lambda x: setattr(app.screen_manager, 'current', 'step1')); save_button = SecondaryButton(text="💾 Speichern"); save_button.bind(on_press=self.save_data); calc_button = GradientButton(text="Berechnen"); calc_button.bind(on_press=self.go_to_step3); nav_bar.add_widget(back_button); nav_bar.add_widget(save_button); nav_bar.add_widget(calc_button); self.layout.add_widget(nav_bar)
    def save_data(self, instance): App.get_running_app().save_from_inputs(self.inputs, "Daten gespeichert!")
    def go_to_step3(self, instance): app = App.get_running_app(); app.save_from_inputs(self.inputs); app.results_df = calculate_all_points(app.data_df, app.point_system); app.screen_manager.current = 'step3'

class Step3Screen(BaseScreen):
    def on_pre_enter(self, *args): self.rebuild_layout()
    def rebuild_layout(self):
        super().rebuild_layout(); app = App.get_running_app()
        self.layout.add_widget(HeaderLabel(text="Endwertung"))
        results_grid = GridLayout(cols=2, spacing=dp(2), size_hint_y=None); results_grid.bind(minimum_height=results_grid.setter('height'))
        results_grid.add_widget(TableHeaderLabel(text="Name", width=dp(200))); results_grid.add_widget(TableHeaderLabel(text="Punkte", width=dp(100)))
        if not app.results_df.empty:
            for _, row in app.results_df.iterrows():
                results_grid.add_widget(Label(text=str(row['Name']), size_hint_y=None, height=dp(40))); results_grid.add_widget(Label(text=str(row['Punkte']), size_hint_y=None, height=dp(40)))
        results_scroll = ScrollView(); results_scroll.add_widget(results_grid); self.layout.add_widget(results_scroll)
        nav_bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10)); back_button = SecondaryButton(text="Zurück"); back_button.bind(on_press=lambda x: setattr(app.screen_manager, 'current', 'step2')); excel_button = SecondaryButton(text="📥 Excel"); excel_button.bind(on_press=self.export_excel); reset_button = GradientButton(text="Neuer Durchgang"); reset_button.bind(on_press=self.reset_app); nav_bar.add_widget(back_button); nav_bar.add_widget(excel_button); nav_bar.add_widget(reset_button); self.layout.add_widget(nav_bar)
    def export_excel(self, instance):
        app = App.get_running_app()
        if app.results_df.empty: toast("Keine Daten zum Exportieren vorhanden."); return
        try:
            download_dir = storagepath.get_downloads_dir(); path = os.path.join(download_dir, 'cwl_bonus_wertung.xlsx')
            app.results_df.to_excel(path, index=False, engine='xlsxwriter'); toast(f"Excel-Datei gespeichert: {path}")
        except Exception as e: toast(f"Fehler beim Speichern: {e}")
    def reset_app(self, instance): app = App.get_running_app(); app.reset_data()

class SettingsScreen(BaseScreen):
    def on_pre_enter(self, *args): self.rebuild_layout()
    def rebuild_layout(self):
        super().rebuild_layout(); app = App.get_running_app()
        self.layout.add_widget(HeaderLabel(text="Einstellungen"))
        
        scroll_content = BoxLayout(orientation='vertical', spacing=dp(20), size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        scroll_content.add_widget(SubheaderLabel(text="Clan-Mitglieder (ein Name pro Zeile)"))
        self.roster_input = StyledBigTextInput(text="\n".join(app.roster)); scroll_content.add_widget(self.roster_input)

        scroll_content.add_widget(SubheaderLabel(text="Punktesystem"))
        
        points_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        points_layout.bind(minimum_height=points_layout.setter('height'))
        
        self.point_inputs = {}
        points = app.point_system

        points_layout.add_widget(Label(text="Punkte für Rathaus-Level Differenz", bold=True))
        ell_grid = GridLayout(cols=5, spacing=dp(5), size_hint_y=None, height=dp(80));
        ell_grid.add_widget(Label(text="RH+2")); ell_grid.add_widget(Label(text="RH+1")); ell_grid.add_widget(Label(text="RH=0")); ell_grid.add_widget(Label(text="RH-1")); ell_grid.add_widget(Label(text="RH-2"))
        self.point_inputs["ell_gt_2"] = StyledTextInput(text=str(points["ell_gt_2"])); ell_grid.add_widget(self.point_inputs["ell_gt_2"])
        self.point_inputs["ell_eq_1"] = StyledTextInput(text=str(points["ell_eq_1"])); ell_grid.add_widget(self.point_inputs["ell_eq_1"])
        self.point_inputs["ell_eq_0"] = StyledTextInput(text=str(points["ell_eq_0"])); ell_grid.add_widget(self.point_inputs["ell_eq_0"])
        self.point_inputs["ell_eq_-1"] = StyledTextInput(text=str(points["ell_eq_-1"])); ell_grid.add_widget(self.point_inputs["ell_eq_-1"])
        self.point_inputs["ell_lt_-2"] = StyledTextInput(text=str(points["ell_lt_-2"])); ell_grid.add_widget(self.point_inputs["ell_lt_-2"])
        points_layout.add_widget(ell_grid)

        points_layout.add_widget(Label(text="Punkte für Angriffe", bold=True, padding=(0, dp(10))))
        atk_grid = GridLayout(cols=3, spacing=dp(10), size_hint_y=None, height=dp(200))
        col1 = BoxLayout(orientation='vertical', spacing=dp(5)); col1.add_widget(Label(text="3 Sterne", bold=True));
        col1.add_widget(Label(text="vs RH+2")); self.point_inputs["atk_3s_gt_2"] = StyledTextInput(text=str(points["atk_3s_gt_2"])); col1.add_widget(self.point_inputs["atk_3s_gt_2"])
        col1.add_widget(Label(text="vs RH=0")); self.point_inputs["atk_3s_eq"] = StyledTextInput(text=str(points["atk_3s_eq"])); col1.add_widget(self.point_inputs["atk_3s_eq"])
        col1.add_widget(Label(text="vs RH-2")); self.point_inputs["atk_3s_lt_-2"] = StyledTextInput(text=str(points["atk_3s_lt_-2"])); col1.add_widget(self.point_inputs["atk_3s_lt_-2"])
        col2 = BoxLayout(orientation='vertical', spacing=dp(5)); col2.add_widget(Label(text="2 Sterne", bold=True));
        col2.add_widget(Label(text="90%+")); self.point_inputs["atk_2s_ge_90"] = StyledTextInput(text=str(points["atk_2s_ge_90"])); col2.add_widget(self.point_inputs["atk_2s_ge_90"])
        col2.add_widget(Label(text="80-89%")); self.point_inputs["atk_2s_80_89"] = StyledTextInput(text=str(points["atk_2s_80_89"])); col2.add_widget(self.point_inputs["atk_2s_80_89"])
        col2.add_widget(Label(text="50-79%")); self.point_inputs["atk_2s_50_79"] = StyledTextInput(text=str(points["atk_2s_50_79"])); col2.add_widget(self.point_inputs["atk_2s_50_79"])
        col3 = BoxLayout(orientation='vertical', spacing=dp(5)); col3.add_widget(Label(text="1 Stern", bold=True));
        col3.add_widget(Label(text="90-99%")); self.point_inputs["atk_1s_90_99"] = StyledTextInput(text=str(points["atk_1s_90_99"])); col3.add_widget(self.point_inputs["atk_1s_90_99"])
        col3.add_widget(Label(text="50-89%")); self.point_inputs["atk_1s_50_89"] = StyledTextInput(text=str(points["atk_1s_50_89"])); col3.add_widget(self.point_inputs["atk_1s_50_89"])
        atk_grid.add_widget(col1); atk_grid.add_widget(col2); atk_grid.add_widget(col3)
        points_layout.add_widget(atk_grid)

        points_layout.add_widget(Label(text="Bonuspunkte", bold=True, padding=(0, dp(10))))
        bonus_grid = GridLayout(cols=5, spacing=dp(5), size_hint_y=None, height=dp(80))
        bonus_grid.add_widget(Label(text="Aktivität")); bonus_grid.add_widget(Label(text="100%")); bonus_grid.add_widget(Label(text="Mut")); bonus_grid.add_widget(Label(text="Extra Mut")); bonus_grid.add_widget(Label(text="7 Angriffe"))
        self.point_inputs["aktiv"] = StyledTextInput(text=str(points["aktiv"])); bonus_grid.add_widget(self.point_inputs["aktiv"])
        self.point_inputs["bonus_100"] = StyledTextInput(text=str(points["bonus_100"])); bonus_grid.add_widget(self.point_inputs["bonus_100"])
        self.point_inputs["mut_base"] = StyledTextInput(text=str(points["mut_base"])); bonus_grid.add_widget(self.point_inputs["mut_base"])
        self.point_inputs["mut_extra"] = StyledTextInput(text=str(points["mut_extra"])); bonus_grid.add_widget(self.point_inputs["mut_extra"])
        self.point_inputs["all_attacks"] = StyledTextInput(text=str(points["all_attacks"])); bonus_grid.add_widget(self.point_inputs["all_attacks"])
        points_layout.add_widget(bonus_grid)

        scroll_content.add_widget(points_layout)
        
        scrollview = ScrollView(); scrollview.add_widget(scroll_content)
        self.layout.add_widget(scrollview)

        save_button = GradientButton(text="Speichern & Schließen", size_hint_y=None, height=dp(50)); save_button.bind(on_press=self.save_and_close); self.layout.add_widget(save_button)
    def save_and_close(self, instance):
        app = App.get_running_app()
        new_roster = [name.strip() for name in self.roster_input.text.split("\n") if name.strip()]; app.roster = list(dict.fromkeys(new_roster))
        for key, widget in self.point_inputs.items():
            try: app.point_system[key] = int(widget.text)
            except ValueError: pass
        save_settings(app.roster, app.point_system); app.screen_manager.current = 'step1'

class CWLRechnerApp(App):
    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.12, 1) # Anthracite
        self.roster, self.point_system = load_settings()
        self.data_df = pd.DataFrame()
        self.results_df = pd.DataFrame()
        self.last_save_time = datetime.now()

        self.screen_manager = ScreenManager(transition=FadeTransition())
        self.screen_manager.add_widget(Step1Screen(name='step1'))
        self.screen_manager.add_widget(Step2Screen(name='step2'))
        self.screen_manager.add_widget(Step3Screen(name='step3'))
        self.screen_manager.add_widget(SettingsScreen(name='settings'))
        
        Clock.schedule_interval(self.autosave_check, 60)
        return self.screen_manager

    def on_start(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])

    def create_new_dataframe(self):
        df = pd.DataFrame(self.roster, columns=["Name"])
        df["Eigenes_Rathaus"] = None
        for i in range(1, 8):
            df[f"Tag{i}_Rathaus_Gegner"] = None; df[f"Tag{i}_Sterne"] = None; df[f"Tag{i}_Prozent"] = None
        return df

    def reset_data(self):
        self.data_df = self.create_new_dataframe(); self.results_df = pd.DataFrame()
        self.screen_manager.get_screen('step1').rebuild_layout()
        self.screen_manager.current = 'step1'

    def save_from_inputs(self, inputs_dict, message=None):
        if self.data_df.empty: self.data_df = self.create_new_dataframe()
        changes_data = [{'Name': name, **{key: w.text if w.text else None for key, w in data.items()}} for name, data in inputs_dict.items()]
        changes_df = pd.DataFrame(changes_data)
        main_df = self.data_df.set_index("Name"); changes_df = changes_df.set_index("Name")
        main_df.update(changes_df); self.data_df = main_df.reset_index()
        self.last_save_time = datetime.now()
        if message and PLYER_AVAILABLE: toast(message)

    def autosave_check(self, dt):
        time_since_save = datetime.now() - self.last_save_time
        if time_since_save > timedelta(minutes=6):
            current_screen = self.screen_manager.current_screen
            if hasattr(current_screen, 'inputs') and current_screen.inputs:
                self.save_from_inputs(current_screen.inputs, "Auto-Speichern...")

if __name__ == '__main__':
    CWLRechnerApp().run()