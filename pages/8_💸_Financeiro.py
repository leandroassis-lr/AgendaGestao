import streamlit as st
import pandas as pd
import utils_chamados
import utils_financeiro
import time

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
        .fin-card-header { font-size: 1.1rem; font-weight: bold; color: #333; margin-bottom: 5px; }
        .fin-label { font-size: 0.85rem; color: #666; margin-bottom: 0; }
        .fin-value { font-size: 1rem; font-weight: 500; color: #222; }
        .status-badge-fin { padding: 5px 10px; border-radius: 15px; font-weight: bold; font-size: 0.8rem; color: white; text-align: center; width: 100%; display: block; }
        .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; color: #333; }
        /* Ajuste para cards */
        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- INICIALIZAÇÃO ---
utils_financeiro.criar_tabelas_lpu()
utils_financeiro.criar_tabela_books()
utils_financeiro.criar_tabela_liberacao()

# --- FUNÇÕES AUXILIARES ---
def formatar_agencia_excel(id_agencia, nome_agencia):
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except: id_str = str(id_agencia).strip()
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo): nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

@st.cache_data(ttl=60)
def carregar_dados_fin():
    df_chamados = utils_chamados.carregar_chamados_db()
    if 'Cód. Agência' in df_chamados.columns and 'Nome Agência' in df_chamados.columns:
        df_chamados['Agencia_Combinada'] = df_chamados.apply(lambda x: formatar_agencia_excel(x['Cód. Agência'], x['Nome Agência']), axis=1)
    
    return (
        df_chamados,
        utils_financeiro.carregar_lpu_fixo(),
        utils_financeiro.carregar_lpu_servico(),
        utils_financeiro.carregar_lpu_equipamento(),
        utils_financeiro.carregar_books_db(),
        utils_financeiro.carregar_liberacao_db()
    )

def calcular_valor_linha(row, lpu_f, lpu_s, lpu_e):
    """Calcula o valor do serviço com base na LPU."""
    serv = str(row.get('Serviço', '')).strip().lower()
    equip = str(row.get('Equipamento', '')).strip().lower()
    qtd = pd.to_numeric(row.get('Qtd.'), errors='coerce')
    if pd.isna(qtd) or qtd == 0: qtd = 1
    
    # 1. Tenta Valor Fixo (Prioridade)
    if serv in lpu_f: return lpu_f[serv]
    
    # 2. Tenta Serviço de Equipamento (Desinstalação ou Reinstalação)
    if equip in lpu_s:
        # Regra para Desinstalação
        keywords_desinst = ['desativacao', 'desinstalação', 'desinstalacao']
        if any(x in serv for x in keywords_desinst): 
            return lpu_s[equip].get('desativacao', 0.0) * qtd
        
        # Regra para Reinstalação (Inclui Instalação Nova e Remanejamento)
        keywords_reinst = ['reinstalacao', 'reinstalação', 'instalação nova', 'instalacao nova', 'remanejamento']
        if any(x in serv for x in keywords_reinst): 
            return lpu_s[equip].get('reinstalacao', 0.0) * qtd
            
    # 3. Tenta Preço Unitário Equipamento (Último recurso)
    if equip in lpu_e: return lpu_e.get(equip, 0.0) * qtd
    
    return 0.0

def definir_status_financeiro(row, lista_books, lista_liberados):
    """Define o status com base no cruzamento de dados."""
    chamado_id = str(row['Nº Chamado'])
    status_tecnico = str(row['Status']).lower()
    
    if chamado_id in lista_liberados:
        return "FATURADO", "#43A047" # Verde Escuro
    if chamado_id in lista_books:
        return "PENDENTE FATURAMENTO", "#FB8C00" # Laranja
    
    fechado_keywords = ['finalizado', 'concluido', 'concluído', 'fechado', 'resolvido', 'encerrado']
    if any(k in status_tecnico for k in fechado_keywords):
        return "AGUARDANDO BOOK", "#E53935" # Vermelho
    
    return "EM ANDAMENTO", "#1E88E5" # Azul

# --- CARREGAMENTO ---
st.markdown("<div class='section-title-center'>PAINEL FINANCEIRO E FATURAMENTO</div>", unsafe_allow_html=True)

with st.spinner("Processando dados financeiros..."):
    df_chamados_raw, lpu_f, lpu_s, lpu_e, df_books, df_lib = carregar_dados_fin()

if df_chamados_raw.empty:
    st.warning("Sem dados. Importe chamados primeiro."); st.stop()

# --- PROCESSAMENTO ---
df_chamados_raw['Valor_Calculado'] = df_chamados_raw.apply(lambda x: calcular_valor_linha(x, lpu_f, lpu_s, lpu_e), axis=1)

set_books = set(df_books[df_books['book_pronto'].astype(str).str.upper().isin(['SIM', 'S'])]['chamado'].astype(str))
set_liberados = set(df_lib['chamado'].astype(str)) if not df_lib.empty else set()

df_chamados_raw[['Status_Fin', 'Cor_Fin']] = df_chamados_raw.apply(
    lambda x: pd.Series(definir_status_financeiro(x, set_books, set_liberados)), axis=1
)

# --- DASHBOARD EXECUTIVO ---
df_faturado = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'FATURADO']
df_pendente = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'PENDENTE FATURAMENTO']
df_aguardando = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'AGUARDANDO BOOK']

