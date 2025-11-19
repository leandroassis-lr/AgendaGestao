import streamlit as st
import pandas as pd
import utils_chamados
import utils_financeiro
import time

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")

if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Faça login antes de acessar esta página."); st.stop()

# Inicializa tabelas
utils_financeiro.criar_tabelas_lpu()
utils_financeiro.criar_tabela_books()
utils_financeiro.criar_tabela_liberacao() # Nova tabela

st.markdown("<h1 style='text-align: center;'>Gestão Financeira e Conciliação</h1>", unsafe_allow_html=True)
st.divider()

# --- 1. IMPORTAÇÕES (3 ABAS) ---
tab_lpu, tab_books, tab_lib = st.tabs([
    "⚙️ 1. Importar LPU (Preços)", 
    "📚 2. Importar Books (Enviado)", 
    "💰 3. Importar Liberação (Banco)"
])

# ABA 1: LPU
with tab_lpu:
    uploaded_lpu = st.file_uploader("Planilha LPU (.xlsx)", type=["xlsx"], key="lpu_up")
    if uploaded_lpu:
        if st.button("🚀 Importar LPU"):
            with st.spinner("Processando..."):
                try:
                    xls = pd.read_excel(uploaded_lpu, sheet_name=None)
                    df_f = xls.get('Valores fixo', pd.DataFrame())
                    df_s = xls.get('Serviço', pd.DataFrame())
                    df_e = xls.get('Equipamento', pd.DataFrame())
                    suc, msg = utils_financeiro.importar_lpu(df_f, df_s, df_e)
                    if suc: st.success(msg)
                    else: st.error(msg)
                except Exception as e: st.error(f"Erro: {e}")

# ABA 2: BOOKS
with tab_books:
    uploaded_books = st.file_uploader("Planilha Books (.xlsx/.csv)", type=["xlsx", "csv"], key="bk_up")
    if uploaded_books:
        if st.button("🚀 Importar Books e Atualizar"):
            with st.spinner("Importando..."):
                try:
                    if uploaded_books.name.endswith('.csv'): df_b = pd.read_csv(uploaded_books, sep=';', dtype=str)
                    else: df_b = pd.read_excel(uploaded_books, dtype=str)
                    
                    suc, msg = utils_financeiro.importar_planilha_books(df_b)
                    if not suc: st.error(msg)
                    else:
                        st.success(msg)
                        # Lógica de Write-Back (Atualizar Protocolo)
                        df_b.columns = [str(c).strip().upper() for c in df_b.columns]
                        df_p = df_b[df_b['BOOK PRONTO?'].str.upper().isin(['SIM', 'S'])]
                        if not df_p.empty:
                            df_bd = utils_chamados.carregar_chamados_db()
                            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                            cnt = 0
                            for _, r in df_p.iterrows():
                                if (i_d := id_map.get(r['CHAMADO'])):
                                    utils_chamados.atualizar_chamado_db(i_d, {'Nº Protocolo': r.get('PROTOCOLO'), 'Status': 'Finalizado'})
                                    cnt += 1
                            st.info(f"{cnt} chamados atualizados com Protocolo/Status no sistema.")
                            st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

# ABA 3: LIBERAÇÃO (NOVA)
with tab_lib:
    st.info("Importe aqui a planilha 'Liberação para Faturamento' enviada pelo Banco.")
    uploaded_lib = st.file_uploader("Planilha Liberação (.xlsx/.csv)", type=["xlsx", "csv"], key="lib_up")
    
    if uploaded_lib:
        if st.button("🚀 Importar Liberação"):
            with st.spinner("Importando Liberação..."):
                try:
                    if uploaded_lib.name.endswith('.csv'): df_l = pd.read_csv(uploaded_lib, sep=';', dtype=str)
                    else: df_l = pd.read_excel(uploaded_lib, dtype=str)
                    
                    suc, msg = utils_financeiro.importar_planilha_liberacao(df_l)
                    if suc: st.success(msg); st.balloons()
                    else: st.error(msg)
                except Exception as e: st.error(f"Erro: {e}")

st.divider()

# --- 2. CÁLCULOS E DADOS ---
@st.cache_data(ttl=60)
def get_data():
    return (
        utils_chamados.carregar_chamados_db(),
        utils_financeiro.carregar_lpu_fixo(),
        utils_financeiro.carregar_lpu_servico(),
        utils_financeiro.carregar_lpu_equipamento(),
        utils_financeiro.carregar_books_db(),
        utils_financeiro.carregar_liberacao_db()
    )

try:
    df_chamados, lpu_f, lpu_s, lpu_e, df_books, df_liberacao = get_data()
    
    # --- RELATÓRIO DE CONCILIAÇÃO (O GRANDE RESUMO) ---
    st.markdown("### 📉 Relatório de Conciliação Mensal")
    st.caption("Comparativo: O que enviamos (Books) vs. O que o Banco pagou (Liberação)")

    # Prepara Book (Enviado) - Filtra só os prontos
    if not df_books.empty:
        df_enviado = df_books[df_books['book_pronto'].str.upper().isin(['SIM', 'S'])].copy()
    else:
        df_enviado = pd.DataFrame(columns=['chamado'])

    # Prepara Liberado (Pago)
    if df_liberacao.empty:
        df_pago = pd.DataFrame(columns=['chamado', 'total', 'protocolo_atendimento'])
    else:
        df_pago = df_liberacao.copy()

    # --- CRUZAMENTO (O PUL DO GATO) ---
    # Left Join: Enviado -> Pago
    df_conci = df_enviado.merge(
        df_pago[['chamado', 'total', 'protocolo_atendimento']], 
        on='chamado', 
        how='left', 
        indicator=True
    )

    # Separa os grupos
    pagos_ok = df_conci[df_conci['_merge'] == 'both']
    pendentes = df_conci[df_conci['_merge'] == 'left_only']
    
    # KPIs
    total_enviado = len(df_enviado)
    total_pago_qtd = len(pagos_ok)
    total_pendente_qtd = len(pendentes)
    valor_recebido_real = pagos_ok['total'].sum() if 'total' in pagos_ok.columns else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Enviados (Books)", total_enviado)
    c2.metric("Confirmados (Pagos)", total_pago_qtd, delta=f"{total_pago_qtd/total_enviado:.1%}" if total_enviado else "0%")
    c3.metric("Pendentes (Glosas/Atraso)", total_pendente_qtd, delta_color="inverse")
    c4.metric("Valor Total Liberado (R$)", f"{valor_recebido_real:,.2f}")

    # Tabela de Pendências
    if not pendentes.empty:
        with st.expander(f"⚠️ Ver Lista de {total_pendente_qtd} Chamados Pendentes de Pagamento", expanded=True):
            st.dataframe(pendentes[['chamado', 'servico', 'sistema', 'data_envio']], use_container_width=True)
    else:
        if total_enviado > 0:
            st.success("Parabéns! Todos os books enviados foram liberados para pagamento.")

    st.divider()
    
    # --- TABELA GERAL (DETALHE) ---
    st.markdown("#### 🔎 Detalhe Geral dos Chamados (Sistema)")
    st.dataframe(df_chamados[['Nº Chamado', 'Agencia_Combinada', 'Status', 'Nº Protocolo', 'Valor (R$)']], use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
