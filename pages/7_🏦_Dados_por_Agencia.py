import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, datetime
import re 
import html 
import io
import math 
import time # Importado GLOBALMENTE

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() 
except:
    pass 

# --- LISTA DE EXCEÇÃO (SERVIÇOS) ---
# Estes itens seguirão a lógica de SERVIÇO (-S-) mesmo sem ter -S- no nome
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
    st.info(f"""
             Arraste seu **Template Padrão** (formato `.xlsx` ou `.csv`) aqui.
             Colunas obrigatórias: `CHAMADO` e `N° AGENCIA`.
     """)
    
    uploaded_files = st.file_uploader(
        "Selecione o(s) arquivo(s) do Template Padrão", 
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
                    if not df_individual.empty: dfs_list.append(df_individual)
                    else: st.warning(f"Arquivo '{uploaded_file.name}' está vazio e será ignorado.")
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo '{uploaded_file.name}': {e}")
                    all_files_ok = False; break 

        if dfs_list and all_files_ok:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
                if df_raw.empty: st.error("Erro: Nenhum dado válido encontrado."); return
            except Exception as e: st.error(f"Erro ao combinar arquivos: {e}"); return

            st.success(f"Sucesso! {len(df_raw)} linhas lidas de {len(uploaded_files)} arquivo(s). Pré-visualização:")
            st.dataframe(df_raw.head(), use_container_width=True) 
            
            if st.button("▶️ Iniciar Importação de Chamados"):
                if df_raw.empty: st.error("Planilha vazia.")
                else:
                    with st.spinner("Importando e atualizando chamados..."):
                        sucesso, num_importados = utils_chamados.bulk_insert_chamados_db(df_raw)
                        if sucesso:
                            st.success(f"🎉 {num_importados} chamados importados/atualizados com sucesso!")
                            st.cache_data.clear() 
                            st.balloons(); st.session_state.importer_done = True 
                        else:
                            st.error("A importação de chamados falhou. Verifique se os cabeçalhos 'CHAMADO' e 'N° AGENCIA' existem.")
        elif not all_files_ok: st.error("Processamento interrompido.")
        elif not dfs_list: st.info("Nenhum dado válido encontrado.")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False; st.rerun()
    if st.button("Cancelar"): st.rerun()

# --- 2. NOVO DIALOG: IMPORTAÇÃO DE LINKS ---
@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    st.info("""
        Atualize apenas os **Links Externos** dos chamados existentes.
        A planilha deve ter apenas duas colunas: **CHAMADO** e **LINK**.
    """)
    
    uploaded_links = st.file_uploader("Planilha de Links (.xlsx/.csv)", type=["xlsx", "csv"], key="link_up_key")
    
    if uploaded_links:
        try:
            if uploaded_links.name.endswith('.csv'): 
                df_links = pd.read_csv(uploaded_links, sep=';', header=0, dtype=str)
            else: 
                df_links = pd.read_excel(uploaded_links, header=0, dtype=str)
            
            df_links.columns = [str(c).strip().upper() for c in df_links.columns]
            
            if 'CHAMADO' not in df_links.columns or 'LINK' not in df_links.columns:
                st.error("Erro: A planilha precisa ter as colunas 'CHAMADO' e 'LINK'.")
            else:
                st.dataframe(df_links.head(), use_container_width=True)
                if st.button("🚀 Atualizar Links"):
                    with st.spinner("Atualizando links..."):
                        df_bd = utils_chamados.carregar_chamados_db()
                        if df_bd.empty: st.error("Banco de dados vazio."); st.stop()
                        
                        id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        count = 0
                        
                        for _, row in df_links.iterrows():
                            chamado = row['CHAMADO']
                            link = row['LINK']
                            if chamado in id_map and pd.notna(link) and str(link).strip():
                                internal_id = id_map[chamado]
                                utils_chamados.atualizar_chamado_db(internal_id, {'Link Externo': link})
                                count += 1
                        
                        st.success(f"✅ {count} links atualizados com sucesso!")
                        st.cache_data.clear() # Limpa cache
                        st.session_state.importer_done = True
                        
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False; st.rerun()
    if st.button("Fechar"): st.rerun()


# --- DIALOG (POP-UP) DE EXPORTAÇÃO ---
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

def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    # --- 1. PREPARAÇÃO DOS DADOS DA LINHA (pega a primeira linha como referência do projeto) ---
    row = df_projeto.iloc[0]
    
    # Funções auxiliares locais para checar preenchimento
    def has_val(col):
        return col in row and pd.notna(row[col]) and str(row[col]).strip() != ""
    
    status_atual = str(row.get('Status', 'Não Iniciado')).strip()
    sub_status_atual = str(row.get('Sub-Status', '')).strip()
    
    # --- 2. REGRA SUPREMA: STATUS DE BLOQUEIO MANUAL ---
    # Se estiver nestes status, NADA muda automaticamente.
    status_bloqueio = [
        "pendência de infra", 
        "pendência de equipamento", 
        "pausada", 
        "cancelada"
    ]
    
    if status_atual.lower() in status_bloqueio:
        # Se quiser limpar o sub-status quando bloqueado, descomente a linha abaixo:
        # if sub_status_atual != "": utils_chamados.atualizar_chamado_db(ids_para_atualizar[0], {"Sub-Status": None})
        return False # Encerra aqui. Não calcula nada.

    # --- 3. DEFINIÇÃO DO TIPO DE FLUXO ---
    n_chamado = str(row.get('Nº Chamado', '')).upper()
    servico_nome = str(row.get('Serviço', '')).strip().lower()
    
    eh_servico = '-S-' in n_chamado
    eh_excecao = servico_nome in SERVICOS_SEM_EQUIPAMENTO
    eh_equipamento = '-E-' in n_chamado
    
    # Variáveis de destino
    novo_status = "Não Iniciado"
    novo_acao = ""

    # --- 4. LÓGICA DE SERVIÇOS E EXCEÇÕES ---
    # Aplica-se se tiver -S- OU for uma das exceções (ex: vistoria, recolhimento)
    if eh_servico or eh_excecao:
        
        # Verificamos do FIM para o COMEÇO (O status mais avançado vence)
        
        # FASE 5: Financeiro / Faturamento (Vem da pág 8)
        # Se tiver algo preenchido em "Status Financeiro" ou "Liberação Banco" (ajuste o nome da coluna se precisar)
        if has_val('Status Financeiro'): 
             novo_status = "Finalizado"
             novo_acao = "Faturado"
             
        # FASE 4: Book / Conclusão
        elif has_val('Nº Protocolo'): # Assumindo que Nº Protocolo indica que o Book foi importado
            
            # Verifica se a coluna "Book Enviado" existe e é "Sim"
            book_enviado = str(row.get('Book Enviado', '')).strip().lower() == 'sim'
            
            if book_enviado:
                novo_status = "Finalizado"
                novo_acao = "Aguardando faturamento"
            else:
                novo_status = "Concluído"
                novo_acao = "Enviar Book"
                
        # FASE 3: Técnico Definido
        elif has_val('Técnico'):
            novo_status = "Em Andamento"
            novo_acao = "Enviar Status cliente"
            
        # FASE 2: Link Importado
        elif has_val('Link Externo'):
            novo_status = "Em Andamento"
            novo_acao = "Acionar técnico"
            
        # FASE 1: Base (Apenas Chamado Importado)
        else:
            novo_status = "Não Iniciado"
            novo_acao = "Abrir chamado no Btime"

    # --- 5. LÓGICA APENAS EQUIPAMENTO (-E-) ---
    # Só entra aqui se NÃO for serviço/exceção, mas tiver -E-
    elif eh_equipamento:
        
        # FASE 4: Financeiro / Faturamento
        if has_val('Status Financeiro'):
             novo_status = "Finalizado"
             novo_acao = "Faturado"
             
        # FASE 3: Data de Envio Preenchida
        elif has_val('Data Envio'):
            novo_status = "Em Andamento"
            novo_acao = "Equipamento Enviado" # Ajustei para "Enviado" para fazer sentido com a data
            
        # FASE 2: Número do Pedido Preenchido
        elif has_val('Nº Pedido'):
            novo_status = "Em Andamento"
            novo_acao = "Equipamento Solicitado"
            
        # FASE 1: Base
        else:
            novo_status = "Não Iniciado"
            novo_acao = "Solicitar equipamento"

    # --- 6. CASO DE FALHA (Nem S nem E nem Exceção) ---
    else:
        novo_status = "Não Iniciado"
        novo_acao = "Verificar Cadastro"

    # --- 7. APLICAÇÃO DA MUDANÇA ---
    # Só atualiza no banco se houver mudança real para evitar processamento inútil
    if status_atual != novo_status or sub_status_atual != novo_acao:
        
        st.toast(f"🔄 Atualizando status para: {novo_status} ({novo_acao})", icon="⚙️")
        
        updates = {
            "Status": novo_status,
            "Sub-Status": novo_acao
        }
        
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
            
        return True # Indica que houve mudança

    return False # Nenhuma mudança necessária
    
# --- FUNÇÃO HELPER PARA LIMPAR VALORES ---
def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() == "none" or str(val).lower() == "nan":
        return default
    return str(val)

# --- Tela Principal da Página ---
def tela_dados_agencia():

    # --- CSS ATUALIZADO E MAIS FORTE ---
    st.markdown("""
      <style>
          .card-status-badge { 
              background-color: #B0BEC5; 
              color: white !important; /* Força texto branco */
              padding: 8px 12px; 
              border-radius: 8px; /* Bordas levemente arredondadas */
              font-weight: bold; 
              font-size: 0.9em; 
              display: flex; /* Garante alinhamento */
              justify-content: center;
              align-items: center;
              width: 100%; 
              text-align: center;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1); /* Sombra leve para destacar */
              text-transform: uppercase;
              min-height: 35px; /* Garante altura mínima mesmo sem texto */
          }

          .card-action-text { 
              text-align: center; 
              font-size: 0.9em; 
              font-weight: 600; 
              margin-top: 8px; 
              color: #1565C0; /* Azul escuro para leitura fácil */
              background-color: #E3F2FD; 
              padding: 6px; 
              border-radius: 5px; 
              border: 1px solid #BBDEFB;
          } 

          .project-card [data-testid="stExpander"] { 
              border: 1px solid #ddd; 
              border-radius: 8px; 
              margin-top: 15px; 
              background-color: white;
          }
          
          .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; color: #333; }
      </style>
  """, unsafe_allow_html=True)
    
    # --- 2. Carregar Dados ---
    utils_chamados.criar_tabela_chamados()
    try:
        with st.spinner("Carregando dados..."):
            df_chamados_raw = utils_chamados.carregar_chamados_db()
    except Exception as e:
        st.warning(f"⚠️ A conexão com o banco oscilou. Tentando reconectar... ({e})")
        st.cache_data.clear(); st.cache_resource.clear()
        time.sleep(1); st.rerun()

    if df_chamados_raw.empty:
        st.info("Nenhum dado encontrado no banco. Use o botão de importação.")
        if st.button("📥 Importar Arquivo"): run_importer_dialog()
        st.stop()

    # --- 3. Criar Campo Combinado de Agência ---
    if 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), axis=1
        )
    else: st.error("Tabela de chamados incompleta."); st.stop()

    # --- 4. Preparar Listas de Opções ---
    status_manual_options = ["(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado"]
    def get_options_list(df, column_name): return ["Todos"] + sorted(df[column_name].dropna().astype(str).unique())
    agencia_list = get_options_list(df_chamados_raw, 'Agencia_Combinada')
    analista_list = get_options_list(df_chamados_raw, 'Analista')
    projeto_list_filtro = get_options_list(df_chamados_raw, 'Projeto')
    gestor_list_filtro = get_options_list(df_chamados_raw, 'Gestor')
    sistema_list = get_options_list(df_chamados_raw, 'Sistema') 
    status_list = get_options_list(df_chamados_raw, 'Status')
    projeto_list_form = sorted([str(p) for p in df_chamados_raw['Projeto'].dropna().unique() if p])
    gestor_list_form = sorted([str(g) for g in df_chamados_raw['Gestor'].dropna().unique() if g])
        
    # --- 5. Filtros e Botões de Ação ---
    if "show_export_popup" not in st.session_state: st.session_state.show_export_popup = False
    
    c_spacer, c_btn_imp, c_btn_exp = st.columns([6, 2, 1.5])
    with c_btn_imp:
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("📥 Importar Geral", use_container_width=True): run_importer_dialog()
        with c_b2:
            if st.button("🔗 Importar Links", use_container_width=True): run_link_importer_dialog()
            
    with c_btn_exp:
        if st.button("⬇️ Exportar", use_container_width=True): st.session_state.show_export_popup = True

    with st.expander("🔎 Filtros e Busca Avançada", expanded=True):
        busca_total = st.text_input("🔎 Busca Rápida (Digite ID, Agência, Projeto...)", placeholder="Ex: AG 0123 ou Instalação...")
        st.write("") 
        f1, f2, f3, f4 = st.columns(4)
        with f1: filtro_agencia = st.selectbox("Agência", options=agencia_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f2: filtro_analista = st.selectbox("Analista", options=analista_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f3: filtro_projeto = st.selectbox("Projeto", options=projeto_list_filtro, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f4: filtro_gestor = st.selectbox("Gestor", options=gestor_list_filtro, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        f5, f6, f7, f8 = st.columns(4)
        with f5: filtro_status = st.selectbox("Status", options=status_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f6: filtro_sistema = st.selectbox("Sistema", options=sistema_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
        with f7: filtro_data_inicio = st.date_input("De (Data)", value=None, format="DD/MM/YYYY")
        with f8: filtro_data_fim = st.date_input("Até (Data)", value=None, format="DD/MM/YYYY")
    st.divider()
    
    # --- 6. Filtrar DataFrame Principal ---
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
        termo = busca_total.lower(); cols_to_search = ['Nº Chamado', 'Projeto', 'Gestor', 'Analista', 'Sistema', 'Serviço', 'Equipamento', 'Descrição', 'Observações e Pendencias', 'Agencia_Combinada']
        masks = []; 
        for col in cols_to_search:
            if col in df_filtrado.columns: masks.append(df_filtrado[col].astype(str).str.lower().str.contains(termo, na=False))
        if masks: combined_mask = pd.concat(masks, axis=1).any(axis=1); df_filtrado = df_filtrado[combined_mask]
    
    # --- LÓGICA DO "MODAL" DE EXPORTAÇÃO ---
    if st.session_state.show_export_popup:
        run_exporter_dialog(df_filtrado)
        
    # --- MUDANÇA: LÓGICA DE AGRUPAMENTO (MOVIDA PARA ANTES DOS KPIs) ---
    try:
        df_filtrado['Agendamento_str'] = df_filtrado['Agendamento'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        chave_agencia = 'Agencia_Combinada'
        chave_projeto = ['Projeto', 'Gestor', 'Serviço', 'Agendamento_str']
    except Exception as e:
        st.error(f"Erro ao processar datas para agrupamento: {e}")
        st.stop()
        
    # --- 7. Painel de KPIs ---
    st.markdown(f"### 📊 Resumo")
    status_fechamento_kpi = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado', 'equipamento entregue - concluído', 'finalizado']
    status_fechamento_set = set(status_fechamento_kpi)
    df_aberto = df_filtrado[~df_filtrado['Status'].astype(str).str.lower().isin(status_fechamento_kpi)]
    df_finalizado = df_filtrado[df_filtrado['Status'].astype(str).str.lower().isin(status_fechamento_kpi)]
    chamados_abertos_count = len(df_aberto)
    chamados_finalizados_count = len(df_finalizado)
    projetos_abertos_count = 0
    projetos_finalizados_count = 0
    
    if not df_filtrado.empty:
        try:
            df_grupos = df_filtrado.groupby(chave_projeto)
            for _, df_grupo in df_grupos:
                status_do_grupo = set(df_grupo['Status'].astype(str).str.lower().fillna('N/A').unique())
                if status_do_grupo.issubset(status_fechamento_set): projetos_finalizados_count += 1
                else: projetos_abertos_count += 1
        except Exception as e: st.error(f"Erro ao agrupar projetos para KPIs: {e}")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Chamados Abertos", chamados_abertos_count)
    kpi2.metric("Projetos Abertos", projetos_abertos_count)
    kpi3.metric("Chamados Finalizados", chamados_finalizados_count)
    kpi4.metric("Projetos Finalizados", projetos_finalizados_count)

    st.markdown("#### 📊 Status")
    status_counts = df_filtrado['Status'].fillna('N/A').value_counts()
    num_status = len(status_counts)
    if num_status > 0:
        num_cols = min(num_status, 5)
        cols_status = st.columns(num_cols)
        idx = 0
        for status_nome, contagem in status_counts.items():
            col_atual = cols_status[idx % num_cols]
            col_atual.metric(status_nome, contagem)
            idx += 1
    else: st.info("Nenhum status para exibir.")
    st.divider()

    # --- 8. NOVA VISÃO HIERÁRQUICA COM PAGINAÇÃO ---
    st.markdown("#### 📋 Projetos e Chamados")
    
    if df_filtrado.empty:
        st.info("Nenhum chamado encontrado para os filtros selecionados.")
        st.stop() 

    status_fechamento_sort = ['concluído', 'cancelado', 'equipamento entregue - concluído', 'finalizado', 'fechado', 'resolvido', 'encerrado']
    df_abertos_sort = df_filtrado[~df_filtrado['Status'].astype(str).str.lower().isin(status_fechamento_sort)].copy()
    df_abertos_sort['Agendamento'] = pd.to_datetime(df_abertos_sort['Agendamento'], errors='coerce')
    min_dates_open = df_abertos_sort.groupby('Agencia_Combinada')['Agendamento'].min()
    all_agencies_in_view = df_filtrado['Agencia_Combinada'].unique()
    sort_df = pd.DataFrame(index=all_agencies_in_view); sort_df['MinDate'] = sort_df.index.map(min_dates_open)
    sort_df = sort_df.reset_index().rename(columns={'index': 'Agencia_Combinada'})
    sort_df = sort_df.sort_values(by='MinDate', ascending=True, na_position='last')
    
    # --- PAGINAÇÃO START ---
    sorted_agency_list = sort_df['Agencia_Combinada'].tolist() 
    ITENS_POR_PAGINA = 10
    total_itens = len(sorted_agency_list)
    total_paginas = math.ceil(total_itens / ITENS_POR_PAGINA)
    
    if st.session_state.pag_agencia_atual >= total_paginas: st.session_state.pag_agencia_atual = 0
    inicio = st.session_state.pag_agencia_atual * ITENS_POR_PAGINA
    fim = inicio + ITENS_POR_PAGINA
    agencias_da_pagina = sorted_agency_list[inicio:fim]
    
    def nav_controls(key_prefix):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
        with c2:
            if st.button("⬅️ Anterior", key=f"{key_prefix}_prev", disabled=(st.session_state.pag_agencia_atual == 0)):
                st.session_state.pag_agencia_atual -= 1; st.rerun()
        with c3:
            st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Página <strong>{st.session_state.pag_agencia_atual + 1}</strong> de <strong>{max(1, total_paginas)}</strong> (Exibindo {len(agencias_da_pagina)} de {total_itens})</div>", unsafe_allow_html=True)
        with c4:
            if st.button("Próximo ➡️", key=f"{key_prefix}_next", disabled=(st.session_state.pag_agencia_atual >= total_paginas - 1)):
                st.session_state.pag_agencia_atual += 1; st.rerun()
    
    df_pagina = df_filtrado[df_filtrado['Agencia_Combinada'].isin(agencias_da_pagina)]
    agencias_agrupadas = df_pagina.groupby(chave_agencia)
    agencia_dfs_dict = dict(list(agencias_agrupadas))
    
    # --- NÍVEL 1: Loop pelas Agências DA PÁGINA ---
    for nome_agencia in agencias_da_pagina:
        df_agencia = agencia_dfs_dict.get(nome_agencia)
        if df_agencia is None: continue
        
        status_fechamento_proj = ['concluído', 'cancelado', 'equipamento entregue - concluído', 'finalizado']
        df_agencia_aberta = df_agencia[~df_agencia['Status'].astype(str).str.lower().isin(status_fechamento_proj)]
        hoje_ts = pd.Timestamp.now().normalize()
        datas_abertas = pd.to_datetime(df_agencia_aberta['Agendamento'], errors='coerce')
        tag_html = "🟦"; urgency_text = "Sem Agendamentos"; analista_urgente_nome = "N/D"
        
        if not datas_abertas.empty:
            earliest_date = datas_abertas.min()
            if pd.isna(earliest_date): urgency_text = "Sem Data Válida"
            else:
                if earliest_date < hoje_ts: tag_html = "<span style='color: var(--red-alert); font-weight: bold;'>🟥 ATRASADO</span>"; urgency_text = f"Urgente: {earliest_date.strftime('%d/%m/%Y')}"
                elif earliest_date == hoje_ts: tag_html = "<span style='color: #FFA726; font-weight: bold;'>🟧 PARA HOJE</span>"; urgency_text = f"📅 {earliest_date.strftime('%d/%m/%Y')}"
                else: urgency_text = f"📅 {earliest_date.strftime('%d/%m/%Y')}"
                
                analistas_urgentes = df_agencia_aberta[df_agencia_aberta['Agendamento'] == earliest_date]['Analista'].dropna().unique()
                if len(analistas_urgentes) == 0: analista_urgente_nome = "Sem Analista"
                elif len(analistas_urgentes) == 1: analista_urgente_nome = analistas_urgentes[0]
                else: analista_urgente_nome = "Múltiplos"

        num_projetos = len(df_agencia.groupby(chave_projeto))
        
        st.markdown('<div class="project-card">', unsafe_allow_html=True)
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
            with col1: st.markdown(tag_html, unsafe_allow_html=True)
            with col2: st.markdown(f"<span style='font-size: 1.15rem; font-weight: bold;'>{nome_agencia}</span>", unsafe_allow_html=True)
            with col3: st.markdown(urgency_text, unsafe_allow_html=True)
            with col4:
                analista_color = utils_chamados.get_color_for_name(analista_urgente_nome)
                analista_html = f"<span style='color: {analista_color}; font-weight: 500;'>{analista_urgente_nome}</span>"
                st.markdown(f"**Analista:** {analista_html}", unsafe_allow_html=True)
            with col5: st.markdown(f"**{num_projetos} {'Projetos' if num_projetos > 1 else 'Projeto'}**", unsafe_allow_html=True)
    
            # --- Nível 2 (Serviços/Projetos) ---
            with st.expander("Ver Projetos"):
                try:
                    projetos_agrupados = df_agencia.groupby(chave_projeto) 
                except KeyError: continue

                for (nome_projeto, nome_gestor, nome_servico, data_agend), df_projeto in projetos_agrupados:
                    first_row = df_projeto.iloc[0]
                    chamado_ids_internos_list = df_projeto['ID'].tolist()
                    
                    st.markdown('<div class="project-card" style="margin-top: 10px;">', unsafe_allow_html=True)
                    with st.container(border=True):                        
                        status_proj = clean_val(first_row.get('Status'), "Não Iniciado")
                        sub_status_proj = clean_val(first_row.get('Sub-Status'), "")
                        status_color = utils_chamados.get_status_color(status_proj)
                        gestor_color = utils_chamados.get_color_for_name(nome_gestor)
                        dt_ag = data_agend if data_agend != "Sem Data" else "Sem Agendamento"
                        
                        col1, col2, col3 = st.columns([3, 2, 2])
                        
                        with col1: 
                            st.markdown(f"##### {clean_val(nome_projeto, 'Sem Projeto').upper()}", unsafe_allow_html=True)
                        
                        with col2: 
                            st.markdown(f"📅 \n{dt_ag}", unsafe_allow_html=True)
                        
                        with col3:
                            
                            status_html = html.escape(status_proj.upper())
                            st.markdown(f"""<div class="card-status-badge" style="background-color: {status_color};">{status_html}</div>""", unsafe_allow_html=True)
                        
                        col4, col5, col6 = st.columns([3, 2, 2])
                        
                        with col4: 
                            st.markdown(f"######\n{clean_val(nome_servico, 'N/D')}", unsafe_allow_html=True)
                        
                        with col5:
                            gestor_html = f"<span style='color: {gestor_color}; font-weight: 500;'>{clean_val(nome_gestor, 'N/D')}</span>"
                            st.markdown(f"######\n{gestor_html}", unsafe_allow_html=True)
                        
                        with col6:
                            # Normaliza o texto para garantir que pegue "Faturado", "faturado" ou "FATURADO"
                            acao_txt = str(sub_status_proj).strip()
                            acao_lower = acao_txt.lower()
                    
                            if acao_lower == "faturado":
                                # --- ESTILO ESPECIAL: VERDE E COM CHECK ---
                                st.markdown(f"****")
                                st.markdown(f"""
                                    <div style="
                                        color: #2E7D32; 
                                        font-weight: bold; 
                                        font-size: 1.1rem; 
                                        margin-top: 5px;
                                        display: flex;
                                        align-items: center;
                                        gap: 5px;
                                    ">
                                        ✔️ Faturado
                                    </div>
                                """, unsafe_allow_html=True)
                    
                            elif acao_txt != "":
                                # --- ESTILO PADRÃO (Caixa Azul para outras ações) ---
                                st.markdown(f"****")
                                st.markdown(f"""<div class="card-action-text">{acao_txt}</div>""", unsafe_allow_html=True)
                            
                            else:
                                # Espaço vazio para manter alinhamento
                                st.write("")  
                                
                        # --- NÍVEL 3 (Expander com formulários) ---
                        expander_title = f"Ver/Editar {len(chamado_ids_internos_list)} Chamado(s) (ID: {first_row['ID']})"
                        with st.expander(expander_title):
                            
                            form_key_lote = f"form_lote_edit_{first_row['ID']}"
                            with st.form(key=form_key_lote):
                                st.markdown(f"**Editar todos os {len(df_projeto)} chamados deste Serviço/Projeto:**")
                                c1, c2 = st.columns(2); novo_prazo = c1.text_input("Prazo", value=first_row.get('Prazo', ''), key=f"{form_key_lote}_prazo")
                                status_manual_atual = status_proj if status_proj in status_manual_options else "(Status Automático)"
                                status_idx = status_manual_options.index(status_manual_atual); novo_status_manual = c2.selectbox("Status", options=status_manual_options, index=status_idx, key=f"{form_key_lote}_status")
                                c3, c4, c5 = st.columns(3); abertura_val = _to_date_safe(first_row.get('Abertura')) or date.today(); nova_abertura = c3.date_input("Data Abertura", value=abertura_val, format="DD/MM/YYYY", key=f"{form_key_lote}_abertura")
                                agend_val = _to_date_safe(first_row.get('Agendamento')); novo_agendamento = c4.date_input("Data Agendamento", value=agend_val, format="DD/MM/YYYY", key=f"{form_key_lote}_agend")
                                final_val = _to_date_safe(first_row.get('Fechamento')); nova_finalizacao = c5.date_input("Data Finalização", value=final_val, format="DD/MM/YYYY", key=f"{form_key_lote}_final")
                                st.markdown("<h6>Detalhes do Projeto</h6>", unsafe_allow_html=True); c6, c7, c8 = st.columns(3)
                                proj_val = first_row.get('Projeto', ''); proj_idx = projeto_list_form.index(proj_val) if proj_val in projeto_list_form else 0; novo_projeto = c6.selectbox("Projeto", options=projeto_list_form, index=proj_idx, key=f"{form_key_lote}_proj")
                                analista_val = first_row.get('Analista', ''); novo_analista = c7.text_input("Analista", value=analista_val, key=f"{form_key_lote}_analista")
                                gestor_val = first_row.get('Gestor', ''); gestor_idx = gestor_list_form.index(gestor_val) if gestor_val in gestor_list_form else 0; novo_gestor = c8.selectbox("Gestor", options=gestor_list_form, index=gestor_idx, key=f"{form_key_lote}_gestor")
                                c9, c10, c11 = st.columns(3); novo_sistema = c9.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"{form_key_lote}_sistema")
                                novo_servico = c10.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"{form_key_lote}_servico"); novo_tecnico = c11.text_input("Técnico", value=first_row.get('Técnico', ''), key=f"{form_key_lote}_tec")
                                nova_descricao = st.text_area("Descrição", value=first_row.get('Descrição', ''), key=f"{form_key_lote}_desc"); nova_obs_pend = st.text_area("Observações e Pendencias", value=first_row.get('Observações e Pendencias', ''), key=f"{form_key_lote}_obs")
                                btn_salvar_lote = st.form_submit_button("💾 Salvar Alterações do Projeto", use_container_width=True)

                            if btn_salvar_lote:
                                updates = {
                                    "Prazo": novo_prazo, 
                                    "Data Abertura": nova_abertura,
                                    "Data Agendamento": novo_agendamento, 
                                    "Data Finalização": nova_finalizacao,
                                    "Projeto": novo_projeto, 
                                    "Analista": novo_analista, 
                                    "Gestor": novo_gestor,
                                    "Sistema": novo_sistema, 
                                    "Serviço": novo_servico, 
                                    "Técnico": novo_tecnico,
                                    "Descrição": nova_descricao, 
                                    "Observações e Pendencias": nova_obs_pend
                                }
                                
                                precisa_recalcular = False 
                            
                                # LÓGICA DE STATUS MANUAL (CANCELADO, PAUSADO, ETC)
                                if novo_status_manual != "(Status Automático)":
                                    # 1. Força o novo status
                                    updates['Status'] = novo_status_manual
                                    # 2. Limpa a Ação/Sub-status (pois cancelado não tem ação pendente)
                                    updates['Sub-Status'] = "" 
                                    # 3. Bloqueia o recálculo
                                    precisa_recalcular = False 
                                    
                                    # Validação extra para Finalizado
                                    if novo_status_manual == "Finalizado" and nova_finalizacao is None:
                                         st.error("Erro: Para 'Finalizado', a Data de Finalização é obrigatória.")
                                         st.stop()
                                
                                # Se deixou no automático, ativamos o recálculo
                                elif novo_status_manual == "(Status Automático)":
                                    precisa_recalcular = True
                            
                                with st.spinner(f"Atualizando {len(chamado_ids_internos_list)} chamados..."):
                                    sucesso_count = 0
                                    for chamado_id in chamado_ids_internos_list:
                                        if utils_chamados.atualizar_chamado_db(chamado_id, updates):
                                            sucesso_count += 1
                                    
                                    if sucesso_count > 0:
                                        st.success(f"✅ Atualizado com sucesso!")
                                        
                                        # ⚠️ CRÍTICO: Limpeza agressiva de Cache para garantir que a tela atualize
                                        st.cache_data.clear()
                                        
                                        if precisa_recalcular:
                                            # Recarrega apenas o necessário para calcular
                                            df_temp = utils_chamados.carregar_chamados_db()
                                            df_proj_temp = df_temp[df_temp['ID'].isin(chamado_ids_internos_list)]
                                            calcular_e_atualizar_status_projeto(df_proj_temp, chamado_ids_internos_list)
                                            st.cache_data.clear() # Limpa de novo após recalcular
                                        
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error("Erro ao atualizar no banco de dados.")
            
                            # Edição Individual (Agrupada por Sistema)
                            st.markdown("---")
                            st.markdown("##### 🔎 Detalhes por Chamado")
                            
                            sistemas_no_projeto = df_projeto.groupby('Sistema')
                            for nome_sistema, df_sistema in sistemas_no_projeto:
                                st.markdown(f"###### {clean_val(nome_sistema, 'N/D')}")
                                
                                for _, chamado_row in df_sistema.iterrows():
                                    with st.expander(f"▶️ {chamado_row['Nº Chamado']} "):
                                        
                                        form_key_ind = f"form_ind_edit_{chamado_row['ID']}"
                                        with st.form(key=form_key_ind):
                                            is_servico = '-S-' in chamado_row['Nº Chamado']
                                            is_equipamento = '-E-' in chamado_row['Nº Chamado']
                                            nome_servico_norm_atual = str(nome_servico).strip().lower()
                                            eh_excecao = nome_servico_norm_atual in SERVICOS_SEM_EQUIPAMENTO
                                            
                                            updates_individuais = {}
                                            link_atual = chamado_row.get('Link Externo')
                                            if pd.notna(link_atual) and str(link_atual).strip():
                                                st.markdown(f"🔗 [**Acessar Link Salvo**]({link_atual})")

                                            if is_servico or eh_excecao:
                                                st.markdown("****")
                                                c_lnk, c_btn_lnk = st.columns([4, 1])
                                                with c_lnk:
                                                    novo_link = st.text_input("Link Externo", value=link_atual if pd.notna(link_atual) else '', key=f"link_{chamado_row['ID']}")
                                                    updates_individuais['Link Externo'] = novo_link
                                                with c_btn_lnk:
                                                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                                                    if pd.notna(link_atual) and str(link_atual).strip(): st.link_button("🌐 Acessar", link_atual)
                                                
                                                c1, c2 = st.columns(2)
                                                proto_val = chamado_row.get('Nº Protocolo', ''); novo_protocolo = c1.text_input("Nº Protocolo", value=proto_val, key=f"proto_{chamado_row['ID']}"); updates_individuais['Nº Protocolo'] = novo_protocolo
                                            
                                            if is_equipamento:
                                                st.markdown("****"); c1, c2 = st.columns(2); pedido_val = chamado_row.get('Nº Pedido', ''); novo_pedido = c1.text_input("Nº Pedido", value=pedido_val, key=f"pedido_{chamado_row['ID']}"); updates_individuais['Nº Pedido'] = novo_pedido
                                                envio_val = _to_date_safe(chamado_row.get('Data Envio')); nova_data_envio = c2.date_input("Data Envio", value=envio_val, format="DD/MM/YYYY", key=f"envio_{chamado_row['ID']}"); updates_individuais['Data Envio'] = nova_data_envio
                                                obs_val = chamado_row.get('Obs. Equipamento', ''); nova_obs_equip = st.text_area("Obs. Equipamento", value=obs_val, height=100, key=f"obs_equip_{chamado_row['ID']}"); updates_individuais['Obs. Equipamento'] = nova_obs_equip
                                            
                                            qtd_val_numeric_ind = pd.to_numeric(chamado_row.get('Qtd.'), errors='coerce'); qtd_int_ind = int(qtd_val_numeric_ind) if pd.notna(qtd_val_numeric_ind) else 0; equip_str_ind = str(chamado_row.get('Equipamento', 'N/A'))
                                            st.text_area("Descrição (equipamento deste chamado)", value=f"{qtd_int_ind:02d} - {equip_str_ind}", disabled=True, height=50, key=f"desc_ind_{chamado_row['ID']}")
                                            btn_salvar_individual = st.form_submit_button("💾 Atualizar", use_container_width=True)

                                        if btn_salvar_individual:
                                            with st.spinner(f"Salvando chamado {chamado_row['Nº Chamado']}..."):
                                                if utils_chamados.atualizar_chamado_db(chamado_row['ID'], updates_individuais):
                                                    st.success("Chamado salvo!")
                                                    st.cache_data.clear(); time.sleep(0.5)
                                                    df_chamados_atualizado = utils_chamados.carregar_chamados_db()
                                                    df_projeto_atualizado = df_chamados_atualizado[df_chamados_atualizado['ID'].isin(chamado_ids_internos_list)]
                                                    calcular_e_atualizar_status_projeto(df_projeto_atualizado, chamado_ids_internos_list)
                                                    st.cache_data.clear(); st.rerun()
                                                else: st.error("Falha ao salvar o chamado.")
                            
                            # (Descrição de Equipamentos com lógica condicional)
                            st.markdown("---")
                            st.markdown("##### Descrição (Total de Equipamentos do Projeto)")

                            nome_servico_norm = str(nome_servico).strip().lower()
                            servico_recolhimento = "recolhimento de eqto"
                            
                            if nome_servico_norm in SERVICOS_SEM_EQUIPAMENTO:
                                if nome_servico_norm == servico_recolhimento: descricao_texto = f"Realizar o {nome_servico}"
                                else: descricao_texto = f"Realizar a {nome_servico}"
                                st.markdown(f"""<div style='background-color: #f0f2f5; border-radius: 5px; padding: 10px; font-size: 0.95rem; font-weight: 500;'>{descricao_texto}</div>""", unsafe_allow_html=True)
                            else:
                                descricao_list_agrupada = []
                                for nome_sistema, df_sistema in sistemas_no_projeto:
                                    nome_sis_limpo = clean_val(nome_sistema, "Sistema não Definido")
                                    descricao_list_agrupada.append(f"**{nome_sis_limpo}**")
                                    for _, chamado_row_desc in df_sistema.iterrows():
                                        qtd_val_numeric = pd.to_numeric(chamado_row_desc.get('Qtd.'), errors='coerce')
                                        qtd_int = int(qtd_val_numeric) if pd.notna(qtd_val_numeric) else 0
                                        equip_str = str(chamado_row_desc.get('Equipamento', 'N/A'))
                                        descricao_list_agrupada.append(f"{qtd_int:02d} - {equip_str}")
                                    descricao_list_agrupada.append("") 
                                descricao_texto = "<br>".join(descricao_list_agrupada)
                                st.markdown(f"""<div style='background-color: #f0f2f5; border-radius: 5px; padding: 10px; font-size: 0.9rem; max-height: 200px; overflow-y: auto;'>{descricao_texto}</div>""", unsafe_allow_html=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True) 
        st.markdown("</div>", unsafe_allow_html=True) 
        st.markdown("<br>", unsafe_allow_html=True) 
    
    if total_paginas > 1:
        st.divider()
        nav_controls("bottom")

# --- Ponto de Entrada ---
tela_dados_agencia ()







