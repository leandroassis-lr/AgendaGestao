import streamlit as st
import pandas as pd
import utils_chamados
from datetime import date, timedelta, datetime
import time
import html

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS E ESTILOS (APENAS PARA O CONTEÚDO PRINCIPAL) ---
st.markdown("""
    <style>
        /* Estilo dos Cards de Métricas do Cockpit */
        .metric-card {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #ddd;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 10px;
        }
        .alert-box { background-color: #ffebee; color: #c62828; padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 0.9em; }
        .success-box { background-color: #e8f5e9; color: #2e7d32; padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 0.9em; }
        
        /* Estilo do Badge de Status (Cinza/Azulado) */
        .card-status-badge { 
            background-color: #90A4AE;
            color: white !important; 
            padding: 4px 12px; 
            border-radius: 4px; 
            font-weight: bold; 
            font-size: 0.75em; 
            display: inline-block;
            text-transform: uppercase; 
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            float: right;
        }
        
        /* Estilo da Ação (Texto Verde) */
        .card-action-text { 
            text-align: center; font-size: 0.85em; font-weight: bold; margin-top: 5px; 
            color: #004D40; text-transform: uppercase;
        }

        /* Ajuste do Expander para parecer um botão cinza claro */
        .project-card [data-testid="stExpander"] { 
            border: 1px solid #eee; 
            border-radius: 6px; 
            margin-top: 10px; 
            background-color: #f0f2f6; 
        }
        .project-card [data-testid="stExpander"] p {
            font-size: 0.9em;
            font-weight: 500;
        }
    </style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURAÇÕES E HELPER FUNCTIONS ---

SERVICOS_SEM_EQUIPAMENTO = [
    "vistoria", "adequação de gerador (recall)", "desinstalação total", "recolhimento de eqto",
    "visita técnica", "vistoria conjunta",
    "desinstalação e descarte de porta giratoria - item para desmontagem e recolhimento para descarte ecológico incluindo transporte",
    "modernização central de alarme honeywell para commbox até 12 sensores",
    "modernização central de alarme honeywell para commbox até 24 sensores",
    "modernização central de alarme honeywell para commbox até 48 sensores",
    "modernização central de alarme honeywell para commbox até 60 sensores",
    "modernização central de alarme honeywell para commbox até 90 sensores",
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

# --- 2. FUNÇÕES DE IMPORTAÇÃO ---
@st.dialog("📥 Importar Chamados (Geral)", width="large")
def run_importer_dialog():
    st.info("Arraste o Template Padrão (.xlsx ou .csv).")
    uploaded_files = st.file_uploader("Selecione arquivos", type=["xlsx", "csv"], accept_multiple_files=True, key="up_imp_geral")
    if uploaded_files:
        dfs = []
        for up in uploaded_files:
            try:
                if up.name.endswith('.csv'): df = pd.read_csv(up, sep=';', dtype=str, encoding='utf-8')
                else: df = pd.read_excel(up, dtype=str)
                dfs.append(df)
            except Exception as e: st.error(f"Erro no arquivo {up.name}: {e}")
        if dfs:
            if st.button("🚀 Confirmar Importação"):
                with st.spinner("Processando..."):
                    df_raw = pd.concat(dfs, ignore_index=True)
                    suc, qtd = utils_chamados.bulk_insert_chamados_db(df_raw)
                    if suc:
                        st.success(f"Sucesso! {qtd} chamados processados.")
                        st.cache_data.clear(); time.sleep(1.5); st.rerun()
                    else: st.error("Falha na importação.")

@st.dialog("🔗 Importar Links", width="medium")
def run_link_importer_dialog():
    st.info("Planilha com colunas: CHAMADO e LINK.")
    up = st.file_uploader("Arquivo", type=["xlsx", "csv"], key="up_imp_link")
    if up and st.button("🚀 Atualizar Links"):
        with st.spinner("Atualizando..."):
            try:
                if up.name.endswith('.csv'): df = pd.read_csv(up, sep=';', dtype=str)
                else: df = pd.read_excel(up, dtype=str)
                df.columns = [str(c).upper().strip() for c in df.columns]
                if 'CHAMADO' in df.columns and 'LINK' in df.columns:
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
                else: st.error("Colunas obrigatórias não encontradas.")
            except Exception as e: st.error(f"Erro: {e}")

# --- 3. LÓGICA DE STATUS ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0]
    def has_val(col): return col in row and pd.notna(row[col]) and str(row[col]).strip() != ""
    def is_faturado():
        val = str(row.get('Status Financeiro', '')).strip().upper()
        return val in ['FATURADO', 'PAGO', 'LIBERADO', 'RECEBIDO']
    
    status_atual = str(row.get('Status', 'Não Iniciado')).strip()
    sub_status_atual = str(row.get('Sub-Status', '')).strip()
    status_bloqueio = ["pendência de infra", "pendência de equipamento", "pausada", "cancelada"]
    if status_atual.lower() in status_bloqueio: return False 

    n_chamado = str(row.get('Nº Chamado', '')).upper()
    servico_nome = str(row.get('Serviço', '')).strip().lower()
    eh_servico = '-S-' in n_chamado
    eh_excecao = servico_nome in SERVICOS_SEM_EQUIPAMENTO
    eh_equipamento = '-E-' in n_chamado
    
    novo_status = "Não Iniciado"; novo_acao = ""

    if eh_servico or eh_excecao:
        if is_faturado(): novo_status = "Finalizado"; novo_acao = "Faturado"
        elif has_val('Nº Protocolo'):
            book_enviado = str(row.get('Book Enviado', '')).strip().lower() == 'sim'
            if book_enviado: novo_status = "Finalizado"; novo_acao = "Aguardando faturamento"
            else: novo_status = "Concluído"; novo_acao = "Enviar Book"
        elif has_val('Técnico'): novo_status = "Em Andamento"; novo_acao = "Enviar Status cliente"
        elif has_val('Link Externo'): novo_status = "Em Andamento"; novo_acao = "Acionar técnico"
        else: novo_status = "Não Iniciado"; novo_acao = "Abrir chamado no Btime"
    elif eh_equipamento:
        if is_faturado(): novo_status = "Finalizado"; novo_acao = "Faturado"
        elif has_val('Data Envio'): novo_status = "Em Andamento"; novo_acao = "Equipamento Enviado"
        elif has_val('Nº Pedido'): novo_status = "Em Andamento"; novo_acao = "Equipamento Solicitado"
        else: novo_status = "Não Iniciado"; novo_acao = "Solicitar equipamento"
    else: novo_status = "Não Iniciado"; novo_acao = "Verificar Cadastro"

    if status_atual != novo_status or sub_status_atual != novo_acao:
        st.toast(f"🔄 Atualizando status para: {novo_status}", icon="⚙️")
        updates = {"Status": novo_status, "Sub-Status": novo_acao}
        for chamado_id in ids_para_atualizar: utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

# --- 4. FUNÇÃO DO POP-UP RESUMO ---
@st.dialog("Resumo do Projeto", width="large")
def mostrar_detalhes_projeto(nome_projeto, df_origem):
    st.markdown(f"#### 📂 {nome_projeto}")
    df_p = df_origem[df_origem['Projeto'] == nome_projeto].copy()
    
    def unificar_agencia(row):
        cod = str(row.get('Cód. Agência', '')).split('.')[0]
        if cod.lower() in ['nan', 'none', '']: cod = "?"
        nome = str(row.get('Nome Agência', '')).strip()
        return f"{cod} - {nome}"

    df_p['Agência'] = df_p.apply(unificar_agencia, axis=1)
    df_p['Agendamento'] = pd.to_datetime(df_p['Agendamento'], errors='coerce')
    df_p['Analista'] = df_p['Analista'].fillna("")
    df_p['Status'] = df_p['Status'].fillna("")

    cols_view = ['Agência', 'Agendamento', 'Status', 'Analista']
    st.dataframe(
        df_p[cols_view], use_container_width=True, hide_index=True,
        column_config={"Agendamento": st.column_config.DateColumn("Agendamento", format="DD/MM/YYYY")}
    )
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🛠️ Gerenciar este Projeto ➤", use_container_width=True):
        st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"
        st.session_state["sel_projeto"] = nome_projeto
        st.rerun()

# --- 5. CARREGAMENTO E SIDEBAR (PADRÃO STREAMLIT) ---
df = utils_chamados.carregar_chamados_db()

# SIDEBAR PADRÃO
with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"):
        run_importer_dialog()
    
    if st.button("🔗 Importar Links"):
        run_link_importer_dialog()

    st.divider()
    st.header("Filtros de Gestão")
    analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    filtro_analista = st.selectbox("Analista", analistas)
    
    gestores = ["Todos"] + sorted(df['Gestor'].dropna().unique().tolist())
    filtro_gestor = st.selectbox("Gestor", gestores)

# --- FILTRAGEM ---
df_filtrado = df.copy()
if filtro_analista != "Todos": df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
if filtro_gestor != "Todos": df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]
lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())

if df.empty: st.warning("Sem dados. Importe chamados na barra lateral."); st.stop()

# --- NAVEGAÇÃO PRINCIPAL ---
if "nav_radio" not in st.session_state: st.session_state["nav_radio"] = "Visão Geral (Cockpit)"

escolha_visao = st.radio(
    "Modo de Visualização:", ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], 
    horizontal=True, key="nav_radio"
)

if escolha_visao == "Visão Geral (Cockpit)":
    st.title("📌 Cockpit de Projetos")
    hoje = pd.Timestamp.today().normalize()
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    
    total = len(df_filtrado)
    pendentes = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim)]
    atrasados = pendentes[pendentes['Agendamento'] < hoje]
    
    k1, k2 = st.columns(2)
    k1.metric("Total Chamados", total)
    k2.metric("🚨 Atrasados", len(atrasados))
    st.divider()
    
    cols = st.columns(3)
    for i, proj in enumerate(lista_projetos):
        df_p = df_filtrado[df_filtrado['Projeto'] == proj]
        total_p = len(df_p)
        concluidos = len(df_p[df_p['Status'].str.lower().isin(status_fim)])
        perc = int((concluidos / total_p) * 100) if total_p > 0 else 0
        
        with cols[i % 3]:
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="margin-bottom:0px;">{proj}</h4>
                <p style="color:#666; font-size:0.9em;"><strong>{concluidos}/{total_p}</strong> prontos ({perc}%)</p>
                <progress value="{perc}" max="100" style="width:100%; height:10px;"></progress>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"🔎 Ver Lista", key=f"btn_{i}"):
                mostrar_detalhes_projeto(proj, df_filtrado)

else:
    # --- MODO OPERACIONAL ---
    c_sel, _ = st.columns([1, 2])
    with c_sel:
        if "sel_projeto" not in st.session_state:
            st.session_state["sel_projeto"] = lista_projetos[0] if lista_projetos else None
        projeto_selecionado = st.selectbox("Selecione o Projeto:", lista_projetos, key="sel_projeto")
    
    df_proj = df_filtrado[df_filtrado['Projeto'] == projeto_selecionado].copy()
    st.divider()
    
    df_proj['Agendamento_dt'] = pd.to_datetime(df_proj['Agendamento'], errors='coerce')
    df_proj['Agendamento_str'] = df_proj['Agendamento_dt'].dt.strftime('%d/%m/%y').fillna("-")
    
    chave_agrupamento = ['Nome Agência', 'Serviço', 'Agendamento_str']
    grupos = df_proj.groupby(chave_agrupamento)
    grupos_lista = list(grupos)
    
    if not grupos_lista: st.info("Nenhum chamado encontrado.")
    else:
        for (nome_agencia, nome_servico, data_str), df_grupo in grupos_lista:
            first_row = df_grupo.iloc[0]
            ids_chamados = df_grupo['ID'].tolist()
            
            status_atual = clean_val(first_row.get('Status'), "NÃO INICIADA")
            acao_atual = clean_val(first_row.get('Sub-Status'), "")
            analista = clean_val(first_row.get('Analista'), "").upper()
            gestor = clean_val(first_row.get('Gestor'), "").upper()
            
            sla_html = ""
            prazo_val = _to_date_safe(first_row.get('Prazo'))
            if prazo_val:
                hoje = date.today(); dias = (prazo_val - hoje).days
                cor_sla = "#D32F2F" if dias < 0 else "#388E3C"
                txt_sla = f"{abs(dias)}d atrasado" if dias < 0 else f"{dias}d restantes"
                sla_html = f"<span style='color:{cor_sla}; font-weight:bold; font-size:0.9em;'>SLA: {txt_sla}</span>"

            with st.container(border=True):
                st.markdown("""<div style="height: 3px; background-color: #D4AF37; margin-bottom: 8px; border-radius: 2px;"></div>""", unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns([1, 2, 3, 2])
                with c1: st.markdown(f"🗓️ **{data_str}**")
                with c2: st.markdown(f"<span style='color:#555; font-size:0.85em;'>Analista:</span> <span style='color:#555;'>{analista}</span>", unsafe_allow_html=True)
                with c3: 
                    cod_ag = str(first_row.get('Cód. Agência', '')).split('.')[0]
                    nome_ag = str(nome_agencia).replace(cod_ag, '').strip(' -')
                    st.markdown(f"<span style='color:#555; font-size:0.85em;'>Agência:</span> <span style='color:#555;'>AG {cod_ag} {nome_ag}</span>", unsafe_allow_html=True)
                with c4: st.markdown(f"""<div class="card-status-badge">{status_atual}</div>""", unsafe_allow_html=True)

                c5, c6, c7, c8 = st.columns([3, 1.5, 1.5, 2])
                with c5: st.markdown(f"<div style='color:#0D47A1; font-weight:bold; font-size:1rem; text-transform:uppercase;'>{nome_servico}</div>", unsafe_allow_html=True)
                with c6: st.markdown(sla_html, unsafe_allow_html=True)
                with c7: 
                    if gestor: st.markdown(f"<span style='color:#C2185B; font-weight:bold; font-size:0.85em;'>Gestor: {gestor}</span>", unsafe_allow_html=True)
                with c8:
                    if str(acao_atual).lower() == "faturado": st.markdown("<div style='text-align:right; color:#2E7D32; font-weight:bold; font-size:0.85em;'>✔️ FATURADO</div>", unsafe_allow_html=True)
                    elif acao_atual: st.markdown(f"<div style='text-align:right; color:#004D40; font-weight:bold; font-size:0.75em; text-transform:uppercase;'>{acao_atual}</div>", unsafe_allow_html=True)

                with st.expander(f" >  Ver/Editar Detalhes - ID: {first_row['ID']}"):
                    form_key = f"form_{first_row['ID']}"
                    with st.form(key=form_key):
                        c1, c2, c3, c4 = st.columns(4)
                        status_opts = ["(Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
                        idx_st = status_opts.index(status_atual) if status_atual in status_opts else 0
                        novo_status = c1.selectbox("Status", status_opts, index=idx_st, key=f"st_{form_key}")
                        
                        abert_val = _to_date_safe(first_row.get('Abertura')) or date.today()
                        nova_abertura = c2.date_input("Abertura", value=abert_val, format="DD/MM/YYYY", key=f"ab_{form_key}")
                        agend_val = _to_date_safe(first_row.get('Agendamento'))
                        novo_agend = c3.date_input("Agendamento", value=agend_val, format="DD/MM/YYYY", key=f"ag_{form_key}")
                        fim_val = _to_date_safe(first_row.get('Fechamento'))
                        novo_fim = c4.date_input("Finalização", value=fim_val, format="DD/MM/YYYY", key=f"fim_{form_key}")

                        c5, c6, c7 = st.columns(3)
                        novo_analista = c5.text_input("Analista", value=first_row.get('Analista', ''), key=f"ana_{form_key}")
                        novo_gestor = c6.text_input("Gestor", value=first_row.get('Gestor', ''), key=f"ges_{form_key}")
                        novo_tec = c7.text_input("Técnico", value=first_row.get('Técnico', ''), key=f"tec_{form_key}")

                        c8, c9, c10 = st.columns(3)
                        proj_list_local = sorted(df_filtrado['Projeto'].unique().tolist())
                        proj_val = first_row.get('Projeto', '')
                        idx_proj = proj_list_local.index(proj_val) if proj_val in proj_list_local else 0
                        novo_projeto = c8.selectbox("Projeto", proj_list_local, index=idx_proj, key=f"proj_{form_key}")
                        novo_servico = c9.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"serv_{form_key}")
                        novo_sistema = c10.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"sis_{form_key}")

                        obs_val = first_row.get('Observações e Pendencias', '')
                        nova_obs = st.text_area("Observações", value=obs_val, height=100, key=f"obs_{form_key}")

                        st.markdown("##### 🔗 Links e Protocolos")
                        c11, c12, c13 = st.columns([1, 2, 1])
                        chamado_num = str(first_row.get('Nº Chamado', ''))
                        link_atual = first_row.get('Link Externo', '')
                        with c11:
                            st.caption("Acesso")
                            if pd.notna(link_atual) and str(link_atual).startswith('http'): st.link_button(f"🔗 {chamado_num}", link_atual, use_container_width=True)
                            else: st.text_input("Nº", value=chamado_num, disabled=True, key=f"d_{form_key}", label_visibility="collapsed")
                        
                        if pd.isna(link_atual): link_atual = ""
                        novo_link = c12.text_input("Link", value=link_atual, key=f"lnk_{form_key}")
                        proto_val = first_row.get('Nº Protocolo', '')
                        novo_proto = c13.text_input("Protocolo", value=proto_val if pd.notna(proto_val) else "", key=f"prot_{form_key}")

                        st.markdown("---")
                        st.markdown("##### 📦 Descrição")
                        desc_texto_final = ""
                        nome_serv_lower = str(nome_servico).lower().strip()
                        if nome_serv_lower in SERVICOS_SEM_EQUIPAMENTO: desc_texto_final = f"Realizar {nome_servico}"
                        else:
                            itens = []
                            for sys, df_sys in df_grupo.groupby('Sistema'):
                                sys_clean = clean_val(sys, "Sistema Geral"); itens.append(f"**{sys_clean}**")
                                for _, row_eq in df_sys.iterrows():
                                    qtd = row_eq.get('Qtd.', 0); equip = row_eq.get('Equipamento', 'Indefinido')
                                    itens.append(f"- {qtd}x {equip}"); itens.append("")
                            desc_texto_final = "<br>".join(itens)
                        st.markdown(f"<div style='background-color:#f5f5f5; padding:10px; font-size:0.9rem; max-height:200px; overflow-y:auto;'>{desc_texto_final}</div>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_salvar = st.form_submit_button("💾 Salvar", use_container_width=True)
                    
                    if btn_salvar:
                        updates = {
                            "Data Abertura": nova_abertura, "Data Agendamento": novo_agend, "Data Finalização": novo_fim,
                            "Analista": novo_analista, "Gestor": novo_gestor, "Técnico": novo_tec,
                            "Projeto": novo_projeto, "Serviço": novo_servico, "Sistema": novo_sistema,
                            "Observações e Pendencias": nova_obs, "Link Externo": novo_link, "Nº Protocolo": novo_proto
                        }
                        recalcular = False
                        if novo_status != "(Automático)":
                            updates["Status"] = novo_status
                            if novo_status in ["Cancelado", "Pausado"]: updates["Sub-Status"] = ""
                            recalcular = False
                            if novo_status == "Finalizado" and novo_fim is None: st.error("Data Finalização obrigatória!"); st.stop()
                        else: recalcular = True
                        
                        with st.spinner("Salvando..."):
                            count = 0
                            for cid in ids_chamados:
                                if utils_chamados.atualizar_chamado_db(cid, updates): count += 1
                            if count > 0:
                                st.success("Salvo!")
                                st.cache_data.clear()
                                if recalcular:
                                    df_all = utils_chamados.carregar_chamados_db()
                                    df_target = df_all[df_all['ID'].isin(ids_chamados)]
                                    calcular_e_atualizar_status_projeto(df_target, ids_chamados)
                                    st.cache_data.clear()
                                time.sleep(0.5); st.rerun()
                            else: st.error("Erro ao salvar.")

