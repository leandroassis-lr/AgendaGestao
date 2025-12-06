import streamlit as st
import pandas as pd
import utils_chamados
import plotly.express as px
from datetime import date, timedelta, datetime
import time
import html
import math

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Projetos Pro", layout="wide")

# --- 2. CARREGAMENTO DE DADOS (COM PRAZOS) ---
@st.cache_data
def load_data():
    # Adicionei 'Data_Prazo' para podermos calcular atrasos
    data = {
        'ID': [101, 102, 103, 104, 105, 106, 107, 108, 109],
        'Projeto': ['Migração Cloud', 'App Mobile', 'Migração Cloud', 'Site Institucional', 'App Mobile', 'CRM Interno', 'Site Institucional', 'Migração Cloud', 'App Mobile'],
        'Tarefa': ['Configurar AWS', 'Design UI/UX', 'Banco de Dados', 'Levantamento Requisitos', 'API Backend', 'Protótipo', 'Deploy', 'Testes de Carga', 'Correção Bugs'],
        'Responsavel': ['Ana', 'Carlos', 'Ana', 'Beatriz', 'Carlos', 'João', 'Beatriz', 'Ana', 'Carlos'],
        'Status': ['Em Andamento', 'Concluído', 'Pendente', 'Concluído', 'Em Andamento', 'Novo', 'Concluído', 'Concluído', 'Pendente'],
        'Data_Inicio': [
            date(2025, 1, 10), date(2025, 1, 12), date(2025, 1, 15), 
            date(2025, 1, 5), date(2025, 2, 1), date(2025, 2, 10), 
            date(2025, 1, 20), date(2025, 2, 15), date(2024, 12, 20) # Data antiga para simular atraso
        ],
        'Data_Prazo': [
            date(2025, 2, 28), date(2025, 1, 30), date(2025, 3, 10), 
            date(2025, 1, 15), date(2025, 3, 0o1), date(2025, 3, 15), 
            date(2025, 2, 0o1), date(2025, 2, 28), date(2025, 1, 10) # Prazo estourado
        ]
    }
    return pd.DataFrame(data)

df_original = load_data()

# --- 3. BARRA LATERAL (FILTROS) ---
st.sidebar.header("🔍 Filtros Avançados")

# A. Buscador Geral
busca_geral = st.sidebar.text_input("Buscador Geral", placeholder="Ex: AWS, Ana, Mobile...")

# B. Filtros Específicos
projetos_unicos = df_original['Projeto'].unique()
filtro_projeto = st.sidebar.multiselect("Projeto", options=projetos_unicos, default=projetos_unicos)

status_unicos = df_original['Status'].unique()
filtro_status = st.sidebar.multiselect("Status", options=status_unicos, default=status_unicos)

# C. Filtro de Data (Baseado na Data de Início)
data_min = df_original['Data_Inicio'].min()
data_max = df_original['Data_Inicio'].max()
filtro_data = st.sidebar.date_input("Período de Início", value=(data_min, data_max))

# --- 4. APLICAÇÃO DOS FILTROS ---
df_filtrado = df_original.copy()

# Filtro de Data
if len(filtro_data) == 2:
    start_date, end_date = filtro_data
    df_filtrado = df_filtrado[(df_filtrado['Data_Inicio'] >= start_date) & (df_filtrado['Data_Inicio'] <= end_date)]

# Filtro de Projeto e Status
if filtro_projeto:
    df_filtrado = df_filtrado[df_filtrado['Projeto'].isin(filtro_projeto)]
if filtro_status:
    df_filtrado = df_filtrado[df_filtrado['Status'].isin(filtro_status)]

# Filtro de Texto Geral
if busca_geral:
    termo = busca_geral.lower()
    df_filtrado = df_filtrado[
        df_filtrado['Projeto'].str.lower().str.contains(termo) |
        df_filtrado['Tarefa'].str.lower().str.contains(termo) |
        df_filtrado['Responsavel'].str.lower().str.contains(termo)
    ]

