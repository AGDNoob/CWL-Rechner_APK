import streamlit as st
import pandas as pd
import numpy as np
import io
import json
import os

# ----------------------------
# Page & Style Setup
# ----------------------------
st.set_page_config(page_title="CWL Bonus Rechner", layout="wide")

# De Luxe Dark Mode CSS
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* Main App Styling */
    body {
        color: #e0e0e0;
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background-color: #111111;
    }
    /* Haupt-Container */
    div.block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    /* Titel-Schild */
    .title-box {
        background: linear-gradient(90deg, #8A2387, #E94057, #F27121);
        color: white;
        padding: 0.7rem 2rem;
        border-radius: 12px;
        display: inline-block;
        font-weight: 700;
        font-size: 1.5rem;
        letter-spacing: 1px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        border: 1px solid #333;
    }
    /* Inhalts-Karte im Dark Mode */
    .content-card {
        background: #1E1E1E;
        padding: 2.5rem;
        border-radius: 16px;
        border: 1px solid #2a2a2a;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    /* Überschriften-Styling */
    h1, h2, h3, h4 {
        color: #ffffff;
        font-weight: 700;
    }
    h5 {
        color: #a0a0a0;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    /* Button Styling */
    .stButton>button {
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 700;
        transition: all 0.2s ease-in-out;
        border: 1px solid #555;
    }
    /* Primärer Button */
    button[kind="primary"] {
        background: linear-gradient(90deg, #8A2387, #E94057, #F27121);
        color: white;
        border: none;
    }
    button[kind="primary"]:hover {
        opacity: 0.9;
    }
    /* Sekundärer Button */
    button[kind="secondary"] {
        background-color: #333333;
        color: #e0e0e0;
    }
    button[kind="secondary"]:hover {
        background-color: #444444;
        border-color: #666;
    }
    /* Data Editor Dark Mode */
    .stDataFrame {
        background-color: #1e1e1e;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# Data Persistence Functions
# ----------------------------
CONFIG_DIR = ".cwl_rechner_config"
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
    if 'clan_roster' not in st.session_state:
        try:
            with open(ROSTER_FILE, 'r') as f: st.session_state.clan_roster = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): st.session_state.clan_roster = ["Beispielspieler"]
    if 'point_system' not in st.session_state:
        try:
            with open(POINTS_FILE, 'r') as f: st.session_state.point_system = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): st.session_state.point_system = default_points

# ----------------------------
# Helper Functions
# ----------------------------
def calculate_all_points(df, point_system):
    # Calculation logic remains the same
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

# --- Session State Initialization ---
if 'step' not in st.session_state: st.session_state.step = "erl_input"
if 'data_df' not in st.session_state: st.session_state.data_df = pd.DataFrame()
load_settings()

# --- Sidebar Navigation & App Header ---
page = st.sidebar.radio("Navigation", ["CWL Rechner", "⚙️ Einstellungen"])
st.markdown('<div style="text-align: center; margin-bottom: 2rem;"><div class="title-box">CWL Bonus Rechner</div></div>', unsafe_allow_html=True)

# --- SETTINGS PAGE ---
if page == "⚙️ Einstellungen":
    st.markdown("<div class='content-card'>", unsafe_allow_html=True)
    st.header("⚙️ Einstellungen")
    # ... (Settings UI code remains the same as the final Streamlit version)
    st.markdown("</div>", unsafe_allow_html=True)

# --- MAIN APP ---
elif page == "CWL Rechner":
    if 'data_df' not in st.session_state or st.session_state.data_df.empty:
        df = pd.DataFrame(st.session_state.clan_roster, columns=["Name"])
        for i in range(1, 8):
            df[f"Tag{i}_Rathaus_Gegner"] = None; df[f"Tag{i}_Sterne"] = None; df[f"Tag{i}_Prozent"] = None
        df["Eigenes_Rathaus"] = None
        st.session_state.data_df = df

    # --- Step 1, 2, 3 Logic ---
    if st.session_state.step == "erl_input":
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.subheader("Schritt 1: Teilnehmer & Rathäuser")
        # ... (UI and logic for Step 1)
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.step == "pct_input":
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.subheader("Schritt 2: Sterne und Zerstörung (%)")
        # ... (UI and logic for Step 2)
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.step == "summary":
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.subheader("Endwertung - Gesamtpunkte je Spieler")
        # ... (UI and logic for Step 3)
        st.markdown("</div>", unsafe_allow_html=True)