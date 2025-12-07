import streamlit as st
import pandas as pd
import utils_chamados
import utils # Para carregar listas de configuração
import plotly.express as px
from datetime import date, timedelta, datetime
import time

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS E ESTILOS ---
st.markdown("""
    <style>
        .metric-card { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 10px; }
        .card-status-badge { background-color: #B0BEC5; color: white !important; padding: 6px 12px; border-radius: 8px; font-weight: bold; font-size: 0.85em; display: flex; justify-content: center; align-items: center; width: 100%; text-transform: uppercase; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .status-mini-card { background-color: white; border: 1px solid #eee; border-radius: 8px; padding: 10px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; }
    </style>
""", unsafe_allow_html=True)

# --- CONSTANTES ---
SERVICOS_SEM_EQUIPAMENTO = [
   "vistoria", "adequação de gerador (recall)", "desinstalação total", "recolhimento de eqto",
    "visita técnica", "vistoria conjunta",
   "desinstalação e descarte de porta giratoria", "modernização central de alarme",
   "montagem e desmontagem da porta para intervenção"
]

def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce', dayfirst=True)
        if pd.isna(ts): return None
        return ts.date()
    except: return None

def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan", ""]: return default
    return str(val)

# --- LÓGICA INTELIGENTE DE STATUS (NOVA) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    
    # Pega a primeira linha para analisar o contexto do grupo
    row = df_projeto.iloc[0]
    
    status_atual = str(row.get('Status', 'Não Iniciado')).strip()
    status_manual_list = ["Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
    
    # 1. Se estiver em um status "Manual/Bloqueante", apenas limpa o sub-status e retorna
    if status_atual in status_manual_list:
        sub_status_atual_val = row.get('Sub-Status')
        sub_status_atual = "" if pd.isna(sub_status_atual_val) else str(sub_status_atual_val).strip()
        
        if sub_status_atual != "":
            updates = {"Sub-Status": None}
            for chamado_id in ids_para_atualizar:
                utils_chamados.atualizar_chamado_db(chamado_id, updates)
            return True 
        return False 
    
    # 2. Verifica tipo de chamado (-S-erviço ou -E-quipamento)
    n_chamado = str(row.get('Nº Chamado', ''))
    has_S = '-S-' in n_chamado or '-s-' in n_chamado
    has_E = '-E-' in n_chamado or '-e-' in n_chamado
    
    # Funções auxiliares de verificação
    def check_col_present(df, col_name):
        if col_name in df.columns:
            return df[col_name].fillna('').astype(str).str.strip().ne('').any()
        return False

    def check_date_present(df, col_name):
        if col_name in df.columns:
            return df[col_name].notna().any()
        return False
    
    # Verifica preenchimento das colunas Chave
    link_presente = check_col_present(df_projeto, 'Link Externo')
    protocolo_presente = check_col_present(df_projeto, 'Nº Protocolo')
    pedido_presente = check_col_present(df_projeto, 'Nº Pedido')
    envio_presente = check_date_present(df_projeto, 'Data Envio')
    tecnico_presente = check_col_present(df_projeto, 'Técnico')
    
    novo_status = "Não Iniciado"
    novo_sub_status = ""

    # --- Cenário 1: Só Serviço (S-Only) ---
    if has_S and not has_E:
        if protocolo_presente:
            novo_status = "Concluído"
            novo_sub_status = "Enviar Book"
        elif tecnico_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Enviar Status Cliente"
        elif link_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Acionar técnico"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Pendente Link"

    # --- Cenário 2: Misto (S e E) ---
    elif has_S and has_E:
        if protocolo_presente:
            novo_status = "Concluído"
            novo_sub_status = "Enviar Book"
        elif tecnico_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Enviar Status Cliente"
        elif envio_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Equipamento entregue - Acionar técnico"
        elif pedido_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Equipamento Solicitado"
        elif link_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Solicitar Equipamento"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Pendente Link"

    # --- Cenário 3: Só Equipamento (E-Only) ---
    elif not has_S and has_E:
        if envio_presente:
            novo_status = "Concluído"
            novo_sub_status = "Equipamento entregue"
        elif pedido_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Equipamento Solicitado"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Solicitar Equipamento"
    
    else: 
        # Caso genérico ou sem padrão definido
        novo_status = "Não Iniciado"
        novo_sub_status = "Verificar Chamados"

    # Verifica se precisa atualizar
    sub_status_atual_val = row.get('Sub-Status')
    sub_status_atual = "" if pd.isna(sub_status_atual_val) else str(sub_status_atual_val).strip()
    
    if status_atual != novo_status or sub_status_atual != novo_sub_status:
        st.toast(f"🔄 Status atualizado: '{status_atual}' -> '{novo_status}'", icon="🤖")
        updates = {"Status": novo_status, "Sub-Status": novo_sub_status}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

# --- FUNÇÕES DE IMPORTAÇÃO ---
@st.dialog("Importar Chamados (Mapeamento Fixo)", width="large")
def run_importer_dialog():
    st.info("Importação via Mapeamento de Colunas (Posição Fixa).")
    uploaded_files = st.file_uploader("Selecione arquivos (.xlsx ou .csv)", type=["xlsx", "csv"], accept_multiple_files=True, key="up_imp_blindado")

    if uploaded_files:
        dfs_list = []
        for uploaded_file in uploaded_files:
            try:
                if uploaded_file.name.endswith('.csv'):
                    try:
                        df = pd.read_csv(uploaded_file, sep=';', header=0, dtype=str, encoding='utf-8-sig')
                        if len(df.columns) < 5: 
                            uploaded_file.seek(0)
                            df = pd.read_csv(uploaded_file, sep=',', header=0, dtype=str, encoding='utf-8-sig')
                    except:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=None, engine='python', header=0, dtype=str)
                else:
                    df = pd.read_excel(uploaded_file, header=0, dtype=str)
                df.dropna(how='all', inplace=True)
                dfs_list.append(df)
            except Exception as e:
                st.error(f"Erro ao ler '{uploaded_file.name}': {e}")
                return

        if dfs_list:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
                if len(df_raw.columns) < 12:
                    st.error("Arquivo com colunas insuficientes.")
                    return

                dados_mapeados = {
                    'Nº Chamado': df_raw.iloc[:, 0], 'Cód. Agência': df_raw.iloc[:, 1], 'Nome Agência': df_raw.iloc[:, 2],
                    'agencia_uf': df_raw.iloc[:, 3], 'Analista': df_raw.iloc[:, 22] if len(df_raw.columns) > 22 else "",
                    'Gestor': df_raw.iloc[:, 20] if len(df_raw.columns) > 20 else "", 'Serviço': df_raw.iloc[:, 4],
                    'Projeto': df_raw.iloc[:, 5], 'Agendamento': df_raw.iloc[:, 6], 'Sistema': df_raw.iloc[:, 8],
                    'Cod_equipamento': df_raw.iloc[:, 9], 'Nome_equipamento': df_raw.iloc[:, 10], 'Qtd': df_raw.iloc[:, 11]
                }
                df_final = pd.DataFrame(dados_mapeados).fillna("")

                def formatar_item(row):
                    qtd = str(row['Qtd']).strip()
                    desc = str(row['Nome_equipamento']).strip()
                    if not desc: desc = str(row['Sistema']).strip()
                    if not desc: return ""
                    if qtd and qtd not in ["0", "nan", "", "None"]: return f"{qtd}x {desc}"
                    return desc

                df_final['Item_Formatado'] = df_final.apply(formatar_item, axis=1)

                def juntar_textos(lista):
                    limpos = [str(x) for x in lista if str(x).strip() not in ["", "nan", "None"]]
                    return " | ".join(dict.fromkeys(limpos))

                colunas_ignoradas_agg = ['Sistema', 'Qtd', 'Item_Formatado', 'Nome_equipamento', 'Cod_equipamento']
                regras = {c: 'first' for c in df_final.columns if c not in colunas_ignoradas_agg}
                regras['Item_Formatado'] = juntar_textos
                df_grouped = df_final.groupby('Nº Chamado', as_index=False).agg(regras)
                df_grouped = df_grouped.rename(columns={'Item_Formatado': 'Sistema'})
                
                df_banco = utils_chamados.carregar_chamados_db()
                lista_novos = []; lista_atualizar = []
                
                if not df_banco.empty:
                    mapa_ids = dict(zip(df_banco['Nº Chamado'].astype(str).str.strip(), df_banco['ID']))
                    for row in df_grouped.to_dict('records'):
                        chamado_num = str(row['Nº Chamado']).strip()
                        if not chamado_num or chamado_num.lower() == 'nan': continue
                        if chamado_num in mapa_ids:
                            row['ID_Banco'] = mapa_ids[chamado_num]
                            lista_atualizar.append(row)
                        else: lista_novos.append(row)
                else: lista_novos = [r for r in df_grouped.to_dict('records') if str(r['Nº Chamado']).strip()]

                df_insert = pd.DataFrame(lista_novos)
                df_update = pd.DataFrame(lista_atualizar)

                c1, c2 = st.columns(2)
                c1.metric("🆕 Criar Novos", len(df_insert))
                c2.metric("🔄 Atualizar Existentes", len(df_update))
                
                with st.expander("🔍 Ver Prévia"): st.dataframe(df_grouped.head())

                if st.button("🚀 Processar Importação"):
                    bar = st.progress(0); status_txt = st.empty()
                    if not df_insert.empty:
                        status_txt.text("Inserindo novos...")
                        utils_chamados.bulk_insert_chamados_db(df_insert)
                        bar.progress(50)
                    if not df_update.empty:
                        status_txt.text("Atualizando dados...")
                        total = len(df_update)
                        for i, row in enumerate(df_update.to_dict('records')):
                            updates = {
                                'Sistema': row['Sistema'], 'Serviço': row['Serviço'], 'Projeto': row['Projeto'],
                                'Agendamento': row['Agendamento'], 'Analista': row['Analista'], 'Gestor': row['Gestor']
                            }
                            utils_chamados.atualizar_chamado_db(row['ID_Banco'], updates)
                            if total > 0: bar.progress(50 + int((i/total)*50))
                    bar.progress(100); status_txt.text("Concluído!")
                    st.success("Importação finalizada!"); time.sleep(1.5)
                    st.cache_data.clear(); st.rerun()

            except Exception as e: st.error(f"Erro no processamento: {e}")

