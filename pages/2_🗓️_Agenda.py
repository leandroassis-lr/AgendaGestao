import streamlit as st
import utils  # Mantemos para o CSS
import utils_chamados # <--- IMPORTANTE: O arquivo da Pag 7
import html
import pandas as pd
from datetime import date

# Dependência opcional
try:
    from streamlit_calendar import calendar
except Exception:
    calendar = None

st.set_page_config(page_title="Agenda - GESTÃO", page_icon="🗓️", layout="wide")
utils.load_css()

def tela_calendario():
    st.markdown("<div class='section-title-center'>AGENDA DE PROJETOS</div>", unsafe_allow_html=True)
    
    # 1. CARREGA DA MESMA FONTE DA PAG 7
    df = utils_chamados.carregar_chamados_db()
    
    # Garante que o DataFrame não está vazio
    if df.empty:
        st.info("Nenhum projeto encontrado para exibir na agenda.")
        return

    # Filtro de Analista
    lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    analista_selecionado = st.selectbox("Filtrar por Analista:", lista_analistas)

    if analista_selecionado != "Todos":
        df_filtrado = df[df['Analista'] == analista_selecionado]
    else:
        df_filtrado = df
    
    st.divider()
    
    # 2. TRATAMENTO DE DATAS
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')

    # Remove agendamentos vazios
    df_calendario = df_filtrado.dropna(subset=['Agendamento']).copy()

    if df_calendario.empty:
        st.info("Nenhum projeto com data de agendamento para exibir (com o filtro atual).")
        return
        
    if calendar is None:
        st.error("ERRO: O componente de calendário não está instalado.")
        return

    # --- 3. AGRUPAMENTO ---
    # Convertemos colunas para string
    cols_to_str = ['Nº Chamado', 'Descrição', 'Status', 'Sub-Status', 'Analista', 'Técnico', 'Cód. Agência'] # Adicionei Cód. Agência aqui por segurança
    for c in cols_to_str:
        if c in df_calendario.columns:
            df_calendario[c] = df_calendario[c].astype(str)

    # Agrupa incluindo 'Cód. Agência' na chave para não perder essa informação
    # Se uma agência tiver códigos diferentes para o mesmo nome (raro, mas possível), vai separar.
    # Se preferir agrupar apenas por nome e pegar o primeiro código, mova 'Cód. Agência' para o dicionário agg com 'first'
    
    # Opção A: Agrupar por Código também (Mais seguro se tiver nomes iguais)
    # df_agrupado = df_calendario.groupby(['Agendamento', 'Cód. Agência', 'Nome Agência', 'Projeto']).agg({ ...
    
    # Opção B: Manter agrupamento atual e pegar o código via 'first' (Mais simples para o código existente)
    df_agrupado = df_calendario.groupby(['Agendamento', 'Nome Agência', 'Projeto']).agg({
        'Nº Chamado': lambda x: ', '.join(sorted(set(x))), 
        'Descrição': lambda x: ' | '.join(x),              
        'Status': 'first',      
        'Sub-Status': 'first',
        'Analista': 'first',
        'Técnico': 'first',
        'ID': 'first',
        'Cód. Agência': 'first' # <--- ADICIONADO: Pega o código da agência
    }).reset_index()

    # 4. MONTAGEM DOS EVENTOS
    eventos = []
    for _, row in df_agrupado.iterrows():
        # Definição de cores
        cor_evento = utils_chamados.get_status_color(row.get('Status'))
        
        # --- MUDANÇA AQUI: Combina Código e Nome ---
        cod = str(row.get('Cód. Agência', '')).replace('.0', '').strip() # Remove decimal se houver
        nome = str(row.get('Nome Agência', 'N/A')).strip()
        
        # Se o código já estiver no nome, não repete
        if cod and cod not in nome:
            nome_agencia_display = f"{cod} - {nome}"
        else:
            nome_agencia_display = nome
            
        nome_projeto = row.get('Projeto', 'N/A')
        
        eventos.append({
            "title": f"{nome_agencia_display} - {nome_projeto}", # Usa o nome combinado
            "color": cor_evento,
            "start": row['Agendamento'].strftime('%Y-%m-%d'),
            "end": row['Agendamento'].strftime('%Y-%m-%d'),
            "allDay": True,
            "extendedProps": {
                "ID": str(row.get('ID', '')),
                "Chamado": str(row.get('Nº Chamado', '')),
                "Projeto": nome_projeto,
                "Agência": nome_agencia_display, # Passa o nome combinado para o detalhe também
                "Analista": str(row.get('Analista', '')),
                "Técnico": str(row.get('Técnico', '')),
                "Status": str(row.get('Status', '')),
                "Sub-Status": str(row.get('Sub-Status', '')),
                "Descrição": str(row.get('Descrição', ''))
            }
        })
    
    opcoes_calendario = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listWeek"},
        "initialView": "dayGridMonth", 
        "locale": "pt-br",
        "buttonText": {"today": "hoje", "month": "mês", "week": "semana", "list": "lista"},
        "navLinks": True,
        "selectable": True
    }
    
    state = calendar(events=eventos, options=opcoes_calendario, key="calendario_geral")
    
    # 5. EXIBIÇÃO DOS DETALHES
    if state and state.get("eventClick"):
        st.session_state.evento_clicado = state["eventClick"]["event"]

    if "evento_clicado" in st.session_state and st.session_state.evento_clicado:
        evento = st.session_state.evento_clicado
        props = evento.get('extendedProps', {})
        
        st.divider()
        st.markdown(f"### 🎫 Chamados: {props.get('Chamado', 'Detalhes')}")
        
        c1, c2, c3 = st.columns(3)
        c1.info(f"**Projeto:**\n{props.get('Projeto')}")
        c2.info(f"**Agência:**\n{props.get('Agência')}")
        c3.warning(f"**Status:**\n{props.get('Status')} ({props.get('Sub-Status')})")
        
        c4, c5 = st.columns(2)
        c4.markdown(f"**👤 Analista:** {props.get('Analista')}")
        c5.markdown(f"**🔧 Técnico:** {props.get('Técnico')}")
        
        if props.get('Descrição') and props.get('Descrição') != 'nan':
            st.markdown("**📝 Itens/Descrição Agrupada:**")
            desc_formatada = props.get('Descrição').replace(' | ', '\n- ')
            st.info(f"- {desc_formatada}")

# --- Controle Principal ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}")
st.sidebar.divider()
if st.sidebar.button("Logout", key="logout_agenda_geral"):
    st.session_state.clear(); st.rerun()

tela_calendario()
