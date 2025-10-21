import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades
from datetime import date, timedelta, datetime # <--- CORREÇÃO AQUI

# Dependência opcional
try:
    import plotly.express as px
except ImportError:
    px = None

st.set_page_config(page_title="Indicadores - GESTÃO", page_icon="📊", layout="wide")
utils.load_css()

def tela_dashboard():
    st.markdown("<div class='section-title-center'>INDICADORES</div>", unsafe_allow_html=True)
    df_original = utils.carregar_projetos_db()
    df_sla_config = utils.carregar_config_db("sla")

    if df_original.empty:
        st.info("Nenhum projeto cadastrado para exibir o dashboard.")
        return
    
    if px is None:
        st.error("ERRO: A biblioteca de gráficos não está instalada. Adicione 'plotly' ao seu requirements.txt")
        st.code("pip install plotly")
        return

    # --- CORREÇÃO CENTRAL: Padronizar colunas de data ---
    # Converte colunas para datetime, tratando erros e valores nulos (gerando NaT)
    df_original['Agendamento'] = pd.to_datetime(df_original['Agendamento'], errors='coerce')
    df_original['Data de Finalização'] = pd.to_datetime(df_original['Data de Finalização'], errors='coerce')
    df_original['Data de Abertura'] = pd.to_datetime(df_original['Data de Abertura'], errors='coerce')
    
    # --- FILTRO DE DATA (POR DATA DE AGENDAMENTO) ---
    st.markdown("#### Filtro de Período (por Data de Agendamento)")
    col_data1, col_data2 = st.columns(2)
    
    df_com_agendamento = df_original.dropna(subset=['Agendamento'])
    
    if df_com_agendamento.empty:
        st.warning("Nenhum projeto com data de agendamento para filtrar.")
        df_filtrado = df_original.copy()
        # Define um período padrão caso não haja datas
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
    else:
        data_min_geral = df_com_agendamento['Agendamento'].min().date()
        data_max_geral = date.today()
        
        with col_data1:
            data_inicio = st.date_input("De", value=data_min_geral, min_value=data_min_geral, max_value=data_max_geral, format="DD/MM/YYYY")
        with col_data2:
            data_fim = st.date_input("Até", value=data_max_geral, min_value=data_min_geral, max_value=data_max_geral, format="DD/MM/YYYY")

        # Filtra usando as datas padronizadas
        df_filtrado = df_original[
            (df_original['Agendamento'].dt.date >= data_inicio) & 
            (df_original['Agendamento'].dt.date <= data_fim)
        ].copy()
    
    # --- MÉTRICAS PRINCIPAIS ---
    total_projetos_periodo = len(df_filtrado)
    finalizados_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("Finalizada|Finalizado", na=False, case=False)])
    pendencia_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("Pendencia|Pendência", na=False, case=False)])
    pausados_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("Pausada|Pausado", na=False, case=False)])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Projetos no Período", value=total_projetos_periodo)
    col2.metric(label="Finalizados no Período", value=finalizados_periodo)
    col3.metric(label="Com Pendência", value=pendencia_periodo)
    col4.metric(label="Pausados", value=pausados_periodo)

    st.divider()
    
    df_ativos = df_filtrado[~df_filtrado["Status"].str.contains("Finalizada|Cancelada|Finalizado|Cancelado", na=False, case=False)].copy()

    # --- GRÁFICOS ---
    col_graf_1, col_graf_2 = st.columns(2)

    with col_graf_1:
        st.subheader("1. SLA dos Projetos Ativos")
        if not df_ativos.empty:
            df_ativos['sla_categoria'] = df_ativos.apply(lambda row: utils.calcular_sla(row, df_sla_config)[0], axis=1)
            def categorizar_sla(status_sla):
                if "Atrasado" in status_sla: return "Fora do Prazo"
                if " restantes" in status_sla or "Vence Hoje" in status_sla: return "Dentro do Prazo"
                return "N/A"
            df_ativos['sla_categoria_simples'] = df_ativos['sla_categoria'].apply(categorizar_sla)
            
            sla_counts = df_ativos['sla_categoria_simples'].value_counts().reset_index()
            
            fig_sla = px.pie(sla_counts, names='sla_categoria_simples', values='count', 
                             color='sla_categoria_simples',
                             color_discrete_map={'Dentro do Prazo':'#66BB6A', 'Fora do Prazo':'#EF5350', 'N/A':'#B0BEC5'},
                             hole=.3, title="Projetos Ativos Dentro vs. Fora do Prazo")
            st.plotly_chart(fig_sla, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo no período para análise de SLA.")

    with col_graf_2:
        st.subheader("2. SLA por Analista (Projetos Ativos)")
        if not df_ativos.empty and 'sla_categoria_simples' in df_ativos.columns and 'Analista' in df_ativos.columns:
            sla_por_analista = df_ativos.groupby(['Analista', 'sla_categoria_simples']).size().reset_index(name='Contagem')
            fig_sla_analista = px.bar(sla_por_analista, x='Analista', y='Contagem', color='sla_categoria_simples',
                                      text='Contagem', barmode='stack',
                                      title="Desempenho de SLA por Analista",
                                      color_discrete_map={'Dentro do Prazo':'#66BB6A', 'Fora do Prazo':'#EF5350', 'N/A':'#B0BEC5'})
            st.plotly_chart(fig_sla_analista, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo no período para análise de SLA por analista.")

    st.divider()
    col_graf_3, col_graf_4, col_graf_5 = st.columns(3)

    with col_graf_3:
        st.subheader("3. Projetos por Status")
        status_counts = df_filtrado['Status'].value_counts().reset_index()
        fig_status = px.pie(status_counts, names='Status', values='count', 
                            color='Status',
                            color_discrete_map={status: utils.get_status_color(status) for status in status_counts['Status']},
                            hole=.3, title="Distribuição Geral de Status")
        st.plotly_chart(fig_status, use_container_width=True)

    with col_graf_4:
        st.subheader("4. Aging de Projetos Ativos")
        df_aging = df_ativos.dropna(subset=['Agendamento']).copy()
        if not df_aging.empty:
            df_aging['dias_em_aberto'] = (datetime.now() - df_aging['Agendamento']).dt.days
            
            bins = [-float('inf'), 0, 30, 60, 90, 120, float('inf')]
            labels = ['Agend. Futuro','0-30 dias', '31-60 dias', '61-90 dias', '91-120 dias', '120+ dias']
            df_aging['aging'] = pd.cut(df_aging['dias_em_aberto'], bins=bins, labels=labels, right=False)
            
            aging_counts = df_aging['aging'].value_counts().sort_index().reset_index()
            
            fig_aging = px.bar(aging_counts, x='aging', y='count', text='count', title="Tempo dos Projetos em Aberto")
            fig_aging.update_traces(textposition='outside')
            fig_aging.update_xaxes(title_text="Faixa de Dias desde o Agendamento")
            st.plotly_chart(fig_aging, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo e agendado no período para análise de Aging.")

    with col_graf_5:
        st.subheader("5. Projetos Finalizados por Mês")
        # Usa o df_original para pegar todos os finalizados, depois filtra pelo período
        df_finalizados_geral = df_original[df_original['Status'].str.contains("Finalizada|Finalizado", na=False, case=False)].copy()
        
        # Filtra os finalizados que estão dentro do período selecionado
        df_finalizados_filtrado = df_finalizados_geral[
            (df_finalizados_geral['Data de Finalização'].dt.date >= data_inicio) &
            (df_finalizados_geral['Data de Finalização'].dt.date <= data_fim)
        ]
        if not df_finalizados_filtrado.empty:
            df_finalizados_filtrado['MesFinalizacao'] = df_finalizados_filtrado['Data de Finalização'].dt.to_period('M').astype(str)
            finalizados_counts = df_finalizados_filtrado['MesFinalizacao'].value_counts().sort_index().reset_index()
            
            fig_finalizados = px.bar(finalizados_counts, x='MesFinalizacao', y='count', text='count', title="Volume de Entregas Mensais")
            fig_finalizados.update_traces(textposition='outside')
            fig_finalizados.update_xaxes(title_text="Mês de Finalização")
            st.plotly_chart(fig_finalizados, use_container_width=True)
        else:
            st.info("Nenhum projeto finalizado no período selecionado.")

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
st.sidebar.divider()
st.sidebar.divider()
st.sidebar.title("Sistema")
if st.sidebar.button("Logout", use_container_width=True, key="logout_dashboard"):
    st.session_state.clear(); st.rerun()
    
tela_dashboard()
