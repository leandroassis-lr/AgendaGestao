import streamlit as st
import pandas as pd
import utils # Apenas para CSS e Login Check
import utils_chamados # <<< NOSSO NOVO ARQUIVO
from datetime import date, datetime
import re 
import html 

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
    
# Função Helper para converter datas (evita erros)
def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce', dayfirst=True) # Tenta ler DD/MM/AAAA
        if pd.isna(ts): return None
        return ts.date()
    except Exception: return None

# --- Funções Helper da Página ---
def extrair_e_mapear_colunas(df, col_map):
    """ Extrai e renomeia colunas com base em índices. """
    df_extraido = pd.DataFrame()
    colunas_originais = df.columns.tolist()
    
    if len(colunas_originais) < 20: 
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas. O formato esperado (com 20+ colunas) não foi reconhecido.")
        return None
    try:
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_map.keys() if idx < len(colunas_originais)}
        df_para_renomear = df[list(col_nomes_originais.values())].copy() 
        col_rename_map = {orig_name: db_name for idx, db_name in col_map.items() if idx in col_nomes_originais and (orig_name := col_nomes_originais[idx])}
        df_extraido = df_para_renomear.rename(columns=col_rename_map)
    except KeyError as e:
        st.error(f"Erro ao mapear colunas. Coluna esperada {e} não encontrada no arquivo.")
        st.error(f"Colunas encontradas: {colunas_originais}")
        return None
    except Exception as e:
        st.error(f"Erro ao processar colunas: {e}"); return None
    return df_extraido

def formatar_agencia_excel(id_agencia, nome_agencia):
    """ Formata o ID e Nome da Agência para o padrão 'AG 0001 - NOME' """
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
         nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"


