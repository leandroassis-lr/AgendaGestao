import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, datetime
import re 
import html 
import io

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() 
except:
    pass 

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

# --- Funções Helper da Página ---
def extrair_e_mapear_colunas(df, col_map):
    df_extraido = pd.DataFrame()
    colunas_originais = df.columns.tolist()
    
    if len(colunas_originais) < 20: 
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas.")
        return None
    try:
        col_indices = list(col_map.keys())
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_indices if idx < len(colunas_originais)}
        df_para_renomear = df[list(col_nomes_originais.values())].copy() 
        col_rename_map = {orig_name: db_name for idx, db_name in col_map.items() if idx in col_nomes_originais and (orig_name := col_nomes_originais[idx])}
        
        df_extraido = df_para_renomear.rename(columns=col_rename_map)
    except KeyError as e:
        st.error(f"Erro ao mapear colunas. Coluna esperada {e} não encontrada.")
        return None
    except Exception as e:
        st.error(f"Erro ao processar colunas: {e}"); return None
    return df_extraido

def formatar_agencia_excel(id_agencia, nome_agencia):
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
          nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

# --- DIALOG DE IMPORTAÇÃO ---
@st.dialog("Importar Novos Chamados (Excel/CSV)")
def run_importer_dialog():
    st.info("""
            Arraste seu arquivo Excel de chamados aqui.
            O sistema espera que a **primeira linha** contenha os cabeçalhos.
    """)
    
    uploaded_files = st.file_uploader(
        "Selecione o(s) arquivo(s)", 
        type=["xlsx", "xls", "csv"], 
        key="chamado_uploader_dialog",
        accept_multiple_files=True
    )

    if uploaded_files:
        dfs_list = []
        all_files_ok = True
        
        with st.spinner("Lendo e processando arquivos..."):
            for uploaded_file in uploaded_files:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_individual = pd.read_csv(uploaded_file, sep=';', header=0, encoding='utf-8', keep_default_na=False, dtype=str) 
                    else:
                        df_individual = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 

                    df_individual.dropna(how='all', inplace=True)
                    if not df_individual.empty:
                        dfs_list.append(df_individual)
                    else:
                        st.warning(f"Arquivo '{uploaded_file.name}' está vazio e será ignorado.")
                
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo '{uploaded_file.name}': {e}")
                    all_files_ok = False
                    break 

        if dfs_list and all_files_ok:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
                if df_raw.empty:
                    st.error("Erro: Nenhum dado válido encontrado nos arquivos.")
                    return
            except Exception as e:
                st.error(f"Erro ao combinar arquivos: {e}")
                return

            col_map = {
                0: 'chamado_id', 1: 'agencia_id', 2: 'agencia_nome', 3: 'agencia_uf',
                9: 'servico', 10: 'projeto_nome', 11: 'data_agendamento', 12: 'sistema',
                13: 'cod_equipamento', 14: 'nome_equipamento', 
                16: 'quantidade', 
                19: 'gestor'
            }
            df_para_salvar = extrair_e_mapear_colunas(df_raw, col_map)
            
            if df_para_salvar is not None:
                st.success(f"Sucesso! {len(df_raw)} linhas lidas.")
                st.dataframe(df_para_salvar.head(), width=None) 
                
                if st.button("▶️ Iniciar Importação"):
                    if df_para_salvar.empty: 
                        st.error("Planilha vazia.")
                    else:
                        with st.spinner("Importando..."):
                            reverse_map = {
                                'chamado_id': 'Chamado', 'agencia_id': 'Codigo_Ponto', 'agencia_nome': 'Nome',
                                'agencia_uf': 'UF', 'servico': 'Servico', 'projeto_nome': 'Projeto',
                                'data_agendamento': 'Data_Agendamento', 'sistema': 'Tipo_De_Solicitacao',
                                'cod_equipamento': 'Sistema', 'nome_equipamento': 'Codigo_Equipamento',
                                'quantidade': 'Quantidade_Solicitada', 
                                'gestor': 'Substitui_Outro_Equipamento_(Sim/Não)'
                            }
                            df_final_para_salvar = df_para_salvar.rename(columns=reverse_map)
                            sucesso, num_importados = utils_chamados.bulk_insert_chamados_db(df_final_para_salvar)
                            if sucesso:
                                st.success(f"🎉 {num_importados} chamados importados!")
                                st.balloons()
                                st.session_state.importer_done = True 
                            else:
                                st.error("Falha na importação.")
        elif not all_files_ok:
            st.error("Erro na leitura.")
        elif not dfs_list:
            st.info("Nenhum dado encontrado.")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False 
        st.rerun()

    if st.button("Cancelar"):
        st.rerun()