# --- 5. LÓGICA DE NEGÓCIO (KPIS E ATRASOS) ---

# A. Verificar Atrasos (Hoje vs Prazo)
hoje = date.today()

def verificar_situacao(row):
    if row['Status'] == 'Concluído':
        return "✅ Finalizado"
    elif row['Data_Prazo'] < hoje:
        return "🔴 Atrasado"
    else:
        return "🟢 No Prazo"

df_filtrado['Situacao'] = df_filtrado.apply(verificar_situacao, axis=1)

# B. Contar Projetos Realmente Finalizados (Lógica Estrita)
# Agrupa o DF original para saber se o projeto está 100% concluído no banco
status_por_projeto = df_original.groupby('Projeto')['Status'].apply(lambda x: (x == 'Concluído').all())
lista_projetos_concluidos_real = status_por_projeto[status_por_projeto == True].index.tolist()

# C. Calcular KPIs da Visão Atual
qtd_chamados = len(df_filtrado)
chamados_finalizados = len(df_filtrado[df_filtrado['Status'] == 'Concluído'])

# Projetos Visíveis
projetos_visiveis = df_filtrado['Projeto'].unique()
kpi_proj_finalizados = 0
kpi_proj_abertos = 0

for proj in projetos_visiveis:
    if proj in lista_projetos_concluidos_real:
        kpi_proj_finalizados += 1
    else:
        kpi_proj_abertos += 1

# --- 6. INTERFACE (DASHBOARD) ---

st.title("📊 Detalhes do Projeto")
st.markdown(f"**Data de Hoje:** {hoje.strftime('%d/%m/%Y')}")
st.markdown("---")

# Cards de KPI
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total de Chamados", qtd_chamados)
with col2:
    st.metric("Projetos Abertos", kpi_proj_abertos, help="Projetos na tela atual que ainda possuem pendências.")
with col3:
    st.metric("Projetos 100% Concluídos", kpi_proj_finalizados, help="Projetos onde TODAS as tarefas (globais) estão prontas.")
with col4:
    st.metric("Tarefas Finalizadas", chamados_finalizados)

st.markdown("---")

# Layout Gráfico + Tabela
col_graf, col_dados = st.columns([1, 2])

with col_graf:
    st.subheader("Status & Prazos")
    if not df_filtrado.empty:
        # Gráfico de Pizza por Situação (Atrasado vs No Prazo vs Finalizado)
        fig = px.pie(
            df_filtrado, 
            names='Situacao', 
            title='Saúde das Tarefas (Prazos)',
            color='Situacao',
            color_discrete_map={
                "✅ Finalizado": "#00CC96",
                "🔴 Atrasado": "#EF553B",
                "🟢 No Prazo": "#636EFA"
            },
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Opcional: Gráfico de barras por Status original
        st.markdown("#### Volumetria por Status")
        contagem = df_filtrado['Status'].value_counts().reset_index()
        contagem.columns = ['Status', 'Qtd']
        fig2 = px.bar(contagem, x='Status', y='Qtd', text='Qtd')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Sem dados para exibir.")

with col_dados:
    st.subheader("Detalhamento das Tarefas")
    
    # Prepara DF para exibição (seleciona colunas e renomeia se precisar)
    df_display = df_filtrado[['ID', 'Projeto', 'Tarefa', 'Responsavel', 'Data_Inicio', 'Data_Prazo', 'Status', 'Situacao']]
    
    # Exibe tabela com formatação condicional (destaque visual)
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data_Inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
            "Data_Prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
            "Situacao": st.column_config.TextColumn(
                "Situação (Prazo)",
                help="Baseado na data de hoje",
                width="medium"
            )
        }
    )

    # Legenda explicativa simples
    st.caption("🔴 Atrasado: Data de Prazo já passou e o Status não é 'Concluído'.")
