import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades com a conexão já estabelecida
import json

st.set_page_config(page_title="Importador de Dados", layout="wide")
st.title("⚙️ Ferramenta de Importação de Dados para o Banco")
st.warning("Use esta página apenas para a migração inicial de dados. Após o uso, remova este arquivo do seu repositório.")

# --- SEÇÃO DE PROJETOS ---
with st.expander("1. Importar Projetos", expanded=True):
    st.info("Faça o upload da sua planilha Excel (.xlsx) contendo todos os projetos.")
    
    # --- BOTÃO PARA LIMPAR DADOS ANTIGOS ---
    st.markdown("#### Limpeza (Passo Opcional, mas Recomendado)")
    st.write("Antes de importar, você pode limpar todos os projetos existentes para evitar duplicatas.")
    if st.button("🗑️ Limpar Todos os Projetos Antigos", type="primary"):
        try:
            with utils.conn.cursor() as cur:
                cur.execute("DELETE FROM projetos;")
            st.success("Tabela de projetos limpa com sucesso! Agora você pode importar os dados.")
        except Exception as e:
            st.error(f"Erro ao limpar a tabela de projetos: {e}")

    uploaded_file_projetos = st.file_uploader("Selecione a planilha de projetos", type=["xlsx"], key="projetos_uploader")

    if uploaded_file_projetos:
        try:
            df_projetos = pd.read_excel(uploaded_file_projetos)
            st.write("Pré-visualização dos dados a serem importados:")
            st.dataframe(df_projetos.head())

            if st.button("▶️ Iniciar Importação dos Projetos"):
                # Mapeamento explícito das colunas do Excel para as do banco de dados (em minúsculo)
                column_mapping = {
                    'Projeto': 'projeto', 'Descrição': 'descricao', 'Agência': 'agencia',
                    'Técnico': 'tecnico', 'Status': 'status', 'Agendamento': 'agendamento',
                    'Data de Abertura': 'data_abertura', 'Data de Finalização': 'data_finalizacao',
                    'Observação': 'observacao', 'Demanda': 'demanda', 'Log Agendamento': 'log_agendamento',
                    'Etapas_Concluidas': 'etapas_concluidas',
                    # Novas colunas adicionadas
                    'Analista': 'analista', 'Gestor': 'gestor'
                }
                
                # Renomeia as colunas do DataFrame para corresponder ao banco de dados
                df_projetos.rename(columns=column_mapping, inplace=True)
                
                # Seleciona apenas as colunas que existem na nossa tabela
                colunas_db = list(column_mapping.values())
                df_para_inserir = df_projetos[[col for col in colunas_db if col in df_projetos.columns]]

                with st.spinner("Importando projetos... Isso pode levar um momento."):
                    total_rows = len(df_para_inserir)
                    success_count = 0
                    
                    with utils.conn.cursor() as cur:
                        for index, row in df_para_inserir.iterrows():
                            # Converte dados que precisam ser JSON para o formato correto
                            for col_json in ['log_agendamento', 'etapas_concluidas']:
                                if col_json in row and pd.notna(row[col_json]):
                                    try:
                                        if not isinstance(row[col_json], str):
                                             row[col_json] = json.dumps(row[col_json])
                                    except (TypeError, ValueError):
                                        row[col_json] = None

                            # Filtra colunas que não existem na tabela do banco
                            row_data = row.dropna()
                            cols = ', '.join(row_data.index)
                            placeholders = ', '.join(['%s'] * len(row_data))
                            
                            sql = f"INSERT INTO projetos ({cols}) VALUES ({placeholders})"
                            try:
                                cur.execute(sql, tuple(row_data.values))
                                success_count += 1
                            except Exception as e:
                                st.warning(f"Não foi possível inserir a linha {index+1}: {e}")

                    st.success(f"{success_count} de {total_rows} projetos importados com sucesso!")

        except Exception as e:
            st.error(f"Ocorreu um erro ao processar o arquivo de projetos: {e}")

# --- SEÇÕES DE CONFIGURAÇÕES E USUÁRIOS ---
st.divider()
with st.expander("2. Importar Configurações e Usuários"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Importar Configurações")
        st.info("Faça o upload do arquivo `config.xlsx` com as abas de Status, Agências, etc.")
        uploaded_file_config = st.file_uploader("Selecione a planilha de configurações", type=["xlsx"], key="config_uploader")
        if uploaded_file_config:
            if st.button("▶️ Iniciar Importação das Configurações"):
                try:
                    xls = pd.ExcelFile(uploaded_file_config)
                    abas_config = ['status', 'agencias', 'projetos_nomes', 'tecnicos', 'sla', 'perguntas', 'etapas_evolucao']
                    count_success = 0
                    with st.spinner("Importando abas de configuração..."):
                        for aba in abas_config:
                            if aba in xls.sheet_names:
                                df_aba = pd.read_excel(xls, sheet_name=aba)
                                if utils.salvar_config_db(df_aba, aba):
                                    count_success += 1
                    st.success(f"{count_success} abas de configuração importadas com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao processar arquivo de configurações: {e}")

    with col2:
        st.subheader("Importar Usuários")
        st.info("Faça o upload do arquivo `usuarios.xlsx`.")
        uploaded_file_users = st.file_uploader("Selecione a planilha de usuários", type=["xlsx"], key="users_uploader")
        if uploaded_file_users:
            if st.button("▶️ Iniciar Importação dos Usuários"):
                try:
                    df_users = pd.read_excel(uploaded_file_users)
                    with st.spinner("Importando usuários..."):
                        with utils.conn.cursor() as cur:
                            cur.execute("DELETE FROM usuarios;") # Limpa usuários antigos
                            for _, row in df_users.iterrows():
                                cur.execute("INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
                                            (row['Nome'], row['Email'], row['Senha']))
                    st.success("Usuários importados com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao processar arquivo de usuários: {e}")
