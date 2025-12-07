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

@st.dialog("Importar Chamados (Mapeamento Fixo)", width="large")
def run_importer_dialog():
    st.info("Importação via Mapeamento de Colunas (Posição Fixa).")
    
    uploaded_files = st.file_uploader(
        "Selecione arquivos (.xlsx ou .csv)", 
        type=["xlsx", "csv"], 
        accept_multiple_files=True,
        key="up_imp_blindado"
    )

    if uploaded_files:
        dfs_list = []
        
        # --- 1. LEITURA DOS ARQUIVOS ---
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
                
                # --- 2. MAPEAMENTO EXATO (O QUE VOCÊ ENVIOU) ---
                # Garante que temos colunas suficientes (pelo menos até a 23, já que Analista é 22)
                if len(df_raw.columns) < 12: # Mínimo para ler até Qtd (11)
                    st.error(f"O arquivo tem apenas {len(df_raw.columns)} colunas. Verifique o arquivo.")
                    st.write("Colunas encontradas:", df_raw.columns.tolist())
                    return

                # SEU MAPEAMENTO AQUI:
                dados_mapeados = {
                    'Nº Chamado': df_raw.iloc[:, 0],
                    'Cód. Agência': df_raw.iloc[:, 1],
                    'Nome Agência': df_raw.iloc[:, 2],
                    'agencia_uf': df_raw.iloc[:, 3],
                    'Analista': df_raw.iloc[:, 22] if len(df_raw.columns) > 22 else "",
                    'Gestor': df_raw.iloc[:, 20] if len(df_raw.columns) > 20 else "",
                    'Serviço': df_raw.iloc[:, 4],
                    'Projeto': df_raw.iloc[:, 5],
                    'Agendamento': df_raw.iloc[:, 6],
                    'Sistema': df_raw.iloc[:, 8],          # Categoria do Sistema
                    'Cod_equipamento': df_raw.iloc[:, 9],
                    'Nome_equipamento': df_raw.iloc[:, 10], # Descrição do item
                    'Qtd': df_raw.iloc[:, 11]
                }
                
                df_final = pd.DataFrame(dados_mapeados)
                df_final = df_final.fillna("")

                # --- 3. FORMATAR ITEM (QTD x NOME_EQUIPAMENTO) ---
                # Usa as colunas que você mapeou: Coluna 11 (Qtd) e Coluna 10 (Nome_equipamento)
                def formatar_item(row):
                    qtd = str(row['Qtd']).strip()
                    desc = str(row['Nome_equipamento']).strip() # Usa o nome do equipamento
                    
                    # Se não tiver nome de equipamento, tenta usar o Sistema (Coluna 8)
                    if not desc: desc = str(row['Sistema']).strip()
                    
                    if not desc: return ""
                    
                    if qtd and qtd not in ["0", "nan", "", "None"]:
                        return f"{qtd}x {desc}"
                    return desc

                df_final['Item_Formatado'] = df_final.apply(formatar_item, axis=1)

                # --- 4. AGRUPAMENTO (JUNTAR ITENS DO MESMO CHAMADO) ---
                def juntar_textos(lista):
                    limpos = [str(x) for x in lista if str(x).strip() not in ["", "nan", "None"]]
                    return " | ".join(dict.fromkeys(limpos))

                # Define regras: para a maioria pega o primeiro valor, para o item junta tudo
                colunas_ignoradas_agg = ['Sistema', 'Qtd', 'Item_Formatado', 'Nome_equipamento', 'Cod_equipamento']
                regras = {c: 'first' for c in df_final.columns if c not in colunas_ignoradas_agg}
                
                regras['Item_Formatado'] = juntar_textos
                
                # Agrupa
                df_grouped = df_final.groupby('Nº Chamado', as_index=False).agg(regras)
                
                # Joga o texto agrupado (ex: "3x Câmera | 1x DVR") na coluna 'Sistema' que vai para o banco
                df_grouped = df_grouped.rename(columns={'Item_Formatado': 'Sistema'})
                
                # --- 5. SEPARAÇÃO (NOVOS vs ATUALIZAR) ---
                df_banco = utils_chamados.carregar_chamados_db()
                lista_novos = []; lista_atualizar = []
                
                if not df_banco.empty:
                    mapa_ids = dict(zip(df_banco['Nº Chamado'].astype(str).str.strip(), df_banco['ID']))
                    
                    for row in df_grouped.to_dict('records'):
                        chamado_num = str(row['Nº Chamado']).strip()
                        if not chamado_num or chamado_num.lower() == 'nan': continue # Pula linhas vazias
                        
                        if chamado_num in mapa_ids:
                            row['ID_Banco'] = mapa_ids[chamado_num]
                            lista_atualizar.append(row)
                        else:
                            lista_novos.append(row)
                else:
                    lista_novos = [r for r in df_grouped.to_dict('records') if str(r['Nº Chamado']).strip()]

                df_insert = pd.DataFrame(lista_novos)
                df_update = pd.DataFrame(lista_atualizar)

                # --- 6. EXIBIÇÃO ---
                c1, c2 = st.columns(2)
                c1.metric("🆕 Criar Novos", len(df_insert))
                c2.metric("🔄 Atualizar Existentes", len(df_update))
                
                with st.expander("🔍 Ver Prévia dos Dados Lidos"):
                    st.dataframe(df_grouped.head())

                if st.button("🚀 Processar Importação"):
                    bar = st.progress(0)
                    status_txt = st.empty()
                    
                    # A. Inserir Novos
                    if not df_insert.empty:
                        status_txt.text("Inserindo novos registros...")
                        utils_chamados.bulk_insert_chamados_db(df_insert)
                        bar.progress(50)
                    
                    # B. Atualizar Existentes
                    if not df_update.empty:
                        status_txt.text("Atualizando dados...")
                        total = len(df_update)
                        for i, row in enumerate(df_update.to_dict('records')):
                            updates = {
                                'Sistema': row['Sistema'], # Aqui vai a lista de equipamentos agrupada
                                'Serviço': row['Serviço'],
                                'Projeto': row['Projeto'],
                                'Agendamento': row['Agendamento'],
                                'Analista': row['Analista'],
                                'Gestor': row['Gestor']
                            }
                            utils_chamados.atualizar_chamado_db(row['ID_Banco'], updates)
                            if total > 0: bar.progress(50 + int((i/total)*50))
                    
                    bar.progress(100)
                    status_txt.text("Concluído!")
                    st.success("Importação finalizada com sucesso!")
                    time.sleep(1.5)
                    st.cache_data.clear()
                    st.rerun()

            except Exception as e: st.error(f"Erro no processamento: {e}")

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
    # --- MODO OPERACIONAL (VISÃO DETALHADA) ---
    
    # 1. ÁREA DE FILTROS (ORGANIZADA EM EXPANDER)
    with st.expander("🎛️ Filtros & Pesquisa", expanded=True):
        
        # Linha Superior: Busca (Esquerda) e Data (Direita)
        c_top1, c_top2 = st.columns([3, 1]) 
        
        with c_top1:
            busca_geral = st.text_input("🔎 Buscador Geral", placeholder="Digite ID, Nome, Serviço, Agência...", label_visibility="collapsed")
        
        with c_top2:
            # Lógica de Data
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            data_min = df_filtrado['Agendamento'].min()
            data_max = df_filtrado['Agendamento'].max()
            if pd.isna(data_min): data_min = date.today()
            if pd.isna(data_max): data_max = date.today()
            
            filtro_data_range = st.date_input(
                "Período", 
                value=(data_min, data_max), 
                format="DD/MM/YYYY",
                label_visibility="collapsed"
            )

        # Linha Inferior: Projetos e Status
        c_bot1, c_bot2 = st.columns(2)
        
        with c_bot1:
            # Carrega Projetos
            try:
                df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                opcoes_projeto_db = df_proj_cfg.iloc[:, 0].tolist() if not df_proj_cfg.empty else []
            except: opcoes_projeto_db = []
            
            if not opcoes_projeto_db:
                opcoes_projeto_db = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
            
            # Lógica de Redirecionamento
            padrao_projetos = []
            if "sel_projeto" in st.session_state:
                proj_selecionado = st.session_state["sel_projeto"]
                if proj_selecionado in opcoes_projeto_db:
                    padrao_projetos = [proj_selecionado]
                st.session_state.pop("sel_projeto", None)
            
            filtro_projeto_multi = st.multiselect("📁 Projetos", options=opcoes_projeto_db, default=padrao_projetos, placeholder="Todos os Projetos")

        with c_bot2:
            # Carrega Status
            opcoes_status = sorted(df_filtrado['Status'].dropna().unique().tolist())
            filtro_status_multi = st.multiselect("📊 Status", options=opcoes_status, default=[], placeholder="Todos os Status")

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

    st.markdown("---") 

    # 2. PAINEL DE KPIs (TOPO)
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

    # Layout de KPIs mais limpo
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📌 Total Chamados", kpi_qtd_chamados)
    k2.metric("📂 Projetos Abertos", kpi_proj_abertos)
    k3.metric("🏁 Projetos Concluídos", proj_fin_count)
    k4.metric("✅ Tarefas Finalizadas", kpi_chamados_fin)
    
    st.markdown("---")

    # 3. RESUMO POR STATUS (MINI CARDS)
    if not df_view.empty:
        st.caption("Resumo Rápido por Status")
        counts = df_view['Status'].value_counts()
        cols_status = st.columns(4)
        for index, (status, count) in enumerate(counts.items()):
            try: cor = utils_chamados.get_status_color(status)
            except: cor = "#90A4AE"
            with cols_status[index % 4]:
                st.markdown(f"""
                <div style="
                    border-left: 4px solid {cor}; 
                    background-color: white; 
                    padding: 8px 12px; 
                    border-radius: 4px; 
                    border: 1px solid #eee;
                    border-left-width: 4px;
                    margin-bottom: 8px;
                    display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600; font-size: 0.85em; color: #555;">{status}</span>
                    <span style="font-weight: bold; font-size: 1.1em; color: #333;">{count}</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Sem dados para exibir resumo de status.")

    st.markdown("---")

    # --- 4. ABAS DE CONTEÚDO ---
    aba_lista, aba_calendario = st.tabs(["📋 Lista Detalhada", "📅 Agenda Semanal"])

    # --- ABA 1: LISTA DETALHADA ---
    with aba_lista:    
        if df_view.empty:
            st.warning("Nenhum chamado encontrado com os filtros atuais.")
        else:
            df_view['Agendamento_str'] = pd.to_datetime(df_view['Agendamento']).dt.strftime('%d/%m/%Y').fillna("Sem Data")
            
            chave_agrupamento = ['Projeto', 'Nome Agência', 'Serviço', 'Agendamento_str']
            grupos = df_view.groupby(chave_agrupamento)
            grupos_lista = list(grupos)
            
            st.markdown(f"**Exibindo {len(df_view)} registros**") # Contador discreto
            
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
                
                # CARD PRINCIPAL (Visual melhorado)
                with st.container(border=True):
                    # Linha de Título
                    c_tit, c_date = st.columns([3, 1])
                    c_tit.markdown(f"**{proj_nome}**")
                    c_date.markdown(f"🗓️ **{data_str}**")
                    
                    # Linha de Detalhes
                    c1, c2, c3, c4 = st.columns([1.5, 2, 3, 2])
                    with c1: st.caption(f"ID(s): {ids_chamados}")
                    with c2: st.markdown(f"👤 **{analista}**")
                    with c3: 
                        cod_ag = str(first_row.get('Cód. Agência', '')).split('.')[0]
                        nome_ag = str(nome_agencia).replace(cod_ag, '').strip(' -')
                        st.markdown(f"🏠 **{cod_ag}** {nome_ag}")
                    with c4: 
                        st.markdown(f"<span style='color:{cor_status}; font-weight:bold;'>● {status_atual}</span>", unsafe_allow_html=True)

                    # Linha de Serviço e Ação
                    c5, c6, c7, c8 = st.columns([2.5, 1.5, 2, 2])
                    with c5: st.markdown(f"<span style='color:#1565C0; font-weight:600;'>{nome_servico}</span>", unsafe_allow_html=True)
                    with c6: 
                        if sla_texto: st.markdown(f"<span style='color:{sla_cor}; font-size:0.9em;'>{sla_texto}</span>", unsafe_allow_html=True)
                    with c7: st.caption(f"Gestor: {gestor}")
                    with c8:
                        if str(acao_atual).lower() == "faturado": st.markdown("✔️ **FATURADO**")
                        elif acao_atual: st.markdown(f"👉 {acao_atual}")

                    # EXPANDER DE EDIÇÃO
                    with st.expander("📝 Editar Detalhes"):
                        form_key = f"form_{first_row['ID']}"
                        with st.form(key=form_key):
                            # ... CARREGAMENTO DE LISTAS ...
                            try:
                                df_status_cfg = utils.carregar_config_db("status")
                                opts_status_db = [str(x) for x in df_status_cfg.iloc[:, 0].dropna().tolist()] if not df_status_cfg.empty else []
                                df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                                opts_proj_db = [str(x) for x in df_proj_cfg.iloc[:, 0].dropna().tolist()] if not df_proj_cfg.empty else []
                                df_tec_cfg = utils.carregar_config_db("tecnicos")
                                opts_tec_db = [str(x) for x in df_tec_cfg.iloc[:, 0].dropna().tolist()] if not df_tec_cfg.empty else []
                                df_users = utils.carregar_usuarios_db()
                                if not df_users.empty: df_users.columns = [col.capitalize() for col in df_users.columns]
                                opts_ana_db = [str(x) for x in df_users["Nome"].dropna().tolist()] if not df_users.empty and "Nome" in df_users.columns else []
                            except:
                                opts_status_db = []; opts_proj_db = []; opts_tec_db = []; opts_ana_db = []

                            def safe_str(val): return str(val) if pd.notna(val) and str(val).lower() not in ['nan', 'none', ''] else ""

                            # Listas
                            status_atual = safe_str(first_row.get('Status', '(Automático)'))
                            lista_final_status = sorted(list(set(opts_status_db + [status_atual] + ["(Automático)", "Finalizado", "Cancelado"])))
                            idx_st = lista_final_status.index(status_atual) if status_atual in lista_final_status else 0
                            
                            val_proj_atual = safe_str(first_row.get('Projeto', ''))
                            lista_final_proj = sorted(list(set(opts_proj_db + [val_proj_atual])))
                            idx_proj = lista_final_proj.index(val_proj_atual) if val_proj_atual in lista_final_proj else 0

                            val_tec_atual = safe_str(first_row.get('Técnico', ''))
                            lista_final_tec = sorted(list(set(opts_tec_db + [val_tec_atual])))
                            idx_tec = lista_final_tec.index(val_tec_atual) if val_tec_atual in lista_final_tec else 0

                            val_ana_atual = safe_str(first_row.get('Analista', ''))
                            lista_final_ana = sorted(list(set(opts_ana_db + [val_ana_atual])))
                            idx_ana = lista_final_ana.index(val_ana_atual) if val_ana_atual in lista_final_ana else 0

                            # FORMULÁRIO
                            c1, c2, c3, c4 = st.columns(4)
                            novo_status = c1.selectbox("Status", lista_final_status, index=idx_st, key=f"st_{form_key}")
                            abert_val = _to_date_safe(first_row.get('Abertura')) or date.today()
                            nova_abertura = c2.date_input("Abertura", value=abert_val, format="DD/MM/YYYY", key=f"ab_{form_key}")
                            agend_val = _to_date_safe(first_row.get('Agendamento'))
                            novo_agend = c3.date_input("Agendamento", value=agend_val, format="DD/MM/YYYY", key=f"ag_{form_key}")
                            fim_val = _to_date_safe(first_row.get('Fechamento'))
                            novo_fim = c4.date_input("Finalização", value=fim_val, format="DD/MM/YYYY", key=f"fim_{form_key}")

                            c5, c6, c7 = st.columns(3)
                            novo_analista = c5.selectbox("Analista (Usuário)", lista_final_ana, index=idx_ana, key=f"ana_{form_key}")
                            novo_gestor = c6.text_input("Gestor", value=first_row.get('Gestor', ''), key=f"ges_{form_key}")
                            novo_tec = c7.selectbox("Técnico Campo", lista_final_tec, index=idx_tec, key=f"tec_{form_key}")

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
                                st.caption("Nº Chamado")
                                if pd.notna(link_atual) and str(link_atual).startswith('http'): st.link_button(f"🔗 {chamado_num}", link_atual)
                                else: st.code(chamado_num)
                            if pd.isna(link_atual): link_atual = ""
                            novo_link = c12.text_input("Link Externo", value=link_atual, key=f"lnk_{form_key}")
                            proto_val = first_row.get('Nº Protocolo', ''); novo_proto = c13.text_input("Protocolo", value=proto_val if pd.notna(proto_val) else "", key=f"prot_{form_key}")
                            
                            st.markdown("---")
                            st.markdown("##### 📦 Descrição")
                            desc_texto_final = ""
                            nome_serv_lower = str(nome_servico).lower().strip()
                            if nome_serv_lower in SERVICOS_SEM_EQUIPAMENTO: desc_texto_final = f"Realizar {nome_servico}"
                            else:
                                itens_desc = []
                                for sys, df_sys in df_grupo.groupby('Sistema'):
                                    sys_clean = clean_val(sys, "Sistema Geral"); itens_desc.append(f"**{sys_clean}**")
                                    for _, row_eq in df_sys.iterrows():
                                        qtd = row_eq.get('Qtd.', 0); equip = row_eq.get('Equipamento', 'Indefinido')
                                        itens_desc.append(f"- {qtd}x {equip}")
                                desc_texto_final = "<br>".join(itens_desc)
                            
                            st.caption("Equipamentos vinculados:")
                            st.markdown(f"<div style='background-color: #f9f9f9; border-radius: 5px; padding: 10px; font-size: 0.9em;'>{desc_texto_final}</div>", unsafe_allow_html=True)
                            st.markdown("<br>", unsafe_allow_html=True)
                            
                            # SALVAR
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

    # --- ABA 2: AGENDA SEMANAL (CALENDÁRIO) ---
    with aba_calendario:
        st.subheader("🗓️ Agenda da Semana")
        
        col_nav, col_vazia = st.columns([1, 4])
        data_referencia = col_nav.date_input("Visualizar semana de:", value=date.today())
        
        inicio_semana = data_referencia - timedelta(days=data_referencia.weekday())
        
        st.caption(f"Semana: {inicio_semana.strftime('%d/%m')} a {(inicio_semana + timedelta(days=4)).strftime('%d/%m')}")
        st.markdown("---")
        
        col_seg, col_ter, col_qua, col_qui, col_sex = st.columns(5)
        cols_dias = [col_seg, col_ter, col_qua, col_qui, col_sex]
        nomes_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
        
        for i, col in enumerate(cols_dias):
            dia_atual = inicio_semana + timedelta(days=i)
            dia_str = dia_atual.strftime('%d/%m')
            
            with col:
                st.markdown(f"""
                    <div style="text-align: center; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 10px;">
                        <div style="font-weight: bold; color: #555;">{nomes_dias[i]}</div>
                        <div style="font-size: 0.85em; color: #999;">{dia_str}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                if not df_view.empty:
                    df_dia = df_view[pd.to_datetime(df_view['Agendamento']).dt.date == dia_atual]
                else:
                    df_dia = pd.DataFrame()
                
                if df_dia.empty:
                    st.markdown("<div style='text-align:center; color:#eee; font-size:1.5em; margin-top:20px;'>-</div>", unsafe_allow_html=True)
                else:
                    df_dia = df_dia.sort_values(by='Analista')
                    
                    for _, row in df_dia.iterrows():
                        id_chamado = row['ID']
                        servico = str(row.get('Serviço', 'Serviço')).strip()
                        if len(servico) > 22: servico = servico[:20] + "..."
                            
                        analista = str(row.get('Analista', 'N/D')).split(' ')[0].upper()
                        cod_ag = str(row.get('Cód. Agência', '')).split('.')[0]
                        status = row.get('Status', '')
                        
                        try: cor_borda = utils_chamados.get_status_color(status)
                        except: cor_borda = "#ccc"
                        
                        st.markdown(f"""
                        <div style="
                            background-color: white; 
                            border-left: 4px solid {cor_borda}; 
                            border-radius: 4px; 
                            padding: 6px 8px; 
                            margin-bottom: 6px; 
                            box-shadow: 0 1px 2px rgba(0,0,0,0.08);
                            font-family: sans-serif;
                        ">
                            <div style="font-weight: 600; font-size: 0.8em; color: #333; margin-bottom: 2px;">{servico}</div>
                            <div style="font-size: 0.75em; color: #666; display: flex; justify-content: space-between;">
                                <span>🏠 {cod_ag}</span>
                            </div>
                            <div style="margin-top: 4px; padding-top: 4px; border-top: 1px dashed #eee; display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 0.7em; font-weight: bold; color: #1565C0; background-color: #E3F2FD; padding: 2px 4px; border-radius: 3px;">{analista}</span>
                                <span style="font-size: 0.65em; color: #999;">#{id_chamado}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
