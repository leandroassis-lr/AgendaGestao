import streamlit as st
import pandas as pd
import utils_chamados
import utils
from datetime import date, timedelta, datetime
import time
import math
import io

st.set_page_config(page_title="Detalhes - GESTÃO", page_icon="🔧", layout="wide")

# --- CSS ESTILO PERSONALIZADO (O MESMO DO SEU CÓDIGO) ---
st.markdown("""
    <style>
        div[data-testid="column"] { padding: 0px; }
        .gold-line { border-top: 3px solid #D4AF37; margin-top: 15px; margin-bottom: 5px; }
        
        /* Estilos Gerais */
        .agencia-header { font-size: 1.1em; font-weight: 800; color: #333; margin-bottom: 4px; }
        .meta-label { font-size: 0.8em; color: #666; font-weight: 600; text-transform: uppercase; }
        
        /* Cores Fixas de Analistas */
        .ana-azul { color: #1565C0; font-weight: 800; background-color: #E3F2FD; padding: 2px 6px; border-radius: 4px; }
        .ana-verde { color: #2E7D32; font-weight: 800; background-color: #E8F5E9; padding: 2px 6px; border-radius: 4px; }
        .ana-rosa  { color: #C2185B; font-weight: 800; background-color: #FCE4EC; padding: 2px 6px; border-radius: 4px; }
        .ana-default { color: #555; font-weight: 700; }

        /* Gestores */
        .gestor-bold { color: #000000; font-weight: 900; font-size: 0.9em; }

        /* Status Badge */
        .status-badge { padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.95em; text-transform: uppercase; color: white; display: inline-block;}
        
        /* KPI Cards */
        .kpi-card { background-color: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; text-align: center; height: 100%; }
        .kpi-title { font-size: 0.85em; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
        .kpi-value { font-size: 1.8em; font-weight: 800; color: #2c3e50; }
        .kpi-blue   { border-bottom: 4px solid #1565C0; }
        .kpi-orange { border-bottom: 4px solid #F57C00; }
        .kpi-green  { border-bottom: 4px solid #2E7D32; }
        .kpi-purple { border-bottom: 4px solid #7B1FA2; }
        
        /* Estilo da Área de Filtros */
        .filter-container { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #e9ecef; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- UTILS LOCAIS ---
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

# --- LÓGICA DE STATUS: CHAMADO E PROJETO (FUNDAMENTAL) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    """
    1. Calcula o status individual de cada chamado (Sub-Status).
    2. Calcula o status macro do projeto baseado no conjunto.
    """
    updates_batch = {} 
    chamados_calculados = [] 

    for idx, row in df_projeto.iterrows():
        n_chamado = str(row.get('Nº Chamado', ''))
        is_equip = '-e-' in n_chamado.lower() or '-E-' in n_chamado
        
        # --- LEITURA DE DADOS ---
        link_presente = row.get('Link Externo') and str(row.get('Link Externo')).strip() not in ['', 'nan', 'None']
        n_pedido = row.get('Nº Pedido') and str(row.get('Nº Pedido')).strip() not in ['', 'nan', 'None']
        tecnico_presente = row.get('Técnico') and str(row.get('Técnico')).strip() not in ['', 'nan', 'None']

        db_liberacao_banco = str(row.get('chk_financeiro_banco', '')).upper() == 'TRUE'
        db_book_controle_sim = str(row.get('Book Enviado', '')).upper() == 'SIM'
        
        chk_cancelado = str(row.get('chk_cancelado', '')).upper() == 'TRUE'
        chk_pend_eq = str(row.get('chk_pendencia_equipamento', '')).upper() == 'TRUE'
        chk_pend_infra = str(row.get('chk_pendencia_infra', '')).upper() == 'TRUE'
        chk_alteracao = str(row.get('chk_alteracao_chamado', '')).upper() == 'TRUE'
        
        chk_envio_parcial = str(row.get('chk_envio_parcial', '')).upper() == 'TRUE'
        chk_entregue_total = str(row.get('chk_equipamento_entregue', '')).upper() == 'TRUE'
        chk_followup = str(row.get('chk_status_enviado', '')).upper() == 'TRUE'

        novo_sub_status = "Em análise"
        
        # --- LÓGICA INDIVIDUAL ---
        if chk_cancelado: novo_sub_status = "Cancelado"
        elif db_liberacao_banco: novo_sub_status = "Faturado"
        elif chk_pend_eq: novo_sub_status = "Pendência de equipamento"
        elif chk_pend_infra: novo_sub_status = "Pendência de Infra"
        elif chk_alteracao: novo_sub_status = "Alteração do chamado"
        else:
            if is_equip:
                if chk_entregue_total: novo_sub_status = "Equipamento entregue"
                elif chk_envio_parcial: novo_sub_status = "Equipamento enviado Parcial"
                elif row.get('Data Envio') and pd.notna(row.get('Data Envio')): novo_sub_status = "Equipamento enviado"
                elif n_pedido: novo_sub_status = "Aguardando envio"
                else: novo_sub_status = "Solicitar equipamento"
            else:
                if db_book_controle_sim: novo_sub_status = "Aguardando Faturamento"
                elif chk_followup: novo_sub_status = "Enviar Book"
                elif tecnico_presente: novo_sub_status = "Follow-up" 
                elif link_presente: novo_sub_status = "Acionar técnico" 
                else: novo_sub_status = "Abrir chamado Btime" 

        updates_batch[row['ID']] = {"Sub-Status": novo_sub_status}
        
        chamado_obj = {
            "ID": row['ID'], "Tipo": "EQUIP" if is_equip else "SERV",
            "SubStatus": novo_sub_status, "Cancelado": chk_cancelado, "Faturado": db_liberacao_banco
        }
        chamados_calculados.append(chamado_obj)

    # --- PARTE B: CALCULAR STATUS DO PROJETO ---
    total = len(chamados_calculados)
    if total == 0: return False

    ativos = [c for c in chamados_calculados if not c['Cancelado']]
    if len(ativos) == 0: status_projeto = "Cancelado"
    else:
        todos_finalizados_banco = all(c['Faturado'] for c in ativos)
        def is_concluido(c): return c['SubStatus'] in ["Faturado", "Aguardando Faturamento", "Equipamento entregue", "Enviar Book"] 
        todos_concluidos = all(is_concluido(c) for c in ativos)
        def is_nao_iniciado(c): return c['SubStatus'] in ["Solicitar equipamento", "Abrir chamado Btime"]
        todos_nao_iniciados = all(is_nao_iniciado(c) for c in ativos)

        if todos_finalizados_banco: status_projeto = "Finalizado"
        elif todos_concluidos: status_projeto = "Concluído"
        elif todos_nao_iniciados: status_projeto = "Não Iniciado"
        else: status_projeto = "Em Andamento"
    
    # Aplica Updates
    for cid, data in updates_batch.items(): utils_chamados.atualizar_chamado_db(cid, data)
    for row in chamados_calculados: utils_chamados.atualizar_chamado_db(row['ID'], {"Status": status_projeto})              
    return True

# --- DIALOG (POP-UP) DETALHES DO CHAMADO ---
@st.dialog("📝 Editar Chamado", width="large")
def open_chamado_dialog(row_dict):
    n_chamado = str(row_dict.get('Nº Chamado', ''))
    is_equip = '-e-' in n_chamado.lower() or '-E-' in n_chamado

    # Carrega Listas
    try:
        df_tc = utils.carregar_config_db("tecnicos"); lista_tecnicos = df_tc.iloc[:,0].dropna().tolist()
    except: lista_tecnicos = []
    try:
        df_gest = utils.carregar_config_db("gestores"); lista_gestores = df_gest.iloc[:,0].dropna().tolist()
    except: lista_gestores = []

    val_tec_atual = str(row_dict.get('Técnico', '')).strip()
    val_gest_atual = str(row_dict.get('Gestor', '')).strip()
    if val_tec_atual and val_tec_atual not in lista_tecnicos: lista_tecnicos.insert(0, val_tec_atual)
    if val_gest_atual and val_gest_atual not in lista_gestores: lista_gestores.insert(0, val_gest_atual)

    st.markdown(f"### 🎫 {n_chamado}")
    st.caption(f"ID: {row_dict.get('ID')}")
    st.markdown("<hr style='margin: 5px 0 15px 0'>", unsafe_allow_html=True)

    with st.form(key=f"form_popup_{row_dict['ID']}"):
        dt_abertura = _to_date_safe(row_dict.get('Abertura'))
        dt_agendamento = _to_date_safe(row_dict.get('Agendamento'))
        dt_finalizacao = _to_date_safe(row_dict.get('Fechamento'))
        dt_envio = _to_date_safe(row_dict.get('Data Envio'))

        # LINHA 1
        c1, c2, c3, c4 = st.columns(4)
        c1.text_input("📅 Abertura", value=(dt_abertura.strftime('%d/%m/%Y') if dt_abertura else "-"), disabled=True)
        c2.text_input("📅 Agendamento", value=(dt_agendamento.strftime('%d/%m/%Y') if dt_agendamento else "-"), disabled=True)
        nova_reprog = c3.date_input("🔄 Reprogramação", value=dt_agendamento, format="DD/MM/YYYY")
        nova_finalizacao = c4.date_input("✅ Finalização", value=dt_finalizacao, format="DD/MM/YYYY")

        # LINHA 2
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        novo_tecnico = r2_c1.selectbox("🔧 Técnico", options=[""] + lista_tecnicos, index=lista_tecnicos.index(val_tec_atual)+1 if val_tec_atual in lista_tecnicos else 0)
        r2_c2.text_input("💻 Sistema", value=row_dict.get('Sistema', ''), disabled=True)
        r2_c3.text_input("🛠️ Serviço", value=row_dict.get('Serviço', ''), disabled=True)
        novo_gestor = r2_c4.text_input("👤 Gestor", value=val_gest_atual) 

        # DESCRIÇÃO
        st.markdown("<br><b>📦 Descrição</b>", unsafe_allow_html=True)
        equip_nome = str(row_dict.get('Equipamento', ''))
        equip_qtd = str(row_dict.get('Qtd.', '')).replace('.0', '')
        desc_bd = str(row_dict.get('Descrição', ''))
        itens_desc = "-"
        if equip_nome and equip_nome.lower() not in ['nan', 'none', '', 'None']:
            if equip_qtd and equip_qtd.lower() not in ['nan', 'none', '']: itens_desc = f"{equip_qtd} - {equip_nome}"
            else: itens_desc = equip_nome
        elif desc_bd and desc_bd.lower() not in ['nan', 'none', '', 'None']: itens_desc = desc_bd
        st.info(itens_desc.replace("|", "\n- ").replace(" | ", "\n- "))

        # LINHA 3
        st.markdown("<br>", unsafe_allow_html=True)
        nova_data_envio = dt_envio
        novo_link = row_dict.get('Link Externo', '')
        novo_protocolo = row_dict.get('Nº Protocolo', '')
        novo_pedido = row_dict.get('Nº Pedido', '')

        if is_equip:
            l3_c1, l3_c2, l3_c3 = st.columns([2, 1.5, 1.5])
            novo_link = l3_c1.text_input("🔢 Nº Chamado Btime (Ref)", value=row_dict.get('Link Externo', ''))
            novo_pedido = l3_c2.text_input("📦 Nº Pedido", value=row_dict.get('Nº Pedido', ''))
            nova_data_envio = l3_c3.date_input("🚚 Data de Envio", value=dt_envio, format="DD/MM/YYYY")
        else:
            l3_c1, l3_c2, l3_c3 = st.columns([3, 1.5, 1.5])
            novo_link = l3_c1.text_input("🔗 Link Externo", value=row_dict.get('Link Externo', ''))
            novo_protocolo = l3_c2.text_input("🔢 Protocolo", value=row_dict.get('Nº Protocolo', ''))
            with l3_c3:
                if novo_link and str(novo_link).lower() not in ['nan', 'none', '']:
                    st.markdown(f"<br><a href='{novo_link}' target='_blank' style='background:#1565C0; color:white; padding:9px 12px; border-radius:4px; text-decoration:none;'>🚀 Abrir Link</a>", unsafe_allow_html=True)

        # CHECKLIST
        st.markdown("---"); st.markdown("### ☑️ Controle de Status & Pendências")
        def is_checked(key): return str(row_dict.get(key, '')).upper() == 'TRUE'
        
        c_chk1, c_chk2 = st.columns(2)
        with c_chk1:
            new_pend_eq = st.checkbox("⚠️ Pendência Equipamento", value=is_checked('chk_pendencia_equipamento'))
            new_pend_infra = st.checkbox("🏗️ Pendência Infra", value=is_checked('chk_pendencia_infra'))
            new_alteracao = st.checkbox("📝 Alteração Chamado", value=is_checked('chk_alteracao_chamado'))
            new_cancelado = st.checkbox("🚫 Cancelado", value=is_checked('chk_cancelado'))
        with c_chk2:
            if is_equip:
                new_envio_parcial = st.checkbox("📦 Envio Parcial", value=is_checked('chk_envio_parcial'))
                new_entregue_total = st.checkbox("✅ Equip. Entregue Total", value=is_checked('chk_equipamento_entregue'))
                new_followup = False
            else:
                new_followup = st.checkbox("📧 Follow-up", value=is_checked('chk_status_enviado'))
                new_envio_parcial = False; new_entregue_total = False

        obs_atual = row_dict.get('Observações e Pendencias', '')
        nova_obs = st.text_area("✍️ Observação / Pendência", value=obs_atual if pd.notna(obs_atual) else "", height=100)
        
        st.markdown("<hr>", unsafe_allow_html=True)
        if st.form_submit_button("💾 SALVAR E RECALCULAR", use_container_width=True):
            # Validação simples
            if new_cancelado and not nova_finalizacao: st.error("Para CANCELAR, informe a Data de Finalização."); return
            
            updates = {
                "Data Agendamento": nova_reprog, "Data Finalização": nova_finalizacao, "Técnico": novo_tecnico,
                "Gestor": novo_gestor, "Observações e Pendencias": nova_obs, "Link Externo": novo_link,
                "Data Envio": nova_data_envio, "Nº Protocolo": novo_protocolo, "Nº Pedido": novo_pedido,
                "chk_pendencia_equipamento": "TRUE" if new_pend_eq else "FALSE",
                "chk_pendencia_infra": "TRUE" if new_pend_infra else "FALSE",
                "chk_alteracao_chamado": "TRUE" if new_alteracao else "FALSE",
                "chk_cancelado": "TRUE" if new_cancelado else "FALSE",
                "chk_envio_parcial": "TRUE" if new_envio_parcial else "FALSE",
                "chk_equipamento_entregue": "TRUE" if new_entregue_total else "FALSE",
                "chk_status_enviado": "TRUE" if new_followup else "FALSE"
            }
            utils_chamados.atualizar_chamado_db(row_dict['ID'], updates)
            
            # Recalcula projeto
            df_novo = utils_chamados.carregar_chamados_db()
            grupo = df_novo[(df_novo['Projeto'] == row_dict.get('Projeto')) & (df_novo['Cód. Agência'] == row_dict.get('Cód. Agência'))]
            if not grupo.empty: calcular_e_atualizar_status_projeto(grupo, grupo['ID'].tolist())
            
            st.toast("✅ Salvo!", icon="💾"); time.sleep(1); st.rerun()

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def main():
    # 1. BOTÃO DE VOLTAR E TÍTULO
    with st.sidebar:
        if st.button("⬅️ Voltar ao Cockpit", use_container_width=True, type="primary"):
            st.switch_page("app.py")
        
        st.divider()
        if st.button("🔄 Recalcular Status", use_container_width=True):
            with st.spinner("Atualizando..."):
                df_todos = utils_chamados.carregar_chamados_db()
                if not df_todos.empty:
                    for _, grupo in df_todos.groupby('Nº Chamado'):
                        calcular_e_atualizar_status_projeto(grupo, grupo['ID'].tolist())
            st.success("Atualizado!"); time.sleep(1); st.rerun()

    st.title("🔧 Detalhes Operacionais")

    # 2. CARREGAMENTO
    df_filtrado = utils_chamados.carregar_chamados_db()
    if df_filtrado.empty: st.warning("Banco vazio."); return

    # --- 3. FILTROS ---
    with st.container():
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        c_tit, c_date = st.columns([4, 1.5])
        with c_tit: st.markdown("### 🔍 Filtros")
        with c_date: 
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            d_min = df_filtrado['Agendamento'].min() if not pd.isna(df_filtrado['Agendamento'].min()) else date.today()
            d_max = df_filtrado['Agendamento'].max() if not pd.isna(df_filtrado['Agendamento'].max()) else date.today()
            filtro_data = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")

        # Filtro Preliminar Data
        df_opcoes = df_filtrado.copy()
        if len(filtro_data) == 2:
            ts_inicio = pd.to_datetime(filtro_data[0])
            ts_fim = pd.to_datetime(filtro_data[1]) + timedelta(hours=23, minutes=59)
            df_opcoes = df_opcoes[(df_opcoes['Agendamento'] >= ts_inicio) & (df_opcoes['Agendamento'] <= ts_fim)]

        # --- RECEBE PROJETO DO COCKPIT ---
        padrao_proj = []
        if "sel_projeto" in st.session_state:
            p = st.session_state["sel_projeto"]
            if p in df_filtrado['Projeto'].unique(): padrao_proj = [p]
            del st.session_state["sel_projeto"]

        # Listas
        df_opcoes['_filtro_agencia'] = df_opcoes['Cód. Agência'].astype(str) + " - " + df_opcoes['Nome Agência'].astype(str)
        lista_ag = sorted(df_opcoes['_filtro_agencia'].dropna().unique().tolist())
        lista_proj = sorted(df_opcoes['Projeto'].dropna().unique().tolist())

        c1, c2, c3, c4 = st.columns(4)
        with c1: busca = st.text_input("Busca", placeholder="ID, Nome...", label_visibility="collapsed")
        with c2: f_ag = st.multiselect("Agência", lista_ag, label_visibility="collapsed", placeholder="Filtrar Agência")
        with c3: 
            if f_ag:
                sub_projs = df_opcoes[df_opcoes['_filtro_agencia'].isin(f_ag)]['Projeto'].unique()
                lista_proj = sorted([p for p in lista_proj if p in sub_projs])
            f_proj = st.multiselect("Projeto", lista_proj, default=padrao_proj, label_visibility="collapsed", placeholder="Filtrar Projeto")
        with c4:
            df_ac = df_opcoes[df_opcoes['Projeto'].isin(f_proj)] if f_proj else df_opcoes
            lista_ac = sorted([str(x) for x in df_ac['Sub-Status'].dropna().unique() if str(x).strip()!=''])
            f_act = st.multiselect("Ação", lista_ac, label_visibility="collapsed", placeholder="Status/Ação")
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 4. APLICA FILTROS FINAIS ---
    df_view = df_filtrado.copy()
    if len(filtro_data) == 2:
        ts_i = pd.to_datetime(filtro_data[0]); ts_f = pd.to_datetime(filtro_data[1]) + timedelta(hours=23, minutes=59)
        df_view = df_view[(df_view['Agendamento'] >= ts_i) & (df_view['Agendamento'] <= ts_f)]
    if busca:
        t = busca.lower()
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(t)).any(axis=1)]
    if f_ag: 
        df_view['_filtro_agencia'] = df_view['Cód. Agência'].astype(str) + " - " + df_view['Nome Agência'].astype(str)
        df_view = df_view[df_view['_filtro_agencia'].isin(f_ag)]
    if f_proj: df_view = df_view[df_view['Projeto'].isin(f_proj)]
    if f_act: df_view = df_view[df_view['Sub-Status'].isin(f_act)]

    # --- 5. KPIs ---
    st_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    qtd_total = len(df_view)
    qtd_fim = len(df_view[df_view['Status'].str.lower().isin(st_fim)])
    proj_abertos = 0
    if not df_view.empty:
        gr = df_view.groupby('Projeto')
        proj_total = gr.ngroups
        proj_conc = sum(1 for _, d in gr if d['Status'].str.lower().isin(st_fim).all())
        proj_abertos = proj_total - proj_conc

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f"""<div class="kpi-card kpi-blue"><div class="kpi-title">Chamados (Filtro)</div><div class="kpi-value">{qtd_total}</div></div>""", unsafe_allow_html=True)
    with k2: st.markdown(f"""<div class="kpi-card kpi-orange"><div class="kpi-title">Projetos Abertos</div><div class="kpi-value">{proj_abertos}</div></div>""", unsafe_allow_html=True)
    with k3: st.markdown(f"""<div class="kpi-card kpi-green"><div class="kpi-title">Projetos Finalizados</div><div class="kpi-value">{proj_conc if 'proj_conc' in locals() else 0}</div></div>""", unsafe_allow_html=True)
    with k4: st.markdown(f"""<div class="kpi-card kpi-purple"><div class="kpi-title">Tarefas Concluídas</div><div class="kpi-value">{qtd_fim}</div></div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 6. VISUALIZAÇÃO PRINCIPAL (CARD AGRUPADO) ---
    aba_lista, aba_cal = st.tabs(["📋 Lista Detalhada", "📅 Agenda"])
    
    with aba_lista:
        if df_view.empty:
            st.warning("Sem dados.")
        else:
            # Agrupamento
            grupos = list(df_view.groupby(['Projeto', 'Cód. Agência', 'Nome Agência']))
            grupos.sort(key=lambda x: x[0][2]) # Ordena por Nome Agência

            # Paginação
            ITENS_PAG = 20
            total_grupos = len(grupos)
            tot_pag = math.ceil(total_grupos / ITENS_PAG)
            
            c_inf, c_pg = st.columns([4, 1])
            with c_inf: st.caption(f"Exibindo {total_grupos} projetos • {tot_pag} páginas")
            with c_pg: pag = st.number_input("Pág", 1, tot_pag if tot_pag > 0 else 1, key="pg_detalhes")
            
            inicio = (pag - 1) * ITENS_PAG
            fim = inicio + ITENS_PAG
            page_groups = grupos[inicio:fim]

            for (nome_proj, cod_ag, nome_ag), df_grupo in page_groups:
                row_head = df_grupo.iloc[0]
                
                # Dados do Cabeçalho
                st_proj = clean_val(row_head.get('Status'), "Não Iniciado")
                cor_st = utils_chamados.get_status_color(st_proj)
                analista = clean_val(row_head.get('Analista'), "N/D").split(' ')[0].upper()
                
                # CSS Analista
                css_ana = "ana-default"
                if "GIOVANA" in analista: css_ana = "ana-azul"
                elif "MARCELA" in analista: css_ana = "ana-verde"
                elif "MONIQUE" in analista: css_ana = "ana-rosa"

                gestor = clean_val(row_head.get('Gestor'), "N/D").split(' ')[0].title()
                nome_ag_limpo = str(nome_ag).replace(str(cod_ag), '').strip(' -')

                # Datas SLA
                datas = pd.to_datetime(df_grupo['Agendamento'], errors='coerce').dropna()
                data_prox = datas.min() if not datas.empty else None
                data_str = data_prox.strftime('%d/%m/%Y') if data_prox else "-"
                
                sla_html = "-"
                if data_prox:
                    data_sla = data_prox + timedelta(days=5)
                    atrasado = data_sla.date() < date.today() and st_proj not in st_fim
                    cor_s = "#D32F2F" if atrasado else "#388E3C"
                    sla_html = f"<span style='color:{cor_s}; font-weight:bold;'>Até {data_sla.strftime('%d/%m')}</span>"

                # Etapa
                hierarquia = [
                    "Pendência de Infra", "Pendência de equipamento", "Alteração do chamado",
                    "Equipamento enviado Parcial", "Solicitar equipamento", "Aguardando envio",
                    "Equipamento enviado", "Abrir chamado Btime", "Acionar técnico",
                    "Follow-up", "Enviar Book", "Aguardando Faturamento", "Faturado", "Equipamento entregue"
                ]
                etapa_txt = "-"
                for h in hierarquia:
                    if any((str(r.get('Sub-Status','')).strip() == h) and (str(r.get('chk_cancelado','')).upper()!='TRUE') for _, r in df_grupo.iterrows()):
                        etapa_txt = h; break
                
                if etapa_txt == "-":
                    ativos = df_grupo[df_grupo['chk_cancelado'].astype(str).str.upper() != 'TRUE']
                    etapa_txt = clean_val(ativos.iloc[0].get('Sub-Status'), "-") if not ativos.empty else "Todos Cancelados"

                # RENDERIZAÇÃO DO CARD
                st.markdown('<div class="gold-line"></div>', unsafe_allow_html=True)
                with st.container():
                    l1_c1, l1_c2, l1_c3, l1_c4 = st.columns([2.5, 1, 1, 1])
                    with l1_c1: st.markdown(f"<span class='agencia-header'>🏢 {cod_ag} - {nome_ag_limpo}</span>", unsafe_allow_html=True)
                    with l1_c2: st.markdown(f"<span class='meta-label'>AGENDAMENTO</span><br><b>📅 {data_str}</b>", unsafe_allow_html=True)
                    with l1_c3: st.markdown(f"<span class='meta-label'>ANALISTA</span><br><span class='{css_ana}'>{analista}</span>", unsafe_allow_html=True)
                    with l1_c4: st.markdown(f"<span class='status-badge' style='background-color:{cor_st}; margin-top:5px;'>{st_proj}</span>", unsafe_allow_html=True)

                    l2_c1, l2_c2, l2_c3, l2_c4 = st.columns([2.5, 1, 1, 1])
                    with l2_c1: st.markdown(f"<span class='meta-label'>PROJETO</span><br><span style='font-size:1em; font-weight:bold; color:#555'>{nome_proj}</span>", unsafe_allow_html=True)
                    with l2_c2: st.markdown(f"<span class='meta-label'>SLA (+5d)</span><br>{sla_html}", unsafe_allow_html=True)
                    with l2_c3: st.markdown(f"<span class='meta-label'>GESTOR</span><br><span class='gestor-bold'>👤 {gestor}</span>", unsafe_allow_html=True)
                    with l2_c4: 
                        if etapa_txt not in ["-", "nan"]: st.markdown(f"<span class='meta-label'>ETAPA ATUAL</span><br><span style='color:#E65100; font-weight:bold;'>👉 {etapa_txt}</span>", unsafe_allow_html=True)
                        else: st.markdown(f"<span class='meta-label'>ETAPA ATUAL</span><br><span style='color:#ccc'>-</span>", unsafe_allow_html=True)

                # EXPANDER COM CHAMADOS
                with st.expander(f"📂 Visualizar {len(df_grupo)} Chamado(s)"):
                    th1, th2, th3, th4, th5 = st.columns([1.2, 3, 1.2, 2, 0.8])
                    th1.markdown("<small style='color:#999'>CHAMADO</small>", unsafe_allow_html=True)
                    th2.markdown("<small style='color:#999'>SERVIÇO</small>", unsafe_allow_html=True)
                    th3.markdown("<small style='color:#999'>DATA</small>", unsafe_allow_html=True)
                    th4.markdown("<small style='color:#999'>AÇÃO</small>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 5px 0 10px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

                    for loop_idx, (idx, row_ch) in enumerate(df_grupo.iterrows()):
                        n_ch = str(row_ch['Nº Chamado'])
                        serv = str(row_ch['Serviço'])
                        acao = str(row_ch.get('Sub-Status', 'Em análise'))
                        if acao in ['nan', 'None', '']: acao = "Em análise"
                        
                        is_canc = str(row_ch.get('chk_cancelado','')).upper() == 'TRUE'
                        style_c = "text-decoration: line-through; color: #999;" if is_canc else ""
                        
                        dt_r = pd.to_datetime(row_ch['Agendamento'], errors='coerce')
                        dt_f = dt_r.strftime('%d/%m') if pd.notna(dt_r) else "-"

                        c1, c2, c3, c4, c5 = st.columns([1.2, 3, 1.2, 2, 0.8])
                        with c1: st.markdown(f"<b style='{style_c}'>🎫 {n_ch}</b>", unsafe_allow_html=True)
                        with c2: st.markdown(f"<span style='color:#333; {style_c}'>{serv}</span>", unsafe_allow_html=True)
                        with c3: st.markdown(f"📅 {dt_f}", unsafe_allow_html=True)
                        with c4: 
                            if is_canc: st.markdown("<span style='font-size:0.85em; color:#D32F2F; font-weight:600;'>🚫 Cancelado</span>", unsafe_allow_html=True)
                            else: st.markdown(f"<span style='font-size:0.85em; color:#E65100; font-weight:600;'>{acao}</span>", unsafe_allow_html=True)
                        with c5:
                            if st.button("🔎", key=f"btn_ch_{row_ch['ID']}_{loop_idx}"):
                                open_chamado_dialog(row_ch.to_dict())
                        st.markdown("<div style='border-bottom: 1px solid #f8f8f8; margin-bottom: 8px;'></div>", unsafe_allow_html=True)

    with aba_cal:
        st.subheader("🗓️ Agenda")
        # (Código simplificado da agenda visual)
        st.info("Visualização semanal disponível.")

if __name__ == "__main__":
    main()
