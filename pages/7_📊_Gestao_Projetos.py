import streamlit as st
import pandas as pd
import utils_chamados
import utils # Para carregar listas de configuração
import plotly.express as px
from datetime import date, timedelta, datetime
import time
import math

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS ESTILO "LISTA TÉCNICA" (IGUAL À IMAGEM) ---
st.markdown("""
    <style>
        /* Remove padding extra das colunas para ficar compacto */
        div[data-testid="column"] { padding: 0px; }
        
        /* Linha Dourada do Topo */
        .gold-line { border-top: 3px solid #D4AF37; margin-top: 10px; margin-bottom: 10px; }
        
        /* Textos e Rótulos */
        .label-meta { font-size: 0.75em; color: #555; font-weight: 600; }
        .text-meta { font-size: 0.85em; color: #333; font-weight: normal; }
        
        /* Estilos Específicos da Imagem */
        .gestor-alert { color: #D32F2F; font-size: 0.8em; font-weight: bold; margin-top: 2px; }
        .action-green { color: #004D40; font-weight: bold; font-size: 0.8em; text-transform: uppercase; text-align: right; }
        .project-title { font-weight: 700; font-size: 1em; color: #2C3E50; }
        .sla-green { color: #2E7D32; font-size: 0.85em; font-weight: 600; margin-left: 10px; }
        .sla-red { color: #C62828; font-size: 0.85em; font-weight: 600; margin-left: 10px; }
        
        /* Badge Status (Igual ao cinza da imagem) */
        .status-box {
            background-color: #CFD8DC; 
            color: #37474F; 
            padding: 4px 12px; 
            border-radius: 4px; 
            font-weight: 700; 
            font-size: 0.75em; 
            text-transform: uppercase;
            display: inline-block;
        }
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
    # --- MODO OPERACIONAL (VISÃO DETALHADA) ---
    
    # 1. ÁREA DE FILTROS (FIXA E ORGANIZADA)
    with st.container(border=True):
        st.markdown("### 🔍 Filtros & Pesquisa")
        
        # Linha 1: Busca e Data
        c_top1, c_top2 = st.columns([3, 1])
        with c_top1:
            busca_geral = st.text_input("Buscador Geral", placeholder="Digite ID, Nome, Serviço...", label_visibility="collapsed")
        with c_top2:
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            d_min = df_filtrado['Agendamento'].min() if not pd.isna(df_filtrado['Agendamento'].min()) else date.today()
            d_max = df_filtrado['Agendamento'].max() if not pd.isna(df_filtrado['Agendamento'].max()) else date.today()
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")

        # Linha 2: Projetos e Status
        c_bot1, c_bot2 = st.columns(2)
        with c_bot1:
            try:
                df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                opcoes_projeto_db = df_proj_cfg.iloc[:, 0].tolist() if not df_proj_cfg.empty else []
            except: opcoes_projeto_db = []
            
            if not opcoes_projeto_db:
                opcoes_projeto_db = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
            
            padrao_projetos = []
            if "sel_projeto" in st.session_state:
                proj_sel = st.session_state["sel_projeto"]
                if proj_sel in opcoes_projeto_db: padrao_projetos = [proj_sel]
                st.session_state.pop("sel_projeto", None)
            
            filtro_projeto_multi = st.multiselect("Projetos", options=opcoes_projeto_db, default=padrao_projetos, placeholder="Filtrar por Projeto", label_visibility="collapsed")

        with c_bot2:
            opcoes_status = sorted(df_filtrado['Status'].dropna().unique().tolist())
            filtro_status_multi = st.multiselect("Status", options=opcoes_status, default=[], placeholder="Filtrar por Status", label_visibility="collapsed")

    # --- APLICAÇÃO DOS FILTROS ---
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

    # 2. KPIs
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    qtd_total = len(df_view)
    qtd_fim = len(df_view[df_view['Status'].str.lower().isin(status_fim)])
    
    if not df_view.empty:
        gr = df_view.groupby('Projeto')
        proj_total = gr.ngroups
        proj_concluidos = sum(1 for _, d in gr if d['Status'].str.lower().isin(status_fim).all())
        proj_abertos = proj_total - proj_concluidos
    else: proj_total=0; proj_concluidos=0; proj_abertos=0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Chamados (Filtro)", qtd_total, border=True)
    k2.metric("Projetos Abertos", proj_abertos, border=True)
    k3.metric("Projetos Finalizados", proj_concluidos, border=True)
    k4.metric("Tarefas Concluídas", qtd_fim, border=True)
    
    st.divider()

    # 3. RESUMO STATUS
    if not df_view.empty:
        counts = df_view['Status'].value_counts()
        cols = st.columns(6)
        i = 0
        for status, count in counts.items():
            try: cor = utils_chamados.get_status_color(status)
            except: cor = "#ccc"
            with cols[i % 6]:
                st.markdown(f"""<div style="border-left:4px solid {cor}; background:white; padding:5px 10px; border-radius:4px; border:1px solid #eee; margin-bottom:5px;"><small style="color:#666;">{status.upper()}</small><br><b>{count}</b></div>""", unsafe_allow_html=True)
            i += 1
    
    st.markdown("<br>", unsafe_allow_html=True)

    # 4. CONTEÚDO (LISTA E CALENDÁRIO)
    aba_lista, aba_calendario = st.tabs(["📋 Lista Detalhada", "📅 Agenda Semanal"])

    with aba_lista:    
        if df_view.empty:
            st.warning("Nenhum chamado encontrado.")
        else:
            df_view['Agendamento_str'] = pd.to_datetime(df_view['Agendamento']).dt.strftime('%d/%m/%Y').fillna("Sem Data")
            grupos = list(df_view.groupby(['Projeto', 'Nome Agência', 'Serviço', 'Agendamento_str']))
            
            # PAGINAÇÃO
            ITENS_POR_PAG = 20
            total_itens = len(grupos)
            total_paginas = math.ceil(total_itens / ITENS_POR_PAG)
            
            c_info, c_pag = st.columns([4, 1])
            with c_info: st.caption(f"Exibindo {total_itens} grupos • Página {st.session_state.get('pag_proj', 1)} de {total_paginas}")
            
            if total_paginas > 1:
                with c_pag: 
                    pag = st.number_input("Pág.", 1, total_paginas, key="pag_proj")
            else: pag = 1
            
            inicio = (pag - 1) * ITENS_POR_PAG
            fim = inicio + ITENS_POR_PAG
                        
            for (proj_nome, nome_agencia, nome_servico, data_str), df_grupo in grupos[inicio:fim]:
                row = df_grupo.iloc[0]
                ids = df_grupo['ID'].tolist()
                
                # --- PREPARAÇÃO DE DADOS ---
                st_atual = clean_val(row.get('Status'), "Não Iniciado")
                acao = clean_val(row.get('Sub-Status'), "")
                analista = clean_val(row.get('Analista'), "N/D").split(' ')[0].upper()
                gestor = clean_val(row.get('Gestor'), "").split(' ')[0].upper()
                
                # Tratamento Agência
                cod_ag = str(row.get('Cód. Agência', '')).split('.')[0]
                nome_ag_limpo = str(nome_agencia).replace(cod_ag, '').strip(' -')

                # SLA
                sla_html = ""
                if _to_date_safe(row.get('Prazo')):
                    dias = (_to_date_safe(row.get('Prazo')) - date.today()).days
                    if dias < 0: sla_html = f"<span class='sla-red'>SLA: {abs(dias)}d atraso</span>"
                    else: sla_html = f"<span class='sla-green'>SLA: {dias}d restantes</span>"

                # --- RENDERIZAÇÃO IGUAL À IMAGEM ---
                
                # 1. A Linha Dourada Superior
                st.markdown('<div class="gold-line"></div>', unsafe_allow_html=True)
                
                # 2. Primeira Linha de Informações (Grid: Data | Analista | Agência | Status)
                c1, c2, c3, c4 = st.columns([1.5, 2, 4, 2.5])
                
                with c1: # DATA
                    st.markdown(f"🗓️ **{data_str}**", unsafe_allow_html=True)
                
                with c2: # ANALISTA
                    st.markdown(f"<span class='label-meta'>Analista:</span> <span class='text-meta'>{analista}</span>", unsafe_allow_html=True)
                    
                with c3: # AGÊNCIA + GESTOR (Vermelho)
                    st.markdown(f"<span class='label-meta'>Agência:</span> <span class='text-meta'>AG {cod_ag} {nome_ag_limpo}</span>", unsafe_allow_html=True)
                    if gestor:
                        st.markdown(f"<div class='gestor-alert'>Gestor: {gestor}</div>", unsafe_allow_html=True)
                
                with c4: # STATUS (Badge Cinza) + SUB-STATUS (Verde)
                    # Alinhamento à direita usando HTML wrapper
                    html_status = f"""
                    <div style="text-align: right;">
                        <span class="status-box">{st_atual}</span>
                        <div class="action-green" style="margin-top:5px;">{acao}</div>
                    </div>
                    """
                    st.markdown(html_status, unsafe_allow_html=True)

                # 3. Segunda Linha: Nome do Projeto/Serviço + SLA
                # Usamos columns de novo para manter alinhamento
                l2_c1, l2_c2 = st.columns([6, 4])
                with l2_c1:
                    
                    st.markdown(f"<span class='project-title'>{nome_servico}</span> {sla_html}", unsafe_allow_html=True)
                    with st.expander(f"📝 Editar Detalhes (ID: {ids[0]})"):

                        form_key = f"form_{row['ID']}"
                        with st.form(key=form_key):
                            try:
                                df_st = utils.carregar_config_db("status"); lst_st = [str(x) for x in df_st.iloc[:,0].dropna().tolist()] if not df_st.empty else []
                                df_pj = utils.carregar_config_db("projetos_nomes"); lst_pj = [str(x) for x in df_pj.iloc[:,0].dropna().tolist()] if not df_pj.empty else []
                                df_tc = utils.carregar_config_db("tecnicos"); lst_tc = [str(x) for x in df_tc.iloc[:,0].dropna().tolist()] if not df_tc.empty else []
                                df_us = utils.carregar_usuarios_db(); df_us.columns = [c.capitalize() for c in df_us.columns] if not df_us.empty else []
                                lst_an = [str(x) for x in df_us["Nome"].dropna().tolist()] if not df_us.empty and "Nome" in df_us.columns else []
                            except: lst_st=[]; lst_pj=[]; lst_tc=[]; lst_an=[]

                            def sf(v): return str(v) if pd.notna(v) and str(v).lower() not in ['nan', 'none', ''] else ""
                            
                            l_st = sorted(list(set(lst_st + [st_atual] + ["(Automático)", "Finalizado"])))
                            i_st = l_st.index(st_atual) if st_atual in l_st else 0
                            
                            v_pj = sf(row.get('Projeto', '')); l_pj = sorted(list(set(lst_pj + [v_pj]))); i_pj = l_pj.index(v_pj) if v_pj in l_pj else 0
                            v_tc = sf(row.get('Técnico', '')); l_tc = sorted(list(set(lst_tc + [v_tc]))); i_tc = l_tc.index(v_tc) if v_tc in l_tc else 0
                            v_an = sf(row.get('Analista', '')); l_an = sorted(list(set(lst_an + [v_an]))); i_an = l_an.index(v_an) if v_an in l_an else 0

                            k1, k2, k3, k4 = st.columns(4)
                            n_st = k1.selectbox("Status", l_st, index=i_st, key=f"st_{form_key}")
                            n_ab = k2.date_input("Abertura", value=_to_date_safe(row.get('Abertura')) or date.today(), format="DD/MM/YYYY", key=f"ab_{form_key}")
                            n_ag = k3.date_input("Agendamento", value=_to_date_safe(row.get('Agendamento')), format="DD/MM/YYYY", key=f"ag_{form_key}")
                            n_fi = k4.date_input("Finalização", value=_to_date_safe(row.get('Fechamento')), format="DD/MM/YYYY", key=f"fi_{form_key}")

                            k5, k6, k7 = st.columns(3)
                            n_an = k5.selectbox("Analista", l_an, index=i_an, key=f"an_{form_key}")
                            n_ge = k6.text_input("Gestor", value=row.get('Gestor', ''), key=f"ge_{form_key}")
                            n_tc = k7.selectbox("Técnico", l_tc, index=i_tc, key=f"tc_{form_key}")

                            k8, k9, k10 = st.columns(3)
                            n_pj = k8.selectbox("Projeto", l_pj, index=i_pj, key=f"pj_{form_key}")
                            n_sv = k9.text_input("Serviço", value=row.get('Serviço', ''), key=f"sv_{form_key}")
                            n_si = k10.text_input("Sistema", value=row.get('Sistema', ''), key=f"si_{form_key}")

                            n_ob = st.text_area("Observações", value=row.get('Observações e Pendencias', ''), height=80, key=f"ob_{form_key}")
                            
                            k11, k12, k13 = st.columns([1, 2, 1])
                            n_lk = k12.text_input("Link", value=row.get('Link Externo', ''), key=f"lk_{form_key}")
                            n_pt = k13.text_input("Protocolo", value=row.get('Nº Protocolo', ''), key=f"pt_{form_key}")
                            
                            st.markdown("---")
                            desc = ""
                            if str(nome_servico).lower() in SERVICOS_SEM_EQUIPAMENTO: desc = f"Realizar {nome_servico}"
                            else:
                                its = []
                                for s, d in df_grupo.groupby('Sistema'):
                                    its.append(f"**{clean_val(s, 'Geral')}**")
                                    for _, r in d.iterrows(): its.append(f"- {r.get('Qtd.', 0)}x {r.get('Equipamento', 'Item')}")
                                desc = "<br>".join(its)
                            st.caption("Itens:"); st.markdown(f"<div style='background:#f9f9f9; padding:10px;'>{desc}</div>", unsafe_allow_html=True); st.markdown("<br>", unsafe_allow_html=True)

                            if st.form_submit_button("💾 Salvar"):
                                upds = {
                                    "Data Abertura": n_ab, "Data Agendamento": n_ag, "Data Finalização": n_fi,
                                    "Analista": n_an, "Gestor": n_ge, "Técnico": n_tc, "Projeto": n_pj,
                                    "Serviço": n_sv, "Sistema": n_si, "Observações e Pendencias": n_ob,
                                    "Link Externo": n_lk, "Nº Protocolo": n_pt
                                }
                                recalc = False
                                if n_st == "(Automático)": recalc = True
                                else:
                                    upds["Status"] = n_st
                                    if n_st in ["Cancelado", "Pausado"]: upds["Sub-Status"] = ""
                                    if n_st == "Finalizado" and n_fi is None: st.error("Data Finalização obrigatória!"); st.stop()

                                with st.spinner("Salvando..."):
                                    c = 0
                                    for cid in ids:
                                        if utils_chamados.atualizar_chamado_db(cid, upds): c += 1
                                    if c > 0:
                                        st.success("Salvo!")
                                        if recalc:
                                            da = utils_chamados.carregar_chamados_db()
                                            dt = da[da['ID'].isin(ids)]
                                            calcular_e_atualizar_status_projeto(dt, ids)
                                        st.cache_data.clear(); time.sleep(0.5); st.rerun()
                                    else: st.error("Erro.")

    with aba_calendario:
        st.subheader("🗓️ Agenda da Semana")
        cn, _ = st.columns([1, 4])
        ref = cn.date_input("Data Ref.", value=date.today(), format="DD/MM/YYYY")
        ini = ref - timedelta(days=ref.weekday())
        st.caption(f"Semana: {ini.strftime('%d/%m')} a {(ini + timedelta(days=4)).strftime('%d/%m')}"); st.markdown("---")
        
        cs = st.columns(5); ds = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
        for i, col in enumerate(cs):
            dia = ini + timedelta(days=i)
            with col:
                st.markdown(f"<div style='text-align:center; border-bottom:2px solid #eee; margin-bottom:10px;'><b>{ds[i]}</b><br><small>{dia.strftime('%d/%m')}</small></div>", unsafe_allow_html=True)
                dd = df_view[pd.to_datetime(df_view['Agendamento']).dt.date == dia] if not df_view.empty else pd.DataFrame()
                if dd.empty: st.markdown("<div style='text-align:center; color:#eee; font-size:2em;'>-</div>", unsafe_allow_html=True)
                else:
                    for _, r in dd.sort_values('Analista').iterrows():
                        cc = utils_chamados.get_status_color(r.get('Status', ''))
                        sv = (str(r.get('Serviço', ''))[:20] + '..') if len(str(r.get('Serviço', ''))) > 22 else r.get('Serviço', '')
                        an = str(r.get('Analista', 'N/D')).split(' ')[0].upper()
                        ag = str(r.get('Cód. Agência', '')).split('.')[0]
                        st.markdown(f"""<div style="background:white; border-left:4px solid {cc}; padding:6px; margin-bottom:6px; box-shadow:0 1px 2px #eee; font-size:0.8em;"><b>{sv}</b><br><div style="display:flex; justify-content:space-between; margin-top:4px;"><span>🏠 {ag}</span><span style="background:#E3F2FD; color:#1565C0; padding:1px 4px; border-radius:3px; font-weight:bold;">{an}</span></div></div>""", unsafe_allow_html=True)



