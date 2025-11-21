import streamlit as st
import pandas as pd
import utils
import utils_chamados
import utils_financeiro # Importante para ler Books e Liberação
from datetime import date, datetime
import re 
import html 
import io
import math 
import time

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() 
except:
    pass 

# --- LISTA DE EXCEÇÃO (SERVIÇOS) ---
SERVICOS_SEM_EQUIPAMENTO = [
    "vistoria", "adequação de gerador (recall)",
    "desinstalação e descarte de porta giratoria - item para desmontagem e recolhimento para descarte ecológico incluindo transporte",
    "desinstalação total",
    "modernização central de alarme honeywell para commbox até 12 sensores",
    "modernização central de alarme honeywell para commbox até 24 sensores",
    "modernização central de alarme honeywell para commbox até 48 sensores",
    "modernização central de alarme honeywell para commbox até 60 sensores",
    "modernização central de alarme honeywell para commbox até 90 sensores",
    "montagem e desmontagem da porta para intervenção", "recolhimento de eqto",
    "visita técnica", "vistoria conjunta"
]

# --- ESTADO DA PAGINAÇÃO ---
if 'pag_agencia_atual' not in st.session_state:
    st.session_state.pag_agencia_atual = 0

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py)."); st.stop()
    
def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce', dayfirst=True) 
        if pd.isna(ts): return None
        return ts.date()
    except: return None

def formatar_agencia_excel(id_agencia, nome_agencia):
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except: id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo): nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan"]: return default
    return str(val)

# --- 1. DIALOGS DE IMPORTAÇÃO ---
@st.dialog("Importar Novos Chamados", width="large")
def run_importer_dialog():
    st.info("Arraste seu **Template Padrão** (.xlsx/.csv). Colunas: `CHAMADO`, `N° AGENCIA`.")
    uploaded_files = st.file_uploader("Arquivos", type=["xlsx", "xls", "csv"], key="chamado_up", accept_multiple_files=True)
    if uploaded_files:
        dfs = []
        for f in uploaded_files:
            try:
                if f.name.endswith('.csv'): df = pd.read_csv(f, sep=';', dtype=str)
                else: df = pd.read_excel(f, dtype=str)
                df.dropna(how='all', inplace=True); dfs.append(df)
            except Exception as e: st.error(f"Erro em {f.name}: {e}")
        
        if dfs:
            df_raw = pd.concat(dfs, ignore_index=True)
            st.dataframe(df_raw.head(), use_container_width=True)
            if st.button("▶️ Iniciar Importação"):
                with st.spinner("Importando..."):
                    suc, num = utils_chamados.bulk_insert_chamados_db(df_raw)
                    if suc: st.success(f"🎉 {num} importados!"); st.cache_data.clear(); st.session_state.imp_done = True
                    else: st.error("Falha na importação.")
    if st.session_state.get("imp_done"): st.session_state.imp_done = False; st.rerun()

@st.dialog("🔗 Importar Links", width="medium")
def run_link_importer_dialog():
    st.info("Colunas: **CHAMADO** e **LINK**.")
    upl = st.file_uploader("Arquivo de Links", type=["xlsx", "csv"], key="link_up")
    if upl:
        try:
            df = pd.read_csv(upl, sep=';', dtype=str) if upl.name.endswith('.csv') else pd.read_excel(upl, dtype=str)
            df.columns = [str(c).strip().upper() for c in df.columns]
            if 'CHAMADO' in df.columns and 'LINK' in df.columns:
                if st.button("🚀 Atualizar"):
                    with st.spinner("..."):
                        df_bd = utils_chamados.carregar_chamados_db()
                        id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        cnt = 0
                        for _, r in df.iterrows():
                            if r['CHAMADO'] in id_map and pd.notna(r['LINK']):
                                utils_chamados.atualizar_chamado_db(id_map[r['CHAMADO']], {'Link Externo': r['LINK']})
                                cnt += 1
                        st.success(f"✅ {cnt} links atualizados!"); st.cache_data.clear(); st.session_state.imp_done = True
            else: st.error("Colunas incorretas.")
        except Exception as e: st.error(f"Erro: {e}")
    if st.session_state.get("imp_done"): st.session_state.imp_done = False; st.rerun()

