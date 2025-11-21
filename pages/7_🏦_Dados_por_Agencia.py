import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, datetime
import re 
import html 
import io
import math 
import time 

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() 
except:
    pass 

# --- LISTA DE EXCEÇÃO (SERVIÇOS) ---
SERVICOS_SEM_EQUIPAMENTO = [
    "vistoria",
    "adequação de gerador (recall)",
    "desinstalação e descarte de porta giratoria - item para desmontagem e recolhimento para descarte ecológico incluindo transporte",
    "desinstalação total",
    "modernização central de alarme honeywell para commbox até 12 sensores",
    "modernização central de alarme honeywell para commbox até 24 sensores",
    "modernização central de alarme honeywell para commbox até 48 sensores",
    "modernização central de alarme honeywell para commbox até 60 sensores",
    "modernização central de alarme honeywell para commbox até 90 sensores",
    "montagem e desmontagem da porta para intervenção",
    "recolhimento de eqto",
    "visita técnica",
    "vistoria conjunta"
]

# --- ESTADO DA PAGINAÇÃO ---
if 'pag_agencia_atual' not in st.session_state:
    st.session_state.pag_agencia_atual = 0

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()
    
# Função Helper para converter datas
def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce', dayfirst=True) 
        if pd.isna(ts): return None
        return ts.date()
    except Exception: return None

def formatar_agencia_excel(id_agencia, nome_agencia):
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
          nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

# --- 1. DIALOG (POP-UP) DE IMPORTAÇÃO GERAL ---
@st.dialog("Importar Novos Chamados (Template Padrão)", width="large")
def run_importer_dialog():
    st.info("Arraste seu **Template Padrão** (formato `.xlsx` ou `.csv`) aqui.\nColunas obrigatórias: `CHAMADO` e `N° AGENCIA`.")
    
    uploaded_files = st.file_uploader("Selecione o(s) arquivo(s)", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

    if uploaded_files:
        dfs_list = []
        all_files_ok = True
        
        with st.spinner("Lendo e processando arquivos..."):
            for uploaded_file in uploaded_files:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file, sep=';', header=0, encoding='utf-8', keep_default_na=False, dtype=str) 
                    else:
                        df = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 
                    df.dropna(how='all', inplace=True)
                    if not df.empty: dfs_list.append(df)
                except Exception as e:
                    st.error(f"Erro ao ler '{uploaded_file.name}': {e}")
                    all_files_ok = False; break 

        if dfs_list and all_files_ok:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
            except Exception as e: st.error(f"Erro ao combinar: {e}"); return

            st.success(f"Sucesso! {len(df_raw)} linhas lidas.")
            st.dataframe(df_raw.head(), use_container_width=True) 
            
            if st.button("▶️ Iniciar Importação"):
                if df_raw.empty: st.error("Vazia.")
                else:
                    with st.spinner("Importando..."):
                        sucesso, num = utils_chamados.bulk_insert_chamados_db(df_raw)
                        if sucesso:
                            st.success(f"🎉 {num} chamados importados!")
                            st.cache_data.clear(); st.balloons(); st.session_state.importer_done = True 
                        else:
                            st.error("Falha na importação.")
        elif not all_files_ok: st.error("Interrompido.")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False; st.rerun()
    if st.button("Cancelar"): st.rerun()

# --- 2. IMPORTAÇÃO DE LINKS ---
@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    st.info("Planilha com: **CHAMADO** e **LINK**.")
    uploaded_links = st.file_uploader("Arquivo", type=["xlsx", "csv"])
    
    if uploaded_links:
        try:
            if uploaded_links.name.endswith('.csv'): df = pd.read_csv(uploaded_links, sep=';', dtype=str)
            else: df = pd.read_excel(uploaded_links, dtype=str)
            
            df.columns = [str(c).strip().upper() for c in df.columns]
            if 'CHAMADO' in df.columns and 'LINK' in df.columns:
                if st.button("🚀 Atualizar Links"):
                    with st.spinner("Atualizando..."):
                        df_bd = utils_chamados.carregar_chamados_db()
                        id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        c = 0
                        for _, r in df.iterrows():
                            chamado = r['CHAMADO']; link = r['LINK']
                            if chamado in id_map and pd.notna(link):
                                utils_chamados.atualizar_chamado_db(id_map[chamado], {'Link Externo': link})
                                c += 1
                        st.success(f"✅ {c} links atualizados!"); st.cache_data.clear(); st.session_state.importer_done = True
            else: st.error("Colunas inválidas.")
        except Exception as e: st.error(f"Erro: {e}")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False; st.rerun()
    if st.button("Fechar"): st.rerun()

# --- EXPORTAÇÃO ---
@st.dialog("⬇️ Exportar", width="small")
def run_exporter_dialog(df):
    st.info(f"Exportando {len(df)} linhas.")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="dados.xlsx")
    if st.button("Fechar"): st.session_state.show_export_popup = False; st.rerun()

