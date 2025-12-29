import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="NFL Draft Simulator", layout="wide")

st.title("🏈 NFL Draft Order Simulator")
st.markdown("""
Este dashboard carrega os dados da NFL, permite simular os jogos restantes 
e calcula a ordem do Draft (Picks 1-18) baseada no **Win %** e **Strength of Schedule (SOS)**.
""")

# --- 1. CARREGAMENTO E TRATAMENTO DE DADOS ---
@st.cache_data
def load_data():
    # Tenta carregar o arquivo
    try:
        df = pd.read_csv("nfl_schedule_2025.csv")
    except FileNotFoundError:
        return pd.DataFrame()

    # 1. Filtrar apenas Temporada Regular
    if 'game_type' in df.columns:
        df = df[df['game_type'] == 'REG']

    # 2. Converter scores para numérico (força erros/strings vazias a virarem NaN)
    # Isso é crucial para a verificação do status funcionar corretamente
    df['home_score'] = pd.to_numeric(df['home_score'], errors='coerce')
    df['away_score'] = pd.to_numeric(df['away_score'], errors='coerce')

    # 3. Criar a coluna 'status' com verificação robusta
    # Se home_score OU away_score forem NaN, o jogo é 'Scheduled'. 
    # Só é 'Final' se ambos tiverem números.
    condition = df['home_score'].isna() | df['away_score'].isna()
    df['status'] = np.where(condition, 'Scheduled', 'Final')

    # Selecionar apenas colunas essenciais
    cols_to_keep = ['week', 'home_team', 'away_team', 'home_score', 'away_score', 'status']
    
    # Verifica se game_id existe antes de tentar manter (segurança extra)
    if 'game_id' in df.columns:
        cols_to_keep.append('game_id')
        
    df = df[cols_to_keep]

    return df

original_df = load_data()

if not original_df.empty:
    # --- 2. INTERFACE DE PREVISÃO ---
    st.subheader("🔮 Previsão dos Jogos Restantes")
    
    # Separa jogos
    final_games = original_df[original_df['status'] == 'Final'].copy()
    scheduled_games = original_df[original_df['status'] == 'Scheduled'].copy()
    
    if not scheduled_games.empty:
        st.info(f"Existem {len(scheduled_games)} jogos restantes para simular.")
        
        # Cria coluna para input do usuário
        scheduled_games['User_Pick'] = 'TBD'
        
        # Editor Interativo
        edited_games = st.data_editor(
            scheduled_games[['week', 'home_team', 'away_team', 'User_Pick']],
            column_config={
                "week": st.column_config.NumberColumn("Semana", width="small"),
                "home_team": "Home",
                "away_team": "Away",
                "User_Pick": st.column_config.SelectboxColumn(
                    "Sua Previsão",
                    help="Escolha o vencedor",
                    width="medium",
                    options=["Home Win", "Away Win", "Tie"],
                    required=True
                )
            },
            hide_index=True,
            num_rows="fixed",
            height=400
        )
    
        # Processamento das escolhas
        simulated_results = []
        for index, row in edited_games.iterrows():
            pick = row['User_Pick']
            
            # Scores fictícios para a lógica de W/L
            if pick == "Home Win":
                h_score, a_score = 21, 10
            elif pick == "Away Win":
                h_score, a_score = 10, 21
            elif pick == "Tie":
                h_score, a_score = 20, 20
            else:
                h_score, a_score = np.nan, np.nan
            
            # Só adiciona à simulação se o usuário tiver escolhido algo
            if pick != 'TBD':
                simulated_results.append({
                    'week': row['week'],
                    'home_team': row['home_team'],
                    'away_team': row['away_team'],
                    'home_score': h_score,
                    'away_score': a_score,
                    'status': 'Simulated'
                })
        
        simulated_df = pd.DataFrame(simulated_results)
        
        # Junta: Jogos Reais + Jogos Simulados
        if not simulated_df.empty:
            full_season_df = pd.concat([final_games, simulated_df], ignore_index=True)
        else:
            full_season_df = final_games
    else:
        st.success("Todos os jogos da temporada regular já foram finalizados.")
        full_season_df = final_games
    
    # --- 3. LÓGICA DE CÁLCULO (STANDINGS + SOS) ---
    
    def calculate_draft_order(games_df):
        all_teams = pd.unique(games_df[['home_team', 'away_team']].values.ravel('K'))
        stats = {team: {'wins': 0, 'losses': 0, 'ties': 0, 'games': 0, 'opponents': []} for team in all_teams}
        
        for _, row in games_df.iterrows():
            home = row['home_team']
            away = row['away_team']
            h_score = row['home_score']
            a_score = row['away_score']
            
            # Pula jogos sem score válido
            if pd.isna(h_score) or pd.isna(a_score):
                continue
                
            stats[home]['opponents'].append(away)
            stats[away]['opponents'].append(home)
            stats[home]['games'] += 1
            stats[away]['games'] += 1
            
            if h_score > a_score:
                stats[home]['wins'] += 1
                stats[away]['losses'] += 1
            elif a_score > h_score:
                stats[away]['wins'] += 1
                stats[home]['losses'] += 1
            else:
                stats[home]['ties'] += 1
                stats[away]['ties'] += 1
    
        # Monta DataFrame
        standings_data = []
        for team, data in stats.items():
            win_pct = 0.0
            if data['games'] > 0:
                win_pct = (data['wins'] + 0.5 * data['ties']) / data['games']
                
            standings_data.append({
                'Team': team,
                'W': data['wins'],
                'L': data['losses'],
                'T': data['ties'],
                'Win %': win_pct,
                'Opponents': data['opponents']
            })
            
        standings_df = pd.DataFrame(standings_data)
        
        # --- CÁLCULO DO SOS ---
        sos_values = []
        for _, row in standings_df.iterrows():
            opponents = row['Opponents']
            if not opponents:
                sos_values.append(0.0)
                continue
            
            opp_total_wins = 0
            opp_total_ties = 0
            opp_total_games = 0
            
            for opp in opponents:
                if opp in stats:
                    opp_total_wins += stats[opp]['wins']
                    opp_total_ties += stats[opp]['ties']
                    opp_total_games += stats[opp]['games']
            
            if opp_total_games > 0:
                sos = (opp_total_wins + 0.5 * opp_total_ties) / opp_total_games
            else:
                sos = 0.0
            
            sos_values.append(sos)
            
        standings_df['SOS'] = sos_values
        return standings_df
    
    # Executa cálculo
    final_standings = calculate_draft_order(full_season_df)
    
    # --- 4. EXIBIÇÃO ---
    st.divider()
    st.header("📋 Draft Order (Top 18 Projection)")
    st.markdown("""
    **Critérios:** 1. Menor Win % | 2. Menor SOS
    """)
    
    # Ordenação
    draft_order = final_standings.sort_values(by=['Win %', 'SOS'], ascending=[True, True]).reset_index(drop=True)
    draft_order.index += 1
    draft_order.index.name = 'Pick'
    
    display_df = draft_order[['Team', 'W', 'L', 'T', 'Win %', 'SOS']].copy()
    display_df['Win %'] = display_df['Win %'].map('{:.3f}'.format)
    display_df['SOS'] = display_df['SOS'].map('{:.3f}'.format)
    
    st.dataframe(display_df, use_container_width=True, height=800)

else:
    st.warning("Por favor, faça o upload do arquivo 'nfl_schedule_2025.csv' no seu repositório.")
