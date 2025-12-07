import streamlit as st
import pandas as pd
import utils_chamados
import plotly.express as px
from datetime import date, timedelta, datetime
import time
import html
import math
import utils

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
        
        /* Ajuste para os cards de status em grid */
        .status-mini-card {
            background-color: white; 
            border: 1px solid #eee; 
            border-radius: 8px; 
            padding: 10px; 
            margin-bottom: 10px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05); 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
        }
    </style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURAÇÕES E CONSTANTES ---

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

# --- 2. FUNÇÕES DE IMPORTAÇÃO ---

@st.dialog("📥 Importar Chamados (Geral)", width="large")
def run_importer_dialog():
    st.info("Arraste o Template Padrão.")
    
    uploaded_files = st.file_uploader("Selecione arquivos", type=["xlsx", "csv"], accept_multiple_files=True, key="up_imp_geral")
    
    if uploaded_files:
        dfs = []
        for up in uploaded_files:
            try:
                # --- LEITURA ROBUSTA (CORREÇÃO DE ENCODING) ---
                if up.name.endswith('.csv'): 
                    # 'utf-8-sig' é o segredo: ele remove o caractere invisível do Excel
                    try:
                        df = pd.read_csv(up, sep=';', dtype=str, encoding='utf-8-sig')
                        # Se falhar (ex: tudo em uma coluna só), tenta vírgula
                        if len(df.columns) <= 1:
                            up.seek(0)
                            df = pd.read_csv(up, sep=',', dtype=str, encoding='utf-8-sig')
                    except:
                        # Última tentativa: encoding windows padrão Brasil
                        up.seek(0)
                        df = pd.read_csv(up, sep=';', dtype=str, encoding='latin1')
                else: 
                    df = pd.read_excel(up, dtype=str)
                
                dfs.append(df)
            except Exception as e: st.error(f"Erro no arquivo {up.name}: {e}")
        
        if dfs:
            try:
                df_raw = pd.concat(dfs, ignore_index=True)
                
                # --- 1. LIMPEZA E PADRONIZAÇÃO DE COLUNAS ---
                # Função para limpar caracteres estranhos (BOM, espaços, etc)
                def limpar_header(col):
                    col = str(col).strip().upper()
                    # Remove caracteres não imprimíveis do começo (o erro fantasma)
                    col = col.replace('\ufeff', '').replace('"', '').replace("'", "")
                    return col

                df_raw.columns = [limpar_header(c) for c in df_raw.columns]
                
                # Mapeamento (Adicionei variações de Nº e N° para garantir)
                mapa_colunas = {
                    'CHAMADO': 'Nº Chamado',
                    'N° AGENCIA': 'Cód. Agência', 'Nº AGENCIA': 'Cód. Agência', 'AGENCIA': 'Cód. Agência',
                    'NÂº AGENCIA': 'Cód. Agência', # Corrige erro de acentuação comum
                    'ANALISTA': 'Analista', 'GESTOR': 'Gestor',
                    'SERVIÇO': 'Serviço', 'SERVICO': 'Serviço', 'TIPO DO SERVIÇO': 'Serviço',
                    'STATUS': 'Status',
                    'DATA ABERTURA': 'Abertura', 'DATA AGENDAMENTO': 'Agendamento', 'AGENDAMENTO': 'Agendamento',
                    'DATA PRAZO': 'Prazo',
                    'DESCRIÇÃO': 'Sistema', 'EQUIPAMENTO': 'Sistema', 'SISTEMA': 'Sistema',
                    'OBSERVAÇÃO': 'Observações e Pendencias', 'QUANTIDADE': 'Qtd', 'QTD': 'Qtd'
                }
                
                df_raw = df_raw.rename(columns=mapa_colunas)
                
                # Diagnóstico Rápido se falhar
                if 'Nº Chamado' not in df_raw.columns:
                    st.error("❌ Erro: Coluna 'CHAMADO' não encontrada.")
                    st.write("Colunas identificadas no arquivo:", df_raw.columns.tolist())
                    return

                # Tratamento de vazios
                for col in ['Sistema', 'Observações e Pendencias', 'Qtd']:
                    if col not in df_raw.columns: df_raw[col] = ""
                df_raw = df_raw.fillna("")

                # --- 2. PRÉ-PROCESSAMENTO (FORMATAR ITEM) ---
                def formatar_item(row):
                    qtd = str(row['Qtd']).strip()
                    desc = str(row['Sistema']).strip()
                    if not desc: return ""
                    if qtd and qtd != "0" and qtd.lower() != "nan":
                        return f"{qtd}x {desc}"
                    return desc

                df_raw['Item_Formatado'] = df_raw.apply(formatar_item, axis=1)

                # --- 3. AGRUPAMENTO ---
                def juntar_textos(lista):
                    # Filtra vazios e duplicados exatos na string final
                    textos = [str(s) for s in lista if str(s).strip()]
                    return " | ".join(dict.fromkeys(textos)) # Remove duplicados mantendo ordem

                # Removemos colunas que vamos agrupar da lista de 'first'
                cols_agrupar = ['Sistema', 'Qtd', 'Observações e Pendencias', 'Item_Formatado']
                regras = {c: 'first' for c in df_raw.columns if c not in cols_agrupar}
                
                regras['Item_Formatado'] = juntar_textos
                regras['Observações e Pendencias'] = juntar_textos

                df_grouped = df_raw.groupby('Nº Chamado', as_index=False).agg(regras)
                df_grouped = df_grouped.rename(columns={'Item_Formatado': 'Sistema'})
                
                # --- 4. SEPARAÇÃO (NOVOS vs ATUALIZAR) ---
                df_banco = utils_chamados.carregar_chamados_db()
                lista_novos = []; lista_atualizar = []
                
                if not df_banco.empty:
                    mapa_ids = dict(zip(df_banco['Nº Chamado'].astype(str).str.strip(), df_banco['ID']))
                    for _, row in df_grouped.iterrows():
                        chamado_num = str(row['Nº Chamado']).strip()
                        if chamado_num in mapa_ids:
                            row['ID_Banco'] = mapa_ids[chamado_num]
                            lista_atualizar.append(row)
                        else:
                            lista_novos.append(row)
                else:
                    for _, row in df_grouped.iterrows(): lista_novos.append(row)

                df_insert = pd.DataFrame(lista_novos)
                df_update = pd.DataFrame(lista_atualizar)

                # --- 5. EXIBIÇÃO ---
                c1, c2 = st.columns(2)
                c1.metric("🆕 Novos", len(df_insert))
                c2.metric("🔄 Atualizar", len(df_update))
                
                if st.button("🚀 Processar Importação"):
                    bar = st.progress(0)
                    status_text = st.empty()
                    
                    if not df_insert.empty:
                        status_text.text("Inserindo...")
                        utils_chamados.bulk_insert_chamados_db(df_insert)
                        bar.progress(50)
                    
                    if not df_update.empty:
                        status_text.text("Atualizando...")
                        total_up = len(df_update)
                        for i, row in enumerate(df_update.iterrows()):
                            idx, dados = row
                            updates = {
                                'Sistema': dados['Sistema'],
                                'Observações e Pendencias': dados['Observações e Pendencias'],
                                'Status': dados['Status']
                            }
                            utils_chamados.atualizar_chamado_db(dados['ID_Banco'], updates)
                            if total_up > 0: bar.progress(50 + int((i / total_up) * 50))
                    
                    bar.progress(100)
                    st.success("Sucesso!")
                    time.sleep(1.5)
                    st.cache_data.clear()
                    st.rerun()

            except Exception as e: st.error(f"Erro crítico: {e}")
                
