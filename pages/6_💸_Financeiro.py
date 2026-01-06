import streamlit as st
import pandas as pd
import utils_chamados
import utils_financeiro
import time
import math
import io # <--- Importante para a exportação
from datetime import date

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")
utils.load_css()

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

# --- INICIALIZAÇÃO DE TABELAS ---
utils_financeiro.criar_tabelas_lpu()
utils_financeiro.criar_tabela_books()
utils_financeiro.criar_tabela_liberacao()

if 'pag_fin_atual' not in st.session_state: st.session_state.pag_fin_atual = 0

# --- FUNÇÕES AUXILIARES (DEFINIDAS NO TOPO) ---
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

def definir_status_financeiro(row, dict_books_info, set_liberados):
    chamado_id = str(row['Nº Chamado']).strip()
    
    # 1. FATURADO (PAGO)
    if chamado_id in set_liberados: 
        return "FATURADO (Pago)", "#2E7D32" # Verde Escuro

    # 2. PENDENTE FATURAMENTO
    if chamado_id in dict_books_info:
        info_book = dict_books_info[chamado_id]
        book_pronto = str(info_book.get('book_pronto', '')).strip().upper() == 'SIM'
        tem_data_envio = str(info_book.get('data_envio', '')).strip() not in ['', 'nan', 'None']
        
        if book_pronto or tem_data_envio:
            return "PENDENTE FATURAMENTO", "#FB8C00" # Laranja
        else:
            return "PENDENTE ENVIO BOOK", "#C62828" # Vermelho
            
    # 3. POTENCIAL
    return "POTENCIAL", "#1565C0" # Azul

# --- SIDEBAR COM EXPORTAÇÃO FINANCEIRA ---
with st.sidebar:
    st.header("📤 Exportação")
    
    # Botão ÚNICO: Relatório Financeiro Calculado
    if st.button("📊 Baixar Relatório Financeiro (.xlsx)"):
        with st.spinner("Gerando planilha financeira..."):
            
            # Recarrega dados para exportação
            df_raw, lpu_f, lpu_s, lpu_e, df_books, df_lib = carregar_dados_fin()
            
            if not df_raw.empty:
                # Calcula Valores
                df_raw['Valor_Total'] = df_raw.apply(lambda x: calcular_valor_linha(x, lpu_f, lpu_s, lpu_e), axis=1)
                
                # Prepara dados auxiliares para KPI
                set_liberados = set(df_lib['chamado'].astype(str).str.strip()) if not df_lib.empty else set()
                dict_books_info = {}
                if not df_books.empty:
                    df_books.columns = [c.upper().strip() for c in df_books.columns]
                    for _, row_b in df_books.iterrows():
                        ch = str(row_b.get('CHAMADO', '')).strip()
                        pronto = row_b.get('BOOK PRONTO?', row_b.get('BOOK PRONTO', row_b.get('PRONTO', '')))
                        dt_env = row_b.get('DATA ENVIO', row_b.get('ENVIO', ''))
                        dict_books_info[ch] = {'book_pronto': pronto, 'data_envio': dt_env}
                
                # Aplica Status KPI
                df_raw['Status_KPI_Fin'] = df_raw.apply(
                    lambda x: definir_status_financeiro(x, dict_books_info, set_liberados)[0], axis=1
                )
                
                # Seleciona Colunas
                colunas_fin = [
                    'Nº Chamado', 'Status_KPI_Fin', 'Valor_Total', 
                    'Agencia_Combinada', 'Serviço', 'Projeto', 'Sistema',
                    'Equipamento', 'Qtd.', 'Status', 'Sub-Status', 
                    'Abertura', 'Fechamento', 
                    'Data Book Enviado', 'Data Faturamento',
                    'Nº Protocolo', 'Analista', 'Gestor'
                ]
                cols_finais = [c for c in colunas_fin if c in df_raw.columns]
                df_export = df_raw[cols_finais].copy()
                
                # Gera Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Financeiro_Detalhado')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Financeiro_Detalhado']
                    fmt_money = workbook.add_format({'num_format': 'R$ #,##0.00'})
                    fmt_header = workbook.add_format({'bold': True, 'bg_color': '#2E7D32', 'font_color': 'white', 'border': 1})
                    
                    for i, col in enumerate(df_export.columns):
                        width = 18
                        if col == 'Valor_Total': width = 15
                        if col == 'Agencia_Combinada': width = 25
                        worksheet.set_column(i, i, width, fmt_money if col == 'Valor_Total' else None)
                        worksheet.write(0, i, col, fmt_header)

                st.download_button(
                    label="✅ Clique aqui para Salvar",
                    data=output.getvalue(),
                    file_name=f"Relatorio_Financeiro_{date.today().strftime('%d-%m-%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Sem dados para gerar relatório.")

