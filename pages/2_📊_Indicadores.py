import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades
from datetime import date, timedelta

# Dependência opcional
try:
    import plotly.express as px
except Exception:
    px = None

st.set_page_config(page_title="Indicadores - GESTÃO", page_icon="📊", layout="wide")
utils.load_css()

def tela_dashboard():
    st.markdown("<div class='section-title-center'>INDICADORES</div>", unsafe_allow_html=True)
    df_original = utils.carregar_projetos_db()
    df_sla_config = utils.carregar_config("sla")

    if df_original.empty:
        st.info("Nenhum projeto cadastrado para exibir o dashboard.")
        return
    
    if px is None:
        st.warning("Biblioteca de gráficos não instalada. Rode: pip install plotly")
        return

    # --- FILTRO DE DATA (POR DATA DE AGENDAMENTO) ---
    st.markdown("#### Filtro de Período (por Data de Agendamento)")
    col_data1, col_data2 = st.columns(2)
    
    df_com_agendamento = df_original.dropna(subset=['Agendamento'])
    if df_com_agendamento.empty:
        st.warning("Nenhum projeto com data de agendamento para filtrar.")
        # Mesmo sem agendamento, podemos mostrar outros dados, então não paramos a execução
        df_filtrado = df_original.copy() # Usa o DF original se não houver agendamentos
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()

    else:
        data_min_geral = df_com_agendamento['Agendamento'].min().date()
        data_max_geral = date.today()
        
        with col_data1:
            data_inicio = st.date_input("De", value=data_min_geral, min_value=data_min_geral, max_value=data_max_geral, format="DD/MM/YYYY")
        with col_data2:
            data_fim = st.date_input("Até", value=data_max_geral, min_value=data_min_geral, max_value=data_max_geral, format="DD/MM/YYYY")

        df_filtrado = df_original[
            (df_original['Agendamento'].dt.date >= data_inicio) & 
            (df_original['Agendamento'].dt.date <= data_fim)
        ].copy()
    
    # --- MÉTRICAS PRINCIPAIS (AJUSTADO) ---
    total_projetos_periodo = len(df_filtrado)
    finalizados_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("Finalizada", na=False)])
    pendencia_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("PENDENCIA", na=False, case=False)])
    pausados_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("PAUSADO", na=False, case=False)])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Projetos no Período", value=total_projetos_periodo)
    with col2:
        st.metric(label="Finalizados no Período", value=finalizados_periodo)
    with col3:
        st.metric(label="Com Pendência", value=pendencia_periodo)
    with col4:
        st.metric(label="Pausados", value=pausados_periodo)

    st.divider()
    
    df_ativos = df_filtrado[~df_filtrado["Status"].str.contains("Finalizada|Cancelada", na=False)].copy()

    # --- GRÁFICOS (ORDEM MANTIDA) ---
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
            sla_counts.columns = ['Categoria', 'Contagem']
            
            fig_sla = px.pie(sla_counts, names='Categoria', values='Contagem', 
                             color='Categoria',
                             color_discrete_map={'Dentro do Prazo':'#66BB6A', 'Fora do Prazo':'#EF5350', 'N/A':'#B0BEC5'},
                             hole=.3)
            st.plotly_chart(fig_sla, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo no período para análise de SLA.")

    with col_graf_2:
        st.subheader("2. SLA por Analista (Projetos Ativos)")
        if not df_ativos.empty and 'sla_categoria_simples' in df_ativos.columns:
            sla_por_analista = df_ativos.groupby(['Analista', 'sla_categoria_simples']).size().reset_index(name='Contagem')
            fig_sla_analista = px.bar(sla_por_analista, x='Analista', y='Contagem', color='sla_categoria_simples',
                                      text='Contagem', barmode='stack',
                                      title="Dentro vs. Fora do Prazo por Analista",
                                      color_discrete_map={'Dentro do Prazo':'#66BB6A', 'Fora do Prazo':'#EF5350', 'N/A':'#B0BEC5'})
            st.plotly_chart(fig_sla_analista, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo no período para análise de SLA por analista.")

    st.divider()
    col_graf_3, col_graf_4, col_graf_5 = st.columns(3)

    with col_graf_3:
        st.subheader("3. Projetos por Status")
        status_counts = df_filtrado['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Contagem']
        fig_status = px.pie(status_counts, names='Status', values='Contagem', 
                            color='Status',
                            color_discrete_map={status: utils.get_status_color(status) for status in status_counts['Status']},
                            hole=.3)
        st.plotly_chart(fig_status, use_container_width=True)

    with col_graf_4:
        st.subheader("4. Aging de Projetos Ativos (desde o Agendamento)")
        df_aging = df_ativos.dropna(subset=['Agendamento']).copy()
        if not df_aging.empty:
            df_aging['dias_em_aberto'] = (pd.to_datetime(date.today()) - df_aging['Agendamento']).dt.days
            
            bins = [0, 30, 60, 90, 120, float('inf')]
            labels = ['0-30 dias', '31-60 dias', '61-90 dias', '91-120 dias', '120+ dias']
            df_aging['aging'] = pd.cut(df_aging['dias_em_aberto'], bins=bins, labels=labels, right=False)
            
            aging_counts = df_aging['aging'].value_counts().sort_index().reset_index()
            aging_counts.columns = ['Faixa de Dias', 'Contagem']
            
            fig_aging = px.bar(aging_counts, x='Faixa de Dias', y='Contagem', text='Contagem')
            fig_aging.update_traces(textposition='outside')
            st.plotly_chart(fig_aging, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo e agendado no período para análise de Aging.")

    with col_graf_5:
        st.subheader("5. Projetos Finalizados por Mês")
        df_finalizados_geral = df_original[df_original['Status'] == 'Finalizada'].copy()
        df_finalizados_filtrado = df_finalizados_geral[
            (df_finalizados_geral['Data de Finalização'].dt.date >= data_inicio) &
            (df_finalizados_geral['Data de Finalização'].dt.date <= data_fim)
        ]
        if not df_finalizados_filtrado.empty:
            df_finalizados_filtrado['MesFinalizacao'] = df_finalizados_filtrado['Data de Finalização'].dt.to_period('M').astype(str)
            finalizados_counts = df_finalizados_filtrado['MesFinalizacao'].value_counts().sort_index().reset_index()
            finalizados_counts.columns = ['Mês', 'Contagem']
            
            fig_finalizados = px.bar(finalizados_counts, x='Mês', y='Contagem', text='Contagem')
            fig_finalizados.update_traces(textposition='outside')
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