@st.dialog("🔗 Importar Links", width="medium")
def run_link_importer_dialog():
    st.info("Planilha simples com colunas: **CHAMADO** e **LINK**.")
    up = st.file_uploader("Arquivo (.xlsx/.csv)", type=["xlsx", "csv"], key="up_imp_link")
    
    if up and st.button("🚀 Atualizar Links"):
        try:
            if up.name.endswith('.csv'): 
                df = pd.read_csv(up, sep=';', dtype=str)
            else: 
                df = pd.read_excel(up, dtype=str)
            
            df.columns = [str(c).upper().strip() for c in df.columns]
            
            if 'CHAMADO' not in df.columns or 'LINK' not in df.columns:
                st.error("Erro: Colunas 'CHAMADO' e 'LINK' são obrigatórias.")
            else:
                with st.spinner("Atualizando links no banco..."):
                   df_bd = utils_chamados.carregar_chamados_db()
                   id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                   
                   cnt = 0
                   for _, row in df.iterrows():
                       chamado = str(row['CHAMADO'])
                       link = str(row['LINK'])
                       if chamado in id_map and pd.notna(link) and link.strip():
                           utils_chamados.atualizar_chamado_db(id_map[chamado], {'Link Externo': link})
                           cnt += 1
                   
                   st.success(f"✅ {cnt} links atualizados com sucesso!")
                   st.cache_data.clear()
                   time.sleep(1.5)
                   st.rerun()
        except Exception as e: st.error(f"Erro: {e}")

