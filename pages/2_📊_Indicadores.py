import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, datetime, timedelta

# Tenta importar Plotly
try:
    import plotly.express as px
except ImportError:
    px = None

st.set_page_config(page_title="Indicadores - GESTÃO", page_icon="📊", layout="wide")
utils.load_css()

def tela_dashboard():
    st.markdown("<div class='section-title-center'>DASHBOARD DE INDICADORES</div>", unsafe_allow_html=True)
    
    # --- 1. CARREGAMENTO ---
    df_raw = utils_chamados.carregar_chamados_db()

    if df_raw.empty:
        st.info("Nenhum dado disponível.")
        return
    
    if px is None:
        st.error("Erro: Plotly não instalado.")
        return

    # --- 2. TRATAMENTO DE DATAS (CRUCIAL) ---
    # Converte tudo para datetime do Pandas e força erros virarem NaT
    for col in ['Agendamento', 'Fechamento', 'Abertura']:
        if col in df_raw.columns:
            df_raw[col] = pd.to_datetime(df_raw[col], errors='coerce')

    # --- 3. AGRUPAMENTO (VISÃO DE PROJETO) ---
    # Transforma linhas de equipamentos em 1 linha por projeto
    
    # Preenche vazios essenciais para o agrupamento
    df_raw['Nome Agência'] = df_raw['Nome Agência'].fillna('N/A')
    df_raw['Projeto'] = df_raw['Projeto'].fillna('Geral')
    
    agg_rules = {
        'Status': 'first',
        'Sub-Status': 'first',
        'Analista': 'first',
        'Fechamento': 'first',
        'Abertura': 'first',
        'ID': 'first'
    }
    
    # Agrupa
    df_proj = df_raw.groupby(['Agendamento', 'Nome Agência', 'Projeto'], dropna=False).agg(agg_rules).reset_index()

    # --- 4. FILTROS ---
    st.markdown("#### 📅 Filtro de Período")
    
    c1, c2 = st.columns(2)
    hoje = pd.Timestamp.today().normalize()
    
    with c1: 
        d_inicio_input = st.date_input("De:", value=hoje - timedelta(days=30))
    with c2: 
        d_fim_input = st.date_input("Até:", value=hoje + timedelta(days=30))
    
    # --- CORREÇÃO DO ERRO TYPEERROR ---
    # Convertemos os inputs (date) para Timestamps (datetime64[ns])
    ts_inicio = pd.to_datetime(d_inicio_input)
    # Ajustamos o fim para pegar o final do dia (23:59:59)
    ts_fim = pd.to_datetime(d_fim_input) + timedelta(hours=23, minutes=59, seconds=59)

    # Filtra DataFrame Principal (Baseado no Agendamento)
    # A comparação agora é Timestamp vs Timestamp (Seguro)
    mask_periodo = (df_proj['Agendamento'] >= ts_inicio) & (df_proj['Agendamento'] <= ts_fim)
    df_filtrado = df_proj[mask_periodo].copy()
    
    if df_filtrado.empty:
        st.warning("Nenhum projeto encontrado neste período de agendamento.")
        # Não damos return aqui para permitir ver os gráficos gerais se quiser, 
        # ou paramos. Vamos deixar continuar mas com dados vazios.

    # --- 5. CÁLCULO DE SLA E STATUS ---
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado', 'equipamento entregue']
    
    def calcular_situacao(row):
        status = str(row['Status']).lower()
        agendamento = row['Agendamento']
        fechamento = row['Fechamento']
        
        # 1. FINALIZADOS
        if status in status_fim:
            # Se tem data de fechamento e ela foi depois do agendamento -> Atrasou
            if pd.notna(fechamento) and pd.notna(agendamento):
                # Compara timestamps
                if fechamento > agendamento + timedelta(days=1): # Tolerância de 1 dia
                    return "Finalizado com Atraso"
            return "Finalizado no Prazo"
        
        # 2. CANCELADOS
        if "cancelado" in status:
            return "Cancelado"
            
        # 3. EM ABERTO
        if pd.notna(agendamento):
            if agendamento < hoje:
                return "Em Aberto (Atrasado)"
            return "Em Aberto (No Prazo)"
        
        return "Sem Data"

    if not df_filtrado.empty:
        df_filtrado['Situacao_SLA'] = df_filtrado.apply(calcular_situacao, axis=1)
    else:
        df_filtrado['Situacao_SLA'] = []

    # Separação
    df_abertos = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim) & ~df_filtrado['Status'].str.lower().contains('cancelado')]
    df_finalizados = df_filtrado[df_filtrado['Status'].str.lower().isin(status_fim)]
    
    # --- 6. CARTÕES (KPIs) ---
    st.divider()
    
    qtd_total = len(df_filtrado)
    qtd_abertos = len(df_abertos)
    qtd_pendencia = len(df_filtrado[df_filtrado['Status'].str.contains("Pendencia|Pendência", na=False, case=False)])
    
    # SLA Global
    fin_prazo = len(df_finalizados[df_finalizados['Situacao_SLA'] == "Finalizado no Prazo"])
    fin_atraso = len(df_finalizados[df_finalizados['Situacao_SLA'] == "Finalizado com Atraso"])
    
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Projetos (Período)", qtd_total)
    k2.metric("Em Aberto", qtd_abertos)
    k3.metric("Com Pendência", qtd_pendencia, delta_color="inverse")
    k4.metric("Entregues no Prazo", fin_prazo, delta_color="normal")
    k5.metric("Entregues Atrasados", fin_atraso, delta_color="inverse")
    
    st.divider()

    # --- 7. GRÁFICOS ---
    
    # LINHA 1: SLA
    c_g1, c_g2 = st.columns(2)
    
    cores_sla = {
        "Finalizado no Prazo": "#2E7D32", 
        "Finalizado com Atraso": "#F9A825", 
        "Em Aberto (No Prazo)": "#1565C0", 
        "Em Aberto (Atrasado)": "#C62828", 
        "Cancelado": "#9E9E9E",
        "Sem Data": "#607D8B"
    }

    with c_g1:
        st.subheader("📊 SLA Geral")
        if not df_filtrado.empty:
            sla_counts = df_filtrado['Situacao_SLA'].value_counts().reset_index()
            sla_counts.columns = ['Situação', 'Qtd']
            fig_sla = px.pie(sla_counts, names='Situação', values='Qtd', color='Situação',
                             color_discrete_map=cores_sla, hole=0.4)
            st.plotly_chart(fig_sla, use_container_width=True)
        else:
            st.info("Sem dados.")

    with c_g2:
        st.subheader("👤 SLA por Analista")
        if not df_filtrado.empty:
            df_filtrado['Analista'] = df_filtrado['Analista'].fillna("Não Definido")
            sla_analista = df_filtrado.groupby(['Analista', 'Situacao_SLA']).size().reset_index(name='Qtd')
            fig_sla_ana = px.bar(sla_analista, x='Analista', y='Qtd', color='Situacao_SLA',
                                 color_discrete_map=cores_sla, barmode='stack', text_auto=True)
            st.plotly_chart(fig_sla_ana, use_container_width=True)
        else:
            st.info("Sem dados.")

    st.divider()
    
    # LINHA 2: AGING E STATUS
    c_g3, c_g4 = st.columns(2)
    
    with c_g3:
        st.subheader("⏳ Aging (Projetos em Aberto)")
        if not df_abertos.empty:
            # Aging baseado na data de ABERTURA
            df_aging = df_abertos.dropna(subset=['Abertura']).copy()
            if not df_aging.empty:
                df_aging['Dias Aberto'] = (hoje - df_aging['Abertura']).dt.days
                bins = [-999, 15, 30, 60, 9999]
                labels = ['0-15 dias', '16-30 dias', '31-60 dias', '+60 dias']
                df_aging['Faixa'] = pd.cut(df_aging['Dias Aberto'], bins=bins, labels=labels)
                
                aging_counts = df_aging['Faixa'].value_counts().sort_index().reset_index()
                aging_counts.columns = ['Faixa', 'Qtd']
                
                fig_aging = px.bar(aging_counts, x='Faixa', y='Qtd', text_auto=True,
                                   color_discrete_sequence=['#FF7043'])
                st.plotly_chart(fig_aging, use_container_width=True)
            else:
                st.info("Projetos abertos sem data de abertura cadastrada.")
        else:
            st.info("Nenhum projeto em aberto no filtro selecionado.")

    with c_g4:
        st.subheader("📌 Status")
        if not df_filtrado.empty:
            st_counts = df_filtrado['Status'].value_counts().reset_index()
            st_counts.columns = ['Status', 'Qtd']
            cores_st = {s: utils_chamados.get_status_color(s) for s in st_counts['Status']}
            fig_st = px.pie(st_counts, names='Status', values='Qtd', color='Status',
                            color_discrete_map=cores_st, hole=0.4)
            st.plotly_chart(fig_st, use_container_width=True)
        else:
            st.info("Sem dados.")

    st.divider()
    
    # LINHA 3: HISTÓRICO DE ENTREGAS (CORREÇÃO FINAL AQUI)
    st.subheader("📅 Histórico de Entregas (Data de Fechamento)")
    
    # Filtra projetos finalizados da base total (df_proj) que tenham data de fechamento
    df_entregas = df_proj[
        df_proj['Status'].str.lower().isin(status_fim) & 
        pd.notna(df_proj['Fechamento'])
    ].copy()
    
    # Aplica o filtro de data SOBRE A DATA DE FECHAMENTO (usando Timestamp seguro)
    mask_entregas = (df_entregas['Fechamento'] >= ts_inicio) & (df_entregas['Fechamento'] <= ts_fim)
    df_entregas_filtrado = df_entregas[mask_entregas]
    
    if not df_entregas_filtrado.empty:
        df_entregas_filtrado['Mes'] = df_entregas_filtrado['Fechamento'].dt.strftime('%d/%m')
        entregas_dia = df_entregas_filtrado['Mes'].value_counts().sort_index().reset_index()
        entregas_dia.columns = ['Dia/Mês', 'Qtd Entregue']
        
        fig_evolucao = px.bar(entregas_dia, x='Dia/Mês', y='Qtd Entregue', text_auto=True)
        fig_evolucao.update_traces(marker_color='#00695C')
        st.plotly_chart(fig_evolucao, use_container_width=True)
    else:
        st.info("Nenhuma entrega registrada (Data de Fechamento) neste período.")

# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Faça login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}")
st.sidebar.divider()
if st.sidebar.button("Logout", key="logout_dash_v4"):
    st.session_state.clear(); st.rerun()

tela_dashboard()