total_geral = df_chamados_raw['Valor_Calculado'].sum()
val_faturado = df_faturado['Valor_Calculado'].sum()
val_pendente = df_pendente['Valor_Calculado'].sum()
val_aguardando = df_aguardando['Valor_Calculado'].sum()

qtd_geral = len(df_chamados_raw)
qtd_faturado = len(df_faturado)
qtd_pendente = len(df_pendente)
qtd_aguardando = len(df_aguardando)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Faturado (Pago)", f"R$ {val_faturado:,.2f}", f"{qtd_faturado} chamados")
c2.metric("Pendente Faturamento (Enviado)", f"R$ {val_pendente:,.2f}", f"{qtd_pendente} chamados", delta_color="off")
c3.metric("Aguardando Book (A Fazer)", f"R$ {val_aguardando:,.2f}", f"{qtd_aguardando} chamados", delta_color="inverse")
c4.metric("Potencial Total", f"R$ {total_geral:,.2f}", f"{qtd_geral} chamados", delta_color="off")

st.divider()

# --- IMPORTADORES ---
with st.expander("⚙️ Configurações e Importações (LPU, Books, Liberação)"):
    tab1, tab2, tab3 = st.tabs(["Preços (LPU)", "Books (Enviados)", "Liberação (Banco)"])
    
    with tab1:
        up_lpu = st.file_uploader("LPU (.xlsx)", type=["xlsx"], key="up_lpu")
        if up_lpu and st.button("Importar LPU"):
            try:
                xls = pd.read_excel(up_lpu, sheet_name=None)
                suc, msg = utils_financeiro.importar_lpu(xls.get('Valores fixo', pd.DataFrame()), xls.get('Serviço', pd.DataFrame()), xls.get('Equipamento', pd.DataFrame()))
                if suc: st.success(msg); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.error(msg)
            except Exception as e: st.error(f"Erro: {e}")

    with tab2:
        up_bk = st.file_uploader("Books (.xlsx/.csv)", type=["xlsx", "csv"], key="up_bk")
        if up_bk and st.button("Importar Books"):
            try:
                df_b = pd.read_csv(up_bk, sep=';', dtype=str) if up_bk.name.endswith('.csv') else pd.read_excel(up_bk, dtype=str)
                suc, msg = utils_financeiro.importar_planilha_books(df_b)
                if suc: st.success(msg); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.error(msg)
            except Exception as e: st.error(f"Erro: {e}")

    with tab3:
        up_lib = st.file_uploader("Liberação (.xlsx/.csv)", type=["xlsx", "csv"], key="up_lib")
        if up_lib and st.button("Importar Liberação"):
            try:
                df_l = pd.read_csv(up_lib, sep=';', dtype=str) if up_lib.name.endswith('.csv') else pd.read_excel(up_lib, dtype=str)
                suc, msg = utils_financeiro.importar_planilha_liberacao(df_l)
                if suc: st.success(msg); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.error(msg)
            except Exception as e: st.error(f"Erro: {e}")