# --- FUNÇÃO DE STATUS (CORRIGIDA - LÓGICA CASCATA) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0]
    
    # 1. Normalização
    def norm(s): return str(s).strip()
    status_atual = norm(row.get('Status', 'Não Iniciado'))
    acao_atual = norm(row.get('Sub-Status', ''))
    
    # 2. Status Manuais (Soberanos)
    # Se for Cancelado/Pausado/Pendência, NÃO roda automação, EXCETO se for para Finalizar (Financeiro)
    status_soberanos = ["pendência de infra", "pendência de equipamento", "pausado", "cancelado"]
    is_manual = status_atual.lower() in status_soberanos
    
    # 3. Verificadores (Flags)
    def tem(col): 
        val = row.get(col)
        return val is not None and not pd.isna(val) and str(val).strip() != ""

    has_link = tem('Link Externo')
    has_tecnico = tem('Técnico')
    has_protocolo = tem('Nº Protocolo')
    has_pedido = tem('Nº Pedido')
    has_envio = tem('Data Envio')
    
    # Flag Banco: Se 'Status Financeiro' ou 'Data Finalização' estiver preenchido
    has_banco = tem('Status Financeiro') or tem('Data Finalização')
    
    # Flag Book: Verifica coluna "Book Enviado"
    book_ok = False
    if 'Book Enviado' in df_projeto.columns:
        if str(row.get('Book Enviado', '')).lower() in ['sim', 's', 'yes']: book_ok = True

    # 4. Definição do Status (CASCATA)
    novo_status = "Não Iniciado"
    nova_acao = "Abrir chamado no Btime"
    
    # Regra Equipamento (-E-)
    is_equip = '-E-' in str(row.get('Nº Chamado', ''))
    is_serv_exc = norm(row.get('Serviço', '')).lower() in SERVICOS_SEM_EQUIPAMENTO
    
    if is_equip and not is_serv_exc:
        if has_banco:
            novo_status = "Finalizado"; nova_acao = "Faturado"
        elif has_envio:
            novo_status = "Concluído"; nova_acao = "Equipamento entregue"
        elif has_pedido:
            novo_status = "Em Andamento"; nova_acao = "Equipamento Solicitado"
        else:
            novo_status = "Não Iniciado"; nova_acao = "Solicitar Equipamento"
    else:
        # Regra Serviço (Geral)
        if has_banco:
            novo_status = "Finalizado"; nova_acao = "Faturado"
        elif has_protocolo:
            novo_status = "Concluído"
            if book_ok: nova_acao = "Aguardando Faturamento"
            else: nova_acao = "Enviar book"
        elif has_tecnico:
            novo_status = "Em Andamento"; nova_acao = "Enviar Status Cliente"
        elif has_link:
            novo_status = "Em Andamento"; nova_acao = "Acionar técnico"
        else:
            novo_status = "Não Iniciado"; nova_acao = "Abrir chamado no Btime"

    # 5. Aplicação da Soberania Manual
    # Se está manual e a nova regra NÃO é Finalizado, mantém manual
    if is_manual and novo_status != "Finalizado":
        return False

    # 6. Atualização
    if status_atual != novo_status or acao_atual != nova_acao:
        updates = {"Status": novo_status, "Sub-Status": nova_acao}
        for cid in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(cid, updates)
        return True
        
    return False

def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan"]: return default
    return str(val)

