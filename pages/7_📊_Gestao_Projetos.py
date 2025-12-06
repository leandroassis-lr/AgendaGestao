import streamlit as st
import pandas as pd
import utils_chamados
from datetime import date, timedelta, datetime
import time
import html
import math

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS E ESTILOS ---
st.markdown("""
    <style>
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
        
        .card-status-badge { 
            background-color: #B0BEC5; color: white !important; padding: 6px 12px; border-radius: 8px; 
            font-weight: bold; font-size: 0.85em; display: flex; justify-content: center; align-items: center; 
            width: 100%; text-transform: uppercase; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .card-action-text { 
            text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 8px; 
            color: #1565C0; background-color: #E3F2FD; padding: 6px; border-radius: 5px; border: 1px solid #BBDEFB;
        }
        .project-card [data-testid="stExpander"] { border: 1px solid #eee; border-radius: 8px; margin-top: 10px; background-color: #f9f9f9; }
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
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan"]: return default
    return str(val)

# --- O CÉREBRO (Lógica de Status) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0]
    
    def has_val(col):
        return col in row and pd.notna(row[col]) and str(row[col]).strip() != ""

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
    else:
        novo_status = "Não Iniciado"; novo_acao = "Verificar Cadastro"

    if status_atual != novo_status or sub_status_atual != novo_acao:
        st.toast(f"🔄 Atualizando status para: {novo_status}", icon="⚙️")
        updates = {"Status": novo_status, "Sub-Status": novo_acao}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

# --- FUNÇÃO DO POP-UP (LAYOUT PREMIUM) ---
@st.dialog("Resumo Executivo", width="large")
def mostrar_detalhes_projeto(nome_projeto, df_origem):
    # 1. Cabeçalho Estilizado
    st.markdown(f"""
        <div style="
            background-color: #F8F9FA; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 5px solid #1E88E5; 
            margin-bottom: 20px;
        ">
            <h3 style="margin: 0; color: #333; font-family: sans-serif;">📂 {nome_projeto}</h3>
            <div style="color: #666; font-size: 0.9em; margin-top: 5px;">Visão sintética de status e responsáveis.</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Preparação dos Dados
    df_p = df_origem[df_origem['Projeto'] == nome_projeto].copy()
    
    def unificar_agencia(row):
        cod = str(row.get('Cód. Agência', '')).split('.')[0]
        nome = str(row.get('Nome Agência', '')).strip()
        # Trata casos de 'nan' ou vazios
        if cod.lower() in ['nan', 'none', '']: cod = "?"
        return f"{cod} - {nome}"

    df_p['Agência'] = df_p.apply(unificar_agencia, axis=1)
    
    # Converte para datetime real para o st.dataframe formatar bonito
    df_p['Agendamento'] = pd.to_datetime(df_p['Agendamento'], errors='coerce')
    
    # Tratamento de Nulos para visualização
    df_p['Analista'] = df_p['Analista'].fillna("-")
    df_p['Status'] = df_p['Status'].fillna("Não Iniciado")

    # 2. Métricas de Topo (KPIs)
    total = len(df_p)
    # Lista de status considerados "Prontos"
    status_ok = ['concluído', 'finalizado', 'faturado', 'fechado']
    concluidos = len(df_p[df_p['Status'].str.lower().isin(status_ok)])
    pendentes = total - concluidos
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Agências", total, border=True)
    c2.metric("✅ Concluídos", concluidos, border=True)
    c3.metric("⏳ Pendentes", pendentes, border=True)

    st.divider()

    # 3. Tabela Configurada
    cols_view = ['Agência', 'Agendamento', 'Status', 'Analista']
    
    st.dataframe(
        df_p[cols_view],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Agência": st.column_config.TextColumn(
                "Agência / Unidade",
                width="medium",
                help="Código e Nome da Agência"
            ),
            "Agendamento": st.column_config.DateColumn(
                "Data Agendada",
                format="DD/MM/YYYY",  # Formato brasileiro
                width="small"
            ),
            "Status": st.column_config.TextColumn(
                "Status Atual",
                width="small"
            ),
            "Analista": st.column_config.TextColumn(
                "Analista",
                width="small"
            )
        }
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. Botão de Ação (Destacado)
    col_l, col_btn = st.columns([2, 2])
    with col_btn:
        # Estilo CSS inline para o botão parecer "Principal"
        if st.button("🛠️ Gerenciar / Editar Projeto ➤", use_container_width=True, type="primary"):
            st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"
            st.session_state["sel_projeto"] = nome_projeto
            st.rerun()
            
# --- CARREGAMENTO DE DADOS ---
df = utils_chamados.carregar_chamados_db()
if df.empty: st.warning("Sem dados."); st.stop()

# --- BARRA LATERAL ---
st.sidebar.header("🎯 Filtros de Gestão")
filtro_analista = st.sidebar.selectbox("Analista", ["Todos"] + sorted(df['Analista'].dropna().unique().tolist()))
filtro_gestor = st.sidebar.selectbox("Gestor", ["Todos"] + sorted(df['Gestor'].dropna().unique().tolist()))