# --- 3. LÓGICA DE STATUS ---
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

# --- 4. FUNÇÃO DO POP-UP RESUMO ---
@st.dialog("Resumo Executivo", width="large")
def mostrar_detalhes_projeto(nome_projeto, df_origem):
    st.markdown(f"""
        <div style="background-color: #F8F9FA; padding: 15px; border-radius: 8px; border-left: 5px solid #1E88E5; margin-bottom: 20px;">
            <h3 style="margin: 0; color: #333; font-family: sans-serif;">📂 {nome_projeto}</h3>
            <div style="color: #666; font-size: 0.9em; margin-top: 5px;">Visão sintética de status e responsáveis.</div>
        </div>
    """, unsafe_allow_html=True)
    
    df_p = df_origem[df_origem['Projeto'] == nome_projeto].copy()
    
    def unificar_agencia(row):
        cod = str(row.get('Cód. Agência', '')).split('.')[0]
        if cod.lower() in ['nan', 'none', '']: cod = "?"
        nome = str(row.get('Nome Agência', '')).strip()
        return f"{cod} - {nome}"

    df_p['Agência'] = df_p.apply(unificar_agencia, axis=1)
    df_p['Agendamento'] = pd.to_datetime(df_p['Agendamento'], errors='coerce')
    df_p['Analista'] = df_p['Analista'].fillna("-")
    df_p['Status'] = df_p['Status'].fillna("Não Iniciado")

    total = len(df_p)
    status_ok = ['concluído', 'finalizado', 'faturado', 'fechado']
    concluidos = len(df_p[df_p['Status'].str.lower().isin(status_ok)])
    pendentes = total - concluidos
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Agências", total, border=True)
    c2.metric("✅ Concluídos", concluidos, border=True)
    c3.metric("⏳ Pendentes", pendentes, border=True)

    st.divider()
    cols_view = ['Agência', 'Agendamento', 'Status', 'Analista']
    st.dataframe(
        df_p[cols_view],
        use_container_width=True, hide_index=True,
        column_config={
           "Agência": st.column_config.TextColumn("Agência / Unidade", width="medium"),
            "Agendamento": st.column_config.DateColumn("Data Agendada", format="DD/MM/YYYY", width="small"),
            "Status": st.column_config.TextColumn("Status Atual", width="small"),
            "Analista": st.column_config.TextColumn("Analista", width="small")
        }
    )
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_l, col_btn = st.columns([2, 2])
    with col_btn:
        if st.button("🛠️ Gerenciar / Editar Projeto ➤", use_container_width=True, type="primary"):
            st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"
            st.session_state["sel_projeto"] = nome_projeto
            st.rerun()

# --- 5. CARREGAMENTO E SIDEBAR ---
df = utils_chamados.carregar_chamados_db()

filtro_analista = "Todos"
filtro_gestor = "Todos"

# SIDEBAR
with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"):
        run_importer_dialog()
    
    if st.button("🔗 Importar Links"):
        run_link_importer_dialog()

    st.divider()
    
    st.header("Filtros de Gestão")
    lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    lista_gestores = ["Todos"] + sorted(df['Gestor'].dropna().unique().tolist())
    filtro_analista = st.selectbox("Analista", lista_analistas)
    filtro_gestor = st.selectbox("Gestor", lista_gestores)

# --- APLICAÇÃO DOS FILTROS ---
if df.empty:
    st.warning("Sem dados. Importe chamados na barra lateral.")
    st.stop()

df_filtrado = df.copy()

if filtro_analista != "Todos": 
    df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]

if filtro_gestor != "Todos": 
    df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]

lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())

# --- NAVEGAÇÃO PRINCIPAL ---

if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = "Visão Geral (Cockpit)"

