import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, timedelta, datetime
import plotly.express as px

st.set_page_config(page_title="Indicadores - GESTÃO", page_icon="📊", layout="wide")
utils.load_css()

def tela_dashboard():
    st.markdown("<div class='section-title-center'>DASHBOARD DE INDICADORES</div>", unsafe_allow_html=True)
    
    # --- 1. CARREGAMENTO ---
    df_raw = utils_chamados.carregar_chamados_db()

    if df_raw.empty:
        st.info("Nenhum dado disponível.")
        return

    # --- 2. TRATAMENTO DE DATAS ---
    # Converte para datetime e remove fuso horário se existir (normalize)
    for col in ['Agendamento', 'Fechamento', 'Abertura']:
        if col in df_raw.columns:
            df_raw[col] = pd.to_datetime(df_raw[col], errors='coerce')

    # --- 3. AGRUPAMENTO (VISÃO DE PROJETO) ---
    # Agrupa por Data + Agência + Projeto para contar 1 linha por Projeto
    
    # Preenche vazios
    df_raw['Nome Agência'] = df_raw['Nome Agência'].fillna('N/A')
    df_raw['Projeto'] = df_raw['Projeto'].fillna('Geral')
    df_raw['Analista'] = df_raw['Analista'].fillna('Sem Analista')
    df_raw['Sub-Status'] = df_raw['Sub-Status'].fillna('Sem Ação')
    
    agg_rules = {
        'Status': 'first',
        'Sub-Status': 'first',
        'Analista': 'first',
        'Fechamento': 'first',
        'Abertura': 'first',
        'ID': 'first'
    }
    
    # Cria o DataFrame de Projetos (Agrupado)
    df_proj = df_raw.groupby(['Agendamento', 'Nome Agência', 'Projeto'], dropna=False).agg(agg_rules).reset_index()

    # --- 4. FILTROS ---
    st.markdown("#### 📅 Filtro de Período (Data do Agendamento)")
    c1, c2, c3 = st.columns([1, 1, 2])
    
    hoje = pd.Timestamp.today().normalize()
    inicio_padrao = hoje - timedelta(days=30)
    fim_padrao = hoje + timedelta(days=30)
    
    with c1: d_inicio = st.date_input("De:", value=inicio_padrao)
    with c2: d_fim = st.date_input("Até:", value=fim_padrao)
    
    # Aplica Filtro
    ts_inicio = pd.to_datetime(d_inicio)
    ts_fim = pd.to_datetime(d_fim) + timedelta(hours=23, minutes=59)

    # Filtra projetos dentro do range OU sem data (backlog) se quiser incluir
    # Aqui vamos focar no intervalo selecionado para os indicadores temporais
    mask = (df_proj['Agendamento'] >= ts_inicio) & (df_proj['Agendamento'] <= ts_fim)
    df_filtrado = df_proj[mask].copy()
    
    if df_filtrado.empty:
        st.warning("Nenhum projeto encontrado neste período.")
        return

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
                if fechamento.date() > agendamento.date():
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

    df_filtrado['Situacao_SLA'] = df_filtrado.apply(calcular_situacao, axis=1)
    
    # Separação para métricas
    df_abertos = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim) & ~df_filtrado['Status'].str.lower().contains('cancelado')]
    df_finalizados = df_filtrado[df_filtrado['Status'].str.lower().isin(status_fim)]
    
    # --- 6. CARTÕES (KPIs) ---
    st.divider()
    
    qtd_total = len(df_filtrado)
    qtd_abertos = len(df_abertos)
    qtd_pendencia = len(df_filtrado[df_filtrado['Status'].str.contains("Pendencia|Pendência", na=False, case=False)])
    
    # SLA Global (Finalizados)
    fin_prazo = len(df_finalizados[df_finalizados['Situacao_SLA'] == "Finalizado no Prazo"])
    fin_atraso = len(df_finalizados[df_finalizados['Situacao_SLA'] == "Finalizado com Atraso"])
    
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Projetos no Período", qtd_total)
    k2.metric("Em Aberto", qtd_abertos)
    k3.metric("Com Pendência", qtd_pendencia, delta_color="inverse")
    k4.metric("Finalizados (Prazo)", fin_prazo, delta_color="normal")
    k5.metric("Finalizados (Atrasado)", fin_atraso, delta_color="inverse")
    
    st.divider()

    # --- 7. GRÁFICOS ---
    
    # LINHA 1: SLA e ANALISTAS
    c_g1, c_g2 = st.columns(2)
    
    with c_g1:
        st.subheader("📊 SLA Geral (Status x Prazo)")
        # Agrupa por situação para o gráfico de pizza
        sla_counts = df_filtrado['Situacao_SLA'].value_counts().reset_index()
        sla_counts.columns = ['Situação', 'Qtd']
        
        cores_sla = {
            "Finalizado no Prazo": "#2E7D32", # Verde
            "Finalizado com Atraso": "#F9A825", # Amarelo Escuro
            "Em Aberto (No Prazo)": "#1565C0", # Azul
            "Em Aberto (Atrasado)": "#C62828", # Vermelho
            "Cancelado": "#9E9E9E",
            "Sem Data": "#607D8B"
        }
        
        fig_sla = px.pie(sla_counts, names='Situação', values='Qtd', color='Situação',
                         color_discrete_map=cores_sla, hole=0.4)
        st.plotly_chart(fig_sla, use_container_width=True)

    with c_g2:
        st.subheader("👤 SLA por Analista")
        # Gráfico de barras empilhadas: Analista x Qtd, colorido por Situação
        if not df_filtrado.empty:
            sla_analista = df_filtrado.groupby(['Analista', 'Situacao_SLA']).size().reset_index(name='Qtd')
            fig_sla_ana = px.bar(sla_analista, x='Analista', y='Qtd', color='Situacao_SLA',
                                 color_discrete_map=cores_sla, barmode='stack', text_auto=True)
            st.plotly_chart(fig_sla_ana, use_container_width=True)

    st.divider()
    
    # LINHA 2: VOLUMETRIA E AGING
    c_g3, c_g4 = st.columns(2)
    
    with c_g3:
        st.subheader("📋 Projetos por Analista (Total)")
        # Simples contagem de projetos por analista
        vol_analista = df_filtrado['Analista'].value_counts().reset_index()
        vol_analista.columns = ['Analista', 'Projetos']
        
        fig_vol = px.bar(vol_analista, x='Projetos', y='Analista', orientation='h', text_auto=True)
        fig_vol.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_vol, use_container_width=True)
        
    with c_g4:
        st.subheader("⏳ Aging de Projetos em Aberto")
        # Baseado na data de ABERTURA até HOJE
        df_aging = df_abertos.dropna(subset=['Abertura']).copy()
        
        if not df_aging.empty:
            df_aging['Dias Aberto'] = (hoje - df_aging['Abertura']).dt.days
            
            # Categorias de Aging
            bins = [-1, 15, 30, 60, 90, 9999]
            labels = ['0-15 dias', '16-30 dias', '31-60 dias', '61-90 dias', '+90 dias']
            df_aging['Faixa Aging'] = pd.cut(df_aging['Dias Aberto'], bins=bins, labels=labels)
            
            aging_counts = df_aging['Faixa Aging'].value_counts().sort_index().reset_index()
            aging_counts.columns = ['Faixa', 'Qtd']
            
            fig_aging = px.bar(aging_counts, x='Faixa', y='Qtd', text_auto=True, 
                               color_discrete_sequence=['#FF7043'])
            st.plotly_chart(fig_aging, use_container_width=True)
        else:
            st.info("Nenhum projeto em aberto com data de abertura válida.")

    st.divider()
    
    # LINHA 3: STATUS E AÇÕES
    c_g5, c_g6 = st.columns(2)
    
    with c_g5:
        st.subheader("📌 Projetos por Status")
        st_counts = df_filtrado['Status'].value_counts().reset_index()
        st_counts.columns = ['Status', 'Qtd']
        
        # Tenta mapear cores
        cores_st = {s: utils_chamados.get_status_color(s) for s in st_counts['Status']}
        
        fig_st = px.pie(st_counts, names='Status', values='Qtd', color='Status',
                        color_discrete_map=cores_st, hole=0.4)
        st.plotly_chart(fig_st, use_container_width=True)

    with c_g6:
        st.subheader("⚡ Projetos por Ação (Sub-Status)")
        # Filtra sub-status vazios
        df_acao = df_filtrado[df_filtrado['Sub-Status'] != 'Sem Ação']
        
        if not df_acao.empty:
            acao_counts = df_acao['Sub-Status'].value_counts().reset_index()
            acao_counts.columns = ['Ação', 'Qtd']
            # Pega Top 10 para não poluir
            acao_counts = acao_counts.head(10)
            
            fig_acao = px.bar(acao_counts, x='Qtd', y='Ação', orientation='h', text_auto=True,
                              color_discrete_sequence=['#5C6BC0'])
            fig_acao.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_acao, use_container_width=True)
        else:
            st.info("Nenhuma ação/sub-status registrado.")

# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Faça login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}")
st.sidebar.divider()
if st.sidebar.button("Logout", key="logout_dash_v3"):
    st.session_state.clear(); st.rerun()

tela_dashboard()
