import streamlit as st
import pandas as pd
import utils_chamados
import utils # Para carregar listas de configuração
import plotly.express as px
from datetime import date, timedelta, datetime
import time
import math
import io

st.set_page_config(page_title="Gestão de Projetos", page_icon="📊", layout="wide")

# --- CSS ESTILO PERSONALIZADO ---
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
        .ana-rosa  { color: #C2185B; font-weight: 800; background-color: #FCE4EC; padding: 2px 6px; border-radius: 4px; }
        .ana-default { color: #555; font-weight: 700; }

        /* Gestores */
        .gestor-bold { color: #000000; font-weight: 900; font-size: 0.9em; }

        /* Status Badge */
        .status-badge { padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.95em; text-transform: uppercase; color: white; display: inline-block;}
        
        /* KPI Cards */
        .kpi-card { background-color: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; text-align: center; height: 100%; }
        .kpi-title { font-size: 0.85em; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
        .kpi-value { font-size: 1.8em; font-weight: 800; color: #2c3e50; }
        .kpi-blue   { border-bottom: 4px solid #1565C0; }
        .kpi-orange { border-bottom: 4px solid #F57C00; }
        .kpi-green  { border-bottom: 4px solid #2E7D32; }
        .kpi-purple { border-bottom: 4px solid #7B1FA2; }
        
        /* Estilo da Área de Filtros */
        .filter-container { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #e9ecef; margin-bottom: 20px; }
        
        /* Planner Card */
        .planner-card { background-color: white; border-radius: 8px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.08); border: 1px solid #e0e0e0; margin-bottom: 15px; transition: all 0.2s ease; position: relative; overflow: hidden; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
        .planner-card:hover { box-shadow: 0 8px 15px rgba(0,0,0,0.1); transform: translateY(-3px); border-color: #bdc3c7; }
        .planner-title { font-size: 1.05rem; font-weight: 700; color: #2c3e50; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .progress-container { width: 100%; background-color: #f1f2f6; border-radius: 4px; height: 6px; margin: 10px 0; overflow: hidden; }
        .progress-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease-in-out; }
        .planner-footer { margin-top: 12px; display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #7f8c8d; border-top: 1px solid #f5f5f5; padding-top: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- UTILS LOCAIS ---
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

# --- DIALOG (POP-UP) DETALHES DO CHAMADO ---
@st.dialog("📝 Editar Chamado", width="large")
def open_chamado_dialog(row_dict):
    # Identifica Tipo
    n_chamado = str(row_dict.get('Nº Chamado', ''))
    is_equip = '-e-' in n_chamado.lower() or '-E-' in n_chamado

    # Carrega Listas
    try:
        df_tc = utils.carregar_config_db("tecnicos")
        lista_tecnicos = df_tc.iloc[:,0].dropna().tolist()
    except: lista_tecnicos = []
    
    try:
        df_gest = utils.carregar_config_db("gestores") 
        lista_gestores = df_gest.iloc[:,0].dropna().tolist()
    except: lista_gestores = []

    val_tec_atual = str(row_dict.get('Técnico', '')).strip()
    val_gest_atual = str(row_dict.get('Gestor', '')).strip()
    
    if val_tec_atual and val_tec_atual not in lista_tecnicos: lista_tecnicos.insert(0, val_tec_atual)
    if val_gest_atual and val_gest_atual not in lista_gestores: lista_gestores.insert(0, val_gest_atual)

    st.markdown(f"### 🎫 {n_chamado}")
    st.caption(f"ID: {row_dict.get('ID')}")
    st.markdown("<hr style='margin: 5px 0 15px 0'>", unsafe_allow_html=True)

    with st.form(key=f"form_popup_{row_dict['ID']}"):
        
        # --- PREPARAÇÃO DE DATAS ---
        dt_abertura = _to_date_safe(row_dict.get('Abertura'))
        dt_agendamento = _to_date_safe(row_dict.get('Agendamento'))
        dt_finalizacao = _to_date_safe(row_dict.get('Fechamento'))
        dt_envio = _to_date_safe(row_dict.get('Data Envio'))

        str_abertura = dt_abertura.strftime('%d/%m/%Y') if dt_abertura else "-"
        str_agendamento = dt_agendamento.strftime('%d/%m/%Y') if dt_agendamento else "-"

        # --- LINHA 1: DATAS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.text_input("📅 Abertura", value=str_abertura, disabled=True)
        c2.text_input("📅 Agendamento Atual", value=str_agendamento, disabled=True)
        nova_reprog = c3.date_input("🔄 Reprogramação", value=dt_agendamento, format="DD/MM/YYYY")
        nova_finalizacao = c4.date_input("✅ Finalização / Cancelamento", value=dt_finalizacao, format="DD/MM/YYYY")

        # --- LINHA 2: PESSOAS ---
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        novo_tecnico = r2_c1.selectbox("🔧 Técnico", options=[""] + lista_tecnicos, index=lista_tecnicos.index(val_tec_atual)+1 if val_tec_atual in lista_tecnicos else 0)
        r2_c2.text_input("💻 Sistema", value=row_dict.get('Sistema', ''), disabled=True)
        r2_c3.text_input("🛠️ Serviço", value=row_dict.get('Serviço', ''), disabled=True)
        novo_gestor = r2_c4.text_input("👤 Gestor", value=val_gest_atual) 

        # --- DESCRIÇÃO ---
        st.markdown("<br><b>📦 Descrição</b>", unsafe_allow_html=True)
        
        # Lógica de visualização prioritária
        equip_nome = str(row_dict.get('Equipamento', ''))
        equip_qtd = str(row_dict.get('Qtd.', '')).replace('.0', '') # Remove decimal se houver
        desc_bd = str(row_dict.get('Descrição', ''))
        
        itens_desc = "-"
        
        # 1. Tenta montar na hora se tiver os dados separados
        if equip_nome and equip_nome.lower() not in ['nan', 'none', '', 'None']:
            if equip_qtd and equip_qtd.lower() not in ['nan', 'none', '']:
                itens_desc = f"{equip_qtd} - {equip_nome}"
            else:
                itens_desc = equip_nome
        # 2. Se não, usa o que foi salvo no campo descrição do banco (que o importador já formatou)
        elif desc_bd and desc_bd.lower() not in ['nan', 'none', '', 'None']:
             itens_desc = desc_bd
             
        # Formatação visual
        itens_desc = itens_desc.replace("|", "\n- ").replace(" | ", "\n- ")
        st.info(itens_desc)

        # --- LINHA 3: CAMPOS ESPECÍFICOS ---
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Inicializa variáveis padrão
        nova_data_envio = dt_envio
        novo_link = row_dict.get('Link Externo', '')
        novo_protocolo = row_dict.get('Nº Protocolo', '')
        novo_pedido = row_dict.get('Nº Pedido', '') # Variável para guardar o pedido

        if is_equip:
            # === MUDANÇA AQUI: Layout de 3 colunas para Equipamento ===
            l3_c1, l3_c2, l3_c3 = st.columns([2, 1.5, 1.5])
            
            # Coluna 1: Ref Btime
            novo_link = l3_c1.text_input("🔢 Nº Chamado Btime (Ref)", value=row_dict.get('Link Externo', ''))
            
            # Coluna 2: Pedido (CAMPO NOVO QUE FALTAVA)
            novo_pedido = l3_c2.text_input("📦 Nº Pedido", value=row_dict.get('Nº Pedido', ''))
            
            # Coluna 3: Data Envio
            nova_data_envio = l3_c3.date_input("🚚 Data de Envio", value=dt_envio, format="DD/MM/YYYY")
            
        else:
            # Layout Serviço (Padrão)
            l3_c1, l3_c2, l3_c3 = st.columns([3, 1.5, 1.5])
            novo_link = l3_c1.text_input("🔗 Link Externo", value=row_dict.get('Link Externo', ''))
            novo_protocolo = l3_c2.text_input("🔢 Protocolo", value=row_dict.get('Nº Protocolo', ''))
            with l3_c3:
                st.markdown("<label style='font-size:14px;'>Acessar</label>", unsafe_allow_html=True)
                if novo_link and str(novo_link).lower() not in ['nan', 'none', '']:
                    st.markdown(f"<a href='{novo_link}' target='_blank' style='background:#1565C0; color:white; padding:9px 12px; border-radius:4px; text-decoration:none; display:block; text-align:center; font-weight:bold; margin-top:0px;'>🚀 Abrir Link</a>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='background:#e0e0e0; color:#999; padding:9px 12px; border-radius:4px; text-align:center; font-weight:bold;'>🚫 Sem Link</div>", unsafe_allow_html=True)

        # --- CHECKLIST DE STATUS ---
        st.markdown("---")
        st.markdown("### ☑️ Controle de Status & Pendências")
        
        def is_checked(key): return str(row_dict.get(key, '')).upper() == 'TRUE'

        chk_pend_eq = is_checked('chk_pendencia_equipamento')
        chk_pend_infra = is_checked('chk_pendencia_infra')
        chk_alteracao = is_checked('chk_alteracao_chamado')
        chk_cancelado = is_checked('chk_cancelado')
        chk_followup = is_checked('chk_status_enviado')
        chk_envio_parcial = is_checked('chk_envio_parcial')
        chk_entregue_total = is_checked('chk_equipamento_entregue')

        col_checks_1, col_checks_2 = st.columns(2)
        with col_checks_1:
            st.markdown("**Geral**")
            new_pend_eq = st.checkbox("⚠️ Pendência de Equipamento", value=chk_pend_eq)
            new_pend_infra = st.checkbox("🏗️ Pendência de Infra", value=chk_pend_infra)
            new_alteracao = st.checkbox("📝 Alteração do Chamado", value=chk_alteracao)
            new_cancelado = st.checkbox("🚫 Cancelado", value=chk_cancelado)
        with col_checks_2:
            st.markdown(f"**Específico ({'Equipamento' if is_equip else 'Serviço'})**")
            if is_equip:
                new_envio_parcial = st.checkbox("📦 Envio Parcial", value=chk_envio_parcial)
                new_entregue_total = st.checkbox("✅ Equipamento Entregue Total", value=chk_entregue_total)
                new_followup = False
            else:
                new_followup = st.checkbox("📧 Follow-up (Status Enviado)", value=chk_followup)
                new_envio_parcial = False
                new_entregue_total = False

        # --- OBSERVAÇÃO ---
        obs_atual = row_dict.get('Observações e Pendencias', '')
        nova_obs = st.text_area("✍️ Observação / Pendência", value=obs_atual if pd.notna(obs_atual) else "", height=100)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # --- AÇÃO DE SALVAR ---
        if st.form_submit_button("💾 SALVAR E RECALCULAR", use_container_width=True):
            # 1. Validações
            erro_msg = []
            if new_cancelado and not nova_finalizacao: erro_msg.append("Para CANCELAR, é obrigatório informar a Data de Finalização.")
            tem_pendencia = new_pend_eq or new_pend_infra or new_alteracao or new_envio_parcial
            if tem_pendencia and (not nova_obs or len(str(nova_obs).strip()) < 5): erro_msg.append("Para Pendências ou Alterações, a DESCRIÇÃO é obrigatória.")
            if not is_equip and new_followup and tem_pendencia: erro_msg.append("Não é possível marcar 'Follow-up' se houver pendências ativas.")

            if erro_msg:
                for e in erro_msg: st.error(e)
            else:
                # 2. Prepara os updates
                updates = {
                    "Data Agendamento": nova_reprog, 
                    "Data Finalização": nova_finalizacao,
                    "Técnico": novo_tecnico,
                    "Gestor": novo_gestor,
                    "Observações e Pendencias": nova_obs,
                    "Link Externo": novo_link, 
                    "Data Envio": nova_data_envio,
                    
                    # Salva corretamente baseado no tipo
                    "Nº Protocolo": novo_protocolo, 
                    "Nº Pedido": novo_pedido, # <--- IMPORTANTE: Adicionado ao Update
                    
                    "chk_pendencia_equipamento": "TRUE" if new_pend_eq else "FALSE",
                    "chk_pendencia_infra": "TRUE" if new_pend_infra else "FALSE",
                    "chk_alteracao_chamado": "TRUE" if new_alteracao else "FALSE",
                    "chk_cancelado": "TRUE" if new_cancelado else "FALSE",
                    "chk_envio_parcial": "TRUE" if new_envio_parcial else "FALSE",
                    "chk_equipamento_entregue": "TRUE" if new_entregue_total else "FALSE",
                    "chk_status_enviado": "TRUE" if new_followup else "FALSE"
                }

                # 3. Salva no Banco
                utils_chamados.atualizar_chamado_db(row_dict['ID'], updates)
                
                # 4. Limpa Cache
                st.cache_data.clear()
                
                # 5. Força o cálculo imediato
                df_novo = utils_chamados.carregar_chamados_db()
                projeto_atual = row_dict.get('Projeto')
                agencia_atual = row_dict.get('Cód. Agência')
                
                if not df_novo.empty and projeto_atual and agencia_atual:
                    grupo_projeto = df_novo[
                        (df_novo['Projeto'] == projeto_atual) & 
                        (df_novo['Cód. Agência'] == agencia_atual)
                    ].copy()

                    idx_row = grupo_projeto.index[grupo_projeto['ID'] == row_dict['ID']].tolist()
                    if idx_row:
                        i = idx_row[0]
                        for k, v in updates.items():
                            grupo_projeto.at[i, k] = v
                    
                    ids_grupo = grupo_projeto['ID'].tolist()
                    calcular_e_atualizar_status_projeto(grupo_projeto, ids_grupo)

                st.toast("✅ Salvo e Atualizado com Sucesso!", icon="💾")
                st.rerun()    
                
# --- LÓGICA DE STATUS: CHAMADO E PROJETO ---
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
        # Verifica se campos chave estão preenchidos
        link_presente = row.get('Link Externo') and str(row.get('Link Externo')).strip() not in ['', 'nan', 'None']
        n_pedido = row.get('Nº Pedido') and str(row.get('Nº Pedido')).strip() not in ['', 'nan', 'None']
        
        # Verifica se tem Técnico (NOVO CRITÉRIO)
        tecnico_presente = row.get('Técnico') and str(row.get('Técnico')).strip() not in ['', 'nan', 'None']

        # Banco de Dados
        db_liberacao_banco = str(row.get('chk_financeiro_banco', '')).upper() == 'TRUE'
        db_book_controle_sim = str(row.get('Book Enviado', '')).upper() == 'SIM'
        
        # Checkboxes UI
        chk_cancelado = str(row.get('chk_cancelado', '')).upper() == 'TRUE'
        chk_pend_eq = str(row.get('chk_pendencia_equipamento', '')).upper() == 'TRUE'
        chk_pend_infra = str(row.get('chk_pendencia_infra', '')).upper() == 'TRUE'
        chk_alteracao = str(row.get('chk_alteracao_chamado', '')).upper() == 'TRUE'
        
        chk_envio_parcial = str(row.get('chk_envio_parcial', '')).upper() == 'TRUE'
        chk_entregue_total = str(row.get('chk_equipamento_entregue', '')).upper() == 'TRUE'
        chk_followup = str(row.get('chk_status_enviado', '')).upper() == 'TRUE'

        novo_sub_status = "Em análise"
        
        # --- LÓGICA INDIVIDUAL ---
        
        if chk_cancelado:
            novo_sub_status = "Cancelado"
        
        elif db_liberacao_banco:
            novo_sub_status = "Faturado"
        
        elif chk_pend_eq:
            novo_sub_status = "Pendência de equipamento"
        
        elif chk_pend_infra:
            novo_sub_status = "Pendência de Infra"
        
        elif chk_alteracao:
            novo_sub_status = "Alteração do chamado"
            
        else:
            # Fluxo Normal (Sem pendência ou cancelamento)
            if is_equip:
                # LÓGICA EQUIPAMENTO (-E-)
                if chk_entregue_total:
                    novo_sub_status = "Equipamento entregue"
                elif chk_envio_parcial:
                    novo_sub_status = "Equipamento enviado Parcial"
                elif row.get('Data Envio') and pd.notna(row.get('Data Envio')):
                    novo_sub_status = "Equipamento enviado"
                elif n_pedido:
                    novo_sub_status = "Aguardando envio"
                else:
                    novo_sub_status = "Solicitar equipamento"
            
            else:
                # LÓGICA SERVIÇO (SEM -E-)
                if db_book_controle_sim:
                    novo_sub_status = "Aguardando Faturamento"
                elif chk_followup:
                    novo_sub_status = "Enviar Book"
                elif tecnico_presente:
                    # Se tem técnico mas não fez follow-up ainda -> Follow-up
                    novo_sub_status = "Follow-up" 
                elif link_presente:
                    # Tem link mas não tem técnico -> Acionar técnico
                    novo_sub_status = "Acionar técnico" 
                else:
                    # Não tem link -> Abrir chamado
                    novo_sub_status = "Abrir chamado Btime" 

        updates_batch[row['ID']] = {"Sub-Status": novo_sub_status}
        
        chamado_obj = {
            "ID": row['ID'],
            "Tipo": "EQUIP" if is_equip else "SERV",
            "SubStatus": novo_sub_status,
            "Cancelado": chk_cancelado,
            "Faturado": db_liberacao_banco
        }
        chamados_calculados.append(chamado_obj)

    # --- PARTE B: CALCULAR STATUS DO PROJETO (CABEÇALHO) ---
    
    total = len(chamados_calculados)
    if total == 0: return False

    ativos = [c for c in chamados_calculados if not c['Cancelado']]
    faturados_count = sum(1 for c in ativos if c['Faturado'])
    
    status_projeto = "Não Iniciado"
    
    if len(ativos) == 0: # Todos cancelados
        status_projeto = "Cancelado"
    else:
        # Definição dos critérios de Status Macro
        todos_finalizados_banco = all(c['Faturado'] for c in ativos)
        
        def is_concluido(c):
            s = c['SubStatus']
            return s in ["Faturado", "Aguardando Faturamento", "Equipamento entregue", "Enviar Book"] 
        
        todos_concluidos = all(is_concluido(c) for c in ativos)
        
        def is_nao_iniciado(c):
            s = c['SubStatus']
            return s in ["Solicitar equipamento", "Abrir chamado Btime"]
        
        todos_nao_iniciados = all(is_nao_iniciado(c) for c in ativos)

        if todos_finalizados_banco:
            status_projeto = "Finalizado"
        elif todos_concluidos:
            status_projeto = "Concluído"
        elif todos_nao_iniciados:
            status_projeto = "Não Iniciado"
        else:
            status_projeto = "Em Andamento"
    
    # --- APLICAÇÃO DOS UPDATES ---
    
    # 1. Atualiza Sub-Status Individual
    for cid, data in updates_batch.items():
        utils_chamados.atualizar_chamado_db(cid, data)
    
    # 2. Atualiza Status Macro em todos
    for row in chamados_calculados:
        utils_chamados.atualizar_chamado_db(row['ID'], {"Status": status_projeto}) 
              
    return True
    
# --- FUNÇÕES DE IMPORTAÇÃO/EXPORTAÇÃO ---
@st.dialog("Importar Chamados", width="large")
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
                if len(df_raw.columns) < 12: st.error("Arquivo com colunas insuficientes."); return

                dados_mapeados = {
                    'Nº Chamado': df_raw.iloc[:, 0], 'Cód. Agência': df_raw.iloc[:, 1], 'Nome Agência': df_raw.iloc[:, 2],
                    'agencia_uf': df_raw.iloc[:, 3], 'Analista': df_raw.iloc[:, 22] if len(df_raw.columns) > 22 else "",
                    'Gestor': df_raw.iloc[:, 20] if len(df_raw.columns) > 20 else "", 'Serviço': df_raw.iloc[:, 4],
                    'Projeto': df_raw.iloc[:, 5], 'Agendamento': df_raw.iloc[:, 6], 
                    'Sistema': df_raw.iloc[:, 8], 
                    'Cod_equipamento': df_raw.iloc[:, 9], 'Nome_equipamento': df_raw.iloc[:, 10], 'Qtd': df_raw.iloc[:, 11]
                }
                df_final = pd.DataFrame(dados_mapeados).fillna("")

                def formatar_item(row):
                    qtd = str(row['Qtd']).strip()
                    desc = str(row['Nome_equipamento']).strip()
                    if not desc: desc = str(row['Sistema']).strip()
                    if not desc: return ""
                    if qtd and qtd not in ["0", "nan", "", "None"]: return f"{qtd} - {desc}"
                    return desc

                df_final['Item_Formatado'] = df_final.apply(formatar_item, axis=1)

                def juntar_textos(lista):
                    limpos = [str(x) for x in lista if str(x).strip() not in ["", "nan", "None"]]
                    return " | ".join(dict.fromkeys(limpos))

                colunas_ignoradas_agg = ['Sistema', 'Qtd', 'Item_Formatado', 'Nome_equipamento', 'Cod_equipamento']
                regras = {c: 'first' for c in df_final.columns if c not in colunas_ignoradas_agg}
                regras['Sistema'] = 'first' 
                regras['Item_Formatado'] = juntar_textos 
                
                df_grouped = df_final.groupby('Nº Chamado', as_index=False).agg(regras)
                df_grouped['Equipamento'] = df_grouped['Item_Formatado']
                df_grouped['Descrição'] = df_grouped['Item_Formatado']

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
                        status_txt.text("Inserindo novos chamados...")
                        utils_chamados.bulk_insert_chamados_db(df_insert)
                    bar.progress(30)
                    
                    if not df_update.empty:
                        status_txt.text("Atualizando dados básicos e equipamentos...")
                        total = len(df_update)
                        for i, row in enumerate(df_update.to_dict('records')):
                            updates = {
                                'Sistema': row['Sistema'], 
                                'Equipamento': row['Equipamento'],
                                'Descrição': row['Descrição'],
                                'Serviço': row['Serviço'], 'Projeto': row['Projeto'],
                                'Agendamento': row['Agendamento'], 'Analista': row['Analista'], 'Gestor': row['Gestor']
                            }
                            utils_chamados.atualizar_chamado_db(row['ID_Banco'], updates)
                            if total > 0: bar.progress(30 + int((i / total) * 30))
                    else: bar.progress(60)

                    status_txt.text("🔄 Aplicando regras automáticas de Status...")
                    df_todos = utils_chamados.carregar_chamados_db()
                    chamados_imp = df_grouped['Nº Chamado'].astype(str).str.strip().tolist()
                    df_afetados = df_todos[df_todos['Nº Chamado'].astype(str).str.strip().isin(chamados_imp)]
                    
                    if not df_afetados.empty:
                        total_calc = len(df_afetados); passo = 0
                        for num_chamado, grupo in df_afetados.groupby('Nº Chamado'):
                            ids_grupo = grupo['ID'].tolist()
                            calcular_e_atualizar_status_projeto(grupo, ids_grupo)
                            passo += len(grupo)
                            bar.progress(min(60 + int((passo / total_calc) * 40), 100))
                    
                    bar.progress(100); status_txt.text("Concluído!")
                    st.success("Importação e Automação finalizadas!"); time.sleep(1.5)
                    st.cache_data.clear(); st.rerun()

            except Exception as e: st.error(f"Erro no processamento: {e}")

@st.dialog("📦 Atualizar Pedidos", width="medium")
def run_pedido_importer_dialog():
    st.info("""
        Atualize em massa o **Nº do Pedido** e a **Data de Envio**.
        A planilha deve ter as colunas: **CHAMADO**, **PEDIDO** e **DATA_ENVIO**.
        
        *Formatos de data aceitos: DD/MM/AAAA ou AAAA-MM-DD*
    """)
    
    uploaded_pedidos = st.file_uploader("Planilha de Pedidos (.xlsx/.csv)", type=["xlsx", "csv"], key="ped_up_key")
    
    if uploaded_pedidos:
        try:
            if uploaded_pedidos.name.endswith('.csv'): 
                df_ped = pd.read_csv(uploaded_pedidos, sep=';', header=0, dtype=str)
                if len(df_ped.columns) < 2: # Tenta vírgula se ponto e vírgula falhar
                    uploaded_pedidos.seek(0)
                    df_ped = pd.read_csv(uploaded_pedidos, sep=',', header=0, dtype=str)
            else: 
                df_ped = pd.read_excel(uploaded_pedidos, header=0, dtype=str)
            
            # Normaliza colunas (Remove espaços e coloca maiúsculo)
            df_ped.columns = [str(c).strip().upper() for c in df_ped.columns]
            
            # Validação das colunas
            colunas_obrigatorias = ['CHAMADO']
            tem_pedido = 'PEDIDO' in df_ped.columns
            tem_data = 'DATA_ENVIO' in df_ped.columns
            
            if 'CHAMADO' not in df_ped.columns:
                st.error("Erro: A coluna 'CHAMADO' é obrigatória.")
            elif not (tem_pedido or tem_data):
                st.error("Erro: A planilha precisa ter pelo menos 'PEDIDO' ou 'DATA_ENVIO'.")
            else:
                st.dataframe(df_ped.head(), use_container_width=True)
                
                if st.button("🚀 Processar Atualização"):
                    with st.spinner("Atualizando dados..."):
                        # 1. Carrega banco para pegar os IDs internos
                        df_bd = utils_chamados.carregar_chamados_db()
                        if df_bd.empty: st.error("Banco de dados vazio."); st.stop()
                        
                        # Mapa: Nome do Chamado (Excel) -> ID Interno (Banco)
                        id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        
                        count = 0
                        total = len(df_ped)
                        bar = st.progress(0)
                        
                        for i, row in df_ped.iterrows():
                            chamado_key = str(row['CHAMADO']).strip()
                            
                            if chamado_key in id_map:
                                internal_id = id_map[chamado_key]
                                updates = {}
                                
                                # Processa Pedido
                                if tem_pedido:
                                    val_ped = str(row['PEDIDO']).strip()
                                    if val_ped and val_ped.lower() not in ['nan', 'none', '']:
                                        updates['Nº Pedido'] = val_ped
                                        
                                # Processa Data Envio
                                if tem_data:
                                    val_dt = str(row['DATA_ENVIO']).strip()
                                    if val_dt and val_dt.lower() not in ['nan', 'none', '']:
                                        # Tenta converter a data
                                        try:
                                            dt_obj = pd.to_datetime(val_dt, dayfirst=True).date()
                                            updates['Data Envio'] = dt_obj
                                        except:
                                            pass # Se falhar a data, ignora ou grava string se preferir
                                
                                # Se tiver algo para atualizar, chama o banco
                                if updates:
                                    utils_chamados.atualizar_chamado_db(internal_id, updates)
                                    count += 1
                            
                            bar.progress((i + 1) / total)
                        
                        st.success(f"✅ {count} chamados atualizados com sucesso!")
                        time.sleep(1.5)
                        st.cache_data.clear() 
                        st.session_state.importer_done = True
                        
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False; st.rerun()
    if st.button("Fechar"): st.rerun()

# --- IMPORTADOR DE LINKS ---
@st.dialog("🔗 Importar Links Externos", width="medium")
def run_link_importer_dialog():
    st.info("""
        Atualize em massa a coluna **Link Externo**.
        A planilha deve ter as colunas: **CHAMADO** e **LINK**.
    """)
    
    uploaded_links = st.file_uploader("Planilha de Links (.xlsx/.csv)", type=["xlsx", "csv"], key="link_up_key")
    
    if uploaded_links:
        try:
            # Leitura do arquivo (lógica padrão)
            if uploaded_links.name.endswith('.csv'): 
                df_link = pd.read_csv(uploaded_links, sep=';', header=0, dtype=str)
                if len(df_link.columns) < 2: 
                    uploaded_links.seek(0)
                    df_link = pd.read_csv(uploaded_links, sep=',', header=0, dtype=str)
            else: 
                df_link = pd.read_excel(uploaded_links, header=0, dtype=str)
            
            # Normaliza colunas para Maiúsculo
            df_link.columns = [str(c).strip().upper() for c in df_link.columns]
            
            # Validação
            if 'CHAMADO' not in df_link.columns or 'LINK' not in df_link.columns:
                st.error("Erro: A planilha precisa das colunas 'CHAMADO' e 'LINK'.")
            else:
                st.dataframe(df_link.head(), use_container_width=True)
                
                if st.button("🚀 Processar Links"):
                    with st.spinner("Atualizando links..."):
                        # Carrega banco para pegar IDs internos
                        df_bd = utils_chamados.carregar_chamados_db()
                        if df_bd.empty: st.error("Banco vazio."); st.stop()
                        
                        # Mapa: Chamado -> ID Interno
                        id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        
                        count = 0
                        total = len(df_link)
                        bar = st.progress(0)
                        
                        for i, row in df_link.iterrows():
                            chamado_key = str(row['CHAMADO']).strip()
                            link_val = str(row['LINK']).strip()
                            
                            # Só atualiza se achou o chamado e o link não for vazio
                            if chamado_key in id_map and link_val and link_val.lower() not in ['nan', 'none', '']:
                                internal_id = id_map[chamado_key]
                                # Chama o atualizador do banco
                                utils_chamados.atualizar_chamado_db(internal_id, {'Link Externo': link_val})
                                count += 1
                            
                            bar.progress((i + 1) / total)
                        
                        st.success(f"✅ {count} links atualizados!")
                        time.sleep(1.5)
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

@st.dialog("⬇️ Exportar Dados Filtrados", width="small")
def run_exporter_dialog(df_data_to_export):
    st.info(f"Preparando {len(df_data_to_export)} linhas para download.")
    colunas_exportacao_ordenadas = [
        'ID', 'Abertura', 'Nº Chamado', 'Cód. Agência', 'Nome Agência', 'UF', 'Projeto', 
        'Agendamento', 'Sistema', 'Serviço', 'Cód. Equip.', 'Equipamento', 'Qtd.', 
        'Gestor', 'Fechamento', 'Status', 'Analista', 'Técnico', 'Prioridade', 
        'Link Externo', 'Nº Protocolo', 'Nº Pedido', 'Data Envio', 'Obs. Equipamento', 
        'Prazo', 'Descrição', 'Observações e Pendencias', 'Sub-Status', 
        'Status Financeiro', 'Observação', 'Log do Chamado', 'Agencia_Combinada'
    ]
    colunas_presentes_no_df = [col for col in colunas_exportacao_ordenadas if col in df_data_to_export.columns]
    df_para_exportar = df_data_to_export[colunas_presentes_no_df]
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_para_exportar.to_excel(writer, index=False, sheet_name="Dados Filtrados")
    buffer.seek(0)
    
    st.download_button(
        label="📥 Baixar Arquivo Excel", data=buffer, file_name="dados_filtrados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
    )
    if st.button("Fechar", use_container_width=True):
        st.session_state.show_export_popup = False; st.rerun()

# --- 5. CARREGAMENTO E SIDEBAR ---
df = utils_chamados.carregar_chamados_db()

colunas_novas_obrigatorias = [
    'chk_cancelado', 
    'chk_pendencia_equipamento', 
    'chk_pendencia_infra',
    'chk_alteracao_chamado', 
    'chk_envio_parcial', 
    'chk_equipamento_entregue',
    'chk_status_enviado', 
    'chk_financeiro_banco', 
    'Book Enviado',
    'Sub-Status'
]

if not df.empty:
    for col in colunas_novas_obrigatorias:
        if col not in df.columns:
            df[col] = "FALSE" # Cria a coluna com valor padrão se ela não existir

with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"): run_importer_dialog()
    if st.button("📦 Atualizar Pedidos"): run_pedido_importer_dialog()
    if st.button("🔗 Atualizar Links"): run_link_importer_dialog()
    
    st.divider()
    
    if st.button("🔄 Atualizar Status"):
        with st.spinner("Reprocessando todos os status..."):
            df_todos = utils_chamados.carregar_chamados_db()
            if not df_todos.empty:
                count_mudou = 0
                for num_chamado, grupo in df_todos.groupby('Nº Chamado'):
                    ids_grupo = grupo['ID'].tolist()
                    if calcular_e_atualizar_status_projeto(grupo, ids_grupo):
                        count_mudou += 1
                st.success(f"Processo finalizado! {count_mudou} projetos tiveram status alterado.")
                time.sleep(2)
                st.rerun()
            else:
                st.warning("Banco de dados vazio.")

    st.divider()
    st.header("📤 Exportação")
    # --- BOTÃO DE EXPORTAÇÃO ESTRUTURADA ---
    if st.button("📥 Baixar Relatório Estruturado (.xlsx)"):
        with st.spinner("Gerando relatório estruturado..."):
            df_export = utils_chamados.carregar_chamados_db()
            
            if not df_export.empty:
                # 1. CRIAÇÃO DO ID_PROJETO
                # Agrupa por 'Cód. Agência' e 'Projeto' e atribui um número sequencial (1, 2, 3...)
                # O 'dense' garante que não pule números
                colunas_agrupadoras = ['Cód. Agência', 'Projeto']
                df_export['ID_PROJETO'] = df_export.groupby(colunas_agrupadoras).ngroup() + 1
                
                # Ordena para ficar bonito no Excel (Agrupado por ID)
                df_export = df_export.sort_values(by=['ID_PROJETO', 'Nº Chamado'])

                # 2. DEFINIÇÃO DA ORDEM DAS COLUNAS (Conforme sua imagem)
                colunas_ordenadas = [
                    'ID_PROJETO',
                    'Abertura',         
                    'Status',
                    'Cód. Agência',
                    'Nome Agência',
                    'UF',
                    'Nº Chamado',
                    'Projeto',
                    'Sistema',
                    'Serviço',
                    'Cód. Equip.',    
                    'Equipamento',     
                    'Qtd.',            
                    'Agendamento',
                    'Reagendamento',     
                    'Fechamento',        
                    'Gestor',
                    'Analista',
                    'Técnico',
                    'Observação',
                    'Log do Chamado',
                    'Link Externo',
                    'Nº Protocolo',
                    'Nº Pedido',
                    'Data Envio',
                    'Obs. Equipamento',
                    'Prazo',
                    'Descrição',
                    'Observações e Pendencias',
                    'Sub-Status',
                    
                    # Colunas de Controle (Checkboxes)
                    'chk_cancelado',
                    'chk_pendencia_equipamento',
                    'chk_pendencia_infra',
                    'chk_alteracao_chamado',
                    'chk_envio_parcial',
                    'chk_equipamento_entregue',
                    'chk_status_enviado',
                    'chk_financeiro_banco',
                    'book_enviado'
                ]
                
                # Filtra apenas as colunas que realmente existem no DataFrame para evitar erro
                cols_finais = [c for c in colunas_ordenadas if c in df_export.columns]
                
                # Cria o DF final apenas com as colunas na ordem certa
                df_final = df_export[cols_finais]

                # 3. EXPORTAÇÃO COM FORMATAÇÃO (XLSXWRITER)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Relatorio_Projetos')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Relatorio_Projetos']
                    
                    # Formatos
                    fmt_header = workbook.add_format({
                        'bold': True, 
                        'bg_color': '#D3D3D3', 
                        'border': 1,
                        'align': 'center',
                        'valign': 'vcenter'
                    })
                    
                    fmt_id = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#E3F2FD'}) # Destaque para o ID
                    
                    # Aplica formatação no cabeçalho
                    for col_num, value in enumerate(df_final.columns.values):
                        worksheet.write(0, col_num, value, fmt_header)
                        
                        # Ajuste de largura das colunas
                        largura = 15 # Padrão
                        if value in ['Nome Agência', 'Projeto', 'Descrição', 'Observação', 'Link Externo']: largura = 40
                        elif value in ['ID_PROJETO', 'UF', 'Qtd.']: largura = 8
                        elif 'chk_' in value: largura = 12
                        
                        worksheet.set_column(col_num, col_num, largura)
                    
                    # Aplica formatação na coluna ID (Primeira coluna)
                    worksheet.set_column(0, 0, 10, fmt_id)

                data_export = output.getvalue()
                
                st.download_button(
                    label="✅ Clique aqui para salvar Relatório",
                    data=data_export,
                    file_name=f"Relatorio_GTS_{date.today().strftime('%d-%m-%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("O banco de dados está vazio.")
                     
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

# --- VISÃO: OPERACIONAL ---
else:
    st.title("🔧 Detalhes do Projeto")

    with st.container():
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        # --- 1. DEFINIÇÃO DA DATA ---
        c_tit, c_date = st.columns([4, 1.5])
        with c_tit: st.markdown("### 🔍 Filtros & Pesquisa")
        with c_date:
            # Garante que a coluna é data
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            
            # Define data padrão
            d_min = df_filtrado['Agendamento'].min() if not pd.isna(df_filtrado['Agendamento'].min()) else date.today()
            d_max = df_filtrado['Agendamento'].max() if not pd.isna(df_filtrado['Agendamento'].max()) else date.today()
            
            # CRIA A VARIÁVEL filtro_data_range
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")

        # --- 2. FILTRO PRELIMINAR ---
        df_opcoes = df_filtrado.copy()
        
        # [FIX] This block is now safely inside the else, so filtro_data_range exists
        if len(filtro_data_range) == 2:
            d_inicio, d_fim = filtro_data_range
            df_opcoes = df_opcoes[
                (df_opcoes['Agendamento'] >= pd.to_datetime(d_inicio)) & 
                (df_opcoes['Agendamento'] <= pd.to_datetime(d_fim))
            ]

        # --- 3. LÓGICA DO BOTÃO "VER DETALHES" ---
        padrao_projetos = []
        if "sel_projeto" in st.session_state:
            proj_vindo_do_cockpit = st.session_state["sel_projeto"]
            if proj_vindo_do_cockpit in df_opcoes['Projeto'].unique():
                padrao_projetos = [proj_vindo_do_cockpit]
            del st.session_state["sel_projeto"]

        # --- 4. PREPARAÇÃO DAS LISTAS ---
        df_opcoes['_filtro_agencia'] = df_opcoes['Cód. Agência'].astype(str) + " - " + df_opcoes['Nome Agência'].astype(str)
        opcoes_agencia = sorted(df_opcoes['_filtro_agencia'].dropna().unique().tolist())
        opcoes_projeto = sorted(df_opcoes['Projeto'].dropna().unique().tolist())
        
        # --- 5. CAMPOS DE FILTRO ---
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1.5])
        
        with c1:
            busca_geral = st.text_input("Busca", placeholder="🔎 ID, Nome, Serviço...", label_visibility="collapsed")
        
        with c2:
            filtro_agencia_multi = st.multiselect("Agências", options=opcoes_agencia, placeholder="Filtrar Agência", label_visibility="collapsed")
            
        with c3:
            if filtro_agencia_multi:
                projs_da_agencia = df_opcoes[df_opcoes['_filtro_agencia'].isin(filtro_agencia_multi)]['Projeto'].unique()
                opcoes_projeto = sorted([p for p in opcoes_projeto if p in projs_da_agencia])

            filtro_projeto_multi = st.multiselect("Projetos", options=opcoes_projeto, default=padrao_projetos, placeholder="Filtrar Projeto", label_visibility="collapsed")
        
        with c4:
            df_acao = df_opcoes.copy()
            if filtro_projeto_multi: df_acao = df_acao[df_acao['Projeto'].isin(filtro_projeto_multi)]
            opcoes_acao = sorted([str(x) for x in df_acao['Sub-Status'].dropna().unique().tolist() if str(x).strip() != ''])
            
            filtro_acao_multi = st.multiselect("Ação / Etapa", options=opcoes_acao, placeholder="Filtrar Ação/Status", label_visibility="collapsed")

        st.markdown('</div>', unsafe_allow_html=True)
        
    # --- APLICAÇÃO DOS FILTROS (CRITICAL FIX: INDENTATION) ---
    # This entire block must be indented to align with 'st.title' above
    # so it is ONLY executed inside the 'else' block.
    
    df_view = df_filtrado.copy()
    
    # 1. Filtro de Data
    if len(filtro_data_range) == 2:
        d_inicio, d_fim = filtro_data_range
        df_view = df_view[(df_view['Agendamento'] >= pd.to_datetime(d_inicio)) & (df_view['Agendamento'] <= pd.to_datetime(d_fim))]

    # 2. Busca Texto
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)]
    
    # 3. Filtro de Agência
    if filtro_agencia_multi:
        df_view['_filtro_agencia'] = df_view['Cód. Agência'].astype(str) + " - " + df_view['Nome Agência'].astype(str)
        df_view = df_view[df_view['_filtro_agencia'].isin(filtro_agencia_multi)]

    # 4. Filtro de Projeto
    if filtro_projeto_multi: 
        df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
        
    # 5. Filtro de Ação
    if filtro_acao_multi:
        df_view = df_view[df_view['Sub-Status'].astype(str).isin(filtro_acao_multi)]
        
    # KPIS DE VISÃO
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
    with k1: st.markdown(f"""<div class="kpi-card kpi-blue"><div class="kpi-title">Chamados (Filtro)</div><div class="kpi-value">{qtd_total}</div></div>""", unsafe_allow_html=True)
    with k2: st.markdown(f"""<div class="kpi-card kpi-orange"><div class="kpi-title">Projetos Abertos</div><div class="kpi-value">{proj_abertos}</div></div>""", unsafe_allow_html=True)
    with k3: st.markdown(f"""<div class="kpi-card kpi-green"><div class="kpi-title">Projetos Finalizados</div><div class="kpi-value">{proj_concluidos}</div></div>""", unsafe_allow_html=True)
    with k4: st.markdown(f"""<div class="kpi-card kpi-purple"><div class="kpi-title">Tarefas Concluídas</div><div class="kpi-value">{qtd_fim}</div></div>""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- BARRA DE RESUMO ---
    if not df_view.empty:
        counts = df_view['Sub-Status'].value_counts()
        top_status = counts.head(5) 
        if len(top_status) > 0:
            cols = st.columns(len(top_status))
            for i, (status, count) in enumerate(top_status.items()):
                try: cor = utils_chamados.get_status_color(status)
                except: cor = "#ccc"
                with cols[i]:
                    st.markdown(f"""<div class="status-summary-box" style="border-left: 5px solid {cor}; background: white; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;"><span class="status-label" style="font-size: 0.75em; font-weight: bold; color: #555; text-transform: uppercase;">{str(status)[:15]}</span><span class="status-val" style="font-size: 1.1em; font-weight: 800; color: #333;">{count}</span></div>""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    aba_lista, aba_calendario = st.tabs(["📋 Lista Detalhada", "📅 Agenda Semanal"])
    
    with aba_lista:     
        if df_view.empty:
            st.warning("Nenhum projeto encontrado com os filtros atuais.")
        else:
            # 1. AGRUPAMENTO
            colunas_agrupamento = ['Projeto', 'Cód. Agência', 'Nome Agência']
            grupos_projeto = list(df_view.groupby(colunas_agrupamento))
            grupos_projeto.sort(key=lambda x: x[0][2]) # Ordena por Nome da Agência

            # 2. PAGINAÇÃO
            ITENS_POR_PAG = 20
            total_itens = len(grupos_projeto)
            total_paginas = math.ceil(total_itens / ITENS_POR_PAG)
            
            if total_paginas > 1:
                c_info, c_pag = st.columns([4, 1])
                with c_info:
                    pag_atual = st.session_state.get('pag_proj', 1)
                    st.caption(f"Exibindo {total_itens} grupos • Página {pag_atual} de {total_paginas}")
                with c_pag:
                    pag = st.number_input("Pág.", 1, total_paginas, key="pag_proj")
            else:
                pag = 1
            
            inicio = (pag - 1) * ITENS_POR_PAG
            fim = inicio + ITENS_POR_PAG
            grupos_pagina_atual = grupos_projeto[inicio:fim]

            # 3. LOOP DE RENDERIZAÇÃO
            for (nome_proj, cod_ag, nome_ag), df_grupo in grupos_pagina_atual:
                row_head = df_grupo.iloc[0]
                
                # --- PREPARAÇÃO DE DADOS DO CABEÇALHO ---
                st_proj = clean_val(row_head.get('Status'), "Não Iniciado")
                cor_st = utils_chamados.get_status_color(st_proj)
                
                analista = clean_val(row_head.get('Analista'), "N/D").split(' ')[0].upper()
                if "GIOVANA" in analista: css_ana = "ana-azul"
                elif "MARCELA" in analista: css_ana = "ana-verde"
                elif "MONIQUE" in analista: css_ana = "ana-rosa"
                else: css_ana = "ana-default"
                
                tecnico = clean_val(row_head.get('Técnico'), "N/D").split(' ')[0].title()
                gestor = clean_val(row_head.get('Gestor'), "N/D").split(' ')[0].title()
                
                nome_ag_limpo = str(nome_ag).replace(str(cod_ag), '').strip(' -')

                # Datas SLA
                datas_validas = pd.to_datetime(df_grupo['Agendamento'], errors='coerce').dropna()
                data_prox = datas_validas.min() if not datas_validas.empty else None
                
                if data_prox:
                    data_str = data_prox.strftime('%d/%m/%Y')
                    data_sla = data_prox + timedelta(days=5)
                    atrasado = data_sla.date() < date.today() and st_proj not in ['Concluído', 'Finalizado', 'Faturado']
                    cor_sla = "#D32F2F" if atrasado else "#388E3C"
                    sla_html = f"<span style='color:{cor_sla}; font-weight:bold;'>Até {data_sla.strftime('%d/%m')}</span>"
                else:
                    data_str = "-"
                    sla_html = "-"

                # --- CÁLCULO DA ETAPA ATUAL (GARGALO) ---
                hierarquia_visual = [
                    "Pendência de Infra", 
                    "Pendência de equipamento", 
                    "Alteração do chamado",
                    "Equipamento enviado Parcial", 
                    "Solicitar equipamento", 
                    "Aguardando envio",
                    "Equipamento enviado", 
                    "Abrir chamado Btime", 
                    "Acionar técnico",
                    "Follow-up", 
                    "Enviar Book", 
                    "Aguardando Faturamento", 
                    "Faturado", 
                    "Equipamento entregue"
                ]
                
                etapa_projeto_txt = "-"
                
                # Varre a hierarquia para encontrar o primeiro status que existe neste grupo
                for h in hierarquia_visual:
                    existe = any(
                        (str(r.get('Sub-Status', '')).strip() == h) and (str(r.get('chk_cancelado', '')).upper() != 'TRUE')
                        for _, r in df_grupo.iterrows()
                    )
                    if existe:
                        etapa_projeto_txt = h
                        break
                
                # Se não achou nenhum da lista (fallback)
                if etapa_projeto_txt == "-":
                    ativos = df_grupo[df_grupo['chk_cancelado'].astype(str).str.upper() != 'TRUE']
                    if not ativos.empty: 
                        etapa_projeto_txt = clean_val(ativos.iloc[0].get('Sub-Status'), "-")
                    else:
                        etapa_projeto_txt = "Todos Cancelados"

                # --- CABEÇALHO DO PROJETO (RENDERIZAÇÃO ÚNICA) ---
                st.markdown('<div class="gold-line"></div>', unsafe_allow_html=True)
                with st.container():
                    # Linha 1
                    l1_c1, l1_c2, l1_c3, l1_c4 = st.columns([2.5, 1, 1, 1])
                    with l1_c1: st.markdown(f"<span class='agencia-header'>🏢 {cod_ag} - {nome_ag_limpo}</span>", unsafe_allow_html=True)
                    with l1_c2: st.markdown(f"<span class='meta-label'>AGENDAMENTO</span><br><b>📅 {data_str}</b>", unsafe_allow_html=True)
                    with l1_c3: st.markdown(f"<span class='meta-label'>ANALISTA</span><br><span class='{css_ana}'>{analista}</span>", unsafe_allow_html=True)
                    with l1_c4: st.markdown(f"<span class='status-badge' style='background-color:{cor_st}; margin-top:5px;'>{st_proj}</span>", unsafe_allow_html=True)

                    # Linha 2
                    l2_c1, l2_c2, l2_c3, l2_c4 = st.columns([2.5, 1, 1, 1])
                    with l2_c1: st.markdown(f"<span class='meta-label'>PROJETO</span><br><span style='font-size:1em; font-weight:bold; color:#555'>{nome_proj}</span>", unsafe_allow_html=True)
                    with l2_c2: st.markdown(f"<span class='meta-label'>SLA (+5d)</span><br>{sla_html}", unsafe_allow_html=True)
                    with l2_c3: st.markdown(f"<span class='meta-label'>GESTOR</span><br><span class='gestor-bold'>👤 {gestor}</span>", unsafe_allow_html=True)
                    with l2_c4: 
                        if etapa_projeto_txt and etapa_projeto_txt not in ["-", "nan"]: 
                            st.markdown(f"<span class='meta-label'>ETAPA ATUAL</span><br><span class='action-text'>👉 {etapa_projeto_txt}</span>", unsafe_allow_html=True)
                        else: 
                            st.markdown(f"<span class='meta-label'>ETAPA ATUAL</span><br><span style='color:#ccc'>-</span>", unsafe_allow_html=True)

                # --- LISTA DE CHAMADOS (DENTRO DO EXPANDER) ---
                label_expander = f"📂 Visualizar {len(df_grupo)} Chamado(s) vinculados"
                with st.expander(label_expander):
                    
                    th1, th2, th3, th4, th5 = st.columns([1.2, 3, 1.2, 2, 0.8])
                    th1.markdown("<small style='color:#999'>CHAMADO</small>", unsafe_allow_html=True)
                    th2.markdown("<small style='color:#999'>SERVIÇO</small>", unsafe_allow_html=True)
                    th3.markdown("<small style='color:#999'>DATA</small>", unsafe_allow_html=True)
                    th4.markdown("<small style='color:#999'>AÇÃO NECESSÁRIA</small>", unsafe_allow_html=True)
                    th5.markdown("")
                    
                    st.markdown("<hr style='margin: 5px 0 10px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

                    # --- CORREÇÃO DO ERRO DE CHAVE DUPLICADA ---
                    # Usamos 'enumerate' para gerar um índice único 'loop_idx' para cada linha visualizada
                    for loop_idx, (idx, row_chamado) in enumerate(df_grupo.iterrows()):
                        n_chamado = str(row_chamado['Nº Chamado'])
                        servico = str(row_chamado['Serviço'])
                        acao_ch = str(row_chamado.get('Sub-Status', ''))
                        if acao_ch in ['nan', 'None', '', '-']: acao_ch = "Em análise"
                        
                        # Tratamento Cancelado visual na lista
                        is_canc = str(row_chamado.get('chk_cancelado', '')).upper() == 'TRUE'
                        style_canc = "text-decoration: line-through; color: #999;" if is_canc else ""
                        
                        dt_raw = pd.to_datetime(row_chamado['Agendamento'], errors='coerce')
                        dt_fmt = dt_raw.strftime('%d/%m') if pd.notna(dt_raw) else "-"

                        c1, c2, c3, c4, c5 = st.columns([1.2, 3, 1.2, 2, 0.8])
                        
                        with c1: st.markdown(f"<b style='{style_canc}'>🎫 {n_chamado}</b>", unsafe_allow_html=True)
                        with c2: st.markdown(f"<span style='color:#333; {style_canc}'>{servico}</span>", unsafe_allow_html=True)
                        with c3: st.markdown(f"📅 {dt_fmt}", unsafe_allow_html=True)
                        with c4: 
                            if is_canc: st.markdown(f"<span style='font-size:0.85em; color:#D32F2F; font-weight:600;'>🚫 Cancelado</span>", unsafe_allow_html=True)
                            else: st.markdown(f"<span style='font-size:0.85em; color:#E65100; font-weight:600;'>{acao_ch}</span>", unsafe_allow_html=True)
                        
                        with c5:
                            # Chave única garantida adicionando loop_idx
                            if st.button("🔎", key=f"btn_ch_{row_chamado['ID']}_{loop_idx}", help="Ver detalhes"):
                                open_chamado_dialog(row_chamado.to_dict())
                                
                        st.markdown("<div style='border-bottom: 1px solid #f8f8f8; margin-bottom: 8px;'></div>", unsafe_allow_html=True)                        
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