# --- FILTROS ---
col_f1, col_f2, col_f3 = st.columns([2, 2, 4])
with col_f1:
    filtro_status_fin = st.multiselect("Filtrar Status Financeiro", options=df_chamados_raw['Status_Fin'].unique(), default=df_chamados_raw['Status_Fin'].unique())
with col_f2:
    filtro_agencia = st.selectbox("Filtrar Agência", options=["Todas"] + sorted(df_chamados_raw['Agencia_Combinada'].unique().tolist()))
with col_f3:
    busca = st.text_input("Busca Rápida", placeholder="Chamado, Protocolo, Valor...")

df_view = df_chamados_raw[df_chamados_raw['Status_Fin'].isin(filtro_status_fin)]
if filtro_agencia != "Todas": df_view = df_view[df_view['Agencia_Combinada'] == filtro_agencia]
if busca:
    t = busca.lower()
    df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower().str.contains(t)).any(axis=1)]

# --- VISÃO DE CARDS ---
st.markdown(f"#### 📋 Detalhamento ({len(df_view)} registros)")

agencias_view = df_view.groupby('Agencia_Combinada')
for nome_agencia, df_ag in agencias_view:
    total_ag = df_ag['Valor_Calculado'].sum()
    st.markdown(f"**🏦 {nome_agencia}** <span style='color:green; font-size:0.9em;'>(Total: R$ {total_ag:,.2f})</span>", unsafe_allow_html=True)
    
    for _, row in df_ag.iterrows():
        chamado = row['Nº Chamado']
        dt_abert = pd.to_datetime(row['Abertura']).strftime('%d/%m/%Y') if pd.notna(row['Abertura']) else "-"
        dt_conc = pd.to_datetime(row['Fechamento']).strftime('%d/%m/%Y') if pd.notna(row['Fechamento']) else "-"
        status_fin = row['Status_Fin']; cor_fin = row['Cor_Fin']; valor = row['Valor_Calculado']
        
        st.markdown(f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 10px; margin-bottom: 10px; background-color: white;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="flex: 1;"><strong>🆔 {chamado}</strong></div>
                <div style="flex: 1; text-align: center; font-size: 0.9em; color: #555;">📅 Abertura: {dt_abert}</div>
                <div style="flex: 1; text-align: center; font-size: 0.9em; color: #555;">🏁 Conclusão: {dt_conc}</div>
                <div style="flex: 1; text-align: right;">
                     <span style="background-color: {cor_fin}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: bold;">{status_fin}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander(f"➕ Detalhes e Valores: R$ {valor:,.2f}"):
            c_det1, c_det2 = st.columns([3, 1])
            with c_det1:
                st.markdown(f"**Projeto:** {row.get('Projeto', 'N/D')}")
                st.markdown(f"**Sistema:** {row.get('Sistema', 'N/D')} | **Serviço:** {row.get('Serviço', 'N/D')}")
                st.markdown(f"**Equipamento:** {row.get('Equipamento', 'N/D')} (Qtd: {row.get('Qtd.', 0)})")
                st.markdown(f"**Descrição:** {row.get('Descrição', '-')}")
            with c_det2:
                st.markdown("**Valor Calculado:**")
                st.markdown(f"<h3 style='color: green;'>R$ {valor:,.2f}</h3>", unsafe_allow_html=True)
                st.markdown(f"**Protocolo:** {row.get('Nº Protocolo', '-')}")

    st.markdown("<br>", unsafe_allow_html=True)
