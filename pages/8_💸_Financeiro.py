import streamlit as st
import pandas as pd
import utils_chamados
import utils_financeiro
import time
import math
from datetime import date

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
        .fin-card-header { font-size: 1.1rem; font-weight: bold; color: #333; margin-bottom: 5px; }
        .fin-label { font-size: 0.85rem; color: #666; margin-bottom: 0; }
        .fin-value { font-size: 1rem; font-weight: 500; color: #222; }
        .status-badge-fin { padding: 5px 10px; border-radius: 15px; font-weight: bold; font-size: 0.8rem; color: white; text-align: center; width: 100%; display: block; }
        .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; color: #333; }
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

# --- ESTADO DA PAGINAÇÃO ---
if 'pag_fin_atual' not in st.session_state:
    st.session_state.pag_fin_atual = 0

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
    serv = str(row.get('Serviço', '')).strip().lower()
    equip = str(row.get('Equipamento', '')).strip().lower()
    qtd = pd.to_numeric(row.get('Qtd.'), errors='coerce')
    if pd.isna(qtd) or qtd == 0: qtd = 1
    
    if serv in lpu_f: return lpu_f[serv]
    if equip in lpu_s:
        keywords_desinst = ['desativacao', 'desinstalação', 'desinstalacao']
        if any(x in serv for x in keywords_desinst): return lpu_s[equip].get('desativacao', 0.0) * qtd
        keywords_reinst = ['reinstalacao', 'reinstalação', 'instalação nova', 'instalacao nova', 'remanejamento']
        if any(x in serv for x in keywords_reinst): return lpu_s[equip].get('reinstalacao', 0.0) * qtd
    if equip in lpu_e: return lpu_e.get(equip, 0.0) * qtd
    return 0.0

def definir_status_financeiro(row, lista_books, lista_liberados):
    chamado_id = str(row['Nº Chamado']).strip()
    
    # Normaliza textos para evitar erros de maiúscula/minúscula
    status_tecnico = str(row.get('Status', '')).strip().lower()
    sub_status = str(row.get('Sub-Status', '')).strip().lower()
    
    # 1. Se está na lista de liberados do banco -> FATURADO
    if chamado_id in lista_liberados: 
        return "FATURADO", "#2E7D32" # Verde Escuro
        
    # 2. Se está na lista de books enviados -> PENDENTE FATURAMENTO
    if chamado_id in lista_books: 
        return "PENDENTE FATURAMENTO", "#FB8C00" # Laranja
        
    # 3. Identificar "Aguardando Book"
    # Pega se o status for de conclusão OU se a ação falar de book
    palavras_chave_fim = ['finalizado', 'concluido', 'concluído', 'fechado', 'resolvido', 'encerrado', 'executado']
    
    status_ok = any(k in status_tecnico for k in palavras_chave_fim)
    acao_book = 'book' in sub_status # Pega "Enviar Book", "Pendente Book", etc.
    
    if status_ok or acao_book: 
        return "AGUARDANDO BOOK", "#C62828" # Vermelho
        
    # 4. Resto
    return "EM ANDAMENTO", "#1565C0" # Azul

# --- CARREGAMENTO ---
st.markdown("<div class='section-title-center'>PAINEL FINANCEIRO E FATURAMENTO</div>", unsafe_allow_html=True)

with st.spinner("Processando dados financeiros..."):
    df_chamados_raw, lpu_f, lpu_s, lpu_e, df_books, df_lib = carregar_dados_fin()

if df_chamados_raw.empty:
    st.warning("Sem dados. Importe chamados primeiro."); st.stop()

# --- PROCESSAMENTO ---
df_chamados_raw['Valor_Calculado'] = df_chamados_raw.apply(lambda x: calcular_valor_linha(x, lpu_f, lpu_s, lpu_e), axis=1)

# Lista de chamados no Book (qualquer um na planilha)
set_books = set(df_books['chamado'].astype(str))
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
        st.info("Importe o controle de Books. Todos os chamados presentes no arquivo terão Status atualizado para 'Finalizado' e Protocolo salvo.")
        up_bk = st.file_uploader("Books (.xlsx/.csv)", type=["xlsx", "csv"], key="up_bk")
        if up_bk and st.button("Importar Books e Atualizar Sistema"):
            try:
                df_b = pd.read_csv(up_bk, sep=';', dtype=str) if up_bk.name.endswith('.csv') else pd.read_excel(up_bk, dtype=str)
                
                # 1. Importar para tabela de Rastreio
                suc, msg = utils_financeiro.importar_planilha_books(df_b)
                
                if not suc: st.error(msg)
                else:
                    st.success(msg)
                    # 2. Write-Back: Atualizar Tabela Principal de Chamados
                    df_b.columns = [str(c).strip().upper() for c in df_b.columns]
                    
                    # --- AJUSTE: NÃO FILTRA MAIS POR 'SIM' ---
                    # Processa TODOS os chamados da planilha
                    df_bd = utils_chamados.carregar_chamados_db()
                    id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                    
                    cnt = 0
                    for _, r in df_b.iterrows():
                        i_d = id_map.get(r['CHAMADO'])
                        if i_d:
                            updates = {
                                'Nº Protocolo': r.get('PROTOCOLO'),
                                'Status': 'Finalizado' # Força Finalizado pois está na planilha de books (concluído)
                            }
                            dt_conc = pd.to_datetime(r.get('DATA CONCLUSAO'), errors='coerce')
                            if not pd.isna(dt_conc): updates['Data Finalização'] = dt_conc

                            utils_chamados.atualizar_chamado_db(i_d, updates)
                            cnt += 1
                    
                    st.info(f"✅ {cnt} chamados foram atualizados automaticamente com Protocolo e Status.")
                    st.cache_data.clear(); st.cache_resource.clear(); time.sleep(1); st.rerun()

            except Exception as e: st.error(f"Erro: {e}")

        with tab3:
            up_lib = st.file_uploader("Liberação (.xlsx/.csv)", type=["xlsx", "csv"], key="up_lib")
            if up_lib and st.button("Importar Liberação"):
                try:
                    df_l = pd.read_csv(up_lib, sep=';', dtype=str) if up_lib.name.endswith('.csv') else pd.read_excel(up_lib, dtype=str)
                    
                    # 1. Salva na tabela espelho (faturamento_liberado)
                    suc, msg = utils_financeiro.importar_planilha_liberacao(df_l)
                    
                    if suc: 
                        st.success(msg)
                        
                        # --- NOVO: SINCRONIZAÇÃO COM A PÁGINA 7 ---
                        with st.spinner("Atualizando status na tabela principal..."):
                            # Carrega os chamados para pegar o ID interno
                            df_bd = utils_chamados.carregar_chamados_db()
                            # Cria um mapa: Nº Chamado -> ID Interno (ex: 'CH-123' -> 55)
                            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                            
                            # Normaliza nomes das colunas do Excel importado
                            df_l.columns = [str(c).strip().upper() for c in df_l.columns]
                            
                            cont_atualizados = 0
                            
                            # Percorre a planilha do banco
                            for _, row in df_l.iterrows():
                                chamado_banco = str(row.get('CHAMADO', '')).strip()
                                
                                # Se esse chamado existe no nosso sistema
                                if chamado_banco in id_map:
                                    id_interno = id_map[chamado_banco]
                                    
                                    # ATUALIZA A TABELA PRINCIPAL
                                    utils_chamados.atualizar_chamado_db(id_interno, {
                                        'Status Financeiro': 'FATURADO',
                                        'Data Faturamento': date.today() # <--- NOVA LINHA: Grava o dia de hoje
                                    })
                                    cont_atualizados += 1
                            
                            st.info(f"🔄 Sincronização completa: {cont_atualizados} chamados foram marcados como FATURADO na gestão principal.")
                            
                        st.cache_data.clear()
                        time.sleep(2)
                        st.rerun()
                    else: 
                        st.error(msg)
                except Exception as e: 
                    st.error(f"Erro: {e}")

# --- FILTROS ---
col_f1, col_f2, col_f3 = st.columns([2, 2, 4])
with col_f1:
    filtro_status_fin = st.multiselect("Filtrar Status Financeiro", options=df_chamados_raw['Status_Fin'].unique(), default=df_chamados_raw['Status_Fin'].unique(), on_change=lambda: st.session_state.update(pag_fin_atual=0))
with col_f2:
    filtro_agencia = st.selectbox("Filtrar Agência", options=["Todas"] + sorted(df_chamados_raw['Agencia_Combinada'].unique().tolist()), on_change=lambda: st.session_state.update(pag_fin_atual=0))
with col_f3:
    busca = st.text_input("Busca Rápida", placeholder="Chamado, Protocolo, Valor...")
    if busca: st.session_state.pag_fin_atual = 0

# Aplica Filtros
df_view = df_chamados_raw[df_chamados_raw['Status_Fin'].isin(filtro_status_fin)]
if filtro_agencia != "Todas": df_view = df_view[df_view['Agencia_Combinada'] == filtro_agencia]
if busca:
    t = busca.lower()
    df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower().str.contains(t)).any(axis=1)]

# --- PAGINAÇÃO ---
lista_agencias_unicas = sorted(df_view['Agencia_Combinada'].unique())
total_itens = len(lista_agencias_unicas)
ITENS_POR_PAGINA = 10
total_paginas = math.ceil(total_itens / ITENS_POR_PAGINA)

if st.session_state.pag_fin_atual >= total_paginas: st.session_state.pag_fin_atual = 0
inicio = st.session_state.pag_fin_atual * ITENS_POR_PAGINA
fim = inicio + ITENS_POR_PAGINA
agencias_da_pagina = lista_agencias_unicas[inicio:fim]

def nav_controls(key_prefix):
    c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
    with c2:
        if st.button("⬅️ Anterior", key=f"{key_prefix}_prev", disabled=(st.session_state.pag_fin_atual == 0)):
            st.session_state.pag_fin_atual -= 1; st.rerun()
    with c3:
        st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Página <strong>{st.session_state.pag_fin_atual + 1}</strong> de <strong>{max(1, total_paginas)}</strong></div>", unsafe_allow_html=True)
    with c4:
        if st.button("Próximo ➡️", key=f"{key_prefix}_next", disabled=(st.session_state.pag_fin_atual >= total_paginas - 1)):
            st.session_state.pag_fin_atual += 1; st.rerun()

# --- VISÃO DE CARDS ---
st.markdown(f"#### 📋 Detalhamento ({len(df_view)} chamados em {total_itens} agências)")

nav_controls("top")
st.divider()

df_pagina = df_view[df_view['Agencia_Combinada'].isin(agencias_da_pagina)]
agencias_view = df_pagina.groupby('Agencia_Combinada')

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

if total_paginas > 1:
    st.divider()
    nav_controls("bottom")




