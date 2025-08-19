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
    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background-color: #111111;
        color: #e0e0e0;
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
    .stButton>button[kind="primary"] {
        background: linear-gradient(90deg, #8A2387, #E94057, #F27121);
        color: white;
        border: none;
    }
    .stButton>button[kind="primary"]:hover {
        opacity: 0.9;
    }
    /* Sekundärer Button */
    .stButton>button[kind="secondary"] {
        background-color: #333333;
        color: #e0e0e0;
    }
    .stButton>button[kind="secondary"]:hover {
        background-color: #444444;
        border-color: #666;
    }
    hr {
        border-top: 1px solid #333;
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .credit-text {
        text-align: center;
        font-size: 1.2rem;
        margin-bottom: 1rem;
    }
    /* Award Card Styling */
    .award-card {
        background-color: #2a2a2a;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #444;
        height: 100%;
    }
    .award-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #a0a0a0;
    }
    .award-name {
        font-size: 1.5rem;
        font-weight: 700;
        color: #e94057; /* Highlight color */
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .award-score {
        font-size: 1rem;
        color: #e0e0e0;
    }
    /* BUG FIX: Hide the annoying text overlay on the sidebar arrow */
    [data-testid="stSidebarNav"] > ul > li > div[role="button"] {
        display: none;
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

def calculate_awards(df, summary_df, point_system):
    if summary_df.empty:
        return {"mvp": {"name": "N/A", "score": ""}, "goliath": {"name": "N/A", "score": ""}}
    mvp = {"name": summary_df.iloc[0]["Name"], "score": f'{summary_df.iloc[0]["Punkte"]} Punkte'}
    df_calc = df.copy()
    goliath_points = pd.Series(0, index=df_calc.index, dtype=float)
    df_calc['Eigenes_Rathaus'] = pd.to_numeric(df_calc['Eigenes_Rathaus'], errors='coerce').fillna(0)
    for i in range(1, 8):
        stars, pct, opp_rh = (pd.to_numeric(df_calc.get(c), errors='coerce') for c in [f"Tag{i}_Sterne", f"Tag{i}_Prozent", f"Tag{i}_Rathaus_Gegner"])
        attack_made = (stars.notna() | pct.notna()) & opp_rh.notna()
        is_goliath_attack = (opp_rh - df_calc['Eigenes_Rathaus']) >= 2
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
        goliath_points += np.where(attack_made & is_goliath_attack, daily_total, 0)
    if goliath_points.sum() > 0:
        winner_idx = goliath_points.idxmax()
        goliath = {"name": df_calc.loc[winner_idx, "Name"], "score": f'{int(goliath_points.max())} Punkte gegen höhere RH'}
    else:
        goliath = {"name": "Niemand", "score": "Keine Angriffe auf viel höhere RH"}
    return {"mvp": mvp, "goliath": goliath}

# --- Session State Initialization ---
if 'step' not in st.session_state: st.session_state.step = "erl_input"
if 'data_df' not in st.session_state: st.session_state.data_df = pd.DataFrame()
load_settings()

# --- Sidebar Navigation & App Header ---
page = st.sidebar.radio("Navigation", ["CWL Rechner", "⚙️ Einstellungen", "Credits"])
st.markdown('<div style="text-align: center; margin-top: 2rem; margin-bottom: 2rem;"><div class="title-box">CWL Bonus Rechner</div></div>', unsafe_allow_html=True)

# --- SETTINGS PAGE ---
if page == "⚙️ Einstellungen":
    st.markdown("<div class='content-card'>", unsafe_allow_html=True)
    st.header("⚙️ Einstellungen")
    st.subheader("👥 Clan-Mitglieder verwalten")
    roster_text = st.text_area("Füge hier die Namen aller Clan-Mitglieder ein (ein Name pro Zeile).", value="\n".join(st.session_state.clan_roster), height=250, label_visibility="collapsed")
    if st.button("Mitgliederliste speichern", type="primary"):
        new_roster = [name.strip() for name in roster_text.split("\n") if name.strip()]
        unique_roster = list(dict.fromkeys(new_roster))
        st.session_state.clan_roster = unique_roster
        save_settings(st.session_state.clan_roster, st.session_state.point_system)
        st.toast("Mitgliederliste aktualisiert und gespeichert!", icon="👥"); st.rerun()
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("🔢 Punktesystem anpassen")
    points = st.session_state.point_system.copy()
    st.markdown("<h5>Punkte für Rathaus-Level Differenz (ELL)</h5>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    points["ell_gt_2"]=c1.number_input("RH+2",value=points["ell_gt_2"]);points["ell_eq_1"]=c2.number_input("RH+1",value=points["ell_eq_1"]);points["ell_eq_0"]=c3.number_input("RH=0",value=points["ell_eq_0"]);points["ell_eq_-1"]=c4.number_input("RH-1",value=points["ell_eq_-1"]);points["ell_lt_-2"]=c5.number_input("RH-2",value=points["ell_lt_-2"])
    st.markdown("<h5>Punkte für Angriffe</h5>", unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1:st.markdown("<h6>3 Sterne</h6>",unsafe_allow_html=True);points["atk_3s_gt_2"]=st.number_input("3⭐ vs RH+2",value=points["atk_3s_gt_2"]);points["atk_3s_eq"]=st.number_input("3⭐ vs RH=0",value=points["atk_3s_eq"]);points["atk_3s_lt_-2"]=st.number_input("3⭐ vs RH-2",value=points["atk_3s_lt_-2"])
    with c2:st.markdown("<h6>2 Sterne</h6>",unsafe_allow_html=True);points["atk_2s_ge_90"]=st.number_input("2⭐ (90%+)",value=points["atk_2s_ge_90"]);points["atk_2s_80_89"]=st.number_input("2⭐ (80-89%)",value=points["atk_2s_80_89"]);points["atk_2s_50_79"]=st.number_input("2⭐ (50-79%)",value=points["atk_2s_50_79"])
    with c3:st.markdown("<h6>1 Stern</h6>",unsafe_allow_html=True);points["atk_1s_90_99"]=st.number_input("1⭐ (90-99%)",value=points["atk_1s_90_99"]);points["atk_1s_50_89"]=st.number_input("1⭐ (50-89%)",value=points["atk_1s_50_89"])
    st.markdown("<h5>Bonuspunkte</h5>", unsafe_allow_html=True)
    c1,c2,c3,c4,c5=st.columns(5)
    points["aktiv"]=c1.number_input("Aktivität",value=points["aktiv"]);points["bonus_100"]=c2.number_input("100% Bonus",value=points["bonus_100"]);points["mut_base"]=c3.number_input("Mutbonus",value=points["mut_base"]);points["mut_extra"]=c4.number_input("Extra Mut",value=points["mut_extra"]);points["all_attacks"]=c5.number_input("Alle 7 Angriffe",value=points["all_attacks"])
    if st.button("Punktesystem speichern",type="primary",use_container_width=True):
        st.session_state.point_system=points
        save_settings(st.session_state.clan_roster,st.session_state.point_system)
        st.toast("Punktesystem aktualisiert!",icon="⚙️")
    st.markdown("</div>", unsafe_allow_html=True)

# --- MAIN APP ---
elif page == "CWL Rechner":
    if 'data_df' not in st.session_state or st.session_state.data_df.empty:
        df = pd.DataFrame(st.session_state.clan_roster, columns=["Name"])
        for i in range(1, 8):
            df[f"Tag{i}_Rathaus_Gegner"] = None; df[f"Tag{i}_Sterne"] = None; df[f"Tag{i}_Prozent"] = None
        df["Eigenes_Rathaus"] = None
        st.session_state.data_df = df

    if st.session_state.step == "erl_input":
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.subheader("Schritt 1: Gegner-Rathaus (ERL) eintragen")
        
        # FEATURE: Clean column names for display
        column_config = {"Name": st.column_config.TextColumn(disabled=True), "Eigenes_Rathaus": "Eigenes RH"}
        for i in range(1, 8):
            column_config[f"Tag{i}_Rathaus_Gegner"] = f"Tag {i} ERL"
        
        edited_df = st.data_editor(st.session_state.data_df, hide_index=True, key="df_editor_erl", use_container_width=True, column_config=column_config)
        
        if st.button("Weiter zu Sterne & Prozent", type="primary"):
            st.session_state.data_df = edited_df
            st.session_state.step = "pct_input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.step == "pct_input":
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.subheader("Schritt 2: Sterne und Zerstörung (%)")

        df = st.session_state.data_df
        star_cols = ["Name"] + [f"Tag{i}_Sterne" for i in range(1, 8)]
        pct_cols = ["Name"] + [f"Tag{i}_Prozent" for i in range(1, 8)]
        
        # FEATURE: Clean column names for display
        star_config = {"Name": st.column_config.TextColumn(disabled=True)}
        pct_config = {"Name": st.column_config.TextColumn(disabled=True)}
        for i in range(1, 8):
            star_config[f"Tag{i}_Sterne"] = f"Tag {i} ⭐"
            pct_config[f"Tag{i}_Prozent"] = f"Tag {i} %"

        st.markdown("<h5>Sterne</h5>", unsafe_allow_html=True)
        edited_stars = st.data_editor(df[star_cols], hide_index=True, key="df_editor_stars", use_container_width=True, column_config=star_config)
        st.markdown("<h5>Prozent</h5>", unsafe_allow_html=True)
        edited_pct = st.data_editor(df[pct_cols], hide_index=True, key="df_editor_pct", use_container_width=True, column_config=pct_config)

        synced_df = df.copy()
        for i in range(1, 8):
            star_col = f"Tag{i}_Sterne"; pct_col = f"Tag{i}_Prozent"
            synced_df[star_col] = pd.to_numeric(edited_stars[star_col], errors='coerce')
            synced_df[pct_col] = pd.to_numeric(edited_pct[pct_col], errors='coerce')
            
            three_star_mask = synced_df[star_col] == 3
            hundred_pct_mask = synced_df[pct_col] == 100
            synced_df.loc[three_star_mask, pct_col] = 100
            synced_df.loc[hundred_pct_mask, star_col] = 3
        
        if not df.equals(synced_df):
            st.session_state.data_df = synced_df
            st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Zurück"):
                st.session_state.data_df = synced_df
                st.session_state.step = "erl_input"
                st.rerun()
        with col2:
            if st.button("Berechnen & Auswerten", type="primary"):
                st.session_state.data_df = synced_df
                st.session_state.step = "summary"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.step == "summary":
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.subheader("Endwertung - Gesamtpunkte je Spieler")
        
        summary_df = calculate_all_points(st.session_state.data_df, st.session_state.point_system)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        st.markdown("<hr>", unsafe_allow_html=True)

        st.subheader("🏆 Clan Awards")
        awards = calculate_awards(st.session_state.data_df, summary_df, st.session_state.point_system)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""<div class="award-card"><div class="award-title">🏅 MVP</div><div class="award-name">{awards['mvp']['name']}</div><div class="award-score">{awards['mvp']['score']}</div></div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="award-card"><div class="award-title">⚔️ David gegen Goliath</div><div class="award-name">{awards['goliath']['name']}</div><div class="award-score">{awards['goliath']['score']}</div></div>""", unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("📊 Grafische Auswertung")
        if not summary_df.empty:
            chart_data = summary_df.rename(columns={'Punkte': 'Punkte'}).set_index('Name')
            st.bar_chart(chart_data)

        st.markdown("<hr>", unsafe_allow_html=True)
        
        @st.cache_data
        def convert_df_to_csv(df):
            return df.to_csv(index=False).encode('utf-8')
        csv = convert_df_to_csv(summary_df)

        st.download_button(label="📥 Excel-Datei herunterladen (.csv)", data=csv, file_name='cwl_bonus_wertung.csv', mime='text/csv')

        st.markdown("<hr>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Zurück zur Eingabe"):
                st.session_state.step = "pct_input"
                st.rerun()
        with col2:
            if st.button("Neuen Durchgang starten", type="primary"):
                st.session_state.data_df = pd.DataFrame()
                st.session_state.step = "erl_input"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# --- CREDITS PAGE ---
elif page == "Credits":
    st.markdown("<div class='content-card'>", unsafe_allow_html=True)
    st.header("Credits")
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<p class='credit-text'><strong>Idee:</strong> MagicDragon</p>", unsafe_allow_html=True)
    st.markdown("<p class='credit-text'><strong>Webseite & Code:</strong> AGDNoob ❤️</p>", unsafe_allow_html=True)
    st.markdown("<p class='credit-text'><strong>System:</strong> MagicDragon & AGDNoob</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
