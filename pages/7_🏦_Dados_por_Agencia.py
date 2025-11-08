import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades
from datetime import date, datetime
import re # Importa re para a limpeza

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() # Tenta carregar o CSS
except:
    pass # Ignora se falhar

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

# --- Funções Helper da Página ---

def extrair_colunas_csv(df, col_indices, col_nomes_map):
    """ Extrai, renomeia e limpa colunas específicas de um DataFrame. """
    # Pega as colunas pelos índices (A=0, B=1, etc.)
    df_extraido = df.iloc[:, col_indices].copy()
    
    # Renomeia as colunas com base nos nomes do DataFrame (que são os nomes no Excel)
    df_extraido.columns = col_nomes_map.keys()
    
    # Renomeia para os nomes do banco
    df_final = df_extraido.rename(columns=col_nomes_map)
    
    return df_final

def limpar_agencia_excel(row):
    """ Função para criar o nome de agência combinado (ex: AG 1234 - NOME) """
    try:
        # Tenta converter o código para inteiro e formatar, senão usa como string
        cod_ponto = int(float(row['Codigo_Ponto']))
        agencia_id_str = f"AG {cod_ponto:04d}"
    except (ValueError, TypeError):
        agencia_id_str = str(row['Codigo_Ponto']).strip()
        
    agencia_nome_str = str(row['Nome']).strip()
    
    # Remove o nome se ele for redundante (ex: "AG 1234 - 1234 NOME")
    if agencia_nome_str.startswith(str(cod_ponto)):
        agencia_nome_str = agencia_nome_str[len(str(cod_ponto)):].strip()
        
    return f"{agencia_id_str} - {agencia_nome_str}"


