import streamlit as st
import pandas as pd
import utils_chamados
from datetime import date, timedelta
import plotly.express as px # Se não tiver, usamos st.bar_chart

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS PARA OS ALERTAS E CARDS ---
st.markdown("""
    <style>
        .metric-card {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #ddd;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 10px;
        }
        .alert-box {
            background-color: #ffebee;
            color: #c62828;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .success-box {
            background-color: #e8f5e9;
            color: #2e7d32;
            padding: 10px;
            border-radius: 5px;
        }
    </style>
""", unsafe_allow_html=True)

# 1. Carregar Dados
df = utils_chamados.carregar_chamados_db()

if df.empty:
    st.warning("Sem dados.")
    st.stop()

# 2. Filtros Laterais (Analista/Gestor)
st.sidebar.header("🎯 Filtros de Gestão")
lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
filtro_analista = st.sidebar.selectbox("Analista Responsável", lista_analistas)

lista_gestores = ["Todos"] + sorted(df['Gestor'].dropna().unique().tolist())
filtro_gestor = st.sidebar.selectbox("Gestor (Banco)", lista_gestores)

# Aplica Filtros
df_filtrado = df.copy()
if filtro_analista != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
if filtro_gestor != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]

# 3. Identificar Projetos Ativos
lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())

# --- NAVEGAÇÃO ENTRE PROJETOS ---
# O usuário escolhe: Ver Resumo Geral ou Entrar num Projeto
escolha_visao = st.radio("Modo de Visualização:", ["Visão Geral (Todos)", "Detalhar um Projeto"], horizontal=True)

# --- FUNÇÃO DO POP-UP (Coloque isso antes do if escolha_visao...) ---
@st.dialog("Detalhes Rápidos do Projeto", width="large")
def mostrar_detalhes_projeto(nome_projeto, df_origem):
    st.caption(f"Visualizando status das agências para: **{nome_projeto}**")
    
    # Filtra apenas este projeto
    df_p = df_origem[df_origem['Projeto'] == nome_projeto].copy()
    
    # Seleciona colunas úteis
    df_view = df_p[['Nº Chamado', 'Nome Agência', 'UF', 'Status', 'Agendamento', 'Técnico']]
    
    # Formata a data para ficar bonita
    df_view['Agendamento'] = pd.to_datetime(df_view['Agendamento']).dt.strftime('%d/%m/%Y').fillna("-")
    
    # Mostra a tabela interativa
    st.dataframe(
        df_view, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Status Atual",
                validate="^[a-zA-Z0-9_]+$"
            ),
        }
    )

# --- BLOCO VISÃO GERAL ATUALIZADO ---
if escolha_visao == "Visão Geral (Todos)":
    st.title("📌 Visão Geral dos Projetos")
    
    # Métricas Globais
    total_geral = len(df_filtrado)
    hoje = pd.Timestamp.today().normalize()
    
    # Conversão segura de datas
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    
    # Lógica de Atraso
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    df_pendente = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim)]
    
    atrasados = df_pendente[df_pendente['Agendamento'] < hoje]
    proximos = df_pendente[(df_pendente['Agendamento'] >= hoje) & (df_pendente['Agendamento'] <= hoje + timedelta(days=5))]
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Total de Chamados", total_geral)
    k2.metric("🚨 Em Atraso", len(atrasados))
    k3.metric("📅 Vencendo (5 dias)", len(proximos))
    
    st.divider()
    
    # Cards por Projeto
    cols = st.columns(3)
    for i, proj in enumerate(lista_projetos):
        df_p = df_filtrado[df_filtrado['Projeto'] == proj]
        total_p = len(df_p)
        concluidos = len(df_p[df_p['Status'].str.lower().isin(status_fim)])
        atrasados_p = len(df_p[(~df_p['Status'].str.lower().isin(status_fim)) & (df_p['Agendamento'] < hoje)])
        
        perc = int((concluidos / total_p) * 100) if total_p > 0 else 0
        
        with cols[i % 3]:
            # HTML do Card (Visual)
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="margin-bottom:0px;">{proj}</h4>
                <p style="color:#666; font-size:0.9em;"><strong>{concluidos}/{total_p}</strong> concluídos ({perc}%)</p>
                <progress value="{perc}" max="100" style="width:100%; height: 10px;"></progress>
                <div style="margin-top: 10px;">
                    {'<div class="alert-box">⚠️ '+str(atrasados_p)+' Atrasados</div>' if atrasados_p > 0 else '<div class="success-box">✅ Em dia</div>'}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Botão para abrir o Pop-up (Key única usando o nome do projeto)
            if st.button(f"🔎 Ver Lista", key=f"btn_pop_{i}"):
                mostrar_detalhes_projeto(proj, df_filtrado)

else:
    # --- VISÃO DETALHADA DO PROJETO ---
    projeto_selecionado = st.selectbox("Selecione o Projeto:", lista_projetos)
    
    df_proj = df_filtrado[df_filtrado['Projeto'] == projeto_selecionado]
    
    st.markdown(f"## 🏗️ {projeto_selecionado}")
    
    tab1, tab2, tab3 = st.tabs(["📅 Cronograma (Agendamentos)", "🚨 Alertas e Atrasos", "📊 Status e Quantidades"])
    
    with tab1:
        st.markdown("### Planejamento por Data")
        # Agrupa por data de agendamento
        df_proj['Data_Str'] = df_proj['Agendamento'].dt.strftime('%d/%m/%Y').fillna("Sem Data")
        datas = sorted(df_proj['Agendamento'].dropna().unique())
        
        for data in datas:
            dt_str = data.strftime('%d/%m/%Y')
            df_dia = df_proj[df_proj['Agendamento'] == data]
            
            with st.expander(f"📆 {dt_str} - ({len(df_dia)} agências)"):
                st.dataframe(
                    df_dia[['Nº Chamado', 'Nome Agência', 'UF', 'Status', 'Técnico']], 
                    use_container_width=True,
                    hide_index=True
                )

    with tab2:
        st.markdown("### ⚠️ Atenção Imediata")
        hoje = pd.Timestamp.today().normalize()
        # Filtra atrasados deste projeto
        atrasados_proj = df_proj[
            (~df_proj['Status'].str.lower().isin(['finalizado', 'concluído', 'faturado', 'cancelado'])) & 
            (df_proj['Agendamento'] < hoje)
        ]
        
        if not atrasados_proj.empty:
            st.error(f"{len(atrasados_proj)} chamados deveriam ter sido feitos e não foram baixados!")
            st.dataframe(atrasados_proj[['Nº Chamado', 'Agendamento', 'Nome Agência', 'Analista', 'Status']], use_container_width=True)
        else:
            st.success("Nenhum atraso neste projeto! Parabéns.")

    with tab3:
        st.markdown("### Visão Quantitativa")
        c1, c2 = st.columns(2)
        
        status_counts = df_proj['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Quantidade']
        
        c1.dataframe(status_counts, use_container_width=True, hide_index=True)
        c2.bar_chart(status_counts.set_index('Status'))