@st.dialog("🔗 Importar Links", width="medium")
def run_link_importer_dialog():
    st.info("Planilha simples com colunas: **CHAMADO** e **LINK**.")
    up = st.file_uploader("Arquivo", type=["xlsx", "csv"], key="up_imp_link")
    if up and st.button("🚀 Atualizar Links"):
        try:
            if up.name.endswith('.csv'): df = pd.read_csv(up, sep=';', dtype=str)
            else: df = pd.read_excel(up, dtype=str)
            
            df.columns = [str(c).upper().strip() for c in df.columns]
            if 'CHAMADO' not in df.columns or 'LINK' not in df.columns:
                st.error("Colunas 'CHAMADO' e 'LINK' obrigatórias.")
            else:
                with st.spinner("Atualizando..."):
                   df_bd = utils_chamados.carregar_chamados_db()
                   id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                   cnt = 0
                   for _, row in df.iterrows():
                       chamado = str(row['CHAMADO'])
                       link = str(row['LINK'])
                       if chamado in id_map and pd.notna(link) and link.strip():
                           utils_chamados.atualizar_chamado_db(id_map[chamado], {'Link Externo': link})
                           cnt += 1
                   st.success(f"✅ {cnt} links atualizados!"); st.cache_data.clear(); time.sleep(1.5); st.rerun()
        except Exception as e: st.error(f"Erro: {e}")