# --- Tela Principal ---
def tela_dados_agencia():
    
    # CSS Original Mantido
    st.markdown("""
        <style>
            .card-status-badge { background-color: #B0BEC5; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.85em; display: inline-block; width: 100%; text-align: center; }
            .card-action-text { text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 8px; color: #1565C0; background-color: #F0F2F5; padding: 4px; border-radius: 5px; border: 1px solid #BBDEFB; } 
            .project-card [data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; margin-top: 15px; }
            .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; color: #333; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    
    utils_chamados.criar_tabela_chamados()
    try:
        with st.spinner("Carregando dados..."):
            df_raw = utils_chamados.carregar_chamados_db()
    except Exception as e:
        st.error(f"Erro banco: {e}"); st.stop()

    if df_raw.empty:
        if st.button("📥 Importar Arquivo"): run_importer_dialog()
        st.stop()

    if 'Cód. Agência' in df_raw.columns:
        df_raw['Agencia_Combinada'] = df_raw.apply(lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), axis=1)
    
    # Filtros
    status_manual_options = ["(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
    agencia_list = ["Todos"] + sorted(df_raw['Agencia_Combinada'].unique())
    
    c1, c2, c3 = st.columns([6, 2, 1.5])
    with c2:
        if st.button("📥 Importar", use_container_width=True): run_importer_dialog()
        if st.button("🔗 Links", use_container_width=True): run_link_importer_dialog()
    with c3:
        if st.button("⬇️ Exportar", use_container_width=True): st.session_state.show_export_popup = True

    if st.session_state.get("show_export_popup"): run_exporter_dialog(df_raw)

    with st.expander("🔎 Filtros", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        filtro_agencia = f1.selectbox("Agência", agencia_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
    
    df_filtrado = df_raw.copy()
    if filtro_agencia != "Todos": df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    
    # KPI
    st.divider()
    st.markdown(f"### 📊 Resumo: {len(df_filtrado)} Chamados")
    st.divider()

    # Paginação
    df_filtrado['Agendamento_str'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('Sem Data')
    chave_projeto = ['Projeto', 'Gestor', 'Serviço', 'Agendamento_str']
    
    # Pega lista de Agências únicas filtradas
    agencias_unicas = sorted(df_filtrado['Agencia_Combinada'].unique())
    
    ITENS_PAG = 10
    if st.session_state.pag_agencia_atual * ITENS_PAG >= len(agencias_unicas): st.session_state.pag_agencia_atual = 0
    inicio = st.session_state.pag_agencia_atual * ITENS_PAG
    fim = inicio + ITENS_PAG
    agencias_pag = agencias_unicas[inicio:fim]
    
    # Controles Nav
    c1, c2, c3 = st.columns([1,2,1])
    if c1.button("⬅️ Ant"): st.session_state.pag_agencia_atual -= 1; st.rerun()
    c2.markdown(f"<div style='text-align:center'>Página {st.session_state.pag_agencia_atual+1}</div>", unsafe_allow_html=True)
    if c3.button("Prox ➡️"): st.session_state.pag_agencia_atual += 1; st.rerun()

    # RENDERIZAÇÃO (Nível 1)
    for nome_agencia in agencias_pag:
        df_ag = df_filtrado[df_filtrado['Agencia_Combinada'] == nome_agencia]
        
        st.markdown('<div class="project-card">', unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"#### {nome_agencia}")
        c2.markdown(f"**{len(df_ag)} Chamados**")
        
        # Nível 2
        with st.expander("Ver Projetos"):
            grupos = df_ag.groupby(chave_projeto)
            for (nm_proj, nm_gest, nm_serv, dt_ag), df_p in grupos:
                r1 = df_p.iloc[0]
                st_txt = clean_val(r1.get('Status'), "Não Iniciado")
                ac_txt = clean_val(r1.get('Sub-Status'), "")
                color = utils_chamados.get_status_color(st_txt)
                
                st.markdown('<div class="project-card" style="margin-top:10px;">', unsafe_allow_html=True)
                l1, l2, l3 = st.columns([3, 2, 2])
                l1.markdown(f"**{clean_val(nm_proj).upper()}**")
                l2.markdown(f"📅 {dt_ag}")
                l3.markdown(f"""<div class="card-status-badge" style="background-color:{color}">{st_txt.upper()}</div>""", unsafe_allow_html=True)
                
                l4, l5, l6 = st.columns([3, 2, 2])
                l4.markdown(f"Serviço: {clean_val(nm_serv)}")
                l5.markdown(f"Gestor: {clean_val(nm_gest)}")
                if ac_txt: l6.markdown(f"""<div class="card-action-text">{ac_txt}</div>""", unsafe_allow_html=True)
                else: l6.markdown("-")
                
                # Nível 3 (Form)
                with st.expander(f"Editar {len(df_p)} Chamados"):
                    ids = df_p['ID'].tolist()
                    fk = f"f_lote_{r1['ID']}"
                    with st.form(fk):
                        st.write("**Edição em Lote**")
                        col_a, col_b = st.columns(2)
                        
                        # CORREÇÃO DO DROPDOWN: Ignora maiuscula/minuscula
                        opts_lower = [x.lower() for x in status_manual_options]
                        try: idx = opts_lower.index(st_txt.lower())
                        except: idx = 0
                        
                        novo_st = col_a.selectbox("Status", status_manual_options, index=idx)
                        nova_obs = col_b.text_area("Obs", value=clean_val(r1.get('Observações e Pendencias')))
                        
                        if st.form_submit_button("Salvar"):
                            upd = {'Observações e Pendencias': nova_obs}
                            recalc = True
                            
                            if novo_st != "(Status Automático)":
                                upd['Status'] = novo_st
                                upd['Sub-Status'] = None
                                recalc = False # Manual trava automação
                            
                            for i in ids: utils_chamados.atualizar_chamado_db(i, upd)
                            
                            if recalc:
                                df_temp = utils_chamados.carregar_chamados_db()
                                df_proj_temp = df_temp[df_temp['ID'].isin(ids)]
                                calcular_e_atualizar_status_projeto(df_proj_temp, ids)
                                
                            st.success("Salvo!"); time.sleep(0.5); st.rerun()
                            
                    # Lista Individual
                    st.divider()
                    for _, ch in df_p.iterrows():
                        with st.expander(f"Chamado {ch['Nº Chamado']}"):
                            with st.form(f"ind_{ch['ID']}"):
                                lk = st.text_input("Link", value=clean_val(ch.get('Link Externo')))
                                if st.form_submit_button("Salvar"):
                                    utils_chamados.atualizar_chamado_db(ch['ID'], {'Link Externo': lk})
                                    # Tenta recalcular
                                    df_temp = utils_chamados.carregar_chamados_db()
                                    df_proj_temp = df_temp[df_temp['ID'].isin(ids)]
                                    calcular_e_atualizar_status_projeto(df_proj_temp, ids)
                                    st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True) # Fim Card Proj
        st.markdown("</div>", unsafe_allow_html=True) # Fim Card Ag

tela_dados_agencia()