escolha_visao = st.radio(
    "Modo de Visualização:", 
    ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], 
    horizontal=True,
    key="nav_radio"
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
    # --- MODO OPERACIONAL COM FILTROS AVANÇADOS ---
    st.markdown("### 🔍 Filtros Detalhados")
    
    # 1. Filtros
    col_busca, col_proj, col_status, col_data = st.columns(4)
    
    # A. Buscador Geral
    busca_geral = col_busca.text_input("Buscador Geral (Texto)")
    
    # B. Filtro por Projeto
    try:
        df_proj_cfg = utils.carregar_config_db("projetos_nomes")
        opcoes_projeto_db = df_proj_cfg.iloc[:, 0].tolist() if not df_proj_cfg.empty else []
    except: opcoes_projeto_db = []
    
    if not opcoes_projeto_db:
        opcoes_projeto_db = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
    
    # ALTERAÇÃO 1: default=[] para iniciar vazio (sem tags pré-selecionadas)
    filtro_projeto_multi = col_proj.multiselect("Projetos", options=opcoes_projeto_db, default=[])
    
    # C. Filtro por Status
    opcoes_status = sorted(df_filtrado['Status'].dropna().unique().tolist())
    # ALTERAÇÃO 1: default=[] para iniciar vazio
    filtro_status_multi = col_status.multiselect("Status", options=opcoes_status, default=[])
    
    # D. Filtro por Data
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    data_min = df_filtrado['Agendamento'].min()
    data_max = df_filtrado['Agendamento'].max()
    if pd.isna(data_min): data_min = date.today()
    if pd.isna(data_max): data_max = date.today()
    
    # ALTERAÇÃO 2: format="DD/MM/YYYY" para padronizar a exibição
    filtro_data_range = col_data.date_input(
        "Período (Agendamento)", 
        value=(data_min, data_max), 
        format="DD/MM/YYYY"
    )

    # --- APLICAR FILTROS ---
    df_view = df_filtrado.copy()
    
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[
            df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)
        ]
    
    # A lógica continua: se o filtro estiver vazio (ninguém selecionado), ele ignora e mostra tudo
    if filtro_projeto_multi: 
        df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
        
    if filtro_status_multi: 
        df_view = df_view[df_view['Status'].isin(filtro_status_multi)]
        
    if len(filtro_data_range) == 2:
        d_inicio, d_fim = filtro_data_range
        df_view = df_view[(df_view['Agendamento'] >= pd.to_datetime(d_inicio)) & (df_view['Agendamento'] <= pd.to_datetime(d_fim))]

    st.divider()
    
    # 2. KPIs SUPERIORES
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

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Chamados (Filtro)", kpi_qtd_chamados)
    col_k2.metric("Projetos Abertos", kpi_proj_abertos)
    col_k3.metric("Projetos Finalizados", proj_fin_count)
    col_k4.metric("Chamados Finalizados", kpi_chamados_fin)
    
    st.divider()

    # 3. RESUMO POR STATUS (HORIZONTAL)
    st.subheader("Resumo por Status")
    
    if not df_view.empty:
        counts = df_view['Status'].value_counts()
        cols_status = st.columns(4)
        
        for index, (status, count) in enumerate(counts.items()):
            try: cor = utils_chamados.get_status_color(status)
            except: cor = "#90A4AE"
            
            with cols_status[index % 4]:
                st.markdown(f"""
                <div class="status-mini-card" style="border-left: 5px solid {cor};">
                    <div style="font-size: 0.8em; color: #666; text-transform: uppercase; font-weight: 600;">{status}</div>
                    <div style="font-size: 1.2em; font-weight: 700; color: #333;">{count}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Sem dados para exibir resumo de status.")
        
    st.divider()

    # --- 1. CRIAÇÃO DAS ABAS (ESSA LINHA É ESSENCIAL) ---
    aba_lista, aba_calendario = st.tabs(["📋 Lista Detalhada", "📅 Agenda Semanal"])

    # --- 2. ABA: LISTA DETALHADA ---
    with aba_lista:    
        st.markdown(f"### 📋 Detalhes ({len(df_view)} registros)")
        
        if df_view.empty:
            st.info("Sem dados para exibir.")
        else:
            df_view['Agendamento_str'] = pd.to_datetime(df_view['Agendamento']).dt.strftime('%d/%m/%Y').fillna("Sem Data")
            
            chave_agrupamento = ['Projeto', 'Nome Agência', 'Serviço', 'Agendamento_str']
            grupos = df_view.groupby(chave_agrupamento)
            grupos_lista = list(grupos)
            
            if not grupos_lista: st.info("Nenhum chamado encontrado com esses filtros.")
            else:
                for (proj_nome, nome_agencia, nome_servico, data_str), df_grupo in grupos_lista:
                    first_row = df_grupo.iloc[0]
                    ids_chamados = df_grupo['ID'].tolist()
                    status_atual = clean_val(first_row.get('Status'), "Não Iniciado")
                    acao_atual = clean_val(first_row.get('Sub-Status'), "")
                    cor_status = utils_chamados.get_status_color(status_atual)
                    analista = clean_val(first_row.get('Analista'), "N/D").upper()
                    gestor = clean_val(first_row.get('Gestor'), "N/D").upper()
                    
                    sla_texto = ""; sla_cor = "#333"
                    prazo_val = _to_date_safe(first_row.get('Prazo'))
                    if prazo_val:
                        hoje_date = date.today(); dias_restantes = (prazo_val - hoje_date).days
                        if dias_restantes < 0: sla_texto = f"SLA: {abs(dias_restantes)}d atrasado"; sla_cor = "#D32F2F"
                        else: sla_texto = f"SLA: {dias_restantes}d restantes"; sla_cor = "#388E3C"
                    
                    with st.container(border=True):
                        st.markdown(f"**{proj_nome}** | 🗓️ **{data_str}**")
                        c1, c2, c3, c4 = st.columns([1.2, 2, 3, 2])
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

                        with st.expander(f" >  Ver/Editar Detalhes - ID: {first_row['ID']}"):
                            form_key = f"form_{first_row['ID']}"
                            with st.form(key=form_key):
                                
                                # --- 1. CARREGAR LISTAS (AGORA USANDO USUÁRIOS REAIS) ---
                                try:
                                    # Carrega Status e Projetos (Configurações)
                                    df_status_cfg = utils.carregar_config_db("status")
                                    opts_status_db = [str(x) for x in df_status_cfg.iloc[:, 0].dropna().tolist()] if not df_status_cfg.empty else []
                                    
                                    df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                                    opts_proj_db = [str(x) for x in df_proj_cfg.iloc[:, 0].dropna().tolist()] if not df_proj_cfg.empty else []
                                    
                                    df_tec_cfg = utils.carregar_config_db("tecnicos")
                                    opts_tec_db = [str(x) for x in df_tec_cfg.iloc[:, 0].dropna().tolist()] if not df_tec_cfg.empty else []

                                    # --- NOVA LÓGICA: CARREGAR USUÁRIOS DO SISTEMA ---
                                    df_users = utils.carregar_usuarios_db()
                                    if not df_users.empty:
                                        df_users.columns = [col.capitalize() for col in df_users.columns]
                                    
                                    if not df_users.empty and "Nome" in df_users.columns:
                                        opts_ana_db = [str(x) for x in df_users["Nome"].dropna().tolist()]
                                    else:
                                        opts_ana_db = []
                                        
                                except:
                                    opts_status_db = []; opts_proj_db = []; opts_tec_db = []; opts_ana_db = []

                                # --- 2. PREPARAR LISTAS (Safe String e Sort) ---
                                def safe_str(val):
                                    if pd.isna(val) or str(val).lower() in ['nan', 'none', '']: return ""
                                    return str(val)

                                # Status
                                status_atual = safe_str(first_row.get('Status', '(Automático)'))
                                lista_raw_st = opts_status_db + [status_atual] + ["(Automático)", "Finalizado", "Cancelado"]
                                lista_final_status = sorted(list(set([s for s in lista_raw_st if s])))
                                idx_st = lista_final_status.index(status_atual) if status_atual in lista_final_status else 0
                                
                                # Projetos
                                val_proj_atual = safe_str(first_row.get('Projeto', ''))
                                lista_raw_proj = opts_proj_db + [val_proj_atual]
                                lista_final_proj = sorted(list(set([p for p in lista_raw_proj if p])))
                                idx_proj = lista_final_proj.index(val_proj_atual) if val_proj_atual in lista_final_proj else 0

                                # Técnico de Campo (Configuração)
                                val_tec_atual = safe_str(first_row.get('Técnico', ''))
                                lista_raw_tec = opts_tec_db + [val_tec_atual]
                                lista_final_tec = sorted(list(set([t for t in lista_raw_tec if t])))
                                idx_tec = lista_final_tec.index(val_tec_atual) if val_tec_atual in lista_final_tec else 0

                                # Analistas (Usuários Cadastrados)
                                val_ana_atual = safe_str(first_row.get('Analista', ''))
                                lista_raw_ana = opts_ana_db + [val_ana_atual]
                                lista_final_ana = sorted(list(set([a for a in lista_raw_ana if a])))
                                idx_ana = lista_final_ana.index(val_ana_atual) if val_ana_atual in lista_final_ana else 0

                                # --- 3. CAMPOS DO FORMULÁRIO ---
                                c1, c2, c3, c4 = st.columns(4)
                                
                                # Status
                                novo_status = c1.selectbox("Status", lista_final_status, index=idx_st, key=f"st_{form_key}")
                                
                                # Data Abertura (Manteve nova_abertura pois está correto no save)
                                abert_val = _to_date_safe(first_row.get('Abertura')) or date.today()
                                nova_abertura = c2.date_input("Abertura", value=abert_val, format="DD/MM/YYYY", key=f"ab_{form_key}")
                                
                                # Data Agendamento (CORRIGIDO: de nova_agend para novo_agend)
                                agend_val = _to_date_safe(first_row.get('Agendamento'))
                                novo_agend = c3.date_input("Agendamento", value=agend_val, format="DD/MM/YYYY", key=f"ag_{form_key}")
                                
                                # Data Finalização (CORRIGIDO: de nova_fim para novo_fim)
                                fim_val = _to_date_safe(first_row.get('Fechamento'))
                                novo_fim = c4.date_input("Finalização", value=fim_val, format="DD/MM/YYYY", key=f"fim_{form_key}")
        
                                # Linha 2
                                c5, c6, c7 = st.columns(3)
                                novo_analista = c5.selectbox("Analista (Usuário)", lista_final_ana, index=idx_ana, key=f"ana_{form_key}")
                                novo_gestor = c6.text_input("Gestor", value=first_row.get('Gestor', ''), key=f"ges_{form_key}")
                                novo_tec = c7.selectbox("Técnico Campo", lista_final_tec, index=idx_tec, key=f"tec_{form_key}")
        
                                # Linha 3
                                c8, c9, c10 = st.columns(3)
                                novo_projeto = c8.selectbox("Nome do Projeto", lista_final_proj, index=idx_proj, key=f"proj_{form_key}")
                                novo_servico = c9.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"serv_{form_key}")
                                novo_sistema = c10.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"sis_{form_key}")

                                obs_val = first_row.get('Observações e Pendencias', '')
                                nova_obs = st.text_area("Observações e Pendências", value=obs_val, height=100, key=f"obs_{form_key}")

                                st.markdown("##### 🔗 Links e Protocolos")
                                c11, c12, c13 = st.columns([1, 2, 1])
                                chamado_num = str(first_row.get('Nº Chamado', ''))
                                link_atual = first_row.get('Link Externo', '')
                                with c11:
                                    st.caption("Nº Chamado (Acesso)")
                                    if pd.notna(link_atual) and str(link_atual).startswith('http'): st.link_button(f"🔗 {chamado_num}", link_atual, use_container_width=True)
                                    else: st.text_input("Chamado", value=chamado_num, disabled=True, label_visibility="collapsed", key=f"dis_ch_{form_key}")
                                if pd.isna(link_atual): link_atual = ""
                                novo_link = c12.text_input("Link Externo (Cole aqui)", value=link_atual, key=f"lnk_{form_key}")
                                proto_val = first_row.get('Nº Protocolo', ''); novo_proto = c13.text_input("Nº Protocolo", value=proto_val if pd.notna(proto_val) else "", key=f"prot_{form_key}")
                                st.markdown("---")
                                
                                st.markdown("##### 📦 Descrição (Equipamentos do Projeto)")
                                desc_texto_final = ""
                                nome_serv_lower = str(nome_servico).lower().strip()
                                if nome_serv_lower in SERVICOS_SEM_EQUIPAMENTO: desc_texto_final = f"Realizar {nome_servico}"
                                else:
                                    itens_desc = []
                                    for sys, df_sys in df_grupo.groupby('Sistema'):
                                        sys_clean = clean_val(sys, "Sistema Geral"); itens_desc.append(f"**{sys_clean}**")
                                        for _, row_eq in df_sys.iterrows():
                                            qtd = row_eq.get('Qtd.', 0); equip = row_eq.get('Equipamento', 'Indefinido')
                                            itens_desc.append(f"- {qtd}x {equip}"); itens_desc.append("")
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
                                            time.sleep(0.5)
                                            st.rerun()
                                        else: st.error("Erro ao salvar.")

# --- 3. ABA: AGENDA SEMANAL (CALENDÁRIO) ---
    with aba_calendario:
        st.subheader("🗓️ Agenda da Semana")
        
        # 1. Seletor para navegar entre semanas
        col_nav, col_vazia = st.columns([1, 4])
        data_referencia = col_nav.date_input("Escolha um dia da semana que deseja visualizar:", value=date.today())
        
        # Calcula o início da semana (Segunda-feira) baseada na data escolhida
        # .weekday(): 0=Segunda, 6=Domingo. Subtraímos para voltar à segunda.
        inicio_semana = data_referencia - timedelta(days=data_referencia.weekday())
        
        st.markdown(f"**Visualizando semana de:** {inicio_semana.strftime('%d/%m')} a {(inicio_semana + timedelta(days=4)).strftime('%d/%m')}")
        st.markdown("---")
        
        # 2. Cria as 5 colunas (Segunda a Sexta)
        col_seg, col_ter, col_qua, col_qui, col_sex = st.columns(5)
        cols_dias = [col_seg, col_ter, col_qua, col_qui, col_sex]
        nomes_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
        
        # 3. Loop para preencher cada dia
        for i, col in enumerate(cols_dias):
            dia_atual = inicio_semana + timedelta(days=i)
            dia_str = dia_atual.strftime('%d/%m')
            
            with col:
                # Cabeçalho do dia
                st.markdown(f"""
                    <div style="text-align: center; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 10px;">
                        <div style="font-weight: bold; color: #555;">{nomes_dias[i]}</div>
                        <div style="font-size: 0.85em; color: #999;">{dia_str}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Filtra os chamados DESTE dia específico
                # Importante: garantimos que ambos sejam date (sem hora) para comparar
                if not df_view.empty:
                    # Garante conversão segura para comparação
                    df_dia = df_view[pd.to_datetime(df_view['Agendamento']).dt.date == dia_atual]
                else:
                    df_dia = pd.DataFrame()
                
                if df_dia.empty:
                    st.markdown("<div style='text-align:center; color:#e0e0e0; font-size:2em; margin-top:20px;'>•</div>", unsafe_allow_html=True)
                else:
                    # Ordena por analista para ficar organizado
                    df_dia = df_dia.sort_values(by='Analista')
                    
                    for _, row in df_dia.iterrows():
                        # Dados para o card
                        id_chamado = row['ID']
                        servico = str(row.get('Serviço', 'Serviço')).strip()
                        # Corta texto se for muito grande
                        if len(servico) > 25: servico = servico[:22] + "..."
                            
                        analista = str(row.get('Analista', 'N/D')).split(' ')[0].upper() # Só o primeiro nome
                        cod_ag = str(row.get('Cód. Agência', '')).split('.')[0]
                        status = row.get('Status', '')
                        
                        # Pega a cor do status
                        try: cor_borda = utils_chamados.get_status_color(status)
                        except: cor_borda = "#ccc"
                        
                        # Card Visual (HTML/CSS)
                        st.markdown(f"""
                        <div style="
                            background-color: white; 
                            border-left: 5px solid {cor_borda}; 
                            border-radius: 6px; 
                            padding: 8px 10px; 
                            margin-bottom: 8px; 
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            font-family: sans-serif;
                        ">
                            <div style="font-weight: bold; font-size: 0.85em; color: #333; margin-bottom: 2px;">{servico}</div>
                            <div style="font-size: 0.8em; color: #666; display: flex; justify-content: space-between;">
                                <span>🏠 AG {cod_ag}</span>
                            </div>
                            <div style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed #eee; display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 0.75em; font-weight: bold; color: #1565C0; background-color: #E3F2FD; padding: 2px 6px; border-radius: 4px;">{analista}</span>
                                <span style="font-size: 0.7em; color: #999;">ID {id_chamado}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)



