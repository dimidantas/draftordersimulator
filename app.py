import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="NFL Draft Simulator", layout="wide", page_icon="🏈")

# --- CSS PARA MELHORAR O VISUAL ---
st.markdown("""
<style>
    .stDataFrame td { vertical-align: middle !important; }
    h1 { color: #013369; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🏈 NFL Draft Order Simulator")

# --- 0. DICIONÁRIO DE LOGOS (Mapeamento Abr -> URL ESPN) ---
# Adicionei os principais. Se algum ficar sem logo, ele usa um genérico.
def get_logo_url(team_abbr):
    base_url = "https://a.espncdn.com/i/teamlogos/nfl/500/"
    # Mapeamento de abreviações antigas/diferentes para o padrão ESPN
    mapping = {
        "WSH": "wsh", "WAS": "wsh", "LAR": "lar", "LA": "lar", 
        "HST": "hou", "HOU": "hou", "BLT": "bal", "BAL": "bal",
        "CLV": "cle", "CLE": "cle", "ARZ": "ari", "ARI": "ari",
        "JAX": "jax", "JAC": "jax", "TEN": "ten", "IND": "ind"
    }
    # Pega do mapa ou usa a própria abreviação em minúsculo
    abbr = mapping.get(team_abbr.upper(), team_abbr.lower())
    return f"{base_url}{abbr}.png"

# --- 1. CARREGAMENTO DE DADOS ---
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

    condition = df['home_score'].isna() | df['away_score'].isna()
    df['status'] = np.where(condition, 'Scheduled', 'Final')

    cols_to_keep = ['week', 'home_team', 'away_team', 'home_score', 'away_score', 'status']
    if 'game_id' in df.columns: cols_to_keep.append('game_id')
    df = df[cols_to_keep]
    
    # Adicionar URLs dos logos
    df['home_logo'] = df['home_team'].apply(get_logo_url)
    df['away_logo'] = df['away_team'].apply(get_logo_url)

    return df

original_df = load_data()

# --- LÓGICA PRINCIPAL ---
if not original_df.empty:
    
    # Abas para separar a Simulação dos Resultados
    tab_simulacao, tab_draft, tab_sos_detalhes = st.tabs(["🔮 Simular Jogos", "📋 Ordem do Draft", "🔍 Raio-X do SOS"])

    # === ABA 1: SIMULAÇÃO ===
    with tab_simulacao:
        st.write("### Jogos Restantes")
        st.caption("Escolha os vencedores abaixo. A tabela atualiza automaticamente.")
        
        final_games = original_df[original_df['status'] == 'Final'].copy()
        scheduled_games = original_df[original_df['status'] == 'Scheduled'].copy()
        
        full_season_df = final_games.copy()

        if not scheduled_games.empty:
            scheduled_games['User_Pick'] = None # Começa vazio
            
            # Editor Visual com Logos
            edited_games = st.data_editor(
                scheduled_games[['week', 'away_logo', 'away_team', 'home_logo', 'home_team', 'User_Pick']],
                column_config={
                    "week": st.column_config.NumberColumn("Wk", width="small"),
                    "away_logo": st.column_config.ImageColumn(" ", width="small"),
                    "away_team": st.column_config.TextColumn("Away", width="small"),
                    "home_logo": st.column_config.ImageColumn(" ", width="small"),
                    "home_team": st.column_config.TextColumn("Home", width="small"),
                    "User_Pick": st.column_config.SelectboxColumn(
                        "Quem Vence?",
                        help="Selecione o vencedor",
                        width="medium",
                        options=["Away Win", "Home Win", "Tie"],
                        required=False
                    )
                },
                hide_index=True,
                use_container_width=True,
                height=500
            )

            # Processar Inputs
            simulated_results = []
            for index, row in edited_games.iterrows():
                pick = row['User_Pick']
                h_team = row['home_team']
                a_team = row['away_team']
                
                if pick == "Home Win":
                    h_score, a_score = 21, 10
                elif pick == "Away Win":
                    h_score, a_score = 10, 21
                elif pick == "Tie":
                    h_score, a_score = 20, 20
                else:
                    h_score, a_score = np.nan, np.nan # Não escolheu ainda
                
                if pick:
                    simulated_results.append({
                        'week': row['week'],
                        'home_team': h_team, 'away_team': a_team,
                        'home_score': h_score, 'away_score': a_score,
                        'status': 'Simulated'
                    })
            
            if simulated_results:
                sim_df = pd.DataFrame(simulated_results)
                full_season_df = pd.concat([final_games, sim_df], ignore_index=True)
        else:
            st.success("Temporada Regular Finalizada!")

    # === CÁLCULOS ===
    # Função unificada de cálculo
    def calculate_stats(games_df):
        all_teams = pd.unique(games_df[['home_team', 'away_team']].values.ravel('K'))
        stats = {team: {'wins': 0, 'losses': 0, 'ties': 0, 'games': 0, 'opponents': []} for team in all_teams}
        
        for _, row in games_df.iterrows():
            if pd.isna(row['home_score']) or pd.isna(row['away_score']): continue
            
            h, a = row['home_team'], row['away_team']
            h_s, a_s = row['home_score'], row['away_score']
            
            # Adiciona à lista de oponentes (SOS)
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

    # DataFrame de Standings
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

    # Cálculo do SOS Detalhado
    sos_details = []
    sos_values = []

    for _, row in standings_df.iterrows():
        opps = row['Opponents']
        opp_w, opp_l, opp_t = 0, 0, 0
        
        # Detalhes textuais
        opp_records_str = []
        
        for opp in opps:
            if opp in stats:
                ow = stats[opp]['wins']
                ol = stats[opp]['losses']
                ot = stats[opp]['ties']
                opp_w += ow; opp_l += ol; opp_t += ot
                opp_records_str.append(f"{opp}({ow}-{ol})")
        
        total_opp_games = opp_w + opp_l + opp_t
        sos = (opp_w + 0.5 * opp_t) / total_opp_games if total_opp_games > 0 else 0.0
        sos_values.append(sos)
        
        sos_details.append({
            'Team': row['Team'],
            'Logo': row['Logo'],
            'SOS': sos,
            'Opponents Record': f"{opp_w}-{opp_l}-{opp_t}",
            'Opponents List': ", ".join(opp_records_str)
        })

    standings_df['SOS'] = sos_values

    # === ABA 2: DRAFT ORDER ===
    with tab_draft:
        st.header("Ordem Projetada (Top 18)")
        
        # Ordenação: 1. Win % Asc, 2. SOS Asc
        draft_order = standings_df.sort_values(by=['Win %', 'SOS'], ascending=[True, True]).reset_index(drop=True)
        draft_order.index += 1
        
        # Display
        display_cols = ['Logo', 'Team', 'W', 'L', 'T', 'Win %', 'SOS']
        st.data_editor(
            draft_order[display_cols],
            column_config={
                "Logo": st.column_config.ImageColumn("Logo", width="small"),
                "Win %": st.column_config.NumberColumn(format="%.3f"),
                "SOS": st.column_config.NumberColumn(format="%.3f"),
            },
            use_container_width=True,
            disabled=True, # Tabela apenas leitura
            height=800
        )

    # === ABA 3: DETALHES SOS ===
    with tab_sos_detalhes:
        st.header("Detalhamento do Strength of Schedule")
        st.markdown("O SOS é calculado somando as vitórias de **todos** os oponentes enfrentados e dividindo pelo total de jogos desses oponentes. Times enfrentados duas vezes contam duas vezes.")
        
        sos_df = pd.DataFrame(sos_details).sort_values(by='SOS')
        
        st.dataframe(
            sos_df,
            column_config={
                "Logo": st.column_config.ImageColumn(" ", width="small"),
                "SOS": st.column_config.NumberColumn(format="%.4f"),
                "Opponents Record": st.column_config.TextColumn("Recorde Combinado dos Rivais"),
                "Opponents List": st.column_config.TextColumn("Oponentes Enfrentados (Recorde)", width="large"),
            },
            use_container_width=True,
            hide_index=True,
            height=800
        )

else:
    st.warning("Faça o upload do arquivo 'nfl_schedule_2025.csv'.")