@st.dialog("⬇️ Exportar", width="small")
def run_exporter_dialog(df):
    cols = ['ID', 'Abertura', 'Nº Chamado', 'Cód. Agência', 'Nome Agência', 'UF', 'Projeto', 'Agendamento', 'Sistema', 'Serviço', 'Equipamento', 'Qtd.', 'Gestor', 'Fechamento', 'Status', 'Analista', 'Técnico', 'Link Externo', 'Nº Protocolo', 'Sub-Status', 'Agencia_Combinada']
    valid_cols = [c for c in cols if c in df.columns]
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df[valid_cols].to_excel(writer, index=False)
    st.download_button("📥 Baixar Excel", buffer.getvalue(), "dados.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- O CÉREBRO DA OPERAÇÃO (NOVA LÓGICA HIERÁRQUICA) ---
def calcular_status_logico(row, set_books_sim, set_books_todos, set_liberados):
    """
    Define o status e a ação com base na hierarquia estrita.
    Retorna: (Novo Status, Nova Ação/Sub-Status)
    """
    chamado_id = str(row['Nº Chamado'])
    status_atual = str(row.get('Status', '')).strip()
    
    # 1. SUPREMO: Está pago (Liberação Banco)?
    if chamado_id in set_liberados:
        return "Finalizado", "Faturado"

    # 2. MANUAL: Se o usuário definiu um status "travado", respeitamos.
    # (Exceto se já tivermos passado pelo passo 1, que ganha de tudo)
    status_travados = ["Cancelado", "Pausado", "Pendência de Infra", "Pendência de Equipamento"]
    # Normaliza para comparar
    if any(s.lower() == status_atual.lower() for s in status_travados):
        sub_atual = str(row.get('Sub-Status', ''))
        return status_atual, sub_atual # Mantém o que o usuário pôs

    # 3. BOOK: Verifica nas planilhas de Book
    if chamado_id in set_books_todos:
        # Se está no book e tem "SIM"/"S"
        if chamado_id in set_books_sim:
            return "Concluído", "Aguardando Faturamento"
        else:
            return "Concluído", "Enviar Book"

    # 4. OPERACIONAL
    tecnico = str(row.get('Técnico', ''))
    link = str(row.get('Link Externo', ''))
    
    # Tem técnico?
    if tecnico and tecnico.lower() not in ['nan', 'none', '', 'n/a']:
        return "Em Andamento", "Enviar Status Cliente"
    
    # Tem link?
    if link and link.lower() not in ['nan', 'none', '', 'n/a']:
        return "Em Andamento", "Acionar técnico"

    # 5. DEFAULT
    return "Não Iniciado", "Abrir chamado no Btime"

def aplicar_inteligencia_em_lote(df_alvo):
    """Aplica a lógica acima para uma lista de chamados e salva no banco se mudar."""
    
    # Carrega dados financeiros para consulta rápida
    df_books = utils_financeiro.carregar_books_db()
    df_lib = utils_financeiro.carregar_liberacao_db()
    
    # Cria Sets para performance (O(1) lookup)
    set_books_todos = set(df_books['chamado'].astype(str))
    set_books_sim = set(df_books[df_books['book_pronto'].astype(str).str.upper().isin(['SIM', 'S'])]['chamado'].astype(str))
    set_liberados = set(df_lib['chamado'].astype(str)) if not df_lib.empty else set()
    
    count_updates = 0
    
    for _, row in df_alvo.iterrows():
        novo_status, novo_sub = calcular_status_logico(row, set_books_sim, set_books_todos, set_liberados)
        
        status_atual = str(row.get('Status', ''))
        sub_atual = str(row.get('Sub-Status', ''))
        
        # Só atualiza o banco se algo mudou (evita escritas desnecessárias)
        if novo_status != status_atual or novo_sub != sub_atual:
            utils_chamados.atualizar_chamado_db(row['ID'], {
                'Status': novo_status,
                'Sub-Status': novo_sub
            })
            count_updates += 1
            
    return count_updates

# --- TELA PRINCIPAL ---
def tela_dados_agencia():
    # CSS
    st.markdown("""
        <style>
            .card-status-badge { background-color: #B0BEC5; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.85em; display: inline-block; width: 100%; text-align: center; }
            .card-action-text { text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 8px; color: var(--primary-dark); background-color: #F0F2F5; padding: 4px; border-radius: 5px; } 
            .project-card [data-testid="stExpander"] { border: 1px solid var(--gray-border); border-radius: var(--std-radius); margin-top: 15px; }
            .project-card [data-testid="stExpander"] > summary { font-weight: 600; font-size: 0.95rem; }
            [data-testid="stExpander"] [data-testid="stForm"] { border: none; box-shadow: none; padding: 0; }
            .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; color: #333; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    
    # Carregar Dados
    utils_chamados.criar_tabela_chamados()
    try:
        with st.spinner("Carregando dados..."):
            df_chamados_raw = utils_chamados.carregar_chamados_db()
    except Exception as e:
        st.warning(f"Reconectando... ({e})"); st.cache_data.clear(); time.sleep(1); st.rerun()

    if df_chamados_raw.empty:
        st.info("Banco vazio."); 
        if st.button("📥 Importar"): run_importer_dialog()
        st.stop()

    # Formatar Agência
    if 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(lambda r: formatar_agencia_excel(r['Cód. Agência'], r['Nome Agência']), axis=1)
    else: st.error("Erro: Colunas de Agência não encontradas."); st.stop()

    # Listas para Filtros
    agencia_list = ["Todos"] + sorted(df_chamados_raw['Agencia_Combinada'].dropna().astype(str).unique())
    analista_list = ["Todos"] + sorted(df_chamados_raw['Analista'].dropna().astype(str).unique())
    projeto_list_filtro = ["Todos"] + sorted(df_chamados_raw['Projeto'].dropna().astype(str).unique())
    status_list = ["Todos"] + sorted(df_chamados_raw['Status'].dropna().astype(str).unique())
    
    # Botões de Ação
    if "show_export_popup" not in st.session_state: st.session_state.show_export_popup = False
    c_spacer, c_btn_imp, c_btn_exp = st.columns([6, 2, 1.5])
    with c_btn_imp:
        c1, c2 = st.columns(2)
        with c1: 
            if st.button("📥 Importar Geral", use_container_width=True): run_importer_dialog()
        with c2:
            if st.button("🔗 Importar Links", use_container_width=True): run_link_importer_dialog()
    with c_btn_exp:
        if st.button("⬇️ Exportar", use_container_width=True): st.session_state.show_export_popup = True

    # Filtros
    with st.expander("🔎 Filtros e Busca Avançada", expanded=True):
        busca_total = st.text_input("🔎 Busca Rápida", placeholder="Chamado, Agência...")
        st.write("")
        f1, f2, f3, f4 = st.columns(4)
        with f1: filtro_agencia = st.selectbox("Agência", options=agencia_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f2: filtro_analista = st.selectbox("Analista", options=analista_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f3: filtro_projeto = st.selectbox("Projeto", options=projeto_list_filtro, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f4: filtro_status = st.selectbox("Status", options=status_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        
    # Aplicação dos Filtros
    df_filtrado = df_chamados_raw.copy()
    if filtro_agencia != "Todos": df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    if filtro_analista != "Todos": df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
    if filtro_projeto != "Todos": df_filtrado = df_filtrado[df_filtrado['Projeto'] == filtro_projeto]
    if filtro_status != "Todos": df_filtrado = df_filtrado[df_filtrado['Status'] == filtro_status]
    if busca_total:
        t = busca_total.lower()
        mask = df_filtrado.astype(str).apply(lambda x: x.str.lower().str.contains(t)).any(axis=1)
        df_filtrado = df_filtrado[mask]

    if st.session_state.show_export_popup: run_exporter_dialog(df_filtrado)

    # Agrupamento
    try:
        df_filtrado['Agendamento_str'] = df_filtrado['Agendamento'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        chave_projeto = ['Projeto', 'Gestor', 'Serviço', 'Agendamento_str']
    except: st.stop()

    # KPIs
    st.markdown("### 📊 Resumo")
    fechados_list = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado', 'finalizado', 'concluído']
    abertos = len(df_filtrado[~df_filtrado['Status'].astype(str).str.lower().isin(fechados_list)])
    fechados = len(df_filtrado) - abertos
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Total na Visão", len(df_filtrado))
    k2.metric("Chamados Abertos", abertos)
    k3.metric("Chamados Finalizados", fechados)
    st.divider()

    # --- PAGINAÇÃO E VISUALIZAÇÃO ---
    st.markdown("#### 📋 Projetos e Chamados")
    
    # Ordenação por Data
    df_abertos_sort = df_filtrado[~df_filtrado['Status'].astype(str).str.lower().isin(fechados_list)].copy()
    df_abertos_sort['Agendamento'] = pd.to_datetime(df_abertos_sort['Agendamento'], errors='coerce')
    min_dates = df_abertos_sort.groupby('Agencia_Combinada')['Agendamento'].min()
    
    agencias_unicas = df_filtrado['Agencia_Combinada'].unique()
    sort_df = pd.DataFrame(index=agencias_unicas); sort_df['MinDate'] = sort_df.index.map(min_dates)
    sort_df = sort_df.sort_values(by='MinDate', ascending=True, na_position='last')
    sorted_list = sort_df.index.tolist()

    ITENS_POR_PAGINA = 10
    total_pags = math.ceil(len(sorted_list) / ITENS_POR_PAGINA)
    if st.session_state.pag_agencia_atual >= total_pags: st.session_state.pag_agencia_atual = 0
    
    inicio = st.session_state.pag_agencia_atual * ITENS_POR_PAGINA
    agencias_pag = sorted_list[inicio : inicio + ITENS_POR_PAGINA]

    # Controles Nav
    c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
    with c2: 
        if st.button("⬅️ Anterior", disabled=(st.session_state.pag_agencia_atual==0)):
            st.session_state.pag_agencia_atual -= 1; st.rerun()
    with c3: st.markdown(f"<div style='text-align:center'>Página {st.session_state.pag_agencia_atual+1} de {max(1, total_pags)}</div>", unsafe_allow_html=True)
    with c4:
        if st.button("Próximo ➡️", disabled=(st.session_state.pag_agencia_atual >= total_pags-1)):
            st.session_state.pag_agencia_atual += 1; st.rerun()
    
    st.divider()

    # Renderização
    df_pag = df_filtrado[df_filtrado['Agencia_Combinada'].isin(agencias_pag)]
    grupos = df_pag.groupby('Agencia_Combinada')
    grupos_dict = dict(list(grupos))

    for ag in agencias_pag:
        df_ag = grupos_dict.get(ag)
        if df_ag is None: continue

        # Logica Card 1
        df_ag_aberta = df_ag[~df_ag['Status'].astype(str).str.lower().isin(fechados_list)]
        hoje = pd.Timestamp.now().normalize()
        datas = pd.to_datetime(df_ag_aberta['Agendamento'], errors='coerce')
        
        tag = "🟦"; txt = "Sem Pendência"; analista = "N/D"
        if not datas.empty:
            min_d = datas.min()
            if pd.isna(min_d): txt = "Data Inválida"
            else:
                txt = f"📅 {min_d.strftime('%d/%m')}"
                if min_d < hoje: tag = "🟥 ATRASADO"; txt = f"Urgente: {min_d.strftime('%d/%m')}"
                elif min_d == hoje: tag = "🟧 HOJE"
                
                anas = df_ag_aberta[df_ag_aberta['Agendamento'] == min_d]['Analista'].unique()
                analista = anas[0] if len(anas) == 1 else ("Múltiplos" if len(anas) > 1 else "Sem Analista")

        st.markdown('<div class="project-card">', unsafe_allow_html=True)
        with st.container():
            c1, c2, c3, c4 = st.columns([1.5, 3, 2, 2])
            c1.markdown(f"<span style='font-weight:bold; color:{'red' if '🟥' in tag else 'orange' if '🟧' in tag else 'blue'}'>{tag}</span>", unsafe_allow_html=True)
            c2.markdown(f"**{ag}**")
            c3.markdown(txt)
            
            cor_ana = utils_chamados.get_color_for_name(analista)
            c4.markdown(f"<span style='color:{cor_ana}; font-weight:bold'>{analista}</span>", unsafe_allow_html=True)

            with st.expander("Ver Projetos"):
                try: projs = df_ag.groupby(chave_projeto)
                except: continue

                for (proj, gest, serv, dt), df_p in projs:
                    row1 = df_p.iloc[0]
                    ids = df_p['ID'].tolist()
                    
                    st.markdown('<div class="project-card" style="margin-top:5px; border-top:1px solid #eee; padding-top:5px;">', unsafe_allow_html=True)
                    
                    st_p = clean_val(row1.get('Status'), "N/D")
                    sub_p = clean_val(row1.get('Sub-Status'), "")
                    cor_st = utils_chamados.get_status_color(st_p)
                    
                    k1, k2, k3 = st.columns([3, 2, 2])
                    k1.markdown(f"**{clean_val(proj).upper()}**")
                    k2.markdown(f"📅 {dt}")
                    k3.markdown(f"<span style='background:{cor_st}; color:white; padding:2px 8px; border-radius:10px; font-size:0.8em'>{st_p.upper()}</span>", unsafe_allow_html=True)
                    
                    k4, k5, k6 = st.columns([3, 2, 2])
                    k4.markdown(f"Serviço: {clean_val(serv)}")
                    k5.markdown(f"Gestor: {clean_val(gest)}")
                    if sub_p: k6.markdown(f"<span style='color:blue; font-weight:bold'>Ação: {sub_p}</span>", unsafe_allow_html=True)
                    
                    # FORMULÁRIO DE EDIÇÃO
                    with st.expander(f"Editar {len(ids)} chamados"):
                        key = f"form_{row1['ID']}"
                        with st.form(key):
                            st.write("Edição em Lote")
                            ec1, ec2 = st.columns(2)
                            # Opções Manuais
                            opts_manuais = ["(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
                            
                            idx_st = 0
                            if st_p in opts_manuais: idx_st = opts_manuais.index(st_p)
                            
                            novo_st = ec1.selectbox("Status (Manual)", opts_manuais, index=idx_st)
                            novo_prazo = ec2.text_input("Prazo", value=clean_val(row1.get('Prazo'), ""))
                            
                            if st.form_submit_button("💾 Salvar"):
                                updates = {'Prazo': novo_prazo}
                                recalcular = False
                                
                                if novo_st != "(Status Automático)":
                                    updates['Status'] = novo_st
                                    updates['Sub-Status'] = None # Limpa sub-status ao forçar manual
                                    recalcular = False # NÃO RECALCULA
                                else:
                                    recalcular = True # Se voltar para auto, recalcula
                                
                                for i in ids: utils_chamados.atualizar_chamado_db(i, updates)
                                
                                st.success("Salvo!")
                                st.cache_data.clear()
                                time.sleep(0.5)
                                
                                # O pulo do gato: Só chama o cérebro se estiver no modo Automático
                                if recalcular:
                                    df_bd = utils_chamados.carregar_chamados_db()
                                    df_p_novo = df_bd[df_bd['ID'].isin(ids)]
                                    aplicar_inteligencia_em_lote(df_p_novo)
                                    st.cache_data.clear()
                                
                                st.rerun()
                        
                        # DETALHES INDIVIDUAIS
                        st.markdown("---")
                        sistemas = df_p.groupby('Sistema')
                        for sis, df_s in sistemas:
                            st.caption(f"Sistema: {clean_val(sis)}")
                            for _, r in df_s.iterrows():
                                with st.expander(f"{r['Nº Chamado']} - {r['Equipamento']}"):
                                    # Link e Botão Juntos
                                    lk = r.get('Link Externo')
                                    c_l1, c_l2 = st.columns([3, 1])
                                    new_lk = c_l1.text_input("Link", value=lk if pd.notna(lk) else "", key=f"lk_{r['ID']}")
                                    if pd.notna(lk) and str(lk).strip():
                                        c_l2.markdown("<br>", unsafe_allow_html=True)
                                        c_l2.link_button("Acessar", lk)
                                    
                                    if st.button("Salvar Link", key=f"btn_{r['ID']}"):
                                        utils_chamados.atualizar_chamado_db(r['ID'], {'Link Externo': new_lk})
                                        st.success("Link Salvo!")
                                        st.cache_data.clear(); time.sleep(0.5)
                                        
                                        # Recalcular inteligência (pois link afeta status)
                                        df_bd = utils_chamados.carregar_chamados_db()
                                        # Apenas 1 linha para recalcular
                                        aplicar_inteligencia_em_lote(df_bd[df_bd['ID'] == r['ID']])
                                        st.cache_data.clear(); st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

tela_dados_agencia()
