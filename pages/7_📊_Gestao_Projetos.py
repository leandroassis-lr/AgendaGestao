import streamlit as st
import pandas as pd
import utils_chamados
import utils # Para carregar listas de configuração
import plotly.express as px
from datetime import date, timedelta, datetime
import time
import math

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS ESTILO PERSONALIZADO (Cores Fixas e Layout) ---
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

        /* Gestores (Preto e Negrito) */
        .gestor-bold { color: #000000; font-weight: 900; font-size: 0.9em; }

        /* Status Badge */
        .status-badge { padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.95em; text-transform: uppercase; color: white; display: inline-block;}
        
        /* Ação */
        .action-text { color: #004D40; font-weight: 700; font-size: 0.85em; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- CSS PARA DASHBOARD E KPIS ---
st.markdown("""
    <style>
        /* ... Mantenha os estilos anteriores (gold-line, analistas, etc) ... */

        /* Estilo da Área de Filtros */
        .filter-container {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #e9ecef;
            margin-bottom: 20px;
        }

        /* Estilo dos Cards de KPI (Topo) */
        .kpi-card {
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border: 1px solid #eee;
            text-align: center;
            height: 100%;
        }
        .kpi-title { font-size: 0.85em; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
        .kpi-value { font-size: 1.8em; font-weight: 800; color: #2c3e50; }
        
        /* Cores de Borda para KPIs */
        .kpi-blue   { border-bottom: 4px solid #1565C0; }
        .kpi-orange { border-bottom: 4px solid #F57C00; }
        .kpi-green  { border-bottom: 4px solid #2E7D32; }
        .kpi-purple { border-bottom: 4px solid #7B1FA2; }

        /* Estilo da Barra de Resumo de Status */
        .status-summary-box {
            background-color: white;
            border: 1px solid #eee;
            border-radius: 6px;
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-label { font-size: 0.75em; font-weight: bold; color: #555; text-transform: uppercase; }
        .status-val { font-size: 1.1em; font-weight: 800; color: #333; }
    </style>
""", unsafe_allow_html=True)

# --- CSS ESTILO "PLANNER / TRELLO" ---
st.markdown("""
    <style>
        /* Card estilo Planner */
        .planner-card {
            background-color: white;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.08); /* Sombra suave */
            border: 1px solid #e0e0e0;
            margin-bottom: 15px;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        
        /* Efeito ao passar o mouse */
        .planner-card:hover {
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
            transform: translateY(-3px);
            border-color: #bdc3c7;
        }

        /* Título do Card */
        .planner-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 8px;
            display: -webkit-box;
            -webkit-line-clamp: 2; /* Limita a 2 linhas */
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        /* Barra de Progresso Customizada */
        .progress-container {
            width: 100%;
            background-color: #f1f2f6;
            border-radius: 4px;
            height: 6px;
            margin: 10px 0;
            overflow: hidden;
        }
        .progress-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease-in-out;
        }

        /* Etiquetas (Badges) */
        .tag-status {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            margin-right: 5px;
        }
        .tag-red { background: #FFEBEE; color: #C62828; }
        .tag-green { background: #E8F5E9; color: #2E7D32; }
        .tag-gray { background: #F5F5F5; color: #757575; }

        /* Rodapé do Card */
        .planner-footer {
            margin-top: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            color: #7f8c8d;
            border-top: 1px solid #f5f5f5;
            padding-top: 8px;
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
    st.title("📌 Visão Geral dos Projetos")
    
    # Cálculos iniciais
    hoje = pd.Timestamp.today().normalize()
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    
    pendentes = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim)]
    atrasados = pendentes[pendentes['Agendamento'] < hoje]
    prox = pendentes[(pendentes['Agendamento'] >= hoje) & (pendentes['Agendamento'] <= hoje + timedelta(days=5))]
    
    # --- MÉTRICAS DE TOPO ---
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total de Chamados", len(df_filtrado))
    m2.metric("🚨 Atrasados Geral", len(atrasados), delta_color="inverse")
    m3.metric("📅 Vencendo na Semana", len(prox))
    
    st.markdown("---")
    st.subheader("Meus Quadros")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- GRID DE CARDS TIPO PLANNER ---
    lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
    cols = st.columns(3)
    
    for i, proj in enumerate(lista_projetos):
        df_p = df_filtrado[df_filtrado['Projeto'] == proj]
        total_p = len(df_p)
        concluidos = len(df_p[df_p['Status'].str.lower().isin(status_fim)])
        atrasados_p = len(df_p[(~df_p['Status'].str.lower().isin(status_fim)) & (df_p['Agendamento'] < hoje)])
        
        perc = int((concluidos / total_p) * 100) if total_p > 0 else 0
        
        if atrasados_p > 0:
            cor_saude = "#e74c3c"
            tag_html = f"<span class='tag-status tag-red'>⚠️ {atrasados_p} Atrasados</span>"
        elif perc == 100:
            cor_saude = "#2ecc71"
            tag_html = "<span class='tag-status tag-green'>✨ Concluído</span>"
        else:
            cor_saude = "#3498db"
            tag_html = "<span class='tag-status tag-gray'>Em dia</span>"

        with cols[i % 3]:
            # IMPORTANTE: O HTML abaixo está alinhado à esquerda para evitar bugs de identação
            card_html = f"""<div class="planner-card" style="border-left: 5px solid {cor_saude};">
<div>
<div class="planner-title" title="{proj}">{proj}</div>
<div style="display:flex; justify-content:space-between; font-size:0.8em; color:#666; margin-bottom:2px;">
<span>Progresso</span><span>{perc}%</span>
</div>
<div class="progress-container">
<div class="progress-bar-fill" style="width: {perc}%; background-color: {cor_saude};"></div>
</div>
</div>
<div>
<div style="margin-bottom:10px;">{tag_html}</div>
<div class="planner-footer">
<span>📋 {concluidos}/{total_p} tarefas</span>
<span>📂 Abrir</span>
</div>
</div>
</div>"""
            
            st.markdown(card_html, unsafe_allow_html=True)
            
            if st.button(f"Ver Detalhes", key=f"btn_plan_{i}", use_container_width=True):
                st.session_state["sel_projeto"] = proj
                st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"
                st.rerun()

else:
    # --- MODO OPERACIONAL (VISÃO DETALHADA) ---
    
    # 1. ÁREA DE FILTROS (Novo Design com Fundo)
    with st.container():
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        c_tit, c_date = st.columns([4, 1.5])
        with c_tit: st.markdown("### 🔍 Filtros & Pesquisa")
        with c_date: 
             # Lógica de Datas (Mantida)
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            d_min = df_filtrado['Agendamento'].min() if not pd.isna(df_filtrado['Agendamento'].min()) else date.today()
            d_max = df_filtrado['Agendamento'].max() if not pd.isna(df_filtrado['Agendamento'].max()) else date.today()
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")

        c1, c2, c3 = st.columns([2, 1.5, 1.5])
        with c1:
            busca_geral = st.text_input("Busca", placeholder="🔎 Digite ID, Nome, Serviço...", label_visibility="collapsed")
        
        with c2:
            # Carregamento de Projetos (Mantido)
            try:
                df_proj_cfg = utils.carregar_config_db("projetos_nomes")
                opcoes_projeto_db = df_proj_cfg.iloc[:, 0].tolist() if not df_proj_cfg.empty else []
            except: opcoes_projeto_db = []
            if not opcoes_projeto_db: opcoes_projeto_db = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
            
            padrao_projetos = []
            if "sel_projeto" in st.session_state:
                proj_sel = st.session_state["sel_projeto"]
                if proj_sel in opcoes_projeto_db: padrao_projetos = [proj_sel]
                st.session_state.pop("sel_projeto", None)

            filtro_projeto_multi = st.multiselect("Projetos", options=opcoes_projeto_db, default=padrao_projetos, placeholder="Filtrar Projeto", label_visibility="collapsed")
        
        with c3:
            opcoes_status = sorted(df_filtrado['Status'].dropna().unique().tolist())
            filtro_status_multi = st.multiselect("Status", options=opcoes_status, default=[], placeholder="Filtrar Status", label_visibility="collapsed")

        st.markdown('</div>', unsafe_allow_html=True) # Fecha container CSS

    # --- APLICAÇÃO DOS FILTROS (Lógica Mantida) ---
    df_view = df_filtrado.copy()
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)]
    if filtro_projeto_multi: df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
    if filtro_status_multi: df_view = df_view[df_view['Status'].isin(filtro_status_multi)]
    if len(filtro_data_range) == 2:
        d_inicio, d_fim = filtro_data_range
        df_view = df_view[(df_view['Agendamento'] >= pd.to_datetime(d_inicio)) & (df_view['Agendamento'] <= pd.to_datetime(d_fim))]

    # 2. KPIs COM DESIGN NOVO
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    qtd_total = len(df_view)
    qtd_fim = len(df_view[df_view['Status'].str.lower().isin(status_fim)])
    
    if not df_view.empty:
        gr = df_view.groupby('Projeto')
        proj_total = gr.ngroups
        proj_concluidos = sum(1 for _, d in gr if d['Status'].str.lower().isin(status_fim).all())
        proj_abertos = proj_total - proj_concluidos
    else: proj_total=0; proj_concluidos=0; proj_abertos=0

    # Renderiza os 4 Cards Coloridos
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card kpi-blue"><div class="kpi-title">Chamados (Filtro)</div><div class="kpi-value">{qtd_total}</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card kpi-orange"><div class="kpi-title">Projetos Abertos</div><div class="kpi-value">{proj_abertos}</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card kpi-green"><div class="kpi-title">Projetos Finalizados</div><div class="kpi-value">{proj_concluidos}</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card kpi-purple"><div class="kpi-title">Tarefas Concluídas</div><div class="kpi-value">{qtd_fim}</div></div>""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # 3. BARRA DE RESUMO DE STATUS (Melhorada)
    if not df_view.empty:
        counts = df_view['Status'].value_counts()
        # Mostra apenas os top 5 status para não quebrar o layout, ou todos se couber
        top_status = counts.head(5) 
        
        cols = st.columns(len(top_status))
        for i, (status, count) in enumerate(top_status.items()):
            try: cor = utils_chamados.get_status_color(status)
            except: cor = "#ccc"
            
            with cols[i]:
                # Cardzinho com borda esquerda na cor do status
                st.markdown(f"""
                <div class="status-summary-box" style="border-left: 5px solid {cor};">
                    <span class="status-label">{status}</span>
                    <span class="status-val">{count}</span>
                </div>
                """, unsafe_allow_html=True)
    
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
                
                # Lógica de Cores Analista
                nome_ana_raw = clean_val(row.get('Analista'), "N/D").split(' ')[0].upper()
                if "GIOVANA" in nome_ana_raw: css_ana = "ana-azul"
                elif "MARCELA" in nome_ana_raw: css_ana = "ana-verde"
                elif "MONIQUE" in nome_ana_raw: css_ana = "ana-rosa"
                else: css_ana = "ana-default"
                
                gestor = clean_val(row.get('Gestor'), "N/D").split(' ')[0].title()
                
                # Tratamento Agência
                cod_ag = str(row.get('Cód. Agência', '')).split('.')[0]
                nome_ag_limpo = str(nome_agencia).replace(cod_ag, '').strip(' -')
                
                # Cor do Status
                cor_st = utils_chamados.get_status_color(st_atual)

                # SLA
                sla_html = ""
                if _to_date_safe(row.get('Prazo')):
                    dias = (_to_date_safe(row.get('Prazo')) - date.today()).days
                    if dias < 0: sla_html = f"<span style='color:#D32F2F; font-weight:bold;'>⚠️ {abs(dias)}d atraso</span>"
                    else: sla_html = f"<span style='color:#388E3C; font-weight:bold;'>🕒 {dias}d restantes</span>"

                # --- RENDERIZAÇÃO (NOVO LAYOUT 3 LINHAS) ---
                
                st.markdown('<div class="gold-line"></div>', unsafe_allow_html=True)
                
                # LINHA 1: Nº e Nome da Agência
                st.markdown(f"<div class='agencia-header'>🏢 {cod_ag} - {nome_ag_limpo}</div>", unsafe_allow_html=True)
                
                # LINHA 2: Projeto - Agendamento - Analista - Status
                # Dividido em 4 colunas proporcionais
                l2_c1, l2_c2, l2_c3, l2_c4 = st.columns([2, 1.5, 1.5, 1])
                
                with l2_c1: 
                    st.markdown(f"<span class='meta-label'></span><br><b>{proj_nome}</b>", unsafe_allow_html=True)
                with l2_c2:
                    st.markdown(f"<span class='meta-label'></span><br>📅 {data_str}", unsafe_allow_html=True)
                with l2_c3:
                    st.markdown(f"<span class='meta-label'></span><br><span class='{css_ana}'>{nome_ana_raw}</span>", unsafe_allow_html=True)
                with l2_c4:
                    st.markdown(f"<span class='meta-label'></span><br><span class='status-badge' style='background-color:{cor_st};'>{st_atual}</span>", unsafe_allow_html=True)

                # LINHA 3: Serviço - SLA - Gestor - Ação
                st.markdown("<div style='margin-top: 6px;'></div>", unsafe_allow_html=True) # Espacinho
                l3_c1, l3_c2, l3_c3, l3_c4 = st.columns([2, 1.5, 1.5, 1])
                
                with l3_c1:
                    st.markdown(f"<span style='color:#1565C0; font-weight:600;'>{nome_servico}</span>", unsafe_allow_html=True)
                with l3_c2:
                    st.markdown(sla_html if sla_html else "-", unsafe_allow_html=True)
                with l3_c3:
                    st.markdown(f"<span class='gestor-bold'>👤 {gestor.upper()}</span>", unsafe_allow_html=True)
                with l3_c4:
                    if acao: st.markdown(f"<span class='action-text'>👉 {acao}</span>", unsafe_allow_html=True)
                    else: st.caption("-")

                # Expander
                with st.expander(f"📝 Editar Detalhes"):
                   
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
