df_filtrado = df.copy()
if filtro_analista != "Todos": df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
if filtro_gestor != "Todos": df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]

lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())

# --- NAVEGAÇÃO PRINCIPAL (COM KEY PARA CONTROLE EXTERNO) ---
if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = "Visão Geral (Cockpit)"

escolha_visao = st.radio(
    "Modo de Visualização:", 
    ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], 
    horizontal=True,
    key="nav_radio" # <--- Importante para navegação funcionar
)

if escolha_visao == "Visão Geral (Cockpit)":
    st.title("📌 Cockpit de Projetos")
    
    hoje = pd.Timestamp.today().normalize()
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    
    total = len(df_filtrado)
    pendentes = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim)]
    atrasados = pendentes[pendentes['Agendamento'] < hoje]
    prox = pendentes[(pendentes['Agendamento'] >= hoje) & (pendentes['Agendamento'] <= hoje + timedelta(days=5))]
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Chamados", total)
    k2.metric("🚨 Atrasados", len(atrasados))
    k3.metric("📅 Vencendo (5 dias)", len(prox))
    st.divider()
    
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
                    {'<div class="alert-box">⚠️ '+str(atrasados_p)+' Atrasados</div>' if atrasados_p > 0 else '<div class="success-box">✅ Em dia</div>'}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"🔎 Ver Lista", key=f"btn_{i}"):
                mostrar_detalhes_projeto(proj, df_filtrado)