# --- MAIN: CARREGAMENTO DOS DADOS PARA O PAINEL ---
st.markdown("<div class='section-title-center'>PAINEL FINANCEIRO (KPIS DO ANO)</div>", unsafe_allow_html=True)

with st.spinner("Processando dados financeiros..."):
    # AQUI ESTAVA O ERRO ANTES: A função carregar_dados_fin agora já está definida acima
    df_chamados_raw, lpu_f, lpu_s, lpu_e, df_books, df_lib = carregar_dados_fin()

if df_chamados_raw.empty:
    st.warning("Sem dados. Importe chamados primeiro."); st.stop()

# --- PROCESSAMENTO DO DASHBOARD ---
df_chamados_raw['Valor_Calculado'] = df_chamados_raw.apply(lambda x: calcular_valor_linha(x, lpu_f, lpu_s, lpu_e), axis=1)

# Dados Auxiliares
set_liberados = set(df_lib['chamado'].astype(str).str.strip()) if not df_lib.empty else set()
dict_books_info = {}
ids_books_enviados_total = set()

if not df_books.empty:
    df_books.columns = [c.upper().strip() for c in df_books.columns]
    for _, row_b in df_books.iterrows():
        ch = str(row_b.get('CHAMADO', '')).strip()
        pronto = row_b.get('BOOK PRONTO?', row_b.get('BOOK PRONTO', row_b.get('PRONTO', '')))
        dt_env = row_b.get('DATA ENVIO', row_b.get('ENVIO', ''))
        
        dict_books_info[ch] = {'book_pronto': pronto, 'data_envio': dt_env}
        
        # Lógica para "Total Enviado"
        is_sim = str(pronto).strip().upper() == 'SIM'
        has_date = str(dt_env).strip() not in ['', 'nan', 'None']
        if is_sim or has_date:
            ids_books_enviados_total.add(ch)

# Aplica Status Visual
df_chamados_raw[['Status_Fin', 'Cor_Fin']] = df_chamados_raw.apply(
    lambda x: pd.Series(definir_status_financeiro(x, dict_books_info, set_liberados)), axis=1
)

# --- CÁLCULO DOS KPIS ---
df_faturado = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'FATURADO (Pago)']
df_pend_fat = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'PENDENTE FATURAMENTO']
df_pend_book = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'PENDENTE ENVIO BOOK']
df_potencial = df_chamados_raw[df_chamados_raw['Status_Fin'] == 'POTENCIAL']

val_faturado = df_faturado['Valor_Calculado'].sum()
val_pend_fat = df_pend_fat['Valor_Calculado'].sum()
val_pend_book = df_pend_book['Valor_Calculado'].sum()
val_potencial = df_potencial['Valor_Calculado'].sum()

# KPI Extra: Total Enviado
mask_total_enviados = df_chamados_raw['Nº Chamado'].astype(str).str.strip().isin(ids_books_enviados_total)
df_total_enviados = df_chamados_raw[mask_total_enviados]
val_total_enviados = df_total_enviados['Valor_Calculado'].sum()
qtd_total_enviados = len(df_total_enviados)

qtd_faturado = len(df_faturado)
qtd_pend_fat = len(df_pend_fat)
qtd_pend_book = len(df_pend_book)
qtd_potencial = len(df_potencial)

# --- EXIBIÇÃO DOS CARDS (5 COLUNAS) ---
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("💰 Total Pago (Banco)", f"R$ {val_faturado:,.2f}", f"{qtd_faturado} chamados")
c2.metric("📤 Books Enviados (Total)", f"R$ {val_total_enviados:,.2f}", f"{qtd_total_enviados} chamados", help="Soma de tudo que foi marcado como Enviado na planilha de books, pago ou não.")
c3.metric("⏳ Pendente Recebimento", f"R$ {val_pend_fat:,.2f}", f"{qtd_pend_fat} chamados", delta_color="off", help="Enviado mas ainda não consta na planilha do banco.")
c4.metric("🚨 Pendente Envio Book", f"R$ {val_pend_book:,.2f}", f"{qtd_pend_book} chamados", delta_color="inverse", help="Está na planilha de books mas sem SIM ou Data.")
c5.metric("📈 Potencial (Aberto)", f"R$ {val_potencial:,.2f}", f"{qtd_potencial} chamados", delta_color="normal")

