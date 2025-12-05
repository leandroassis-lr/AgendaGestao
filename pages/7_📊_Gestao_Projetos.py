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

# Lista de Exceções (Para lógica automática)
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

# --- FUNÇÃO DO POP-UP RESUMO ---
@st.dialog("Resumo do Projeto", width="large")
def mostrar_detalhes_projeto(nome_projeto, df_origem):
    st.markdown(f"**Projeto:** {nome_projeto}")
    df_p = df_origem[df_origem['Projeto'] == nome_projeto].copy()
    
    def unificar_agencia(row):
        cod = str(row.get('Cód. Agência', '')).split('.')[0]
        nome = str(row.get('Nome Agência', '')).strip()
        return f"{cod} - {nome}"
    df_p['Agência'] = df_p.apply(unificar_agencia, axis=1)
    df_p['Agendamento'] = pd.to_datetime(df_p['Agendamento']).dt.strftime('%d/%m/%Y').fillna("-")
    
    cols = ['Agência', 'Agendamento', 'Status', 'Analista']
    st.dataframe(df_p[[c for c in cols if c in df_p.columns]], use_container_width=True, hide_index=True)
    st.caption("Para editar, mude para 'Detalhar um Projeto'.")

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

# --- NAVEGAÇÃO PRINCIPAL ---
escolha_visao = st.radio("Modo de Visualização:", ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], horizontal=True)

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
        projeto_selecionado = st.selectbox("Selecione o Projeto para Trabalhar:", lista_projetos)
    
    df_proj = df_filtrado[df_filtrado['Projeto'] == projeto_selecionado].copy()
    
    st.divider()
    
    # Agrupamento para edição (Agência + Serviço + Data)
    # Isso simula os "Cards" da página 7, mas filtrados pelo Projeto
    df_proj['Agendamento_str'] = pd.to_datetime(df_proj['Agendamento']).dt.strftime('%d/%m/%Y').fillna("Sem Data")
    
    # Agrupamos por Agência e Serviço dentro do projeto
    chave_agrupamento = ['Nome Agência', 'Serviço', 'Agendamento_str']
    grupos = df_proj.groupby(chave_agrupamento)
    
    st.markdown(f"### 📋 Gerenciamento: {projeto_selecionado} ({len(df_proj)} chamados)")
    
    # Paginação simples se tiver muitos grupos
    grupos_lista = list(grupos)
    TOTAL_GRUPOS = len(grupos_lista)
    
    if TOTAL_GRUPOS == 0:
        st.info("Nenhum chamado encontrado neste projeto com os filtros atuais.")
    else:
        for (nome_agencia, nome_servico, data_str), df_grupo in grupos_lista:
            first_row = df_grupo.iloc[0]
            ids_chamados = df_grupo['ID'].tolist()
            
            # --- DESENHO DO CARD DE EDIÇÃO ---
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1: st.markdown(f"**🏦 {nome_agencia}**")
                with c2: st.markdown(f"📅 {data_str}")
                
                status_atual = clean_val(first_row.get('Status'), "Não Iniciado")
                acao_atual = clean_val(first_row.get('Sub-Status'), "")
                cor_status = utils_chamados.get_status_color(status_atual)
                
                with c3:
                    st.markdown(f"""<div class="card-status-badge" style="background-color: {cor_status};">{status_atual}</div>""", unsafe_allow_html=True)
                
                # Linha 2: Serviço e Ação
                c4, c5 = st.columns([3, 2])
                with c4: st.caption(f"Serviço: {nome_servico}")
                with c5:
                    if str(acao_atual).lower() == "faturado":
                        st.markdown("<strong style='color:#2E7D32'>✔️ Faturado</strong>", unsafe_allow_html=True)
                    elif acao_atual:
                        st.markdown(f"<div class='card-action-text'>{acao_atual}</div>", unsafe_allow_html=True)

                # --- FORMULÁRIO DE EDIÇÃO (EXPANDER) ---
                with st.expander(f"✏️ Editar {len(df_grupo)} chamado(s)"):
                    form_key = f"form_{first_row['ID']}"
                    with st.form(key=form_key):
                        st.markdown("##### Dados Gerais")
                        col_a, col_b = st.columns(2)
                        
                        status_opts = ["(Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
                        idx_st = 0
                        if status_atual in status_opts: idx_st = status_opts.index(status_atual)
                        
                        novo_status = col_a.selectbox("Status Manual", status_opts, index=idx_st, key=f"st_{form_key}")
                        
                        dt_ag_orig = _to_date_safe(first_row.get('Agendamento'))
                        novo_agend = col_b.date_input("Agendamento", value=dt_ag_orig, format="DD/MM/YYYY", key=f"ag_{form_key}")
                        
                        st.markdown("##### Financeiro e Conclusão")
                        col_c, col_d = st.columns(2)
                        dt_fim_orig = _to_date_safe(first_row.get('Fechamento'))
                        novo_fim = col_c.date_input("Data Finalização", value=dt_fim_orig, format="DD/MM/YYYY", key=f"fim_{form_key}")
                        
                        tecnico_val = first_row.get('Técnico', '')
                        novo_tec = col_d.text_input("Técnico", value=tecnico_val, key=f"tec_{form_key}")
                        
                        obs_val = first_row.get('Observações e Pendencias', '')
                        nova_obs = st.text_area("Observações", value=obs_val, height=70, key=f"obs_{form_key}")
                        
                        btn_salvar = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                    
                    if btn_salvar:
                        updates = {
                            "Data Agendamento": novo_agend,
                            "Data Finalização": novo_fim,
                            "Técnico": novo_tec,
                            "Observações e Pendencias": nova_obs
                        }
                        
                        recalcular = False
                        if novo_status != "(Automático)":
                            updates["Status"] = novo_status
                            updates["Sub-Status"] = ""
                            recalcular = False
                            if novo_status == "Finalizado" and novo_fim is None:
                                st.error("Data Finalização obrigatória para Finalizado!")
                                st.stop()
                        else:
                            recalcular = True
                        
                        with st.spinner("Salvando..."):
                            count = 0
                            for cid in ids_chamados:
                                if utils_chamados.atualizar_chamado_db(cid, updates): count += 1
                            
                            if count > 0:
                                st.success("Salvo!")
                                st.cache_data.clear()
                                if recalcular:
                                    # Recalcula lógica automática
                                    df_all = utils_chamados.carregar_chamados_db()
                                    df_target = df_all[df_all['ID'].isin(ids_chamados)]
                                    calcular_e_atualizar_status_projeto(df_target, ids_chamados)
                                    st.cache_data.clear()
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("Erro ao salvar.")