# --- Tela Principal da Página ---
def tela_dados_agencia():
    st.markdown("<div class='section-title-center'>GESTÃO POR AGÊNCIA</div>", unsafe_allow_html=True)
    st.write(" ")

    # --- 1. Importador de Chamados ---
    with st.expander("📥 Importar Novos Chamados (Excel/CSV)"):
        st.info("""
            Arraste seu arquivo Excel de chamados (formato `.xlsx` ou `.csv` com `;`) aqui.
            Se um `Número do Chamado` já existir, ele será **atualizado**.
        """)
        uploaded_file = st.file_uploader("Selecione o arquivo Excel/CSV de chamados", type=["xlsx", "xls", "csv"], key="chamado_uploader")

        if uploaded_file is not None:
            try:
                # Determina o tipo de arquivo e lê
                if uploaded_file.name.endswith('.csv'):
                    # Lê como CSV, detectando o delimitador (provavelmente ;)
                    df_raw = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='latin-1', skiprows=1) # Pula linha 2
                else:
                    # Lê como Excel, pulando a primeira linha (cabeçalho)
                    df_raw = pd.read_excel(uploaded_file, header=0, skiprows=[0]) # Pula linha 2
                
                st.success("Arquivo carregado. Pré-visualização das colunas lidas:")
                st.dataframe(df_raw.head(), use_container_width=True)

                # --- Mapeamento (Conforme sua solicitação A, B, C...) ---
                # Coluna A=0, B=1, C=2, D=3, J=9, K=10, L=11, M=12, N=13, O=14, P=15, T=19
                col_indices = [0, 1, 2, 3, 9, 10, 11, 12, 13, 14, 15, 19]
                
                # Pega os nomes das colunas originais do arquivo (da linha 1)
                col_nomes_originais = df_raw.columns.tolist()
                
                # Mapeia o nome original -> nome do BD
                col_nomes_map = {
                    col_nomes_originais[0]: 'chamado_id',
                    col_nomes_originais[1]: 'agencia_id', # Codigo_Ponto
                    col_nomes_originais[2]: 'agencia_nome', # Nome
                    col_nomes_originais[3]: 'agencia_uf', # UF
                    col_nomes_originais[9]: 'servico', # Servico
                    col_nomes_originais[10]: 'projeto_nome', # Projeto
                    col_nomes_originais[11]: 'data_agendamento', # Data_Agendamento
                    col_nomes_originais[12]: 'sistema', # Tipo_De_Solicitacao
                    col_nomes_originais[13]: 'cod_equipamento', # Sistema
                    col_nomes_originais[14]: 'nome_equipamento', # Codigo_Equipamento
                    col_nomes_originais[15]: 'quantidade', # Nome_Equipamento
                    col_nomes_originais[19]: 'gestor' # Substitui_Outro_Equipamento_...
                }
                
                # Extrai e renomeia
                df_para_salvar = df_raw.iloc[:, col_indices].copy()
                df_para_salvar.columns = col_nomes_map.values()
                # ----------------------------------------------------

                if st.button("▶️ Iniciar Importação de Chamados"):
                    if df_para_salvar.empty:
                        st.error("Planilha vazia ou colunas não encontradas.")
                    else:
                        with st.spinner("Importando e atualizando chamados..."):
                            # Renomeia colunas de volta para o formato que 'bulk_insert_chamados_db' espera
                            # (Isso é um pouco redundante, mas usa a função que já temos)
                            reverse_map = {v: k for k, v in utils.bulk_insert_chamados_db.__defaults__[0].items()} # Hack para pegar o map
                            df_para_salvar_final = df_para_salvar.rename(columns=reverse_map)

                            sucesso, num_importados = utils.bulk_insert_chamados_db(df_para_salvar_final)
                            if sucesso:
                                st.success(f"🎉 {num_importados} chamados importados/atualizados com sucesso!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("A importação de chamados falhou.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")
                st.error("Se for um CSV, verifique se o delimitador é ponto e vírgula (;) e a codificação é 'latin-1'.")

    st.divider()

    # --- 2. Carregar e Combinar Dados do BD ---
    with st.spinner("Carregando dados de projetos e chamados..."):
        df_projetos_raw = utils.carregar_projetos_db() 
        df_chamados_raw = utils.carregar_chamados_db()

    if df_projetos_raw.empty and df_chamados_raw.empty:
        st.info("Nenhum dado de projeto ou chamado encontrado no sistema.")
        st.stop()

    # --- 3. Criar o Campo Combinado de Agência (para filtros e grupos) ---
    def criar_agencia_combinada(row):
        # Limpa e formata o ID
        try:
            cod_ponto = int(float(row['Agência']))
            agencia_id_str = f"AG {cod_ponto:04d}"
        except (ValueError, TypeError):
            agencia_id_str = str(row['Agência']).strip()
        return f"{agencia_id_str} - {str(row.get('agencia_nome', 'N/A')).strip()}"

    # Adiciona o campo combinado em ambos os DFs
    if not df_projetos_raw.empty and 'Agência' in df_projetos_raw.columns:
        # No 'projetos', o nome da agência não está separado, então usamos o ID
        df_projetos_raw['Agencia_Combinada'] = df_projetos_raw['Agência'].astype(str) 
    else:
        df_projetos_raw['Agencia_Combinada'] = None

    if not df_chamados_raw.empty and 'Cód. Agência' in df_chamados_raw.columns:
        # No 'chamados', nós temos ambos, então combinamos
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: f"AG {int(float(row['Cód. Agência'])):04d} - {str(row['Nome Agência']).strip()}" if pd.notna(row['Cód. Agência']) else 'N/A', 
            axis=1
        )
    else:
        df_chamados_raw['Agencia_Combinada'] = None

    # Pega lista única de todas as agências
    agencias_projetos = df_projetos_raw['Agencia_Combinada'].dropna().astype(str).unique()
    agencias_chamados = df_chamados_raw['Agencia_Combinada'].dropna().astype(str).unique()
    lista_agencias_completa = sorted(list(set(agencias_projetos) | set(agencias_chamados)))
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

    # --- 5. Exibição dos Dados ---
    if agencia_selecionada == "Todas":
        df_projetos_filtrado = df_projetos_raw
        df_chamados_filtrado = df_chamados_raw
    else:
        df_projetos_filtrado = df_projetos_raw[df_projetos_raw['Agencia_Combinada'] == agencia_selecionada]
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Agencia_Combinada'] == agencia_selecionada]

    # --- 6. Painel Financeiro e KPIs ---
    total_projetos = len(df_projetos_filtrado)
    total_chamados = len(df_chamados_filtrado)
    valor_total_chamados = 0.0
    chamados_abertos_count = 0
    
    if not df_chamados_filtrado.empty:
        if 'Valor (R$)' in df_chamados_filtrado.columns:
            valor_total_chamados = pd.to_numeric(df_chamados_filtrado['Valor (R$)'], errors='coerce').fillna(0).sum()
        if 'Status' in df_chamados_filtrado.columns:
            status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado']
            chamados_abertos_count = len(df_chamados_filtrado[~df_chamados_filtrado['Status'].astype(str).str.lower().isin(status_fechamento)])

    st.markdown(f"### 📊 Resumo da Agência: {agencia_selecionada}")
    cols_kpi = st.columns(4)
    cols_kpi[0].metric("Total de Projetos", total_projetos)
    cols_kpi[1].metric("Total de Chamados", total_chamados)
    cols_kpi[2].metric("Chamados Abertos", chamados_abertos_count)
    cols_kpi[3].metric("Financeiro Chamados (R$)", f"{valor_total_chamados:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')) 

    # --- 7. Abas de Detalhes (Visão por Projeto) ---
    tab_projetos, tab_chamados = st.tabs(["Visão por Projetos", "Visão por Chamados (Financeiro)"])

    with tab_projetos:
        st.markdown("#### 📋 Histórico de Projetos na Agência")
        
        # Agrupa os projetos (do app principal) por nome
        if df_projetos_filtrado.empty:
            st.info("Nenhum projeto encontrado para esta agência.")
        else:
            colunas_projetos_visiveis = ['ID', 'Projeto', 'Status', 'Analista', 'Prioridade', 'Agendamento']
            colunas_projetos = [col for col in colunas_projetos_visiveis if col in df_projetos_filtrado.columns]
            
            # Agrupa os chamados (do excel) por nome de projeto
            df_chamados_por_projeto = df_chamados_filtrado.groupby('Projeto')
            
            # Loop pelos projetos
            for _, projeto_row in df_projetos_filtrado.iterrows():
                projeto_nome = projeto_row['Projeto']
                st.markdown("---")
                # Cabeçalho do Projeto (similar à tela de projetos)
                st.markdown(f"**PROJETO: {projeto_nome.upper()}** (ID: {projeto_row['ID']}) | Status: {projeto_row['Status']} | Analista: {projeto_row['Analista']}")
                
                # Expander para os chamados associados
                with st.expander(f"Ver Chamados Associados a este Projeto ({projeto_nome})"):
                    if projeto_nome in df_chamados_por_projeto.groups:
                        df_chamados_do_projeto = df_chamados_por_projeto.get_group(projeto_nome)
                        colunas_chamados_visiveis = ['Nº Chamado', 'Descrição', 'Status', 'Abertura', 'Fechamento', 'Equipamento', 'Qtd.']
                        colunas_chamados = [col for col in colunas_chamados_visiveis if col in df_chamados_do_projeto.columns]
                        st.dataframe(df_chamados_do_projeto[colunas_chamados], use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum chamado importado encontrado para este projeto.")

    with tab_chamados:
        st.markdown("#### 🎫 Histórico de Chamados (Visão Financeira)")
        if df_chamados_filtrado.empty:
            st.info("Nenhum chamado importado encontrado para esta agência.")
        else:
            colunas_chamados_visiveis = ['Nº Chamado', 'Descrição', 'Status', 'Abertura', 'Fechamento', 'Valor (R$)']
            colunas_chamados = [col for col in colunas_chamados_visiveis if col in df_chamados_filtrado.columns]
            
            if chamados_abertos_count > 0:
                st.warning(f"**Atenção:** {chamados_abertos_count} chamado(s) ainda estão abertos ou sem status de fechamento.")
            elif total_chamados > 0:
                st.success("Todos os chamados listados estão fechados.")

            st.dataframe(df_chamados_filtrado[colunas_chamados], use_container_width=True, hide_index=True)


# --- Ponto de Entrada ---
tela_dados_agencia()