st.divider()

# --- BOTÃO DE SINCRONIZAÇÃO MANUAL ---
col_sync, col_info = st.columns([1, 4])
with col_sync:
    if st.button("🔄 Sincronizar Tudo", help="Atualiza a Página 7 com base nestes KPIs."):
        with st.spinner("Aplicando regras financeiras na gestão..."):
            df_bd = utils_chamados.carregar_chamados_db()
            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
            
            count_ops = 0
            for index, row in df_chamados_raw.iterrows():
                chamado_num = str(row['Nº Chamado'])
                status_kpi = row['Status_Fin']
                
                if chamado_num in id_map:
                    updates = {}
                    if status_kpi == 'FATURADO (Pago)':
                        updates = {'Status': 'Finalizado', 'Sub-Status': 'Faturado', 'chk_financeiro_banco': 'TRUE', 'chk_financeiro_book': 'TRUE'}
                    elif status_kpi == 'PENDENTE FATURAMENTO':
                        updates = {'Status': 'Finalizado', 'Sub-Status': 'Aguardando faturamento', 'chk_financeiro_book': 'TRUE'}
                    elif status_kpi == 'PENDENTE ENVIO BOOK':
                        updates = {'Status': 'Finalizado', 'Sub-Status': 'Enviar Book'}

                    if updates:
                        utils_chamados.atualizar_chamado_db(id_map[chamado_num], updates)
                        count_ops += 1

            st.toast(f"{count_ops} chamados sincronizados!", icon="✅"); time.sleep(1); st.rerun()

with col_info:
    st.info("Este botão aplica os status dos KPIs acima lá na tela de Gestão de Projetos (Pág 7).")

st.divider()

# --- IMPORTADORES ---
with st.expander("⚙️ Importações (LPU, Books, Liberação)"):
    tab1, tab2, tab3 = st.tabs(["Preços (LPU)", "Books (Controle)", "Liberação (Banco)"])
    
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
        st.info("Importe a planilha de Controle de Books. O sistema verificará as colunas 'BOOK PRONTO?' e 'DATA ENVIO'.")
        up_bk = st.file_uploader("Books (.xlsx/.csv)", type=["xlsx", "csv"], key="up_bk")
        if up_bk and st.button("Importar Books"):
            try:
                df_b = pd.read_csv(up_bk, sep=';', dtype=str) if up_bk.name.endswith('.csv') else pd.read_excel(up_bk, dtype=str)
                df_b.columns = [str(c).strip().upper() for c in df_b.columns]
                
                suc, msg = utils_financeiro.importar_planilha_books(df_b)
                
                if suc:
                    st.success(msg)
                    # Sincronia Rápida KPI
                    df_bd = utils_chamados.carregar_chamados_db()
                    id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                    cnt = 0
                    for _, r in df_b.iterrows():
                        i_d = id_map.get(r.get('CHAMADO'))
                        if i_d:
                            current_row = df_bd[df_bd['ID'] == i_d].iloc[0]
                            updates = {'Nº Protocolo': r.get('PROTOCOLO')}
                            
                            book_ok = str(r.get('BOOK PRONTO?', r.get('BOOK PRONTO', ''))).upper() == 'SIM'
                            if book_ok:
                                updates['chk_financeiro_book'] = 'TRUE'
                                if pd.isna(current_row.get('Data Book Enviado')): updates['Data Book Enviado'] = date.today()

                            dt_conc = pd.to_datetime(r.get('DATA CONCLUSAO'), errors='coerce')
                            if not pd.isna(dt_conc): updates['Data Finalização'] = dt_conc

                            utils_chamados.atualizar_chamado_db(i_d, updates)
                            cnt += 1
                    
                    st.info(f"✅ {cnt} chamados atualizados com dados da planilha.")
                    st.cache_data.clear(); time.sleep(1.5); st.rerun()
                else: st.error(msg)
            except Exception as e: st.error(f"Erro: {e}")

    with tab3:
        st.info("Importe a planilha de Liberação (Banco). Chamados aqui viram 'Total Acumulado'.")
        up_lib = st.file_uploader("Liberação (.xlsx/.csv)", type=["xlsx", "csv"], key="up_lib")
        if up_lib and st.button("Importar Liberação"):
            try:
                df_l = pd.read_csv(up_lib, sep=';', dtype=str) if up_lib.name.endswith('.csv') else pd.read_excel(up_lib, dtype=str)
                df_l.columns = [str(c).strip().upper() for c in df_l.columns]
                
                suc, msg = utils_financeiro.importar_planilha_liberacao(df_l)
                if suc:
                    st.success(msg)
                    # Sincronia Imediata
                    df_bd = utils_chamados.carregar_chamados_db()
                    id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                    c_banco = 0
                    for _, row in df_l.iterrows():
                        ch = str(row.get('CHAMADO', '')).strip()
                        if ch in id_map:
                            i_d = id_map[ch]
                            curr = df_bd[df_bd['ID'] == i_d].iloc[0]
                            upd = {'Status Financeiro': 'FATURADO', 'chk_financeiro_banco': 'TRUE'}
                            if pd.isna(curr.get('Data Faturamento')): upd['Data Faturamento'] = date.today()
                            utils_chamados.atualizar_chamado_db(i_d, upd)
                            c_banco += 1
                    st.info(f"✅ {c_banco} chamados marcados como Faturado/Pago.")
                    st.cache_data.clear(); time.sleep(1.5); st.rerun()
                else: st.error(msg)
            except Exception as e: st.error(f"Erro: {e}")

