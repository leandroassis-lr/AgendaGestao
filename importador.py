import streamlit as st
import pandas as pd
import psycopg2.extras
from utils_postgres import get_db_connection, normalize_key # Importando do seu novo utils

def bulk_insert_projetos(conn, df):
    """
    Insere um DataFrame inteiro no banco de dados de uma vez.
    É muito mais rápido do que inserir linha por linha.
    """
    st.info("Iniciando a importação...")

    # 1. Normalizar os nomes das colunas do arquivo para o padrão do banco
    # Ex: transforma "descrição do projeto" em "Descricao"
    df_renamed = df.rename(columns={col: normalize_key(col) for col in df.columns})

    # 2. Filtrar apenas pelas colunas que realmente existem na tabela 'projetos'
    db_columns = [
        'Projeto', 'Descricao', 'Agencia', 'Tecnico', 'Status',
        'Agendamento', 'Data_Abertura', 'Data_Finalizacao',
        'Observacao', 'Demanda', 'Log_Agendamento',
        'Respostas_Perguntas', 'Etapas_Concluidas'
    ]
    df_to_insert = df_renamed[[col for col in db_columns if col in df_renamed.columns]]

    # 3. Converter o DataFrame em uma lista de tuplas (formato que o DB entende)
    # tratando valores NaN (células vazias) para None (NULL no banco)
    tuples = [tuple(row.where(pd.notna(row), None)) for index, row in df_to_insert.iterrows()]
    cols = ','.join([f'"{col}"' for col in df_to_insert.columns])

    # 4. Executar o comando de inserção em massa
    with conn.cursor() as cur:
        try:
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO projetos ({cols}) VALUES %s",
                tuples
            )
            conn.commit() # Salva as alterações
            st.success(f"{len(tuples)} projetos importados com sucesso!")
            return len(tuples)
        except Exception as e:
            st.error(f"Ocorreu um erro durante a importação: {e}")
            conn.rollback() # Desfaz a operação em caso de erro
            return 0


st.set_page_config(layout="centered")
st.title("Ferramenta de Importação de Projetos 🚀")
st.warning("Atenção: Use esta ferramenta apenas uma vez para migrar seus dados antigos.")

uploaded_file = st.file_uploader(
    "Selecione um arquivo Excel ou CSV com seus projetos",
    type=["csv", "xlsx"]
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.subheader("Pré-visualização dos dados")
        st.write("Verifique se as colunas e os dados parecem corretos antes de importar.")
        st.dataframe(df)

        if st.button("Iniciar Importação para o Banco de Dados", type="primary"):
            with st.spinner("Conectando ao banco e importando dados... Por favor, aguarde."):
                conn = get_db_connection()
                if conn:
                    bulk_insert_projetos(conn, df)
                else:
                    st.error("Não foi possível conectar ao banco de dados.")

    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
