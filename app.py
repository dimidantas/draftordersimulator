import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="NFL Draft Simulator", layout="wide", page_icon="🏈")

# --- CUSTOM CSS FOR "PRO" LOOK ---
st.markdown("""
<style>
    /* Clean up the top padding */
    .block-container { padding-top: 2rem; }
    
    /* Style for the Game Cards */
    .game-card {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #e0e0e0;
    }
    
    /* Center text in columns */
    div[data-testid="column"] {
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    /* Make metrics stand out */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #eee;
        padding: 10px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏈 NFL Draft Order Simulator")

# --- 0. UTILS & LOGOS ---
def get_logo_url(team_abbr):
    base_url = "https://a.espncdn.com/i/teamlogos/nfl/500/"
    mapping = {
        "WSH": "wsh", "WAS": "wsh", "LAR": "lar", "LA": "lar", 
        "HST": "hou", "HOU": "hou", "BLT": "bal", "BAL": "bal",
        "CLV": "cle", "CLE": "cle", "ARZ": "ari", "ARI": "ari",
        "JAX": "jax", "JAC": "jax", "TEN": "ten", "IND": "ind"
    }
    abbr = mapping.get(team_abbr.upper(), team_abbr.lower())
    return f"{base_url}{abbr}.png"

# --- 1. DATA LOADING ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("nfl_schedule_2025.csv")
    except FileNotFoundError:
        return pd.DataFrame()

    if 'game_type' in df.columns:
        df = df[df['game_type'] == 'REG']

    df['home_score'] = pd.to_numeric(df['home_score'], errors='coerce')
    df['away_score'] = pd.to_numeric(df['away_score'], errors='coerce')

    # Status Logic
    condition = df['home_score'].isna() | df['away_score'].isna()
    df['status'] = np.where(condition, 'Scheduled', 'Final')

    cols_to_keep = ['week', 'home_team', 'away_team', 'home_score', 'away_score', 'status']
    if 'game_id' in df.columns: 
        cols_to_keep.append('game_id')
    else:
        # Create a dummy ID if not exists to handle state
        df['game_id'] = df.index.astype(str)
        
    df = df[cols_to_keep]
    
    df['home_logo'] = df['home_team'].apply(get_logo_url)
    df['away_logo'] = df['away_team'].apply(get_logo_url)

    return df

original_df = load_data()

# --- STATE MANAGEMENT FOR PICKS ---
# We need to store user picks in session_state so they persist when changing tabs
if 'user_picks' not in st.session_state:
    st.session_state['user_picks'] = {}

# --- MAIN APP LOGIC ---
if not original_df.empty:
    
    # Tabs
    tab_sim, tab_draft, tab_sos = st.tabs(["🔮 Predict Games", "📋 Draft Order", "🔍 SOS Deep Dive"])

    # === TAB 1: SIMULATION (NEW UI) ===
    with tab_sim:
        st.write("### Remaining Games")
        st.caption("Select the winners below. The Draft Order updates in real-time.")
        
        # Split Data
        final_games = original_df[original_df['status'] == 'Final'].copy()
        scheduled_games = original_df[original_df['status'] == 'Scheduled'].copy()
        
        if scheduled_games.empty:
            st.success("Season finished! No games left to predict.")
            full_season_df = final_games
        else:
            # Group by Week to organize the UI
            weeks = sorted(scheduled_games['week'].unique())
            
            # --- THE NEW UI LOOP ---
            for week in weeks:
                with st.expander(f"Week {week}", expanded=True if week == weeks[0] else False):
                    week_games = scheduled_games[scheduled_games['week'] == week]
                    
                    for _, row in week_games.iterrows():
                        game_id = row['game_id']
                        
                        # Layout: Logo Away | Name | BUTTONS | Name | Logo Home
                        c1, c2, c3, c4, c5 = st.columns([1, 2, 4, 2, 1])
                        
                        with c1: st.image(row['away_logo'], width=50)
                        with c2: st.write(f"**{row['away_team']}**")
                        
                        with c3:
                            # Unique key for each radio is crucial
                            current_pick = st.session_state['user_picks'].get(game_id, "TBD")
                            
                            selection = st.radio(
                                "Choose Winner",
                                options=["Away", "Tie", "Home"],
                                index=0 if current_pick == "Away" else 2 if current_pick == "Home" else 1 if current_pick == "Tie" else 1,
                                horizontal=True,
                                key=f"radio_{game_id}",
                                label_visibility="collapsed"
                            )
                            
                            # Update State
                            st.session_state['user_picks'][game_id] = selection

                        with c4: st.write(f"**{row['home_team']}**")
                        with c5: st.image(row['home_logo'], width=50)
                        
                        st.divider()

            # --- PROCESS PREDICTIONS ---
            simulated_results = []
            for _, row in scheduled_games.iterrows():
                gid = row['game_id']
                pick = st.session_state['user_picks'].get(gid, "TBD") # Default to TBD/Tie logic if untouched? Let's assume Tie for untouched or just skip
                
                # Logic to assign scores based on pick
                if pick == "Home":
                    h_score, a_score = 21, 10
                elif pick == "Away":
                    h_score, a_score = 10, 21
                else: # Tie or TBD (Treat TBD as Tie for calculation safety or 0-0)
                    h_score, a_score = 20, 20
                
                simulated_results.append({
                    'week': row['week'],
                    'home_team': row['home_team'], 'away_team': row['away_team'],
                    'home_score': h_score, 'away_score': a_score,
                    'status': 'Simulated'
                })
            
            sim_df = pd.DataFrame(simulated_results)
            full_season_df = pd.concat([final_games, sim_df], ignore_index=True)

    # === CALCULATIONS ENGINE ===
    def calculate_stats(games_df):
        all_teams = pd.unique(games_df[['home_team', 'away_team']].values.ravel('K'))
        stats = {team: {'wins': 0, 'losses': 0, 'ties': 0, 'games': 0, 'opponents': []} for team in all_teams}
        
        for _, row in games_df.iterrows():
            if pd.isna(row['home_score']) or pd.isna(row['away_score']): continue
            
            h, a = row['home_team'], row['away_team']
            h_s, a_s = row['home_score'], row['away_score']
            
            stats[h]['opponents'].append(a)
            stats[a]['opponents'].append(h)
            stats[h]['games'] += 1; stats[a]['games'] += 1
            
            if h_s > a_s:
                stats[h]['wins'] += 1; stats[a]['losses'] += 1
            elif a_s > h_s:
                stats[a]['wins'] += 1; stats[h]['losses'] += 1
            else:
                stats[h]['ties'] += 1; stats[a]['ties'] += 1
        return stats

    stats = calculate_stats(full_season_df)

    standings_rows = []
    for team, data in stats.items():
        win_pct = (data['wins'] + 0.5 * data['ties']) / data['games'] if data['games'] > 0 else 0
        standings_rows.append({
            'Team': team,
            'Logo': get_logo_url(team),
            'W': data['wins'], 'L': data['losses'], 'T': data['ties'],
            'Win %': win_pct,
            'Opponents': data['opponents']
        })
    
    standings_df = pd.DataFrame(standings_rows)

    # SOS Calculation
    sos_details = []
    sos_values = []

    for _, row in standings_df.iterrows():
        opps = row['Opponents']
        opp_w, opp_l, opp_t = 0, 0, 0
        opp_records_str = []
        
        for opp in opps:
            if opp in stats:
                ow = stats[opp]['wins']
                ol = stats[opp]['losses']
                ot = stats[opp]['ties']
                opp_w += ow; opp_l += ol; opp_t += ot
                opp_records_str.append(f"{opp} ({ow}-{ol}-{ot})")
        
        total_opp_games = opp_w + opp_l + opp_t
        sos = (opp_w + 0.5 * opp_t) / total_opp_games if total_opp_games > 0 else 0.0
        sos_values.append(sos)
        
        sos_details.append({
            'Team': row['Team'],
            'Logo': row['Logo'],
            'SOS': sos,
            'Opponents Record': f"{opp_w}-{opp_l}-{opp_t}",
            'Opponents Detail': ", ".join(opp_records_str)
        })

    standings_df['SOS'] = sos_values

    # === TAB 2: DRAFT ORDER ===
    with tab_draft:
        st.header("Projected Draft Order (Top 18)")
        st.markdown("**Sorting Rules:** 1. Lowest Win %, 2. Lowest SOS")
        
        draft_order = standings_df.sort_values(by=['Win %', 'SOS'], ascending=[True, True]).reset_index(drop=True)
        draft_order.index += 1
        
        display_cols = ['Logo', 'Team', 'W', 'L', 'T', 'Win %', 'SOS']
        
        st.data_editor(
            draft_order[display_cols],
            column_config={
                "Logo": st.column_config.ImageColumn(" ", width="small"),
                "Team": st.column_config.TextColumn("Team", width="medium"),
                "Win %": st.column_config.NumberColumn(format="%.3f"),
                "SOS": st.column_config.NumberColumn(format="%.4f"),
            },
            use_container_width=True,
            disabled=True,
            height=900
        )

    # === TAB 3: SOS DETAILS ===
    with tab_sos:
        st.header("Strength of Schedule (SOS) X-Ray")
        st.markdown("SOS = Average win percentage of all opponents faced.")
        
        sos_df = pd.DataFrame(sos_details).sort_values(by='SOS')
        
        st.dataframe(
            sos_df,
            column_config={
                "Logo": st.column_config.ImageColumn(" ", width="small"),
                "SOS": st.column_config.NumberColumn(format="%.4f"),
                "Opponents Record": st.column_config.TextColumn("Combined Opp. Record"),
                "Opponents Detail": st.column_config.TextColumn("Opponents List", width="large"),
            },
            use_container_width=True,
            hide_index=True,
            height=800
        )

else:
    st.error("Data not found. Please upload 'nfl_schedule_2025.csv'.")