else:
    # --- MODO OPERACIONAL (ANTIGA PÁGINA 7) ---
    col_sel, col_rest = st.columns([1, 2])
    with col_sel:
        # Selectbox com KEY para permitir pré-seleção
        if "sel_projeto" not in st.session_state:
            st.session_state["sel_projeto"] = lista_projetos[0] if lista_projetos else None
            
        projeto_selecionado = st.selectbox(
            "Selecione o Projeto para Trabalhar:", 
            lista_projetos,
            key="sel_projeto" # <--- Importante
        )
    
    df_proj = df_filtrado[df_filtrado['Projeto'] == projeto_selecionado].copy()
    
    st.divider()
    
    df_proj['Agendamento_str'] = pd.to_datetime(df_proj['Agendamento']).dt.strftime('%d/%m/%Y').fillna("Sem Data")
    
    chave_agrupamento = ['Nome Agência', 'Serviço', 'Agendamento_str']
    grupos = df_proj.groupby(chave_agrupamento)
    
    st.markdown(f"### 📋 Gerenciamento: {projeto_selecionado} ({len(df_proj)} chamados)")
    
    grupos_lista = list(grupos)
    TOTAL_GRUPOS = len(grupos_lista)
    
    if TOTAL_GRUPOS == 0:
        st.info("Nenhum chamado encontrado neste projeto com os filtros atuais.")
    else:
        # --- LOOP DOS GRUPOS (CARDS) ---
        for (nome_agencia, nome_servico, data_str), df_grupo in grupos_lista:
            first_row = df_grupo.iloc[0]
            ids_chamados = df_grupo['ID'].tolist()
            
            # Variáveis Visuais
            status_atual = clean_val(first_row.get('Status'), "Não Iniciado")
            acao_atual = clean_val(first_row.get('Sub-Status'), "")
            cor_status = utils_chamados.get_status_color(status_atual)
            analista = clean_val(first_row.get('Analista'), "N/D").upper()
            gestor = clean_val(first_row.get('Gestor'), "N/D").upper()
            
            # SLA
            sla_texto = ""; sla_cor = "#333"
            prazo_val = _to_date_safe(first_row.get('Prazo'))
            if prazo_val:
                hoje = date.today(); dias_restantes = (prazo_val - hoje).days
                if dias_restantes < 0: sla_texto = f"SLA: {abs(dias_restantes)}d atrasado"; sla_cor = "#D32F2F"
                else: sla_texto = f"SLA: {dias_restantes}d restantes"; sla_cor = "#388E3C"
            
            # --- CARD ---
            with st.container(border=True):
                st.markdown("""<div style="height: 4px; background-color: #D4AF37; margin-bottom: 12px; border-radius: 2px;"></div>""", unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns([1.2, 2, 3, 2])
                with c1: st.markdown(f"🗓️ **{data_str}**")
                with c2: st.markdown(f"<span style='color:#555; font-size:0.9em;'>Analista:</span> <span style='color:#1565C0; font-weight:500;'>{analista}</span>", unsafe_allow_html=True)
                with c3:
                    cod_ag = str(first_row.get('Cód. Agência', '')).split('.')[0]
                    nome_ag = str(nome_agencia).replace(cod_ag, '').strip(' -')
                    st.markdown(f"<span style='color:#555; font-size:0.9em;'>Agência:</span> **AG {cod_ag} {nome_ag}**", unsafe_allow_html=True)
                with c4: st.markdown(f"""<div class="card-status-badge" style="background-color: {cor_status}; margin-bottom: 5px;">{status_atual}</div>""", unsafe_allow_html=True)

                c5, c6, c7, c8 = st.columns([2.5, 1.5, 2, 2])
                with c5: st.markdown(f"<div style='color:#0D47A1; font-weight:bold; font-size:1.1em; text-transform:uppercase;'>{nome_servico}</div>", unsafe_allow_html=True)
                with c6:
                    if sla_texto: st.markdown(f"<span style='color:{sla_cor}; font-weight:bold; font-size:0.9em;'>{sla_texto}</span>", unsafe_allow_html=True)
                with c7: st.markdown(f"<span style='color:#555; font-size:0.9em;'>Gestor:</span> <span style='color:#C2185B; font-weight:bold;'>{gestor}</span>", unsafe_allow_html=True)
                with c8:
                    if str(acao_atual).lower() == "faturado": st.markdown("<div style='text-align:center; color:#2E7D32; font-weight:bold;'>✔️ FATURADO</div>", unsafe_allow_html=True)
                    elif acao_atual: st.markdown(f"<div style='text-align:center; color:#004D40; font-weight:bold; font-size:0.85em; text-transform:uppercase;'>{acao_atual}</div>", unsafe_allow_html=True)

                # --- FORMULÁRIO ---
                with st.expander(f" >  Ver/Editar Detalhes - ID: {first_row['ID']}"):
                    form_key = f"form_{first_row['ID']}"
                    with st.form(key=form_key):
                        
                        # L1: Status | Abertura | Agendamento | Finalização
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

                        # L2: Analista | Gestor | Técnico
                        c5, c6, c7 = st.columns(3)
                        novo_analista = c5.text_input("Analista", value=first_row.get('Analista', ''), key=f"ana_{form_key}")
                        novo_gestor = c6.text_input("Gestor", value=first_row.get('Gestor', ''), key=f"ges_{form_key}")
                        novo_tec = c7.text_input("Técnico", value=first_row.get('Técnico', ''), key=f"tec_{form_key}")

                        # L3: Projeto | Serviço | Sistema
                        c8, c9, c10 = st.columns(3)
                        proj_val = first_row.get('Projeto', '')
                        proj_list_local = sorted(df_filtrado['Projeto'].unique().tolist())
                        idx_proj = proj_list_local.index(proj_val) if proj_val in proj_list_local else 0
                        novo_projeto = c8.selectbox("Nome do Projeto", proj_list_local, index=idx_proj, key=f"proj_{form_key}")
                        novo_servico = c9.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"serv_{form_key}")
                        novo_sistema = c10.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"sis_{form_key}")

                        # L4: Observações
                        obs_val = first_row.get('Observações e Pendencias', '')
                        nova_obs = st.text_area("Observações e Pendências", value=obs_val, height=100, key=f"obs_{form_key}")

                        # L5: Links e Protocolos
                        st.markdown("##### 🔗 Links e Protocolos")
                        c11, c12, c13 = st.columns([1, 2, 1])
                        chamado_num = str(first_row.get('Nº Chamado', ''))
                        link_atual = first_row.get('Link Externo', '')
                        
                        with c11:
                            st.caption("Nº Chamado (Acesso)")
                            if pd.notna(link_atual) and str(link_atual).startswith('http'):
                                st.link_button(f"🔗 {chamado_num}", link_atual, use_container_width=True)
                            else:
                                st.text_input("Chamado", value=chamado_num, disabled=True, label_visibility="collapsed", key=f"dis_ch_{form_key}")

                        if pd.isna(link_atual): link_atual = ""
                        novo_link = c12.text_input("Link Externo (Cole aqui)", value=link_atual, key=f"lnk_{form_key}")
                        
                        proto_val = first_row.get('Nº Protocolo', '')
                        if pd.isna(proto_val): proto_val = ""
                        novo_proto = c13.text_input("Nº Protocolo", value=proto_val, key=f"prot_{form_key}")

                        # L6: Descrição
                        st.markdown("---")
                        st.markdown("##### 📦 Descrição (Equipamentos do Projeto)")
                        desc_texto_final = ""
                        nome_serv_lower = str(nome_servico).lower().strip()
                        
                        if nome_serv_lower in SERVICOS_SEM_EQUIPAMENTO:
                            desc_texto_final = f"Realizar {nome_servico}"
                        else:
                            itens_desc = []
                            for sys, df_sys in df_grupo.groupby('Sistema'):
                                sys_clean = clean_val(sys, "Sistema Geral")
                                itens_desc.append(f"**{sys_clean}**")
                                for _, row_eq in df_sys.iterrows():
                                    qtd = row_eq.get('Qtd.', 0)
                                    equip = row_eq.get('Equipamento', 'Indefinido')
                                    itens_desc.append(f"- {qtd}x {equip}")
                                itens_desc.append("")
                            desc_texto_final = "<br>".join(itens_desc)

                        st.markdown(f"<div style='background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 5px; padding: 10px; font-size: 0.9rem; max-height: 200px; overflow-y: auto;'>{desc_texto_final}</div>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        btn_salvar = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                    
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
                            if novo_status == "Finalizado" and novo_fim is None:
                                st.error("Data Finalização obrigatória!"); st.stop()
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
                                time.sleep(0.5)
                                st.rerun()
                            else: st.error("Erro ao salvar.")

