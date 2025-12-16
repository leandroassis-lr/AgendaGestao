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
        
        /* Pop-up Largo */
        div[data-testid="stDialog"] { width: 70vw; }
    </style>
""", unsafe_allow_html=True)

# --- CSS PARA DASHBOARD E KPIS ---
st.markdown("""
    <style>
        .filter-container { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #e9ecef; margin-bottom: 20px; }
        .kpi-card { background-color: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; text-align: center; height: 100%; }
        .kpi-title { font-size: 0.85em; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
        .kpi-value { font-size: 1.8em; font-weight: 800; color: #2c3e50; }
        .kpi-blue   { border-bottom: 4px solid #1565C0; }
        .kpi-orange { border-bottom: 4px solid #F57C00; }
        .kpi-green  { border-bottom: 4px solid #2E7D32; }
        .kpi-purple { border-bottom: 4px solid #7B1FA2; }
        .status-summary-box { background-color: white; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; }
        .status-label { font-size: 0.75em; font-weight: bold; color: #555; text-transform: uppercase; }
        .status-val { font-size: 1.1em; font-weight: 800; color: #333; }
    </style>
""", unsafe_allow_html=True)

# --- CSS PARA PLANNER ---
st.markdown("""
    <style>
        .planner-card { background-color: white; border-radius: 8px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.08); border: 1px solid #e0e0e0; margin-bottom: 15px; transition: all 0.2s ease; position: relative; overflow: hidden; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
        .planner-card:hover { box-shadow: 0 8px 15px rgba(0,0,0,0.1); transform: translateY(-3px); border-color: #bdc3c7; }
        .planner-title { font-size: 1.05rem; font-weight: 700; color: #2c3e50; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .progress-container { width: 100%; background-color: #f1f2f6; border-radius: 4px; height: 6px; margin: 10px 0; overflow: hidden; }
        .progress-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease-in-out; }
        .tag-status { font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 12px; display: inline-flex; align-items: center; margin-right: 5px; }
        .tag-red { background: #FFEBEE; color: #C62828; }
        .tag-green { background: #E8F5E9; color: #2E7D32; }
        .tag-gray { background: #F5F5F5; color: #757575; }
        .planner-footer { margin-top: 12px; display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #7f8c8d; border-top: 1px solid #f5f5f5; padding-top: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

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

# --- LÓGICA DE STATUS "TOP-DOWN" ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0]
    # ... (Sua lógica de status original mantida intacta aqui) ...
    n_chamado = str(row.get('Nº Chamado', ''))
    is_equip = '-e-' in n_chamado.lower()
    is_serv = not is_equip 
    link_presente = row.get('Link Externo') and str(row.get('Link Externo')).strip() not in ['', 'nan', 'None']
    tecnico_presente = row.get('Técnico') and str(row.get('Técnico')).strip() not in ['', 'nan', 'None']
    pedido_presente = row.get('Nº Pedido') and str(row.get('Nº Pedido')).strip() not in ['', 'nan', 'None']
    envio_presente = row.get('Data Envio') and pd.notna(row.get('Data Envio'))
    flag_banco = str(row.get('chk_financeiro_banco', '')).upper() == 'TRUE'
    flag_book = str(row.get('chk_financeiro_book', '')).upper() == 'TRUE'
    book_enviado_sim = str(row.get('Book Enviado', '')).upper() == 'SIM'
    chk_status_cli = str(row.get('chk_status_enviado', '')).upper() == 'TRUE'
    chk_eq_entregue = str(row.get('chk_equipamento_entregue', '')).upper() == 'TRUE'
    status_atual = str(row.get('Status', 'Não Iniciado')).strip()
    status_manual_bloqueantes = ["Pendência de Infra", "Pendência de Equipamento", "Cancelado", "Pausado"]
    novo_status = "Não Iniciado"; novo_sub_status = ""

    if flag_banco: novo_status = "Finalizado"; novo_sub_status = "FATURADO"
    elif flag_book:
        if book_enviado_sim: novo_status = "Finalizado"; novo_sub_status = "AGUARDANDO FATURAMENTO"
        else: novo_status = "Finalizado"; novo_sub_status = "ENVIAR BOOK"
    elif status_atual in status_manual_bloqueantes: novo_status = status_atual; novo_sub_status = str(row.get('Sub-Status', ''))
    elif is_equip:
        if chk_eq_entregue: novo_status = "Concluído"; novo_sub_status = "Aguardando Faturamento"
        elif envio_presente: novo_status = "Em Andamento"; novo_sub_status = "Aguardando Entrega"
        elif pedido_presente: novo_status = "Em Andamento"; novo_sub_status = "Aguardando envio do equipamento"
        else: novo_status = "Não Iniciado"; novo_sub_status = "Solicitar Equipamento"
    else: 
        if chk_status_cli: novo_status = "Concluído"; novo_sub_status = "Enviar Book"
        elif tecnico_presente: novo_status = "Em Andamento"; novo_sub_status = "Enviar Status Cliente"
        elif link_presente: novo_status = "Em Andamento"; novo_sub_status = "Acionar técnico"
        else: novo_status = "Não Iniciado"; novo_sub_status = "Abrir chamado Btime"

    sub_status_db = str(row.get('Sub-Status', '')).strip()
    sub_status_novo_str = str(novo_sub_status).strip()

    if status_atual != novo_status or sub_status_db != sub_status_novo_str:
        updates = {"Status": novo_status, "Sub-Status": novo_sub_status}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

# --- IMPORTADOR ---
@st.dialog("Importar Chamados", width="large")
def run_importer_dialog():
    # ... (Seu importador mantido) ...
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
                            uploaded_file.seek(0); df = pd.read_csv(uploaded_file, sep=',', header=0, dtype=str, encoding='utf-8-sig')
                    except:
                        uploaded_file.seek(0); df = pd.read_csv(uploaded_file, sep=None, engine='python', header=0, dtype=str)
                else: df = pd.read_excel(uploaded_file, header=0, dtype=str)
                df.dropna(how='all', inplace=True); dfs_list.append(df)
            except Exception as e: st.error(f"Erro ao ler '{uploaded_file.name}': {e}"); return

        if dfs_list:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
                if len(df_raw.columns) < 12: st.error("Arquivo com colunas insuficientes."); return

                dados_mapeados = {
                    'Nº Chamado': df_raw.iloc[:, 0], 'Cód. Agência': df_raw.iloc[:, 1], 'Nome Agência': df_raw.iloc[:, 2],
                    'agencia_uf': df_raw.iloc[:, 3], 'Analista': df_raw.iloc[:, 22] if len(df_raw.columns) > 22 else "",
                    'Gestor': df_raw.iloc[:, 20] if len(df_raw.columns) > 20 else "", 'Serviço': df_raw.iloc[:, 4],
                    'Projeto': df_raw.iloc[:, 5], 'Agendamento': df_raw.iloc[:, 6], 'Sistema': df_raw.iloc[:, 8], 
                    'Cod_equipamento': df_raw.iloc[:, 9], 'Nome_equipamento': df_raw.iloc[:, 10], 'Qtd': df_raw.iloc[:, 11]
                }
                df_final = pd.DataFrame(dados_mapeados).fillna("")

                def formatar_item(row):
                    qtd = str(row['Qtd']).strip(); desc = str(row['Nome_equipamento']).strip()
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
                regras['Sistema'] = 'first'; regras['Item_Formatado'] = juntar_textos 
                
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
                        if chamado_num in mapa_ids: row['ID_Banco'] = mapa_ids[chamado_num]; lista_atualizar.append(row)
                        else: lista_novos.append(row)
                else: lista_novos = [r for r in df_grouped.to_dict('records') if str(r['Nº Chamado']).strip()]

                df_insert = pd.DataFrame(lista_novos); df_update = pd.DataFrame(lista_atualizar)
                c1, c2 = st.columns(2); c1.metric("🆕 Criar Novos", len(df_insert)); c2.metric("🔄 Atualizar Existentes", len(df_update))
                
                if st.button("🚀 Processar Importação"):
                    bar = st.progress(0); status_txt = st.empty()
                    if not df_insert.empty:
                        status_txt.text("Inserindo..."); utils_chamados.bulk_insert_chamados_db(df_insert)
                    bar.progress(30)
                    if not df_update.empty:
                        status_txt.text("Atualizando...")
                        for i, row in enumerate(df_update.to_dict('records')):
                            updates = {
                                'Sistema': row['Sistema'], 'Equipamento': row['Equipamento'], 'Descrição': row['Descrição'],
                                'Serviço': row['Serviço'], 'Projeto': row['Projeto'], 'Agendamento': row['Agendamento'], 
                                'Analista': row['Analista'], 'Gestor': row['Gestor']
                            }
                            utils_chamados.atualizar_chamado_db(row['ID_Banco'], updates)
                    bar.progress(60)
                    status_txt.text("Automação..."); df_todos = utils_chamados.carregar_chamados_db()
                    chamados_imp = df_grouped['Nº Chamado'].astype(str).str.strip().tolist()
                    df_afetados = df_todos[df_todos['Nº Chamado'].astype(str).str.strip().isin(chamados_imp)]
                    if not df_afetados.empty:
                        for num_chamado, grupo in df_afetados.groupby('Nº Chamado'):
                            ids_grupo = grupo['ID'].tolist(); calcular_e_atualizar_status_projeto(grupo, ids_grupo)
                    bar.progress(100); status_txt.text("Concluído!"); st.success("Sucesso!"); time.sleep(1.5); st.cache_data.clear(); st.rerun()

            except Exception as e: st.error(f"Erro: {e}")

@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    # ... (Seu importador de links mantido) ...
    st.info("Atualize Links Externos. Colunas: CHAMADO e LINK."); uploaded_links = st.file_uploader("Planilha", type=["xlsx", "csv"], key="link_up_key")
    if uploaded_links:
        try:
            if uploaded_links.name.endswith('.csv'): df_links = pd.read_csv(uploaded_links, sep=';', header=0, dtype=str)
            else: df_links = pd.read_excel(uploaded_links, header=0, dtype=str)
            df_links.columns = [str(c).strip().upper() for c in df_links.columns]
            if 'CHAMADO' in df_links.columns and 'LINK' in df_links.columns:
                if st.button("🚀 Atualizar Links"):
                    with st.spinner("..."):
                        df_bd = utils_chamados.carregar_chamados_db(); id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        count = 0
                        for _, row in df_links.iterrows():
                            ch = row['CHAMADO']; lk = row['LINK']
                            if ch in id_map and pd.notna(lk) and str(lk).strip():
                                utils_chamados.atualizar_chamado_db(id_map[ch], {'Link Externo': lk}); count += 1
                        st.success(f"{count} links atualizados!"); st.cache_data.clear(); st.rerun()
            else: st.error("Colunas CHAMADO e LINK obrigatórias.")
        except Exception as e: st.error(f"Erro: {e}")

# --- DIALOG DO DETALHE DO CHAMADO (NOVO POP-UP) ---
@st.dialog("Detalhes do Chamado", width="large")
def editar_chamado_dialog(row_dict, id_chamado):
    row = pd.Series(row_dict)
    form_key = f"pop_{id_chamado}"
    
    st.markdown(f"### 🎫 {row.get('Nº Chamado')}")
    st.caption(f"Projeto: {row.get('Projeto')} | Agência: {row.get('Nome Agência')}")
    
    # Listas
    try:
        df_pj = utils.carregar_config_db("projetos_nomes"); lst_pj = [str(x) for x in df_pj.iloc[:,0].dropna().tolist()] if not df_pj.empty else []
        df_tc = utils.carregar_config_db("tecnicos"); lst_tc = [str(x) for x in df_tc.iloc[:,0].dropna().tolist()] if not df_tc.empty else []
        df_us = utils.carregar_usuarios_db(); df_us.columns = [c.capitalize() for c in df_us.columns] if not df_us.empty else []
        lst_an = [str(x) for x in df_us["Nome"].dropna().tolist()] if not df_us.empty and "Nome" in df_us.columns else []
    except: lst_pj=[]; lst_tc=[]; lst_an=[]
    
    def sf(v): return str(v) if pd.notna(v) and str(v).lower() not in ['nan', 'none', ''] else ""
    
    st_atual = row.get('Status', 'Não Iniciado')
    l_st_manual = ["Pendência de Infra", "Pendência de Equipamento", "Cancelado", "Pausado"]
    is_manual_mode = st_atual in l_st_manual
    lista_opcoes = ["🔄 STATUS AUTOMATICO"] + l_st_manual
    if st_atual not in lista_opcoes: lista_opcoes.append(st_atual)
    idx_inicial = lista_opcoes.index(st_atual) if st_atual in lista_opcoes else 0

    v_pj = sf(row.get('Projeto', '')); l_pj = sorted(list(set(lst_pj + [v_pj]))); i_pj = l_pj.index(v_pj) if v_pj in l_pj else 0
    v_tc = sf(row.get('Técnico', '')); l_tc = sorted(list(set(lst_tc + [v_tc]))); i_tc = l_tc.index(v_tc) if v_tc in l_tc else 0
    v_an = sf(row.get('Analista', '')); l_an = sorted(list(set(lst_an + [v_an]))); i_an = l_an.index(v_an) if v_an in l_an else 0

    is_financeiro_locked = str(row.get('chk_financeiro_banco', '')).upper() == 'TRUE' or str(row.get('chk_financeiro_book', '')).upper() == 'TRUE'
    n_chamado_str = str(row.get('Nº Chamado', '')); is_equip = '-e-' in n_chamado_str.lower()
    
    with st.form(key=form_key):
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            if is_financeiro_locked: st.markdown(f"<small>Status</small><br><b style='color:#2E7D32'>{st_atual}</b>", unsafe_allow_html=True); n_st = st_atual
            else: n_st = st.selectbox("Status", lista_opcoes, index=idx_inicial); st.caption("Modo Manual" if is_manual_mode else "Automático")
        n_ab = k2.date_input("Abertura", value=_to_date_safe(row.get('Abertura')) or date.today(), format="DD/MM/YYYY")
        n_ag = k3.date_input("Agendamento", value=_to_date_safe(row.get('Agendamento')), format="DD/MM/YYYY")
        n_fi = k4.date_input("Finalização", value=_to_date_safe(row.get('Fechamento')), format="DD/MM/YYYY")

        k5, k6, k7 = st.columns(3)
        n_an = k5.selectbox("Analista", l_an, index=i_an); n_ge = k6.text_input("Gestor", value=row.get('Gestor', '')); n_tc = k7.selectbox("Técnico", l_tc, index=i_tc)

        k8, k9, k10 = st.columns(3)
        n_pj = k8.selectbox("Projeto", l_pj, index=i_pj); n_sv = k9.text_input("Serviço", value=row.get('Serviço', '')); n_si = k10.text_input("Sistema", value=row.get('Sistema', ''))

        n_ob = st.text_area("Observações", value=row.get('Observações e Pendencias', ''), height=80)
        st.markdown("---")
        val_chk_cli = str(row.get('chk_status_enviado', '')).upper() == 'TRUE'; val_chk_ent = str(row.get('chk_equipamento_entregue', '')).upper() == 'TRUE'
        n_lk = row.get('Link Externo', ''); n_pt = row.get('Nº Protocolo', ''); n_pedido = row.get('Nº Pedido', ''); n_envio = _to_date_safe(row.get('Data Envio'))
        ret_chk_cli = val_chk_cli; ret_chk_ent = val_chk_ent

        if is_equip:
            c_e1, c_e2, c_e3, c_e4 = st.columns([1, 1.5, 1.5, 2])
            c_e1.text_input("Nº Chamado", value=n_chamado_str, disabled=True)
            n_pedido = c_e2.text_input("📦 Nº Pedido", value=n_pedido)
            n_envio = c_e3.date_input("🚚 Data Envio", value=n_envio, format="DD/MM/YYYY")
            with c_e4: st.markdown("<br>", unsafe_allow_html=True); ret_chk_ent = st.checkbox("✅ EQUIPAMENTO ENTREGUE", value=val_chk_ent)
        else:
            c_s1, c_s2, c_s3, c_s4 = st.columns([1, 2, 1.5, 1.5])
            with c_s1:
                if n_lk: st.markdown(f"<small>Link</small><br><a href='{n_lk}' target='_blank'>🔗 Abrir Link</a>", unsafe_allow_html=True)
                else: st.text_input("Nº Chamado", value=n_chamado_str, disabled=True)
            n_lk = c_s2.text_input("Link URL", value=n_lk)
            n_pt = c_s3.text_input("Protocolo", value=n_pt)
            with c_s4: st.markdown("<br>", unsafe_allow_html=True); ret_chk_cli = st.checkbox("✅ STATUS ENVIADO", value=val_chk_cli)

        st.markdown("---")
        itens_salvos = str(row.get('Equipamento', '')).strip()
        if not itens_salvos or itens_salvos.lower() in ['nan', 'none', '']: itens_salvos = str(row.get('Descrição', '')).strip()
        desc = itens_salvos.replace("|", "<br>").replace(" | ", "<br>") if itens_salvos and itens_salvos.lower() not in ['nan', 'none', ''] else "Sem itens."
        st.caption("Itens:"); st.markdown(f"<div style='background:#f9f9f9; padding:10px;'>{desc}</div><br>", unsafe_allow_html=True)

        if st.form_submit_button("💾 Salvar Alterações"):
            upds = {
                "Data Abertura": n_ab, "Data Agendamento": n_ag, "Data Finalização": n_fi, "Analista": n_an, "Gestor": n_ge,
                "Técnico": n_tc, "Projeto": n_pj, "Serviço": n_sv, "Sistema": n_si, "Observações e Pendencias": n_ob,
                "Link Externo": n_lk, "Nº Protocolo": n_pt, "Nº Pedido": n_pedido, "Data Envio": n_envio,
                "chk_status_enviado": "TRUE" if ret_chk_cli else "FALSE", "chk_equipamento_entregue": "TRUE" if ret_chk_ent else "FALSE"
            }
            # Lógica Imediata
            if ret_chk_cli and not val_chk_cli: upds["Status"] = "Concluído"; upds["Sub-Status"] = "Enviar Book"
            elif ret_chk_ent and not val_chk_ent: upds["Status"] = "Concluído"; upds["Sub-Status"] = "Aguardando Faturamento"
            elif not is_equip and n_tc and str(n_tc) != "" and str(n_tc) != str(v_tc):
                if n_lk: upds["Status"] = "Em Andamento"; upds["Sub-Status"] = "Enviar Status Cliente"
                else: upds["Status"] = "Em Andamento"; upds["Sub-Status"] = "Acionar técnico"
            elif n_st == "🔄 STATUS AUTOMATICO": upds["Status"] = "Não Iniciado"; upds["Sub-Status"] = ""
            elif not is_financeiro_locked and n_st in l_st_manual: upds["Status"] = n_st
            
            if utils_chamados.atualizar_chamado_db(id_chamado, upds):
                st.success("Salvo!"); time.sleep(0.5); st.rerun()
            else: st.error("Erro.")

# --- 5. CARREGAMENTO E SIDEBAR ---
df = utils_chamados.carregar_chamados_db()

with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"): run_importer_dialog()
    if st.button("🔗 Importar Links"): run_link_importer_dialog()
    
    st.divider()
    st.header("📤 Exportação")
    if st.button("📥 Baixar Base Completa (.xlsx)"):
        df_export = utils_chamados.carregar_chamados_db()
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df_export.to_excel(writer, index=False, sheet_name='Base_Chamados')
            st.download_button("✅ Clique aqui para salvar", data=output.getvalue(), file_name=f"Backup_Chamados_{date.today()}.xlsx")
        else: st.warning("Vazio.")
            
    st.header("Filtros de Gestão")
    lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    filtro_analista = st.selectbox("Analista", lista_analistas)

if df.empty: st.warning("Sem dados."); st.stop()

df_filtrado = df.copy()
if filtro_analista != "Todos": df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]

if "nav_radio" not in st.session_state: st.session_state["nav_radio"] = "Visão Geral (Cockpit)"
escolha_visao = st.radio("Modo de Visualização:", ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], horizontal=True, key="nav_radio")

if escolha_visao == "Visão Geral (Cockpit)":
    # ... (MANTIDO SEU DASHBOARD ORIGINAL) ...
    st.title("📌 Visão Geral dos Projetos")
    hoje = pd.Timestamp.today().normalize()
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado']
    
    pendentes = df_filtrado[~df_filtrado['Status'].str.lower().isin(status_fim)]
    atrasados = pendentes[pendentes['Agendamento'] < hoje]
    prox = pendentes[(pendentes['Agendamento'] >= hoje) & (pendentes['Agendamento'] <= hoje + timedelta(days=5))]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total de Chamados", len(df_filtrado))
    m2.metric("🚨 Atrasados Geral", len(atrasados), delta_color="inverse")
    m3.metric("📅 Vencendo na Semana", len(prox))
    
    st.markdown("---")
    st.subheader("Meus Quadros")
    
    def navegar_para_projeto(nome_projeto):
        st.session_state["sel_projeto"] = nome_projeto
        st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"

    lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
    cols = st.columns(3)
    for i, proj in enumerate(lista_projetos):
        df_p = df_filtrado[df_filtrado['Projeto'] == proj]
        total_p = len(df_p); concluidos = len(df_p[df_p['Status'].str.lower().isin(status_fim)])
        perc = int((concluidos / total_p) * 100) if total_p > 0 else 0
        cor_saude = "#2ecc71" if perc == 100 else "#3498db"
        
        with cols[i % 3]:
            st.markdown(f"""<div class="planner-card" style="border-left: 5px solid {cor_saude};">
            <div class="planner-title">{proj}</div>
            <div class="progress-container"><div class="progress-bar-fill" style="width: {perc}%; background: {cor_saude};"></div></div>
            <div class="planner-footer"><span>📋 {concluidos}/{total_p}</span></div></div>""", unsafe_allow_html=True)
            st.button(f"Ver Detalhes", key=f"btn_plan_{i}", on_click=navegar_para_projeto, args=(proj,))

else:
    # --- MODO OPERACIONAL (VISÃO DETALHADA - AQUI ESTÁ A MUDANÇA) ---
    st.title("Gestão Operacional de Projetos")
    
    # Prepara dados
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    df_filtrado['Agencia_Fmt'] = df_filtrado.apply(lambda x: f"{str(x['Cód. Agência']).split('.')[0]} - {x['Nome Agência']}", axis=1)
    df_filtrado['Projeto'] = df_filtrado['Projeto'].fillna("Sem Projeto")

    # Agrupa
    grupos = df_filtrado.groupby(['Agencia_Fmt', 'Projeto'])

    # Filtros Rápidos
    busca = st.text_input("🔎 Buscar Chamado (ID, Agência, etc)...")
    if busca:
        t = busca.lower()
        # Filtra grupos que tenham o termo
        pass
    
    for (agencia, projeto), df_grupo in grupos:
        if busca and busca.lower() not in agencia.lower() and busca.lower() not in projeto.lower() and not df_grupo.astype(str).apply(lambda x: x.str.lower().str.contains(busca.lower())).any().any():
            continue

        qtd = len(df_grupo)
        status_lista = df_grupo['Status'].str.lower().tolist()
        st_proj = "Em Andamento"
        if all(s in ['finalizado', 'concluído'] for s in status_lista): st_proj = "Finalizado"
        elif all(s == 'não iniciado' for s in status_lista): st_proj = "Não Iniciado"
        
        # O EXPANDER AGORA É O PROJETO (AGÊNCIA + PROJETO)
        with st.expander(f"🏢 {agencia} | 📁 {projeto} | {qtd} Chamados | Status: {st_proj}", expanded=False):
            
            # LISTA DOS CHAMADOS DENTRO DO PROJETO
            cols = st.columns([1.5, 3, 2, 2, 1.5])
            cols[0].markdown("**ID**")
            cols[1].markdown("**Serviço**")
            cols[2].markdown("**Sistema**")
            cols[3].markdown("**Status**")
            cols[4].markdown("**Ação**")
            st.divider()

            for _, row in df_grupo.iterrows():
                cc1, cc2, cc3, cc4, cc5 = st.columns([1.5, 3, 2, 2, 1.5])
                cc1.markdown(f"**{row['Nº Chamado']}**")
                cc2.caption(row.get('Serviço', '-'))
                cc3.caption(row.get('Sistema', '-'))
                st_ch = row.get('Status', '-')
                cc4.markdown(f"**{st_ch}**")
                
                # BOTÃO QUE ABRE O POP-UP
                if cc5.button("✏️ Editar", key=f"edt_{row['ID']}"):
                    editar_chamado_dialog(row.to_dict(), row['ID'])
