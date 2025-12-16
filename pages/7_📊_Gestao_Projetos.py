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
        .ana-rosa  { color: #C2185B; font-weight: 800; background-color: #FCE4EC; padding: 2px 6px; border-radius: 4px; }
        .ana-default { color: #555; font-weight: 700; }

        /* Gestores */
        .gestor-bold { color: #000000; font-weight: 900; font-size: 0.9em; }

        /* Status Badge */
        .status-badge { padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.95em; text-transform: uppercase; color: white; display: inline-block;}
        
        /* KPI Cards */
        .kpi-card { background-color: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; text-align: center; height: 100%; }
        .kpi-title { font-size: 0.85em; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
        .kpi-value { font-size: 1.8em; font-weight: 800; color: #2c3e50; }
        .kpi-blue   { border-bottom: 4px solid #1565C0; }
        .kpi-orange { border-bottom: 4px solid #F57C00; }
        .kpi-green  { border-bottom: 4px solid #2E7D32; }
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
@st.dialog("📝 Detalhes do Chamado", width="medium")
def open_chamado_dialog(row_dict):
    st.markdown(f"### 🎫 {row_dict.get('Nº Chamado', '')}")
    st.caption(f"ID Interno: {row_dict.get('ID')}")
    
    # --- BLOCO 1: Status e Datas ---
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Status Atual:**<br>{row_dict.get('Status')}", unsafe_allow_html=True)
    c2.markdown(f"**Abertura:**<br>{_to_date_safe(row_dict.get('Abertura')) or '-'}", unsafe_allow_html=True)
    c3.markdown(f"**Agendamento:**<br>{_to_date_safe(row_dict.get('Agendamento')) or '-'}", unsafe_allow_html=True)

    st.divider()

    # --- BLOCO 2: Informações Técnicas ---
    st.markdown(f"**Projeto:** {row_dict.get('Projeto')}")
    st.markdown(f"**Serviço:** {row_dict.get('Serviço')}")
    st.markdown(f"**Sistema:** {row_dict.get('Sistema')}")
    
    st.divider()

    # --- BLOCO 3: Descrição e Itens ---
    st.markdown("📦 **Descrição / Equipamentos:**")
    itens_desc = str(row_dict.get('Equipamento', '')).replace("|", "\n- ").replace(" | ", "\n- ")
    if not itens_desc or itens_desc == "nan": 
        itens_desc = str(row_dict.get('Descrição', '-'))
    st.info(itens_desc)

    st.divider()

    # --- BLOCO 4: Edição e Links ---
    with st.form(key=f"form_popup_{row_dict['ID']}"):
        obs_atual = row_dict.get('Observações e Pendencias', '')
        nova_obs = st.text_area("✍️ Observação / Pendência", value=obs_atual if pd.notna(obs_atual) else "", height=100)
        
        # Link Externo e Protocolo
        cl1, cl2, cl3 = st.columns([1, 1, 1])
        link_ext = row_dict.get('Link Externo', '')
        
        with cl1:
            if link_ext and str(link_ext).lower() not in ['nan', 'none', '']:
                st.markdown(f"<br><a href='{link_ext}' target='_blank' style='background:#1565C0; color:white; padding:8px 12px; border-radius:4px; text-decoration:none; display:block; text-align:center;'>🔗 Acessar Link</a>", unsafe_allow_html=True)
            else:
                st.caption("Sem link externo")
        
        with cl2:
            st.text_input("Protocolo", value=row_dict.get('Nº Protocolo', ''), disabled=True)
        
        with cl3:
            st.date_input("Data Finalização", value=_to_date_safe(row_dict.get('Fechamento')), disabled=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.form_submit_button("💾 Salvar Observação"):
            # Atualiza apenas a observação no banco
            utils_chamados.atualizar_chamado_db(row_dict['ID'], {"Observações e Pendencias": nova_obs})
            st.success("Observação salva com sucesso!")
            time.sleep(1)
            st.rerun()

# --- LÓGICA DE STATUS "TOP-DOWN" ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0]
    n_chamado = str(row.get('Nº Chamado', ''))
    
    # Identificação de Tipo
    is_equip = '-e-' in n_chamado.lower()
    
    # Campos Chave
    link_presente = row.get('Link Externo') and str(row.get('Link Externo')).strip() not in ['', 'nan', 'None']
    tecnico_presente = row.get('Técnico') and str(row.get('Técnico')).strip() not in ['', 'nan', 'None']
    pedido_presente = row.get('Nº Pedido') and str(row.get('Nº Pedido')).strip() not in ['', 'nan', 'None']
    envio_presente = row.get('Data Envio') and pd.notna(row.get('Data Envio'))
    
    # Flags Checkboxes
    flag_banco = str(row.get('chk_financeiro_banco', '')).upper() == 'TRUE'
    flag_book = str(row.get('chk_financeiro_book', '')).upper() == 'TRUE'
    book_enviado_sim = str(row.get('Book Enviado', '')).upper() == 'SIM'
    
    chk_status_cli = str(row.get('chk_status_enviado', '')).upper() == 'TRUE'
    chk_eq_entregue = str(row.get('chk_equipamento_entregue', '')).upper() == 'TRUE'

    status_atual = str(row.get('Status', 'Não Iniciado')).strip()
    status_manual_bloqueantes = ["Pendência de Infra", "Pendência de Equipamento", "Cancelado", "Pausado"]

    novo_status = "Não Iniciado"
    novo_sub_status = ""

    # HIERARQUIA 1: FINANCEIRO (BANCO)
    if flag_banco:
        novo_status = "Finalizado"
        novo_sub_status = "FATURADO"
    # HIERARQUIA 2: FINANCEIRO (BOOK)
    elif flag_book:
        if book_enviado_sim:
            novo_status = "Finalizado"
            novo_sub_status = "AGUARDANDO FATURAMENTO"
        else:
            novo_status = "Finalizado"
            novo_sub_status = "ENVIAR BOOK"
    # HIERARQUIA 3: STATUS MANUAL
    elif status_atual in status_manual_bloqueantes:
        novo_status = status_atual
        novo_sub_status = str(row.get('Sub-Status', ''))
    # HIERARQUIA 4: AUTOMÁTICO EQUIPAMENTO (-E-)
    elif is_equip:
        if chk_eq_entregue:
            novo_status = "Concluído"
            novo_sub_status = "Aguardando Faturamento"
        elif envio_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Aguardando Entrega"
        elif pedido_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Aguardando envio do equipamento"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Solicitar Equipamento"
    # HIERARQUIA 5: AUTOMÁTICO SERVIÇO
    else: 
        if chk_status_cli:
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
            novo_sub_status = "Abrir chamado Btime"

    # APLICAÇÃO
    sub_status_db = str(row.get('Sub-Status', '')).strip()
    sub_status_novo_str = str(novo_sub_status).strip()

    if status_atual != novo_status or sub_status_db != sub_status_novo_str:
        updates = {"Status": novo_status, "Sub-Status": novo_sub_status}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False
    
# --- FUNÇÕES DE IMPORTAÇÃO/EXPORTAÇÃO ---
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

@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    st.info("Atualize apenas os **Links Externos** dos chamados existentes.")
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
                        st.cache_data.clear()
                        st.session_state.importer_done = True
                        
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False; st.rerun()
    if st.button("Fechar"): st.rerun()

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

with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"): run_importer_dialog()
    if st.button("🔗 Importar Links"): run_link_importer_dialog()
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
    if st.button("📥 Baixar Base Completa (.xlsx)"):
        df_export = utils_chamados.carregar_chamados_db()
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Base_Chamados')
                workbook = writer.book
                worksheet = writer.sheets['Base_Chamados']
                format_header = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
                for i, col in enumerate(df_export.columns):
                    worksheet.set_column(i, i, 20)
                    worksheet.write(0, i, col, format_header)
            data_export = output.getvalue()
            st.download_button(
                label="✅ Clique aqui para salvar",
                data=data_export,
                file_name=f"Backup_Chamados_{date.today().strftime('%d-%m-%Y')}.xlsx",
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

if "nav_radio" not in st.session_state: st.session_state["nav_radio"] = "Visão Geral (Cockpit)"
escolha_visao = st.radio("Modo de Visualização:", ["Visão Geral (Cockpit)", "Detalhar um Projeto (Operacional)"], horizontal=True, key="nav_radio")

# --- VISÃO 1: COCKPIT ---
if escolha_visao == "Visão Geral (Cockpit)":
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
    st.markdown("<br>", unsafe_allow_html=True)

    lista_projetos = sorted(df_filtrado['Projeto'].dropna().unique().tolist())
    cols = st.columns(3)
        
    def navegar_para_projeto(nome_projeto):
        st.session_state["sel_projeto"] = nome_projeto
        st.session_state["nav_radio"] = "Detalhar um Projeto (Operacional)"

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
            st.button(
                f"Ver Detalhes", 
                key=f"btn_plan_{i}", 
                use_container_width=True,
                on_click=navegar_para_projeto,
                args=(proj,)
            )

# --- VISÃO 2: OPERACIONAL ---
else:
    with st.container():
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        c_tit, c_date = st.columns([4, 1.5])
        with c_tit: st.markdown("### 🔍 Filtros & Pesquisa")
        with c_date: 
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            d_min = df_filtrado['Agendamento'].min() if not pd.isna(df_filtrado['Agendamento'].min()) else date.today()
            d_max = df_filtrado['Agendamento'].max() if not pd.isna(df_filtrado['Agendamento'].max()) else date.today()
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")

        c1, c2, c3 = st.columns([2, 1.5, 1.5])
        with c1:
            busca_geral = st.text_input("Busca", placeholder="🔎 Digite ID, Nome, Serviço...", label_visibility="collapsed")
        
        with c2:
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

        st.markdown('</div>', unsafe_allow_html=True)

    df_view = df_filtrado.copy()
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)]
    if filtro_projeto_multi: df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
    if filtro_status_multi: df_view = df_view[df_view['Status'].isin(filtro_status_multi)]
    if len(filtro_data_range) == 2:
        d_inicio, d_fim = filtro_data_range
        df_view = df_view[(df_view['Agendamento'] >= pd.to_datetime(d_inicio)) & (df_view['Agendamento'] <= pd.to_datetime(d_fim))]

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

    if not df_view.empty:
        counts = df_view['Status'].value_counts()
        top_status = counts.head(5) 
        if len(top_status) > 0:
            cols = st.columns(len(top_status))
            for i, (status, count) in enumerate(top_status.items()):
                try: cor = utils_chamados.get_status_color(status)
                except: cor = "#ccc"
                with cols[i]:
                    st.markdown(f"""<div class="status-summary-box" style="border-left: 5px solid {cor}; background: white; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;"><span class="status-label" style="font-size: 0.75em; font-weight: bold; color: #555; text-transform: uppercase;">{status}</span><span class="status-val" style="font-size: 1.1em; font-weight: 800; color: #333;">{count}</span></div>""", unsafe_allow_html=True)
    
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
                
                # --- PREPARAÇÃO DE DADOS ---
                # Status e Cores
                st_proj = clean_val(row_head.get('Status'), "Não Iniciado")
                cor_st = utils_chamados.get_status_color(st_proj)
                
                # Analista (CSS)
                analista = clean_val(row_head.get('Analista'), "N/D").split(' ')[0].upper()
                if "GIOVANA" in analista: css_ana = "ana-azul"
                elif "MARCELA" in analista: css_ana = "ana-verde"
                elif "MONIQUE" in analista: css_ana = "ana-rosa"
                else: css_ana = "ana-default"
                
                # Outros campos
                tecnico = clean_val(row_head.get('Técnico'), "N/D").split(' ')[0].title()
                gestor = clean_val(row_head.get('Gestor'), "N/D").split(' ')[0].title()
                acao_txt = clean_val(row_head.get('Sub-Status'), "-")
                nome_ag_limpo = str(nome_ag).replace(str(cod_ag), '').strip(' -')

                # CÁLCULO DE DATAS E SLA
                # Pega a menor data de agendamento do grupo (a mais próxima)
                datas_validas = pd.to_datetime(df_grupo['Agendamento'], errors='coerce').dropna()
                data_prox = datas_validas.min() if not datas_validas.empty else None
                
                if data_prox:
                    data_str = data_prox.strftime('%d/%m/%Y')
                    # SLA = Data + 5 dias
                    data_sla = data_prox + timedelta(days=5)
                    atrasado = data_sla.date() < date.today() and st_proj not in ['Concluído', 'Finalizado', 'Faturado']
                    cor_sla = "#D32F2F" if atrasado else "#388E3C" # Vermelho se estourou, Verde se ok
                    sla_html = f"<span style='color:{cor_sla}; font-weight:bold;'>Até {data_sla.strftime('%d/%m')}</span>"
                else:
                    data_str = "-"
                    sla_html = "-"

                # --- RENDERIZAÇÃO VISUAL (NOVO LAYOUT) ---
                st.markdown('<div class="gold-line"></div>', unsafe_allow_html=True)
                
                # Container para os dados do cabeçalho
                with st.container():
                    # LINHA 1: Agência | Data | Analista | STATUS
                    l1_c1, l1_c2, l1_c3, l1_c4 = st.columns([2.5, 1, 1, 1])
                    
                    with l1_c1:
                         st.markdown(f"<span class='agencia-header'>🏢 {cod_ag} - {nome_ag_limpo}</span>", unsafe_allow_html=True)
                    with l1_c2:
                         st.markdown(f"<span class='meta-label'>AGENDAMENTO</span><br><b>📅 {data_str}</b>", unsafe_allow_html=True)
                    with l1_c3:
                         st.markdown(f"<span class='meta-label'>ANALISTA</span><br><span class='{css_ana}'>{analista}</span>", unsafe_allow_html=True)
                    with l1_c4:
                         st.markdown(f"<span class='status-badge' style='background-color:{cor_st}; margin-top:5px;'>{st_proj}</span>", unsafe_allow_html=True)

                    # LINHA 2: Projeto | SLA | Gestor | Ação
                    l2_c1, l2_c2, l2_c3, l2_c4 = st.columns([2.5, 1, 1, 1])
                    
                    with l2_c1:
                        st.markdown(f"<span class='meta-label'>PROJETO</span><br><span style='font-size:1em; font-weight:bold; color:#555'>{nome_proj}</span>", unsafe_allow_html=True)
                    with l2_c2:
                        st.markdown(f"<span class='meta-label'>SLA (+5d)</span><br>{sla_html}", unsafe_allow_html=True)
                    with l2_c3:
                        st.markdown(f"<span class='meta-label'>GESTOR</span><br><span class='gestor-bold'>👤 {gestor}</span>", unsafe_allow_html=True)
                    with l2_c4:
                        if acao_txt and acao_txt != "-":
                            st.markdown(f"<span class='meta-label'>AÇÃO</span><br><span class='action-text'>👉 {acao_txt}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<span class='meta-label'>AÇÃO</span><br><span style='color:#ccc'>-</span>", unsafe_allow_html=True)

                # Expander
                label_expander = f"📂 Visualizar {len(df_grupo)} Chamado(s) vinculados"
                with st.expander(label_expander):
                    for i, row_chamado in df_grupo.iterrows():
                        num_chamado = str(row_chamado['Nº Chamado'])
                        servico = str(row_chamado['Serviço'])
                        if st.button(f"📄 {num_chamado}  |  {servico}", key=f"btn_ch_{row_chamado['ID']}", use_container_width=True):
                            open_chamado_dialog(row_chamado.to_dict())
                            
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