# --- FILTROS E TABELA ---
col_f1, col_f2, col_f3 = st.columns([2, 2, 4])
with col_f1:
    filtro_status_fin = st.multiselect("Filtrar KPI", options=df_chamados_raw['Status_Fin'].unique(), default=df_chamados_raw['Status_Fin'].unique(), on_change=lambda: st.session_state.update(pag_fin_atual=0))
with col_f2:
    filtro_agencia = st.selectbox("Filtrar Agência", options=["Todas"] + sorted(df_chamados_raw['Agencia_Combinada'].unique().tolist()), on_change=lambda: st.session_state.update(pag_fin_atual=0))
with col_f3:
    busca = st.text_input("Busca Rápida", placeholder="Chamado, Protocolo, Valor...")
    if busca: st.session_state.pag_fin_atual = 0

df_view = df_chamados_raw[df_chamados_raw['Status_Fin'].isin(filtro_status_fin)]
if filtro_agencia != "Todas": df_view = df_view[df_view['Agencia_Combinada'] == filtro_agencia]
if busca:
    t = busca.lower()
    df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower().str.contains(t)).any(axis=1)]

# PAGINAÇÃO
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

st.divider()
nav_controls("top")

df_pagina = df_view[df_view['Agencia_Combinada'].isin(agencias_da_pagina)]
agencias_view = df_pagina.groupby('Agencia_Combinada')

for nome_agencia, df_ag in agencias_view:
    total_ag = df_ag['Valor_Calculado'].sum()
    st.markdown(f"**🏦 {nome_agencia}** <span style='color:green; font-size:0.9em;'>(Total: R$ {total_ag:,.2f})</span>", unsafe_allow_html=True)
    
    for _, row in df_ag.iterrows():
        chamado = row['Nº Chamado']
        status_fin = row['Status_Fin']; cor_fin = row['Cor_Fin']; valor = row['Valor_Calculado']
        st.markdown(f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 10px; margin-bottom: 5px; background-color: white;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="flex: 1;"><strong>🆔 {chamado}</strong></div>
                <div style="flex: 1; text-align: center; font-size: 0.9em; color: #555;">📅 {pd.to_datetime(row['Abertura']).strftime('%d/%m/%Y') if pd.notna(row['Abertura']) else '-'}</div>
                <div style="flex: 1; text-align: right;">
                     <span style="background-color: {cor_fin}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: bold;">{status_fin}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.expander(f"➕ R$ {valor:,.2f} | Detalhes"):
            st.write(f"Serviço: {row.get('Serviço')} | Equipamento: {row.get('Equipamento')} (Qtd: {row.get('Qtd.', 0)})")

if total_paginas > 1:
    st.divider()
    nav_controls("bottom")