# --- LÓGICA DE STATUS ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    
    status_atual = str(df_projeto.iloc[0].get('Status', 'Não Iniciado')).strip()
    status_manual_list = ["Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
    if status_atual in status_manual_list:
        sub_status_atual_val = df_projeto.iloc[0].get('Sub-Status')
        sub_status_atual = "" if pd.isna(sub_status_atual_val) else str(sub_status_atual_val).strip()
        
        if sub_status_atual != "":
            updates = {"Sub-Status": None}
            for chamado_id in ids_para_atualizar:
                utils_chamados.atualizar_chamado_db(chamado_id, updates)
            return True 
        return False 
    
    has_S = df_projeto['Nº Chamado'].str.contains('-S-').any()
    has_E = df_projeto['Nº Chamado'].str.contains('-E-').any()
    
    def check_col_present(df, col_name):
        if col_name in df.columns:
            return df[col_name].fillna('').astype(str).str.strip().ne('').any()
        return False

    def check_date_present(df, col_name):
        if col_name in df.columns:
            return df[col_name].notna().any()
        return False
    
    link_presente = check_col_present(df_projeto, 'Link Externo')
    protocolo_presente = check_col_present(df_projeto, 'Nº Protocolo')
    pedido_presente = check_col_present(df_projeto, 'Nº Pedido')
    envio_presente = check_date_present(df_projeto, 'Data Envio')
    tecnico_presente = check_col_present(df_projeto, 'Técnico')
    
    novo_status = "Não Iniciado"
    novo_sub_status = ""

    # Lógica Simplificada para brevidade (mantendo a original)
    if has_S and not has_E:
        if protocolo_presente:
            novo_status = "Concluído"; novo_sub_status = "Enviar Book"
        elif tecnico_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Enviar Status Cliente"
        elif link_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Acionar técnico"
        else:
            novo_status = "Não Iniciado"; novo_sub_status = "Pendente Link"
    elif has_S and has_E:
        if protocolo_presente:
            novo_status = "Concluído"; novo_sub_status = "Enviar Book"
        elif tecnico_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Enviar Status Cliente"
        elif envio_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Equipamento entregue - Acionar técnico"
        elif pedido_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Equipamento Solicitado"
        elif link_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Solicitar Equipamento"
        else:
            novo_status = "Não Iniciado"; novo_sub_status = "Pendente Link"
    elif not has_S and has_E:
        if envio_presente:
            novo_status = "Concluído"; novo_sub_status = "Equipamento entregue"
        elif pedido_presente:
            novo_status = "Em Andamento"; novo_sub_status = "Equipamento Solicitado"
        else:
            novo_status = "Não Iniciado"; novo_sub_status = "Solicitar Equipamento"
    else: 
        novo_status = "Não Iniciado"; novo_sub_status = "Verificar Chamados"

    sub_status_atual_val = df_projeto.iloc[0].get('Sub-Status')
    sub_status_atual = "" if pd.isna(sub_status_atual_val) else str(sub_status_atual_val).strip()
    
    if status_atual != novo_status or sub_status_atual != novo_sub_status:
        st.info(f"Status mudou para '{novo_status} | {novo_sub_status}'")
        updates = {"Status": novo_status, "Sub-Status": novo_sub_status}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() == "none" or str(val).lower() == "nan":
        return default
    return str(val)

# --- TELA PRINCIPAL (MODIFICADA) ---
def tela_dados_agencia():
    
    # CSS
    st.markdown("""
        <style>
            .card-grid { display: grid; grid-template-columns: 2.5fr 2fr 2.5fr 2.5fr; gap: 16px; align-items: start; }
            .card-status-badge { background-color: #B0BEC5; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.85em; display: inline-block; width: 100%; text-align: center; }
            .card-action-text { text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 8px; color: var(--primary-dark); background-color: #F0F2F5; padding: 4px; border-radius: 5px; } 
            .project-card [data-testid="stExpander"] { border: 1px solid var(--gray-border); border-radius: var(--std-radius); margin-top: 15px; }
            .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; color: #333; }
            /* Ajuste para alinhar botões com input text */
            div[data-testid="column"] button {
                margin-top: 29px; /* Empurra o botão para alinhar com o input */
                width: 100%;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # 1. Título Centralizado
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    
    # 2. Carregar Dados
    utils_chamados.criar_tabela_chamados()
    with st.spinner("Carregando dados..."):
        df_chamados_raw = utils_chamados.carregar_chamados_db()

    if df_chamados_raw.empty:
        st.info("Nenhum dado encontrado. Use o botão de importação.")
        # Precisa de um botão aqui caso esteja vazio
        if st.button("📥 Importar"): run_importer_dialog()
        st.stop()

    # Preparar Dados
    if 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), 
            axis=1
        )
    else:
        st.error("Tabela incompleta."); st.stop()

    # Listas para Filtros
    def get_options_list(df, column_name):
        options = sorted(df[column_name].dropna().astype(str).unique())
        return ["Todos"] + options

    agencia_list = get_options_list(df_chamados_raw, 'Agencia_Combinada')
    analista_list = get_options_list(df_chamados_raw, 'Analista')
    projeto_list_filtro = get_options_list(df_chamados_raw, 'Projeto')
    gestor_list_filtro = get_options_list(df_chamados_raw, 'Gestor')
    sistema_list = get_options_list(df_chamados_raw, 'Sistema')
    status_list = get_options_list(df_chamados_raw, 'Status')

    # Inicializar estado do popup de exportação
    if "show_export_popup" not in st.session_state:
        st.session_state.show_export_popup = False

    # --- BARRA DE CONTROLES SUPERIOR (BUSCA + BOTÕES LADO A LADO) ---
    # Dividindo: Busca (Grande), Importar (Pequeno), Exportar (Pequeno)
    col_search, col_imp, col_exp = st.columns([4, 1, 1])
    
    with col_search:
        busca_total = st.text_input("🔎 Busca Rápida", placeholder="Digite Nº Chamado, Agência, ou qualquer termo...", label_visibility="visible")
    
    with col_imp:
        # Botão Importar
        if st.button("📥 Importar", use_container_width=True):
            run_importer_dialog()
            
    with col_exp:
        # Botão Exportar
        if st.button("⬇️ Exportar", use_container_width=True):
            st.session_state.show_export_popup = True

    # --- BARRA DE FILTROS DIVIDIDA (4 COLUNAS) ---
    with st.expander("🎛️ Filtros Avançados", expanded=True):
        
        # Linha 1 de Filtros (4 Colunas)
        f1, f2, f3, f4 = st.columns(4)
        with f1: filtro_agencia = st.selectbox("Agência", options=agencia_list)
        with f2: filtro_analista = st.selectbox("Analista", options=analista_list)
        with f3: filtro_projeto = st.selectbox("Projeto", options=projeto_list_filtro)
        with f4: filtro_gestor = st.selectbox("Gestor", options=gestor_list_filtro)
        
        # Linha 2 de Filtros (4 Colunas)
        f5, f6, f7, f8 = st.columns(4)
        with f5: filtro_status = st.selectbox("Status", options=status_list)
        with f6: filtro_sistema = st.selectbox("Sistema", options=sistema_list)
        with f7: filtro_data_inicio = st.date_input("De (Data)", value=None, format="DD/MM/YYYY")
        with f8: filtro_data_fim = st.date_input("Até (Data)", value=None, format="DD/MM/YYYY")

    st.divider()

    # --- FILTRAGEM DOS DADOS ---
    df_filtrado = df_chamados_raw.copy()
    
    if filtro_agencia != "Todos": df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    if filtro_analista != "Todos": df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
    if filtro_projeto != "Todos": df_filtrado = df_filtrado[df_filtrado['Projeto'] == filtro_projeto]
    if filtro_gestor != "Todos": df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]
    if filtro_status != "Todos": df_filtrado = df_filtrado[df_filtrado['Status'] == filtro_status]
    if filtro_sistema != "Todos": df_filtrado = df_filtrado[df_filtrado['Sistema'] == filtro_sistema]

    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    if filtro_data_inicio: df_filtrado = df_filtrado[df_filtrado['Agendamento'] >= pd.to_datetime(filtro_data_inicio)]
    if filtro_data_fim: df_filtrado = df_filtrado[df_filtrado['Agendamento'] <= pd.to_datetime(filtro_data_fim).replace(hour=23, minute=59)]

    if busca_total:
        termo = busca_total.lower()
        cols_to_search = ['Nº Chamado', 'Projeto', 'Gestor', 'Analista', 'Sistema', 'Agencia_Combinada', 'Equipamento']
        masks = []
        for col in cols_to_search:
            if col in df_filtrado.columns:
                masks.append(df_filtrado[col].astype(str).str.lower().str.contains(termo, na=False))
        if masks:
            combined_mask = pd.concat(masks, axis=1).any(axis=1)
            df_filtrado = df_filtrado[combined_mask]

    # --- LÓGICA DO MODAL DE EXPORTAÇÃO ---
    if st.session_state.show_export_popup:
        with st.expander("⬇️ Confirmar Download", expanded=True):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_filtrado.to_excel(writer, index=False, sheet_name="Dados Filtrados")
            buffer.seek(0)
            
            c_down, c_close = st.columns([3,1])
            with c_down:
                st.download_button(label="📥 Baixar Excel", data=buffer, file_name="dados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with c_close:
                if st.button("Fechar X", use_container_width=True):
                    st.session_state.show_export_popup = False
                    st.rerun()

    # --- KPIs ---
    total_chamados = len(df_filtrado)
    status_fechamento_kpi = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado', 'equipamento entregue - concluído', 'finalizado']
    abertos = len(df_filtrado[~df_filtrado['Status'].astype(str).str.lower().isin(status_fechamento_kpi)]) if not df_filtrado.empty else 0

    col_kpi1, col_kpi2 = st.columns(2)
    col_kpi1.metric("Total Visível", total_chamados)
    col_kpi2.metric("Pendentes", abertos)
    st.divider()

    # --- VISUALIZAÇÃO HIERÁRQUICA (Agência -> Projeto) ---
    if df_filtrado.empty:
        st.info("Nenhum registro encontrado.")
        st.stop()

    df_filtrado['Agendamento_str'] = df_filtrado['Agendamento'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
    agencias_agrupadas = df_filtrado.groupby('Agencia_Combinada')
    
    # Listas para formulários
    projeto_list_form = sorted([str(p) for p in df_chamados_raw['Projeto'].dropna().unique() if p])
    gestor_list_form = sorted([str(g) for g in df_chamados_raw['Gestor'].dropna().unique() if g])
    status_manual_options = ["(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]

    for nome_agencia, df_agencia in agencias_agrupadas:
        
        # Lógica de cores/urgência da agência
        hoje_ts = pd.Timestamp.now().normalize()
        status_fechamento_proj = ['concluído', 'cancelado', 'equipamento entregue - concluído', 'finalizado']
        df_agencia_aberta = df_agencia[~df_agencia['Status'].astype(str).str.lower().isin(status_fechamento_proj)]
        datas_abertas = pd.to_datetime(df_agencia_aberta['Agendamento'], errors='coerce')
        
        tag_html = "🟦"
        urgency_text = "Sem Agendamentos"
        if not datas_abertas.empty:
            earliest = datas_abertas.min()
            if earliest < hoje_ts:
                tag_html = "<span style='color:red;font-weight:bold;'>🟥 ATRASADO</span>"
                urgency_text = f"Urgente: {earliest.strftime('%d/%m/%Y')}"
            elif earliest == hoje_ts:
                tag_html = "<span style='color:orange;font-weight:bold;'>🟧 HOJE</span>"
                urgency_text = f"Para Hoje: {earliest.strftime('%d/%m/%Y')}"
            else:
                urgency_text = f"Próximo: {earliest.strftime('%d/%m/%Y')}"
        
        num_projetos = len(df_agencia.groupby(['Projeto', 'Gestor', 'Agendamento_str']))

        # Card Agência
        st.markdown('<div class="project-card">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.5, 3, 2, 1.5])
        c1.markdown(tag_html, unsafe_allow_html=True)
        c2.markdown(f"**{nome_agencia}**")
        c3.markdown(urgency_text)
        c4.markdown(f"**{num_projetos} Projetos**")
        
        with st.expander("Ver Projetos"):
            try:
                projetos_agrupados = df_agencia.groupby(['Projeto', 'Gestor', 'Agendamento_str'])
            except: continue

            for (nome_projeto, nome_gestor, data_agend), df_projeto in projetos_agrupados:
                first_row = df_projeto.iloc[0]
                chamado_ids = df_projeto['ID'].tolist()
                status_atual = clean_val(first_row.get('Status'), "Não Iniciado")
                sub_status = clean_val(first_row.get('Sub-Status'), "")
                
                # Card Projeto
                st.markdown('<div style="border-top:1px solid #eee; padding-top:10px; margin-top:10px;">', unsafe_allow_html=True)
                cp1, cp2, cp3, cp4 = st.columns([2, 2, 2, 2])
                cp1.markdown(f"📅 **{data_agend}**\n##### {clean_val(nome_projeto).upper()}")
                cp2.markdown(f"**Analista:** {clean_val(first_row.get('Analista'))}")
                cp3.markdown(f"**Gestor:** {clean_val(nome_gestor)}")
                
                status_color = utils_chamados.get_status_color(status_atual)
                cp4.markdown(f"<div class='card-status-badge' style='background-color:{status_color}'>{status_atual.upper()}</div>", unsafe_allow_html=True)
                if sub_status: cp4.markdown(f"<div class='card-action-text'>{sub_status}</div>", unsafe_allow_html=True)

                # Edição
                with st.expander(f"Editar Projeto (IDs: {min(chamado_ids)}...)", expanded=False):
                    with st.form(key=f"form_{first_row['ID']}"):
                        st.write("Edição em Lote")
                        ec1, ec2, ec3 = st.columns(3)
                        n_prazo = ec1.text_input("Prazo", value=first_row.get('Prazo',''))
                        
                        st_idx = status_manual_options.index(status_atual) if status_atual in status_manual_options else 0
                        n_status = ec2.selectbox("Status Manual", options=status_manual_options, index=st_idx)
                        
                        abert_val = _to_date_safe(first_row.get('Abertura')) or date.today()
                        n_abert = ec3.date_input("Abertura", value=abert_val, format="DD/MM/YYYY")
                        
                        desc = st.text_area("Descrição", value=first_row.get('Descrição',''))
                        
                        if st.form_submit_button("Salvar Lote"):
                            # Lógica de salvamento simplificada para o exemplo
                            updates = {"Prazo": n_prazo, "Data Abertura": n_abert, "Descrição": desc}
                            if n_status != "(Status Automático)": 
                                updates['Status'] = n_status
                                updates['Sub-Status'] = None
                            
                            for cid in chamado_ids:
                                utils_chamados.atualizar_chamado_db(cid, updates)
                            
                            df_recalc = utils_chamados.carregar_chamados_db()
                            df_p_recalc = df_recalc[df_recalc['ID'].isin(chamado_ids)]
                            calcular_e_atualizar_status_projeto(df_p_recalc, chamado_ids)
                            st.rerun()
                    
                    # Listar Individuais
                    st.markdown("---")
                    for _, row_ind in df_projeto.iterrows():
                         st.text(f"{row_ind['Nº Chamado']} - {row_ind['Equipamento']}")

        st.markdown("</div>", unsafe_allow_html=True) # Fecha card agência

# Ponto de Entrada
tela_dados_agencia()
