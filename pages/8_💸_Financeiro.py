import streamlit as st
import pandas as pd
import utils_chamados  # Para carregar e ATUALIZAR os chamados
import utils_financeiro # Nosso arquivo de ferramentas financeiras
import re
import time

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")

# --- FUNÇÃO HELPER (Necessária para criar a coluna Agencia_Combinada) ---
def formatar_agencia_excel(id_agencia, nome_agencia):
    """Cria o nome combinado da agência (AG XXXX - Nome)"""
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
          nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

# --- Controle de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- Criar Tabelas no Banco (Executa se não existirem) ---
utils_financeiro.criar_tabelas_lpu()
utils_financeiro.criar_tabela_books()
utils_financeiro.criar_tabela_liberacao()

st.markdown("<h1 style='text-align: center;'>Gestão Financeira e Conciliação</h1>", unsafe_allow_html=True)
st.divider()

# ==============================================================================
# 1. SEÇÃO DE IMPORTAÇÕES (3 ABAS)
# ==============================================================================
tab_lpu, tab_books, tab_lib = st.tabs([
    "⚙️ 1. Importar LPU (Preços)", 
    "📚 2. Importar Books (Enviado)", 
    "💰 3. Importar Liberação (Banco)"
])

# --- ABA 1: LPU ---
with tab_lpu:
    st.info("Carregue a tabela de preços (LPU) para permitir o cálculo automático.")
    uploaded_lpu = st.file_uploader("Planilha LPU (.xlsx)", type=["xlsx"], key="lpu_up")
    
    if uploaded_lpu:
        if st.button("🚀 Importar LPU"):
            with st.spinner("Processando LPU..."):
                try:
                    xls = pd.read_excel(uploaded_lpu, sheet_name=None)
                    df_f = xls.get('Valores fixo', pd.DataFrame())
                    df_s = xls.get('Serviço', pd.DataFrame())
                    df_e = xls.get('Equipamento', pd.DataFrame())
                    
                    suc, msg = utils_financeiro.importar_lpu(df_f, df_s, df_e)
                    if suc: st.success(msg); st.balloons()
                    else: st.error(msg)
                except Exception as e: st.error(f"Erro: {e}")

# --- ABA 2: BOOKS (Com atualização de Chamados) ---
with tab_books:
    st.info("Importe o controle de Books enviados. Isso atualiza o 'Protocolo' e 'Status' na página Dados por Agência.")
    uploaded_books = st.file_uploader("Planilha Books (.xlsx/.csv)", type=["xlsx", "csv"], key="bk_up")
    
    if uploaded_books:
        if st.button("🚀 Importar Books e Atualizar Sistema"):
            with st.spinner("Importando e Atualizando..."):
                try:
                    if uploaded_books.name.endswith('.csv'): df_b = pd.read_csv(uploaded_books, sep=';', dtype=str)
                    else: df_b = pd.read_excel(uploaded_books, dtype=str)
                    
                    # 1. Importar para tabela de Rastreio
                    suc, msg = utils_financeiro.importar_planilha_books(df_b)
                    
                    if not suc: st.error(msg)
                    else:
                        st.success(msg)
                        
                        # 2. Write-Back: Atualizar Tabela Principal de Chamados
                        df_b.columns = [str(c).strip().upper() for c in df_b.columns]
                        # Filtra apenas BOOK PRONTO = SIM
                        df_p = df_b[df_b['BOOK PRONTO?'].str.upper().isin(['SIM', 'S'])]
                        
                        if not df_p.empty:
                            df_bd = utils_chamados.carregar_chamados_db()
                            # Mapa para achar o ID interno pelo Nº Chamado
                            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                            
                            cnt = 0
                            for _, r in df_p.iterrows():
                                i_d = id_map.get(r['CHAMADO'])
                                if i_d:
                                    # Atualiza Protocolo, Data Final e Status
                                    updates = {
                                        'Nº Protocolo': r.get('PROTOCOLO'),
                                        'Status': 'Finalizado'
                                    }
                                    # Tenta converter data
                                    dt_conc = pd.to_datetime(r.get('DATA CONCLUSAO'), errors='coerce')
                                    if not pd.isna(dt_conc):
                                        updates['Data Finalização'] = dt_conc

                                    utils_chamados.atualizar_chamado_db(i_d, updates)
                                    cnt += 1
                            
                            st.info(f"✅ {cnt} chamados foram atualizados automaticamente com Protocolo e Status.")
                            # Limpa cache para refletir mudanças
                            st.cache_data.clear()
                            st.cache_resource.clear()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Nenhum book marcado como 'SIM' encontrado para atualização.")

                except Exception as e: st.error(f"Erro: {e}")

# --- ABA 3: LIBERAÇÃO (BANCO) ---
with tab_lib:
    st.info("Importe o espelho de 'Liberação para Faturamento' do Banco para fazer a conciliação.")
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

# ==============================================================================
# 2. CARREGAMENTO E CÁLCULO DE DADOS
# ==============================================================================

@st.cache_data(ttl=60)
def carregar_dados_completos():
    """Carrega chamados e todos os dicionários de preço/rastreio."""
    df_chamados = utils_chamados.carregar_chamados_db()
    
    # --- CORREÇÃO CRÍTICA: Recriar a coluna Agencia_Combinada ---
    if 'Cód. Agência' in df_chamados.columns and 'Nome Agência' in df_chamados.columns:
        df_chamados['Agencia_Combinada'] = df_chamados.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), axis=1
        )
    # -------------------------------------------------------------

    lpu_fixo = utils_financeiro.carregar_lpu_fixo()
    lpu_servico = utils_financeiro.carregar_lpu_servico()
    lpu_equip = utils_financeiro.carregar_lpu_equipamento()
    
    df_books = utils_financeiro.carregar_books_db()
    df_liberacao = utils_financeiro.carregar_liberacao_db()
    
    return df_chamados, lpu_fixo, lpu_servico, lpu_equip, df_books, df_liberacao