# --- Tela Principal da Página ---
def tela_dados_agencia():
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    st.write(" ")
    
    # --- Roda a função de criação/atualização da tabela ---
    utils_chamados.criar_tabela_chamados()

    # --- 1. Importador de Chamados ---
    with st.expander("📥 Importar Novos Chamados (Excel/CSV)"):
        st.info(f"""
            Arraste seu arquivo Excel de chamados (formato `.xlsx` ou `.csv` com `;`) aqui.
            O sistema espera que a **primeira linha** contenha os cabeçalhos.
            As colunas necessárias (A, B, C, D, J, K, L, M, N, O, Q, T) serão lidas automaticamente.
            Se um `Chamado` (Coluna A) já existir, ele será **atualizado**.
        """)
        uploaded_file = st.file_uploader("Selecione o arquivo Excel/CSV de chamados", type=["xlsx", "xls", "csv"], key="chamado_uploader")

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file, sep=';', header=0, encoding='latin-1', keep_default_na=False, dtype=str) 
                else:
                    df_raw = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 

                df_raw.dropna(how='all', inplace=True)
                if df_raw.empty: st.error("Erro: O arquivo está vazio."); st.stop()

                # --- Mapeamento (Q = 16) ---
                col_map = {
                    0: 'chamado_id', 1: 'agencia_id', 2: 'agencia_nome', 3: 'agencia_uf',
                    9: 'servico', 10: 'projeto_nome', 11: 'data_agendamento', 12: 'sistema',
                    13: 'cod_equipamento', 14: 'nome_equipamento', 
                    16: 'quantidade', # Coluna Q (Quantidade_Solicitada)
                    19: 'gestor'
                }
                
                df_para_salvar = extrair_e_mapear_colunas(df_raw, col_map)
                
                if df_para_salvar is not None:
                    st.success("Arquivo lido. Pré-visualização dos dados extraídos:")
                    st.dataframe(df_para_salvar.head(), use_container_width=True)

                    if st.button("▶️ Iniciar Importação de Chamados"):
                        if df_para_salvar.empty: st.error("Planilha vazia ou colunas não encontradas.")
                        else:
                            with st.spinner("Importando e atualizando chamados..."):
                                # Renomeia colunas para o formato que 'bulk_insert_chamados_db' espera
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
                                    st.success(f"🎉 {num_importados} chamados importados/atualizados com sucesso!")
                                    st.balloons(); st.rerun() 
                                else:
                                    st.error("A importação de chamados falhou.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")
                st.error("Verifique o formato do arquivo (Excel ou CSV com ';') e se ele não está corrompido.")

    st.divider()

    # --- 2. Carregar Dados (APENAS CHAMADOS) ---
    with st.spinner("Carregando dados de chamados..."):
        df_chamados_raw = utils_chamados.carregar_chamados_db()

    if df_chamados_raw.empty:
        st.info("Nenhum dado de chamado encontrado no sistema. Comece importando um arquivo acima.")
        st.stop()

    # --- 3. Criar o Campo Combinado de Agência ---
    if not df_chamados_raw.empty and 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), 
            axis=1
        )
    else:
        st.error("Tabela de chamados parece estar incompleta (sem 'Cód. Agência'). Tente re-importar."); st.stop()

    lista_agencias_completa = sorted(df_chamados_raw['Agencia_Combinada'].dropna().astype(str).unique())
    lista_agencias_completa = [a for a in lista_agencias_completa if a not in ["N/A", "None", ""]]
    lista_agencias_completa.insert(0, "Todas") 

    # --- 4. Filtro Principal por Agência ---
    st.markdown("#### 🏦 Selecionar Agência")
    agencia_selecionada = st.selectbox(
        "Selecione uma Agência para ver o histórico completo:",
        options=lista_agencias_completa,
        key="filtro_agencia_principal",
        label_visibility="collapsed"
    )
    st.divider()

    # --- 5. Exibição dos Dados (Filtrados) ---
    if agencia_selecionada == "Todas":
        df_chamados_filtrado = df_chamados_raw
    else:
        # Filtra pelo Cód. Agência (extrai o número)
        agencia_id_filtro = agencia_selecionada.split(" - ")[0].replace("AG ", "").lstrip('0')
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Cód. Agência'].astype(str) == agencia_id_filtro]


    # --- 6. Painel Financeiro e KPIs ---
    total_chamados = len(df_chamados_filtrado)
    valor_total_chamados = 0.0; chamados_abertos_count = 0
    if not df_chamados_filtrado.empty:
        if 'Valor (R$)' in df_chamados_filtrado.columns:
            valor_total_chamados = pd.to_numeric(df_chamados_filtrado['Valor (R$)'], errors='coerce').fillna(0).sum()
        if 'Status' in df_chamados_filtrado.columns:
            status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado']
            chamados_abertos_count = len(df_chamados_filtrado[~df_chamados_filtrado['Status'].astype(str).str.lower().isin(status_fechamento)])

    st.markdown(f"### 📊 Resumo da Agência: {agencia_selecionada}")
    cols_kpi = st.columns(3) 
    cols_kpi[0].metric("Total de Chamados", total_chamados)
    cols_kpi[1].metric("Chamados Abertos", chamados_abertos_count)
    cols_kpi[2].metric("Financeiro Chamados (R$)", f"{valor_total_chamados:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')) 
    st.divider()

    # --- 7. NOVA VISÃO EM CARDS (Agrupado por Agência) ---
    st.markdown("#### 📋 Chamados Registrados")
    
    if df_chamados_filtrado.empty:
        st.info("Nenhum chamado encontrado para esta agência.")
    else:
        # Ordena os chamados pela data de agendamento mais recente
        df_chamados_filtrado['Agendamento'] = pd.to_datetime(df_chamados_filtrado['Agendamento'], errors='coerce')
        df_chamados_filtrado = df_chamados_filtrado.sort_values(by="Agendamento", ascending=False, na_position='last')
        
        # --- NÃO agrupa por projeto, mostra lista reta ---
        
        for _, row in df_chamados_filtrado.iterrows():
            chamado_id_str = str(row.get('Nº Chamado', 'N/A'))
            chamado_id_interno = row.get('ID') # ID da tabela 'chamados'
            
            # --- Monta o Cabeçalho (Conforme solicitado) ---
            data_recente_str = "Sem Data"
            if pd.notna(row.get('Agendamento')):
                try: data_recente_str = pd.to_datetime(row.get('Agendamento')).strftime('%d/%m/%Y')
                except: pass # Mantém "Sem Data" se falhar
                
            agencia_nome = row.get('Agencia_Combinada', 'N/A')
            projeto_nome = str(row.get('Projeto', 'N/A')).upper()
            gestor_nome = html.escape(str(row.get('Gestor', 'N/A')))
            uf_nome = html.escape(str(row.get('UF', 'N/A')))
            status_chamado = html.escape(str(row.get('Status', 'N/A')))
            
            # Usa o estilo de card do app principal
            st.markdown(f"""
                <div class='project-card'>
                    <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                        <div style='flex: 3;'>
                            <h6 style='margin-bottom: 5px;'>📅 {data_recente_str} | {agencia_nome} ({uf_nome})</h6>
                            <h5 style='margin:2px 0;'>{projeto_nome}</h5>
                        </div>
                        <div style='flex: 1; text-align: right;'>
                            <span style='font-weight: bold; color: {utils_chamados.get_color_for_name(gestor_nome)};'>{gestor_nome}</span>
                            <span style="background-color:{utils_chamados.get_status_color(status_chamado)}; color:black; padding:4px 8px; border-radius:5px; font-weight:bold; font-size:0.8em; margin-top: 5px; display: block;">{status_chamado}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # --- Expander INTERNO com Formulário de Edição ---
            with st.expander(f"Editar Chamado: {chamado_id_str}"):
                
                with st.form(f"form_chamado_edit_{chamado_id_interno}"):
                    st.markdown(f"**Editando Chamado:** {chamado_id_str}")
                    
                    # Colunas do Card (Conforme solicitado)
                    col_form1, col_form2, col_form3 = st.columns(3)
                    with col_form1:
                        data_abertura = _to_date_safe(row.get('Abertura'))
                        st.date_input("Data Abertura (Importado)", value=data_abertura, format="DD/MM/YYYY", disabled=True, key=f"abertura_{chamado_id_interno}")
                        
                        agendamento_val = _to_date_safe(row.get('Agendamento'))
                        novo_agendamento = st.date_input("Data Agendamento (Editável)", value=agendamento_val, format="DD/MM/YYYY", key=f"agend_{chamado_id_interno}")
                        
                        finalizacao_val = _to_date_safe(row.get('Fechamento'))
                        novo_fechamento = st.date_input("Data Finalização (Editável)", value=finalizacao_val, format="DD/MM/YYYY", key=f"final_{chamado_id_interno}")

                    with col_form2:
                        st.text_input("Nº Chamado", value=chamado_id_str, disabled=True, key=f"id_{chamado_id_interno}")
                        novo_sistema = st.text_input("Sistema (Editável)", value=row.get('Sistema'), key=f"sis_{chamado_id_interno}")
                        novo_servico = st.text_input("Serviço (Editável)", value=row.get('Serviço'), key=f"serv_{chamado_id_interno}")
                        
                    with col_form3:
                        novo_equip = st.text_input("Nome Equipamento (Editável)", value=row.get('Equipamento'), key=f"equip_{chamado_id_interno}")
                        
                        # --- CORREÇÃO DO ERRO 'numpy.int64' / ValueError ---
                        qtd_valor_raw = row.get('Qtd.')
                        # 1. Verifica se não é nulo/NaN, 2. Tenta converter para float, 3. Converte para int
                        try:
                            qtd_valor = int(float(qtd_valor_raw)) if pd.notna(qtd_valor_raw) else 0
                        except (ValueError, TypeError):
                            qtd_valor = 0 # Define 0 se o valor for um texto (ex: "N/A")
                        
                        nova_qtd = st.number_input("Quantidade (Editável)", value=qtd_valor, min_value=0, step=1, key=f"qtd_{chamado_id_interno}")
                        # --- FIM DA CORREÇÃO ---

                        status_fin_opts = ["Pendente", "Faturado", "Concluído", "N/A"]
                        status_fin_atual = str(row.get('Status Financeiro', 'Pendente'))
                        idx_fin = status_fin_opts.index(status_fin_atual) if status_fin_atual in status_fin_opts else 0
                        novo_status_financeiro = st.selectbox("Status Financeiro (Editável)", options=status_fin_opts, index=idx_fin, key=f"fin_{chamado_id_interno}")
                    
                    st.markdown("---")
                    nova_observacao = st.text_area(
                        "Observações (Editável)", 
                        value=row.get('Observação', ''),
                        placeholder="Insira observações sobre este chamado...",
                        key=f"obs_{chamado_id_interno}"
                    )
                    log_chamado = row.get('Log do Chamado', '')
                    st.text_area(
                        "Log de Alterações", 
                        value=log_chamado, 
                        disabled=True, 
                        height=100,
                        key=f"log_{chamado_id_interno}"
                    )
                    
                    btn_salvar_chamado = st.form_submit_button("💾 Salvar Alterações do Chamado")
                    
                    if btn_salvar_chamado:
                        updates = {
                            "Data Agendamento": novo_agendamento,
                            "Data Finalização": novo_fechamento,
                            "Observação": nova_observacao,
                            "Sistema": novo_sistema,
                            "Serviço": novo_servico,
                            "Nome Equipamento": novo_equip,
                            "Quantidade": nova_qtd,
                            "Status Financeiro": novo_status_financeiro
                        }
                        with st.spinner("Salvando..."):
                            # Atualiza usando o ID INTERNO (único)
                            sucesso = utils_chamados.atualizar_chamado_db(chamado_id_interno, updates) 
                            if sucesso:
                                st.success(f"Chamado {chamado_id_str} atualizado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Falha ao salvar as alterações.")

# --- Ponto de Entrada ---
tela_dados_agencia()
