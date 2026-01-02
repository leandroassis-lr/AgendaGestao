import streamlit as st
import pandas as pd
import utils  # Importa arquivo de utilidades (CSS)
import utils_chamados # <--- IMPORTANTE: Conexão com a Pag 7
from datetime import date, timedelta, datetime

# Dependência opcional
try:
    import plotly.express as px
except ImportError:
    px = None

st.set_page_config(page_title="Indicadores - GESTÃO", page_icon="📊", layout="wide")
utils.load_css()

def tela_dashboard():
    st.markdown("<div class='section-title-center'>DASHBOARD DE INDICADORES</div>", unsafe_allow_html=True)
    
    # 1. CARREGA DA MESMA FONTE DA PAG 7
    df_raw = utils_chamados.carregar_chamados_db()

    if df_raw.empty:
        st.info("Nenhum projeto cadastrado para exibir o dashboard.")
        return
    
    if px is None:
        st.error("ERRO: A biblioteca de gráficos não está instalada.")
        return

    # 2. PADRONIZAÇÃO DE DATAS
    df_raw['Agendamento'] = pd.to_datetime(df_raw['Agendamento'], errors='coerce')
    df_raw['Fechamento'] = pd.to_datetime(df_raw['Fechamento'], errors='coerce')
    df_raw['Abertura'] = pd.to_datetime(df_raw['Abertura'], errors='coerce')

    # --- 3. APLICAÇÃO DA REGRA DA AGENDA (AGRUPAMENTO) ---
    # Aqui transformamos linhas de equipamentos em linhas de PROJETOS ÚNICOS
    # Agrupamos por Data + Agência + Projeto (igual à Agenda)
    
    # Preenche nulos para não perder dados no agrupamento
    df_raw['Nome Agência'] = df_raw['Nome Agência'].fillna('N/A')
    df_raw['Projeto'] = df_raw['Projeto'].fillna('N/A')
    
    # Definimos como agregar cada coluna
    agg_rules = {
        'Status': 'first',      # Pega o status principal
        'Sub-Status': 'first',
        'Analista': 'first',
        'Fechamento': 'first',
        'Abertura': 'first',
        'Nº Chamado': 'first',  # Pega um dos chamados como referência
        'ID': 'first'
    }
    
    # Se houverem colunas extras que queremos manter, adicionamos aqui
    # Realiza o agrupamento (Mantendo Agendamento como coluna, não índice)
    df_projetos_unicos = df_raw.groupby(['Agendamento', 'Nome Agência', 'Projeto'], dropna=False).agg(agg_rules).reset_index()

    # --- FIM DO AGRUPAMENTO ---

    # Lista de status considerados "Finalizados"
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado', 'equipamento entregue']
    
    # --- FILTRO DE DATA (POR DATA DE AGENDAMENTO) ---
    st.markdown("#### 📅 Filtro de Período")
    col_data1, col_data2 = st.columns(2)
    
    df_com_agendamento = df_projetos_unicos.dropna(subset=['Agendamento'])
    
    if df_com_agendamento.empty:
        st.warning("Nenhum projeto com data de agendamento para filtrar.")
        df_filtrado = df_projetos_unicos.copy()
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
    else:
        # Pega datas min/max da base agrupada
        data_min_geral = df_com_agendamento['Agendamento'].min().date()
        
        with col_data1:
            data_inicio = st.date_input("De", value=date.today().replace(day=1), format="DD/MM/YYYY")
        with col_data2:
            data_fim = st.date_input("Até", value=date.today(), format="DD/MM/YYYY")

        # Filtra a base JÁ AGRUPADA
        df_filtrado = df_projetos_unicos[
            (df_projetos_unicos['Agendamento'].dt.date >= data_inicio) & 
            (df_projetos_unicos['Agendamento'].dt.date <= data_fim)
        ].copy()
    
    # --- MÉTRICAS PRINCIPAIS ---
    total_projetos_periodo = len(df_filtrado)
    
    # Contagem baseada na lista oficial de status
    finalizados_periodo = len(df_filtrado[df_filtrado["Status"].str.lower().isin(status_fim)])
    
    # CORREÇÃO DO ERRO ANTERIOR: .str.contains com case=False trata o lower internamente
    pendencia_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("Pendencia|Pendência", na=False, case=False)])
    pausados_periodo = len(df_filtrado[df_filtrado["Status"].str.contains("Pausada|Pausado|Cancelado", na=False, case=False)])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Projetos (Visitas)", value=total_projetos_periodo)
    col2.metric(label="Finalizados / Faturados", value=finalizados_periodo)
    col3.metric(label="Com Pendência", value=pendencia_periodo)
    col4.metric(label="Pausados / Cancelados", value=pausados_periodo)

    st.divider()
    
    # Define DF de Ativos (Tudo que não está na lista de fim nem cancelado)
    df_ativos = df_filtrado[
        ~df_filtrado["Status"].str.lower().isin(status_fim) & 
        ~df_filtrado["Status"].str.contains("Cancelado", na=False, case=False)
    ].copy()

    # --- GRÁFICOS ---
    col_graf_1, col_graf_2 = st.columns(2)

    with col_graf_1:
        st.subheader("1. SLA dos Projetos Ativos")
        if not df_ativos.empty:
            hoje = pd.Timestamp.today().normalize()
            
            def definir_sla(row):
                if pd.isna(row['Agendamento']): return "Sem Data"
                if row['Agendamento'] < hoje: return "Fora do Prazo (Atrasado)"
                return "Dentro do Prazo"

            df_ativos['sla_categoria'] = df_ativos.apply(definir_sla, axis=1)
            
            sla_counts = df_ativos['sla_categoria'].value_counts().reset_index()
            sla_counts.columns = ['Categoria', 'Qtd']
            
            fig_sla = px.pie(sla_counts, names='Categoria', values='Qtd', 
                             color='Categoria',
                             color_discrete_map={
                                 'Dentro do Prazo':'#66BB6A', 
                                 'Fora do Prazo (Atrasado)':'#EF5350', 
                                 'Sem Data':'#B0BEC5'
                             },
                             hole=.4)
            st.plotly_chart(fig_sla, use_container_width=True)
        else:
            st.info("Nenhum projeto ativo no período.")

    with col_graf_2:
        st.subheader("2. SLA por Analista (Ativos)")
        if not df_ativos.empty and 'Analista' in df_ativos.columns:
            sla_por_analista = df_ativos.groupby(['Analista', 'sla_categoria']).size().reset_index(name='Contagem')
            
            fig_sla_analista = px.bar(sla_por_analista, x='Analista', y='Contagem', color='sla_categoria',
                                      text='Contagem', barmode='stack',
                                      color_discrete_map={
                                         'Dentro do Prazo':'#66BB6A', 
                                         'Fora do Prazo (Atrasado)':'#EF5350', 
                                         'Sem Data':'#B0BEC5'
                                      })
            st.plotly_chart(fig_sla_analista, use_container_width=True)
        else:
            st.info("Dados insuficientes para gráfico por analista.")

    st.divider()
    col_graf_3, col_graf_4, col_graf_5 = st.columns(3)

    with col_graf_3:
        st.subheader("3. Distribuição de Status")
        if not df_filtrado.empty:
            status_counts = df_filtrado['Status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'count']
            
            # Tenta pegar cores do utils_chamados
            cores_map = {stt: utils_chamados.get_status_color(stt) for stt in status_counts['Status']}
            
            fig_status = px.pie(status_counts, names='Status', values='count', 
                                color='Status',
                                color_discrete_map=cores_map,
                                hole=.4)
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.info("Sem dados.")

    with col_graf_4:
        st.subheader("4. Aging (Dias em Aberto)")
        # Aging baseado na Data de Abertura (usando o df_ativos já agrupado)
        df_aging = df_ativos.dropna(subset=['Abertura']).copy()
        if not df_aging.empty:
            df_aging['dias_em_aberto'] = (datetime.now() - df_aging['Abertura']).dt.days
            
            bins = [-float('inf'), 0, 15, 30, 60, float('inf')]
            labels = ['Futuro/Hoje','1-15 dias', '16-30 dias', '31-60 dias', '+60 dias']
            df_aging['aging'] = pd.cut(df_aging['dias_em_aberto'], bins=bins, labels=labels, right=False)
            
            aging_counts = df_aging['aging'].value_counts().sort_index().reset_index()
            aging_counts.columns = ['Faixa', 'Qtd']
            
            fig_aging = px.bar(aging_counts, x='Faixa', y='Qtd', text='Qtd', title="Tempo desde Abertura")
            fig_aging.update_traces(marker_color='#42A5F5')
            st.plotly_chart(fig_aging, use_container_width=True)
        else:
            st.info("Sem datas de abertura válidas para cálculo.")

    with col_graf_5:
        st.subheader("5. Entregas por Mês")
        # Pega todos os finalizados da BASE AGRUPADA (sem filtro de período inicial)
        df_finalizados_geral = df_projetos_unicos[df_projetos_unicos['Status'].str.lower().isin(status_fim)].copy()
        
        # Filtra os que foram fechados DENTRO do período selecionado
        df_finalizados_filtrado = df_finalizados_geral[
            (df_finalizados_geral['Fechamento'].dt.date >= data_inicio) &
            (df_finalizados_geral['Fechamento'].dt.date <= data_fim)
        ]
        
        if not df_finalizados_filtrado.empty:
            df_finalizados_filtrado['MesFinalizacao'] = df_finalizados_filtrado['Fechamento'].dt.strftime('%Y-%m')
            finalizados_counts = df_finalizados_filtrado['MesFinalizacao'].value_counts().sort_index().reset_index()
            finalizados_counts.columns = ['Mês', 'Qtd']
            
            fig_finalizados = px.bar(finalizados_counts, x='Mês', y='Qtd', text='Qtd')
            fig_finalizados.update_traces(marker_color='#66BB6A')
            st.plotly_chart(fig_finalizados, use_container_width=True)
        else:
            st.info("Nenhuma entrega (Fechamento) neste período.")

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}")
st.sidebar.divider()
if st.sidebar.button("Logout", use_container_width=True, key="logout_dashboard_indicadores"):
    st.session_state.clear(); st.rerun()
    
tela_dashboard()
