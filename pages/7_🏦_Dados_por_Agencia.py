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

# --- 1. DIALOG DE IMPORTAÇÃO GERAL ---
@st.dialog("Importar Novos Chamados (Template Padrão)", width="large")
def run_importer_dialog():
    st.info("Arraste seu **Template Padrão** aqui.")
    uploaded_files = st.file_uploader("Arquivos", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

    if uploaded_files:
        dfs_list = []
        for uploaded_file in uploaded_files:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, sep=';', header=0, encoding='utf-8', keep_default_na=False, dtype=str) 
                else:
                    df = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 
                if not df.empty: dfs_list.append(df)
            except: pass 

        if dfs_list:
            df_raw = pd.concat(dfs_list, ignore_index=True)
            st.dataframe(df_raw.head(), use_container_width=True) 
            
            if st.button("▶️ Iniciar Importação"):
                sucesso, num = utils_chamados.bulk_insert_chamados_db(df_raw)
                if sucesso:
                    st.success(f"🎉 {num} chamados importados!")
                    st.cache_data.clear(); st.balloons(); st.session_state.importer_done = True 
                    st.rerun()

# --- 2. DIALOG DE IMPORTAÇÃO DE LINKS ---
@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    st.info("Planilha deve ter colunas: **CHAMADO** e **LINK**.")
    uploaded_links = st.file_uploader("Planilha", type=["xlsx", "csv"])
    
    if uploaded_links:
        if uploaded_links.name.endswith('.csv'): df_links = pd.read_csv(uploaded_links, sep=';', dtype=str)
        else: df_links = pd.read_excel(uploaded_links, dtype=str)
        
        df_links.columns = [str(c).strip().upper() for c in df_links.columns]
        
        if st.button("🚀 Atualizar Links"):
            df_bd = utils_chamados.carregar_chamados_db()
            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
            count = 0
            for _, row in df_links.iterrows():
                chamado = row['CHAMADO']; link = row['LINK']
                if chamado in id_map and pd.notna(link):
                    utils_chamados.atualizar_chamado_db(id_map[chamado], {'Link Externo': link})
                    count += 1
            st.success(f"✅ {count} links atualizados!"); st.cache_data.clear(); st.rerun()

# --- 3. DIALOG DE EXPORTAÇÃO ---
@st.dialog("⬇️ Exportar", width="small")
def run_exporter_dialog(df_data):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_data.to_excel(writer, index=False)
    st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="dados.xlsx")


# --- 4. FUNÇÃO CÉREBRO DE STATUS (CORRIGIDA E FINAL) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0] # Pega dados do projeto
    
    # 1. Normaliza Status Atual
    def normalize_status(s): return str(s).strip()
    status_atual = normalize_status(row.get('Status', 'Não Iniciado'))
    acao_atual = normalize_status(row.get('Sub-Status', ''))
    
    # 2. Verifica Status Manuais (Soberanos)
    # Se estiver nestes status, SÓ MUDA se for "Finalizado" (Banco)
    status_soberanos = ["pendência de infra", "pendência de equipamento", "pausado", "cancelado"]
    is_manual = status_atual.lower() in status_soberanos
    
    # 3. Verifica quais dados existem
    def tem(col): 
        val = row.get(col)
        return val is not None and not pd.isna(val) and str(val).strip() != ""
    
    has_link = tem('Link Externo')
    has_tecnico = tem('Técnico')
    has_protocolo = tem('Nº Protocolo')
    
    # Simulação do Banco: Se 'Status Financeiro' estiver preenchido (ou Data Finalização)
    # Assumindo que a planilha do banco preenche "Status Financeiro"
    has_banco = tem('Status Financeiro') or tem('Data Finalização')

    # Verifica Book ("Sim" ou "S")
    book_aprovado = False
    if 'Book Enviado' in df_projeto.columns: # Verifica se a coluna existe
        val_book = str(row.get('Book Enviado', '')).lower()
        if val_book in ['sim', 's', 'yes']: book_aprovado = True

    # 4. Lógica Cascata (Prioridades)
    novo_status = "Não Iniciado"
    nova_acao = "Abrir chamado no Btime"

    # PRIORIDADE 1: BANCO (Finaliza tudo)
    if has_banco:
        novo_status = "Finalizado"
        nova_acao = "Faturado"
    
    # PRIORIDADE 2: PROTOCOLO (Concluído)
    elif has_protocolo:
        novo_status = "Concluído"
        if book_aprovado:
            nova_acao = "Aguardando Faturamento"
        else:
            nova_acao = "Enviar book"
            
    # PRIORIDADE 3: TÉCNICO (Em Andamento)
    elif has_tecnico:
        novo_status = "Em Andamento"
        nova_acao = "Enviar Status Cliente"
        
    # PRIORIDADE 4: LINK (Em Andamento)
    elif has_link:
        novo_status = "Em Andamento"
        nova_acao = "Acionar técnico"
        
    # PRIORIDADE 5: DEFAULT (Criado)
    else:
        novo_status = "Não Iniciado"
        nova_acao = "Abrir chamado no Btime"

    # 5. Aplica a Soberania do Manual
    # Se for manual (Cancelado/Pausado) e a nova regra NÃO for Finalizado, mantém o manual.
    if is_manual and novo_status != "Finalizado":
        return False

    # 6. Atualiza no Banco se mudou
    if status_atual != novo_status or acao_atual != nova_acao:
        updates = {"Status": novo_status, "Sub-Status": nova_acao}
        for id_chamado in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(id_chamado, updates)
        return True
        
    return False