# --- 5. CARREGAMENTO E SIDEBAR ---
df = utils_chamados.carregar_chamados_db()

with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"): run_importer_dialog()
    if st.button("🔗 Importar Links"): run_link_importer_dialog()
    
    st.divider()
    st.header("Filtros de Gestão")
    lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    lista_gestores = ["Todos"] + sorted(df['Gestor'].dropna().unique().tolist())
    filtro_analista = st.selectbox("Analista", lista_analistas)
    filtro_gestor = st.selectbox("Gestor", lista_gestores)

if df.empty:
    st.warning("Sem dados. Importe chamados na barra lateral.")
    st.stop()

df_filtrado = df.copy()
if filtro_analista != "Todos": df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
if filtro_gestor != "Todos": df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]

if "nav_radio" not in st.session_state: st.session_state["nav_radio"] = "Visão Geral (Cockpit)"
escolha_visao = st.radio("Modo de Visualização:", ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], horizontal=True, key="nav_radio")

if escolha_visao == "Visão Geral (Cockpit)":
    st.title("📌 Cockpit de Projetos")
    hoje = pd.Timestamp.today().normalize()
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    
    pendentes = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim)]
    atrasados = pendentes[pendentes['Agendamento'] < hoje]
    prox = pendentes[(pendentes['Agendamento'] >= hoje) & (pendentes['Agendamento'] <= hoje + timedelta(days=5))]
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Chamados", len(df_filtrado))
    k2.metric("🚨 Atrasados", len(atrasados))
    k3.metric("📅 Vencendo (5 dias)", len(prox))
    st.divider()
    
    lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
    cols = st.columns(3)
    for i, proj in enumerate(lista_projetos):
        df_p = df_filtrado[df_filtrado['Projeto'] == proj]
        total_p = len(df_p)
        concluidos = len(df_p[df_p['Status'].str.lower().isin(status_fim)])
        atrasados_p = len(df_p[(~df_p['Status'].str.lower().isin(status_fim)) & (df_p['Agendamento'] < hoje)])
        perc = int((concluidos / total_p) * 100) if total_p > 0 else 0
        
        with cols[i % 3]:
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="margin-bottom:0px;">{proj}</h4>
                <p style="color:#666; font-size:0.9em;"><strong>{concluidos}/{total_p}</strong> prontos ({perc}%)</p>
                <progress value="{perc}" max="100" style="width:100%; height:10px;"></progress>
                <div style="margin-top:10px;">
                    {'<div style="color:red; font-weight:bold;">⚠️ '+str(atrasados_p)+' Atrasados</div>' if atrasados_p > 0 else '<div style="color:green;">✅ Em dia</div>'}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"🔎 Ver Lista", key=f"btn_{i}"):
                st.session_state["sel_projeto"] = proj
                st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"
                st.rerun()