def calcular_preco(row, lpu_fixo, lpu_servico, lpu_equip):
    """Calcula preço baseado na LPU (Fixo -> Serviço Equip -> Preço Equip)."""
    servico_norm = str(row.get('Serviço', '')).strip().lower()
    equip_norm = str(row.get('Equipamento', '')).strip().lower()
    qtd = pd.to_numeric(row.get('Qtd.'), errors='coerce')

    # 1. Tenta Valor Fixo
    if servico_norm in lpu_fixo:
        return lpu_fixo[servico_norm] 

    if pd.isna(qtd) or qtd == 0: qtd = 1
        
    # 2. Tenta Serviço de Equipamento (D/R)
    if equip_norm in lpu_servico:
        precos_serv = lpu_servico[equip_norm]
        if 'desativação' in servico_norm or 'desinstalação' in servico_norm:
            return precos_serv.get('desativacao', 0.0) * qtd
        if 'reinstalação' in servico_norm or 'reinstalacao' in servico_norm:
            return precos_serv.get('reinstalacao', 0.0) * qtd

    # 3. Tenta Preço Unitário Equipamento
    if equip_norm in lpu_equip:
        return lpu_equip.get(equip_norm, 0.0) * qtd
        
    return 0.0

# --- Execução Principal da Página ---
try:
    with st.spinner("Carregando dados financeiros..."):
        df_chamados_raw, lpu_fixo, lpu_servico, lpu_equip, df_books, df_liberacao = carregar_dados_completos()
    
    if df_chamados_raw.empty:
        st.warning("Nenhum chamado encontrado.")
        st.stop()
        
    # Aplica Cálculo de Preço
    df_chamados_raw['Valor_Calculado'] = df_chamados_raw.apply(
        calcular_preco, args=(lpu_fixo, lpu_servico, lpu_equip), axis=1
    )

    # ==============================================================================
    # 3. RELATÓRIO DE CONCILIAÇÃO
    # ==============================================================================
    st.markdown("### 📉 Relatório de Conciliação Mensal")
    st.caption("Comparativo: O que enviamos (Books) vs. O que o Banco pagou (Liberação)")

    # 1. Prepara Book (Enviado) - Apenas 'SIM'
    if not df_books.empty:
        # Filtra books prontos
        df_enviado = df_books[df_books['book_pronto'].str.upper().isin(['SIM', 'S'])].copy()
    else:
        df_enviado = pd.DataFrame(columns=['chamado'])

    # 2. Prepara Liberado (Pago)
    if df_liberacao.empty:
        # Cria colunas vazias para não quebrar o merge
        df_pago = pd.DataFrame(columns=['chamado', 'total', 'protocolo_atendimento'])
    else:
        df_pago = df_liberacao.copy()

    # 3. Cruzamento (Left Join: Enviado -> Pago)
    # Usamos 'chamado' como chave
    df_conci = df_enviado.merge(
        df_pago[['chamado', 'total', 'protocolo_atendimento']], 
        on='chamado', 
        how='left', 
        indicator=True
    )

    # Separa grupos
    pagos_ok = df_conci[df_conci['_merge'] == 'both']
    pendentes = df_conci[df_conci['_merge'] == 'left_only']
    
    # KPIs Conciliação
    total_enviado = len(df_enviado)
    total_pago_qtd = len(pagos_ok)
    total_pendente_qtd = len(pendentes)
    valor_recebido_real = pagos_ok['total'].sum() if 'total' in pagos_ok.columns else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Enviados (Books)", total_enviado)
    c2.metric("Confirmados (Pagos)", total_pago_qtd, delta=f"{total_pago_qtd/total_enviado:.1%}" if total_enviado else "0%")
    c3.metric("Pendentes (Atraso/Glosa)", total_pendente_qtd, delta_color="inverse")
    c4.metric("Valor Total Liberado (R$)", f"{valor_recebido_real:,.2f}")

    # Tabela de Pendências
    if not pendentes.empty:
        with st.expander(f"⚠️ Ver Lista de {total_pendente_qtd} Chamados Pendentes de Pagamento", expanded=True):
            st.warning("Estes chamados foram enviados (Book Pronto), mas não constam na planilha de Liberação do Banco.")
            # Seleciona colunas que existem
            cols_show = ['chamado', 'servico', 'sistema', 'data_envio']
            cols_finais = [c for c in cols_show if c in pendentes.columns]
            st.dataframe(pendentes[cols_finais], use_container_width=True)
    else:
        if total_enviado > 0:
            st.success("Parabéns! Todos os books enviados foram liberados para pagamento.")

    st.divider()
    
    # ==============================================================================
    # 4. TABELA GERAL DETALHADA
    # ==============================================================================
    st.markdown("#### 🔎 Detalhe Geral dos Chamados (Sistema)")
    
    colunas_visuais = [
        'Nº Chamado', 'Agencia_Combinada', 'Serviço', 'Equipamento', 'Qtd.', 
        'Valor_Calculado', 'Status', 'Nº Protocolo', 'Fechamento'
    ]
    colunas_reais = [c for c in colunas_visuais if c in df_chamados_raw.columns]
    
    df_display = df_chamados_raw[colunas_reais].copy()
    
    # Formatação de Moeda Visual
    if 'Valor_Calculado' in df_display.columns:
        df_display['Valor_Calculado'] = df_display['Valor_Calculado'].map('R$ {:,.2f}'.format)
        
    st.dataframe(df_display, use_container_width=True)

except Exception as e:
    st.error(f"Ocorreu um erro crítico ao gerar a página: {e}")