def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() == "none" or str(val).lower() == "nan":
        return default
    return str(val)

# --- Tela Principal da Página ---
def tela_dados_agencia():
    
    # CSS (Voltando ao estilo original que funcionava, mas com ajuste na AÇÃO)
    st.markdown("""
        <style>
            .card-status-badge { 
                background-color: #B0BEC5; color: white; padding: 6px 12px; 
                border-radius: 20px; font-weight: bold; font-size: 0.85em; 
                display: inline-block; width: 100%; text-align: center; 
            }
            .card-action-text { 
                text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 5px;
                color: #1565C0; background-color: #E3F2FD; padding: 6px; 
                border-radius: 5px; border: 1px solid #BBDEFB;
                width: 100%; display: block;
            } 
            .project-card {
                border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-top: 10px;
            }
            .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    
    utils_chamados.criar_tabela_chamados()
    try:
        with st.spinner("Carregando..."):
            df_chamados_raw = utils_chamados.carregar_chamados_db()
    except:
        st.error("Erro de conexão."); st.stop()

    if df_chamados_raw.empty:
        st.warning("Sem dados."); 
        if st.button("📥 Importar"): run_importer_dialog()
        st.stop()

    if 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), axis=1
        )
    
    # --- FILTROS ---
    agencia_list = ["Todos"] + sorted(df_chamados_raw['Agencia_Combinada'].unique())
    
    c1, c2, c3 = st.columns([6, 2, 1])
    with c2:
        if st.button("📥 Importar Geral", use_container_width=True): run_importer_dialog()
        if st.button("🔗 Importar Links", use_container_width=True): run_link_importer_dialog()
    with c3:
        if st.button("⬇️ Exportar", use_container_width=True): st.session_state.show_export_popup = True

    if st.session_state.get("show_export_popup"): run_exporter_dialog(df_chamados_raw)

    with st.expander("🔎 Filtros"):
        filtro_agencia = st.selectbox("Agência", options=agencia_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
    
    df_filtrado = df_chamados_raw.copy()
    if filtro_agencia != "Todos": df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    
    # --- KPI ---
    st.divider()
    k1, k2 = st.columns(2)
    k1.metric("Total Chamados", len(df_filtrado))
    
    # --- PAGINAÇÃO & GROUPBY ---
    df_filtrado['Agendamento_str'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('Sem Data')
    chave_projeto = ['Projeto', 'Gestor', 'Serviço', 'Agendamento_str']
    
    agencias_unicas = sorted(df_filtrado['Agencia_Combinada'].unique())
    total_itens = len(agencias_unicas)
    ITENS_POR_PAGINA = 10
    
    if st.session_state.pag_agencia_atual * ITENS_POR_PAGINA >= total_itens: st.session_state.pag_agencia_atual = 0
    inicio = st.session_state.pag_agencia_atual * ITENS_POR_PAGINA
    fim = inicio + ITENS_POR_PAGINA
    agencias_pagina = agencias_unicas[inicio:fim]
    
    # Controles
    c_nav1, c_nav2, c_nav3 = st.columns([1, 2, 1])
    if c_nav1.button("⬅️ Anterior"): st.session_state.pag_agencia_atual -= 1; st.rerun()
    c_nav2.markdown(f"<div style='text-align:center; margin-top:5px'>Página {st.session_state.pag_agencia_atual + 1}</div>", unsafe_allow_html=True)
    if c_nav3.button("Próximo ➡️"): st.session_state.pag_agencia_atual += 1; st.rerun()
    
    # --- RENDERIZAÇÃO ---
    for nome_agencia in agencias_pagina:
        df_agencia = df_filtrado[df_filtrado['Agencia_Combinada'] == nome_agencia]
        
        # CARD AGENCIA (NÍVEL 1)
        st.markdown('<div class="project-card" style="background-color: #f9f9f9; border-left: 5px solid #333;">', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        col1.markdown(f"### {nome_agencia}")
        col2.markdown(f"**{len(df_agencia)} chamados**")
        
        with st.expander("Ver Projetos"):
            grupos = df_agencia.groupby(chave_projeto)
            for (nm_proj, nm_gestor, nm_servico, dt_agend), df_proj in grupos:
                row = df_proj.iloc[0]
                
                # Status e Cores
                status_proj = clean_val(row.get('Status'), "Não Iniciado")
                acao_proj = clean_val(row.get('Sub-Status'), "")
                color = utils_chamados.get_status_color(status_proj)
                
                st.markdown('<div class="project-card">', unsafe_allow_html=True)
                
                # --- LINHA 1: Título, Data e STATUS PRINCIPAL ---
                l1_c1, l1_c2, l1_c3 = st.columns([3, 2, 2])
                l1_c1.markdown(f"**{clean_val(nm_proj).upper()}**")
                l1_c2.markdown(f"📅 {dt_agend}")
                
                # AQUI O STATUS FICA EM CIMA
                l1_c3.markdown(f"""<div class="card-status-badge" style="background-color: {color};">{status_proj.upper()}</div>""", unsafe_allow_html=True)
                
                st.markdown("") # Spacer
                
                # --- LINHA 2: Serviço, Gestor e AÇÃO (SUB-STATUS) ---
                l2_c1, l2_c2, l2_c3 = st.columns([3, 2, 2])
                l2_c1.markdown(f"Serviço: {clean_val(nm_servico)}")
                l2_c2.markdown(f"Gestor: {clean_val(nm_gestor)}")
                
                # AQUI A AÇÃO FICA EM BAIXO
                if acao_proj:
                    l2_c3.markdown(f"""<div class="card-action-text">{acao_proj}</div>""", unsafe_allow_html=True)
                else:
                    l2_c3.markdown("-")
                
                # --- NÍVEL 3: EDITAR E CHAMADOS ---
                with st.expander(f"Editar {len(df_proj)} Chamados"):
                    ids_proj = df_proj['ID'].tolist()
                    
                    # Formulário de Edição em Lote
                    with st.form(key=f"form_lote_{row['ID']}"):
                        st.write("**Edição em Lote**")
                        fe_c1, fe_c2 = st.columns(2)
                        
                        # Dropdown inteligente (Case Insensitive)
                        opcoes_status = ["(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
                        status_atual_norm = status_proj.title()
                        index_st = 0
                        # Tenta achar o status atual na lista ignorando maiuscula/minuscula
                        for i, opt in enumerate(opcoes_status):
                            if opt.lower() == status_atual_norm.lower(): index_st = i; break
                        
                        novo_st_manual = fe_c1.selectbox("Status", opcoes_status, index=index_st)
                        nova_obs = fe_c2.text_area("Observações", value=clean_val(row.get('Observações e Pendencias')))
                        
                        if st.form_submit_button("💾 Salvar Projeto"):
                            updates = {'Observações e Pendencias': nova_obs}
                            
                            should_recalc = False
                            
                            if novo_st_manual != "(Status Automático)":
                                # Se selecionou manual, aplica e limpa sub-status
                                updates['Status'] = novo_st_manual
                                updates['Sub-Status'] = None
                                should_recalc = False # Não roda automação
                            else:
                                should_recalc = True # Roda automação
                            
                            for i in ids_proj: utils_chamados.atualizar_chamado_db(i, updates)
                            
                            if should_recalc:
                                # Recarrega para ter os dados frescos e calcular
                                df_bd = utils_chamados.carregar_chamados_db()
                                df_p = df_bd[df_bd['ID'].isin(ids_proj)]
                                calcular_e_atualizar_status_projeto(df_p, ids_proj)
                                
                            st.success("Salvo!"); time.sleep(0.5); st.rerun()

                    st.divider()
                    # Lista Individual
                    for _, r_ch in df_proj.iterrows():
                        with st.expander(f"Chamado {r_ch['Nº Chamado']}"):
                            with st.form(f"ind_{r_ch['ID']}"):
                                link_val = st.text_input("Link Externo", value=clean_val(r_ch.get('Link Externo')))
                                if st.form_submit_button("Salvar"):
                                    utils_chamados.atualizar_chamado_db(r_ch['ID'], {'Link Externo': link_val})
                                    # Tenta recalcular automação pois Link mudou
                                    df_bd = utils_chamados.carregar_chamados_db()
                                    df_p = df_bd[df_bd['ID'].isin(ids_proj)]
                                    calcular_e_atualizar_status_projeto(df_p, ids_proj)
                                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True) # Fim Card Projeto
        
        st.markdown('</div>', unsafe_allow_html=True) # Fim Card Agencia

# --- Execução ---
tela_dados_agencia()