else:
    # --- MODO OPERACIONAL ---
    with st.container(border=True):
        st.markdown("### 🔍 Filtros Detalhados")
        c_busca, c_proj, c_status, c_data = st.columns([1.5, 2, 1.5, 1])
        
        with c_busca:
            busca_geral = st.text_input("Buscador Geral", placeholder="Pesquisar...", label_visibility="collapsed")
            st.caption("Texto: ID, Nome, Serviço...")

        with c_proj:
            try:
                df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                opcoes_projeto_db = df_proj_cfg.iloc[:, 0].tolist() if not df_proj_cfg.empty else []
            except: opcoes_projeto_db = []
            if not opcoes_projeto_db: opcoes_projeto_db = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
            
            padrao_projetos = []
            if "sel_projeto" in st.session_state:
                proj_selecionado = st.session_state["sel_projeto"]
                if proj_selecionado in opcoes_projeto_db: padrao_projetos = [proj_selecionado]
                st.session_state.pop("sel_projeto", None)
            
            filtro_projeto_multi = st.multiselect("Projetos", options=opcoes_projeto_db, default=padrao_projetos, placeholder="Selecione", label_visibility="collapsed")
            st.caption("Filtrar por Projeto")

        with c_status:
            opcoes_status = sorted(df_filtrado['Status'].dropna().unique().tolist())
            filtro_status_multi = st.multiselect("Status", options=opcoes_status, default=[], placeholder="Selecione", label_visibility="collapsed")
            st.caption("Filtrar por Status")

        with c_data:
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            d_min = df_filtrado['Agendamento'].min()
            d_max = df_filtrado['Agendamento'].max()
            if pd.isna(d_min): d_min = date.today()
            if pd.isna(d_max): d_max = date.today()
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")
            st.caption("Período")

    df_view = df_filtrado.copy()
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)]
    if filtro_projeto_multi: df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
    if filtro_status_multi: df_view = df_view[df_view['Status'].isin(filtro_status_multi)]
    if len(filtro_data_range) == 2:
        d_inicio, d_fim = filtro_data_range
        df_view = df_view[(df_view['Agendamento'] >= pd.to_datetime(d_inicio)) & (df_view['Agendamento'] <= pd.to_datetime(d_fim))]

    st.markdown("<br>", unsafe_allow_html=True)
    status_conclusao = ['concluído', 'finalizado', 'faturado', 'fechado']
    
    if not df_view.empty:
        gr_proj = df_view.groupby('Projeto')
        kpi_proj_total = gr_proj.ngroups
        proj_fin = sum(1 for _, d in gr_proj if d['Status'].str.lower().isin(status_conclusao).all())
        kpi_proj_abertos = kpi_proj_total - proj_fin
    else: kpi_proj_total = 0; kpi_proj_abertos = 0; proj_fin = 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Chamados (Filtro)", len(df_view), border=True)
    k2.metric("Projetos Abertos", kpi_proj_abertos, border=True)
    k3.metric("Projetos Finalizados", proj_fin, border=True)
    k4.metric("Tarefas Concluídas", len(df_view[df_view['Status'].str.lower().isin(status_conclusao)]), border=True)
    
    st.divider()
    if not df_view.empty:
        counts = df_view['Status'].value_counts()
        cols_status = st.columns(6)
        idx_col = 0
        for status, count in counts.items():
            try: cor = utils_chamados.get_status_color(status)
            except: cor = "#90A4AE"
            with cols_status[idx_col % 6]:
                st.markdown(f"""<div style="border-left: 4px solid {cor}; background-color: white; padding: 5px 10px; border-radius: 4px; border: 1px solid #f0f0f0; margin-bottom: 5px; display: flex; flex-direction: column;"><span style="font-size: 0.75em; color: #777;">{status}</span><span style="font-weight: bold; font-size: 1.1em; color: #333;">{count}</span></div>""", unsafe_allow_html=True)
            idx_col += 1
    
    st.markdown("<br>", unsafe_allow_html=True)
    aba_lista, aba_calendario = st.tabs(["📋 Lista Detalhada", "📅 Agenda Semanal"])

    with aba_lista:    
        if df_view.empty: st.warning("Nenhum chamado encontrado.")
        else:
    # --- MODO OPERACIONAL (VISÃO DETALHADA) ---
    
    # 1. ÁREA DE FILTROS (ORGANIZADA EM EXPANDER)
    with st.container(border=True):
        st.markdown("### 🔍 Filtros Detalhados")
        c_busca, c_proj, c_status, c_data = st.columns([1.5, 2, 1.5, 1])
        
        with c_busca:
            busca_geral = st.text_input("Buscador Geral", placeholder="Pesquisar...", label_visibility="collapsed")
            st.caption("Texto: ID, Nome, Serviço...")

        with c_proj:
            try:
                df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                opcoes_projeto_db = df_proj_cfg.iloc[:, 0].tolist() if not df_proj_cfg.empty else []
            except: opcoes_projeto_db = []
            
            if not opcoes_projeto_db:
                opcoes_projeto_db = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
            
            padrao_projetos = []
            if "sel_projeto" in st.session_state:
                proj_selecionado = st.session_state["sel_projeto"]
                if proj_selecionado in opcoes_projeto_db:
                    padrao_projetos = [proj_selecionado]
                st.session_state.pop("sel_projeto", None)
            
            filtro_projeto_multi = st.multiselect("Projetos", options=opcoes_projeto_db, default=padrao_projetos, placeholder="Selecione Projetos", label_visibility="collapsed")
            st.caption("Filtrar por Projeto")

        with c_status:
            opcoes_status = sorted(df_filtrado['Status'].dropna().unique().tolist())
            filtro_status_multi = st.multiselect("Status", options=opcoes_status, default=[], placeholder="Selecione Status", label_visibility="collapsed")
            st.caption("Filtrar por Status")

        with c_data:
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            d_min = df_filtrado['Agendamento'].min()
            d_max = df_filtrado['Agendamento'].max()
            if pd.isna(d_min): d_min = date.today()
            if pd.isna(d_max): d_max = date.today()
            
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")
            st.caption("Período")

    # --- MOTOR DE FILTRAGEM ---
    df_view = df_filtrado.copy()
    
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[
            df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)
        ]
    if filtro_projeto_multi: df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
    if filtro_status_multi: df_view = df_view[df_view['Status'].isin(filtro_status_multi)]
    if len(filtro_data_range) == 2:
        d_inicio, d_fim = filtro_data_range
        df_view = df_view[(df_view['Agendamento'] >= pd.to_datetime(d_inicio)) & (df_view['Agendamento'] <= pd.to_datetime(d_fim))]

    st.markdown("<br>", unsafe_allow_html=True) 

    # 2. PAINEL DE KPIs
    status_conclusao = ['concluído', 'finalizado', 'faturado', 'fechado']
    kpi_qtd_chamados = len(df_view)
    kpi_chamados_fin = len(df_view[df_view['Status'].str.lower().isin(status_conclusao)])
    
    if not df_view.empty:
        gr_proj = df_view.groupby('Projeto')
        kpi_proj_total_view = gr_proj.ngroups
        proj_fin_count = 0
        for nome, dados in gr_proj:
            if dados['Status'].str.lower().isin(status_conclusao).all():
                proj_fin_count += 1
        kpi_proj_abertos = kpi_proj_total_view - proj_fin_count
    else:
        kpi_proj_total_view = 0; kpi_proj_abertos = 0; proj_fin_count = 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Chamados (Filtro)", kpi_qtd_chamados, border=True)
    k2.metric("Projetos Abertos", kpi_proj_abertos, border=True)
    k3.metric("Projetos Finalizados", proj_fin_count, border=True)
    k4.metric("Tarefas Concluídas", kpi_chamados_fin, border=True)
    
    st.divider()

    # 3. RESUMO POR STATUS (HORIZONTAL)
    if not df_view.empty:
        counts = df_view['Status'].value_counts()
        cols_status = st.columns(6) 
        idx_col = 0
        for status, count in counts.items():
            try: cor = utils_chamados.get_status_color(status)
            except: cor = "#90A4AE"
            with cols_status[idx_col % 6]:
                st.markdown(f"""
                <div style="border-left: 4px solid {cor}; background-color: white; padding: 5px 10px; border-radius: 4px; border: 1px solid #f0f0f0; margin-bottom: 5px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); display: flex; flex-direction: column; align-items: flex-start;">
                    <span style="font-size: 0.75em; color: #777; text-transform: uppercase;">{status}</span>
                    <span style="font-weight: bold; font-size: 1.1em; color: #333;">{count}</span>
                </div>""", unsafe_allow_html=True)
            idx_col += 1
    else:
        st.info("Sem dados para exibir resumo de status.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 4. ABAS DE CONTEÚDO ---
    aba_lista, aba_calendario = st.tabs(["📋 Lista Detalhada", "📅 Agenda Semanal"])

    # --- ABA 1: LISTA DETALHADA COM PAGINAÇÃO ---
    with aba_lista:    
        if df_view.empty:
            st.warning("Nenhum chamado encontrado.")
        else:
            df_view['Agendamento_str'] = pd.to_datetime(df_view['Agendamento']).dt.strftime('%d/%m/%Y').fillna("Sem Data")
            
            # Agrupamento
            chave_agrupamento = ['Projeto', 'Nome Agência', 'Serviço', 'Agendamento_str']
            grupos = df_view.groupby(chave_agrupamento)
            grupos_lista = list(grupos)
            
            # --- PAGINAÇÃO (LIMITADOR DE 20) ---
            ITENS_POR_PAGINA = 20
            total_itens = len(grupos_lista)
            total_paginas = math.ceil(total_itens / ITENS_POR_PAGINA)
            
            # Controle de Página (Topo)
            col_pag_info, col_pag_input = st.columns([4, 1])
            with col_pag_info:
                st.caption(f"Mostrando {total_itens} registros agrupados (Página {st.session_state.get('pag_atual_proj', 1)} de {total_paginas})")
            
            if total_paginas > 1:
                with col_pag_input:
                    pagina = st.number_input("Página", min_value=1, max_value=total_paginas, value=1, key="pag_input_proj")
                    st.session_state['pag_atual_proj'] = pagina
            else:
                pagina = 1

            # Slice da lista
            inicio = (pagina - 1) * ITENS_POR_PAGINA
            fim = inicio + ITENS_POR_PAGINA
            grupos_pagina = grupos_lista[inicio:fim]
            
            # --- LOOP DE CARDS (AGORA PAGINADO) ---
            for (proj_nome, nome_agencia, nome_servico, data_str), df_grupo in grupos_pagina:
                first_row = df_grupo.iloc[0]
                ids_chamados = df_grupo['ID'].tolist()
                
                # Tratamento de dados para exibição
                status_atual = clean_val(first_row.get('Status'), "Não Iniciado")
                acao_atual = clean_val(first_row.get('Sub-Status'), "")
                cor_status = utils_chamados.get_status_color(status_atual)
                analista = clean_val(first_row.get('Analista'), "N/D").upper()
                gestor = clean_val(first_row.get('Gestor'), "N/D").upper()
                
                # SLA
                sla_texto = ""; sla_cor = "#333"
                prazo_val = _to_date_safe(first_row.get('Prazo'))
                if prazo_val:
                    hoje_date = date.today()
                    dias_restantes = (prazo_val - hoje_date).days
                    if dias_restantes < 0: 
                        sla_texto = f"⚠️ {abs(dias_restantes)}d atrasado"
                        sla_cor = "#D32F2F"
                    else: 
                        sla_texto = f"🕒 {dias_restantes}d restantes"
                        sla_cor = "#388E3C"
                
                # CARD PRINCIPAL
                with st.container(border=True):
                    # LINHA 1: Projeto | Data | Analista | Status
                    c1, c2, c3, c4 = st.columns([3, 1.2, 1.5, 1.5])
                    with c1: st.markdown(f"**📂 {proj_nome}**")
                    with c2: st.markdown(f"🗓️ {data_str}")
                    with c3: st.markdown(f"👤 {analista}")
                    with c4: st.markdown(f"""<div class="card-status-badge" style="background-color: {cor_status}; margin: 0;">{status_atual}</div>""", unsafe_allow_html=True)

                    # LINHA 2: Serviço | SLA | Gestor | Ação
                    c5, c6, c7, c8 = st.columns([3, 1.2, 1.5, 1.5])
                    with c5: st.markdown(f"<span style='color:#1565C0; font-weight:600;'>{nome_servico}</span>", unsafe_allow_html=True)
                    with c6: st.markdown(f"<span style='color:{sla_cor}; font-size:0.9em; font-weight:bold;'>{sla_texto}</span>", unsafe_allow_html=True) if sla_texto else st.caption("-")
                    with c7: st.caption(f"Gestor: {gestor}")
                    with c8: 
                        if str(acao_atual).lower() == "faturado": st.markdown("✔️ **FATURADO**")
                        elif acao_atual: st.markdown(f"👉 {acao_atual}")
                        else: st.caption("-")

                    # LINHA 3: Agência
                    cod_ag = str(first_row.get('Cód. Agência', '')).split('.')[0]
                    nome_ag = str(nome_agencia).replace(cod_ag, '').strip(' -')
                    st.markdown(f"""<div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #f0f0f0; color: #555; font-size: 0.95em;">🏠 <b>AG {cod_ag}</b> - {nome_ag}<span style="float:right; color:#999; font-size:0.8em;">ID: {ids_chamados[0]}</span></div>""", unsafe_allow_html=True)

                    # EXPANDER DE EDIÇÃO (FORMULÁRIO CORRIGIDO)
                    with st.expander("📝 Editar / Detalhes"):
                        form_key = f"form_{first_row['ID']}"
                        with st.form(key=form_key):
                            # Carregamento de Listas Seguro
                            try:
                                df_status_cfg = utils.carregar_config_db("status"); opts_status_db = [str(x) for x in df_status_cfg.iloc[:, 0].dropna().tolist()] if not df_status_cfg.empty else []
                                df_proj_cfg = utils.carregar_config_db("projetos_nomes"); opts_proj_db = [str(x) for x in df_proj_cfg.iloc[:, 0].dropna().tolist()] if not df_proj_cfg.empty else []
                                df_tec_cfg = utils.carregar_config_db("tecnicos"); opts_tec_db = [str(x) for x in df_tec_cfg.iloc[:, 0].dropna().tolist()] if not df_tec_cfg.empty else []
                                df_users = utils.carregar_usuarios_db(); df_users.columns = [col.capitalize() for col in df_users.columns] if not df_users.empty else []
                                opts_ana_db = [str(x) for x in df_users["Nome"].dropna().tolist()] if not df_users.empty and "Nome" in df_users.columns else []
                            except: opts_status_db=[]; opts_proj_db=[]; opts_tec_db=[]; opts_ana_db=[]

                            def safe_str(val): return str(val) if pd.notna(val) and str(val).lower() not in ['nan', 'none', ''] else ""
                            
                            lista_final_status = sorted(list(set(opts_status_db + [status_atual] + ["(Automático)", "Finalizado", "Cancelado"])))
                            idx_st = lista_final_status.index(status_atual) if status_atual in lista_final_status else 0
                            
                            val_proj = safe_str(first_row.get('Projeto', '')); lista_proj = sorted(list(set(opts_proj_db + [val_proj]))); idx_proj = lista_proj.index(val_proj) if val_proj in lista_proj else 0
                            val_tec = safe_str(first_row.get('Técnico', '')); lista_tec = sorted(list(set(opts_tec_db + [val_tec]))); idx_tec = lista_tec.index(val_tec) if val_tec in lista_tec else 0
                            val_ana = safe_str(first_row.get('Analista', '')); lista_ana = sorted(list(set(opts_ana_db + [val_ana]))); idx_ana = lista_ana.index(val_ana) if val_ana in lista_ana else 0

                            # Definição dos Inputs (Variáveis que o botão salvar usa)
                            c1, c2, c3, c4 = st.columns(4)
                            novo_status = c1.selectbox("Status", lista_final_status, index=idx_st, key=f"st_{form_key}")
                            nova_abertura = c2.date_input("Abertura", value=_to_date_safe(first_row.get('Abertura')) or date.today(), format="DD/MM/YYYY", key=f"ab_{form_key}")
                            novo_agend = c3.date_input("Agendamento", value=_to_date_safe(first_row.get('Agendamento')), format="DD/MM/YYYY", key=f"ag_{form_key}")
                            novo_fim = c4.date_input("Finalização", value=_to_date_safe(first_row.get('Fechamento')), format="DD/MM/YYYY", key=f"fim_{form_key}")

                            c5, c6, c7 = st.columns(3)
                            novo_analista = c5.selectbox("Analista (Usuário)", lista_ana, index=idx_ana, key=f"ana_{form_key}")
                            novo_gestor = c6.text_input("Gestor", value=first_row.get('Gestor', ''), key=f"ges_{form_key}")
                            novo_tec = c7.selectbox("Técnico", lista_tec, index=idx_tec, key=f"tec_{form_key}")

                            c8, c9, c10 = st.columns(3)
                            novo_projeto = c8.selectbox("Projeto", lista_proj, index=idx_proj, key=f"proj_{form_key}")
                            novo_servico = c9.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"serv_{form_key}")
                            novo_sistema = c10.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"sis_{form_key}")

                            nova_obs = st.text_area("Observações", value=first_row.get('Observações e Pendencias', ''), height=100, key=f"obs_{form_key}")
                            
                            c11, c12, c13 = st.columns([1, 2, 1])
                            chamado_num = str(first_row.get('Nº Chamado', ''))
                            link_val = first_row.get('Link Externo', '')
                            with c11: st.link_button(f"🔗 {chamado_num}", link_val) if pd.notna(link_val) and str(link_val).startswith('http') else st.caption(chamado_num)
                            novo_link = c12.text_input("Link", value=link_val if pd.notna(link_val) else "", key=f"lnk_{form_key}")
                            novo_proto = c13.text_input("Protocolo", value=first_row.get('Nº Protocolo', '') if pd.notna(first_row.get('Nº Protocolo', '')) else "", key=f"prot_{form_key}")

                            st.markdown("---")
                            desc_final = ""
                            if str(nome_servico).lower().strip() in SERVICOS_SEM_EQUIPAMENTO: desc_final = f"Realizar {nome_servico}"
                            else:
                                itens = []
                                for sys, df_s in df_grupo.groupby('Sistema'):
                                    itens.append(f"**{clean_val(sys, 'Geral')}**")
                                    for _, r in df_s.iterrows(): itens.append(f"- {r.get('Qtd.', 0)}x {r.get('Equipamento', 'Item')}")
                                desc_final = "<br>".join(itens)
                            st.caption("Itens:"); st.markdown(f"<div style='background-color:#f9f9f9; padding:10px; border-radius:5px;'>{desc_final}</div>", unsafe_allow_html=True)
                            st.markdown("<br>", unsafe_allow_html=True)

                            # Lógica de Salvamento
                            if st.form_submit_button("💾 Salvar", use_container_width=True):
                                updates = {
                                    "Data Abertura": nova_abertura, "Data Agendamento": novo_agend, "Data Finalização": novo_fim,
                                    "Analista": novo_analista, "Gestor": novo_gestor, "Técnico": novo_tec, "Projeto": novo_projeto,
                                    "Serviço": novo_servico, "Sistema": novo_sistema, "Observações e Pendencias": nova_obs,
                                    "Link Externo": novo_link, "Nº Protocolo": novo_proto
                                }
                                recalcular_auto = False
                                if novo_status == "(Automático)":
                                    recalcular_auto = True
                                else:
                                    updates["Status"] = novo_status
                                    if novo_status in ["Cancelado", "Pausado"]: updates["Sub-Status"] = ""
                                    if novo_status == "Finalizado" and novo_fim is None: st.error("Data Finalização obrigatória!"); st.stop()

                                with st.spinner("Salvando..."):
                                    cnt = 0
                                    for cid in ids_chamados:
                                        if utils_chamados.atualizar_chamado_db(cid, updates): cnt += 1
                                    
                                    if cnt > 0:
                                        st.success("Salvo!")
                                        if recalcular_auto:
                                            df_all = utils_chamados.carregar_chamados_db()
                                            df_target = df_all[df_all['ID'].isin(ids_chamados)]
                                            calcular_e_atualizar_status_projeto(df_target, ids_chamados)
                                        
                                        st.cache_data.clear(); time.sleep(0.5); st.rerun()
                                    else: st.error("Erro ao salvar.")

    with aba_calendario:
        st.subheader("🗓️ Agenda da Semana")
        c_nav, _ = st.columns([1, 4])
        dt_ref = c_nav.date_input("Data Ref.", value=date.today())
        ini_sem = dt_ref - timedelta(days=dt_ref.weekday())
        st.caption(f"Semana: {ini_sem.strftime('%d/%m')} a {(ini_sem + timedelta(days=4)).strftime('%d/%m')}"); st.markdown("---")
        
        cols = st.columns(5); dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
        for i, col in enumerate(cols):
            dia = ini_sem + timedelta(days=i)
            with col:
                st.markdown(f"<div style='text-align:center; border-bottom:2px solid #eee; margin-bottom:10px;'><b>{dias[i]}</b><br><small>{dia.strftime('%d/%m')}</small></div>", unsafe_allow_html=True)
                df_d = df_view[pd.to_datetime(df_view['Agendamento']).dt.date == dia] if not df_view.empty else pd.DataFrame()
                if df_d.empty: st.markdown("<div style='text-align:center; color:#eee; font-size:2em;'>-</div>", unsafe_allow_html=True)
                else:
                    for _, r in df_d.sort_values('Analista').iterrows():
                        cor = utils_chamados.get_status_color(r.get('Status', ''))
                        serv = (str(r.get('Serviço', ''))[:20] + '..') if len(str(r.get('Serviço', ''))) > 22 else r.get('Serviço', '')
                        an = str(r.get('Analista', 'N/D')).split(' ')[0].upper()
                        ag = str(r.get('Cód. Agência', '')).split('.')[0]
                        st.markdown(f"""<div style="background:white; border-left:4px solid {cor}; padding:6px; margin-bottom:6px; box-shadow:0 1px 2px #eee; font-size:0.8em;"><b>{serv}</b><br><div style="display:flex; justify-content:space-between; margin-top:4px;"><span>🏠 {ag}</span><span style="background:#E3F2FD; color:#1565C0; padding:1px 4px; border-radius:3px; font-weight:bold;">{an}</span></div></div>""", unsafe_allow_html=True)
