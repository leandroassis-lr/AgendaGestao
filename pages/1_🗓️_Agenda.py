import streamlit as st
import utils # Importa nosso arquivo de utilidades
import html
import pandas as pd

# Dependência opcional
try:
    from streamlit_calendar import calendar
except Exception:
    calendar = None

st.set_page_config(page_title="Agenda - GESTÃO", page_icon="🗓️", layout="wide")
utils.load_css()

def tela_calendario():
    st.markdown("<div class='section-title-center'>AGENDA</div>", unsafe_allow_html=True)
    df = utils.carregar_projetos_db()
    
    # Garante que o DataFrame não está vazio antes de prosseguir
    if df.empty or 'Analista' not in df.columns:
        st.info("Nenhum projeto encontrado para exibir na agenda.")
        return

    lista_analistas = ["Todos"] + df['Analista'].dropna().unique().tolist()
    analista_selecionado = st.selectbox("Filtrar por Analista:", lista_analistas)

    if analista_selecionado != "Todos":
        df_filtrado = df[df['Analista'] == analista_selecionado]
    else:
        df_filtrado = df
    
    st.divider()
    
    # --- CORREÇÃO APLICADA AQUI ---
    # 1. Converte a coluna 'Agendamento' para um formato de data seguro.
    #    Valores que não são datas (nulos, em branco) se tornarão 'NaT' (Not a Time).
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')

    # 2. Agora, removemos com segurança todas as linhas onde o agendamento é nulo (NaT).
    df_calendario = df_filtrado.dropna(subset=['Agendamento'])

    if df_calendario.empty:
        st.info("Nenhum projeto com data de agendamento para exibir (com o filtro atual).")
        return
        
    if calendar is None:
        st.error("ERRO: O componente de calendário não está instalado. Adicione 'streamlit-calendar' ao seu requirements.txt")
        st.code("pip install streamlit-calendar")
        return

    eventos = []
    for _, row in df_calendario.iterrows():
        # A verificação 'dropna' acima garante que 'Agendamento' é uma data válida aqui.
        eventos.append({
            "title": f"{row.get('Agência', 'N/A')} - {row.get('Projeto', 'N/A')}",
            "color": utils.get_status_color(row.get('Status')),
            "start": row['Agendamento'].strftime('%Y-%m-%d'),
            "end": row['Agendamento'].strftime('%Y-%m-%d'),
            "extendedProps": {
                "Projeto": row.get('Projeto', 'N/A'), "Agência": row.get('Agência', 'N/A'),
                "Analista": row.get('Analista', 'N/A'), "Status": row.get('Status', 'N/A'),
                "Descrição": row.get('Descrição', 'N/A')
            }
        })
    
    opcoes_calendario = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listWeek"},
        "initialView": "dayGridMonth", "locale": "pt-br",
        "buttonText": {"today": "hoje", "month": "mês", "week": "semana", "list": "lista"}
    }
    
    state = calendar(events=eventos, options=opcoes_calendario, key="calendario")
    
    # Lógica para exibir detalhes do evento clicado
    if state and state.get("eventClick"):
        st.session_state.evento_clicado = state["eventClick"]["event"]

    if "evento_clicado" in st.session_state and st.session_state.evento_clicado:
        evento = st.session_state.evento_clicado
        
        st.divider()
        st.subheader(f"Detalhes de: {html.escape(evento['title'])}")
        
        props = evento.get('extendedProps', {})
        
        col1, col2 = st.columns(2)
        col1.markdown(f"**Projeto:** {html.escape(props.get('Projeto', ''))}")
        col2.markdown(f"**Agência:** {html.escape(props.get('Agência', ''))}")
        col1.markdown(f"**Analista:** {html.escape(props.get('Analista', ''))}")
        col2.markdown(f"**Status:** {html.escape(props.get('Status', ''))}")
        
        st.markdown(f"**Descrição:**")
        st.info(f"{html.escape(props.get('Descrição', 'Nenhuma descrição.'))}")

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
st.sidebar.divider()
st.sidebar.divider()
st.sidebar.title("Sistema")
if st.sidebar.button("Logout", use_container_width=True, key="logout_agenda"):
    st.session_state.clear(); st.rerun()

tela_calendario()
