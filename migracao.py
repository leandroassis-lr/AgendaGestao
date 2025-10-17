import pandas as pd
import sqlite3
import sys

# --- CONFIGURAÇÕES ---
ARQUIVO_EXCEL = 'projetos.xlsx'
ARQUIVO_DB = 'gestao_projetos.db'
NOME_TABELA = 'projetos'

# Nomes exatos das colunas como devem estar no banco de dados
# Esta lista PRECISA ter a mesma ordem das colunas no seu arquivo Excel
COLUNAS_ESPERADAS = [
    "ID", "Status", "Agendamento", "Analista", "Agencia", "Gestor", 
    "Projeto", "Tecnico", "Demanda", "Descricao", "Observacao", 
    "Data_Abertura", "Data_Finalizacao", "Log_Agendamento", "Etapas_Concluidas"
]

def migrar_dados():
    print("Iniciando a migração de dados do Excel para o SQLite...")

    # --- Passo 1: Ler o arquivo Excel ---
    try:
        # Usamos 'openpyxl' que é bom para arquivos .xlsx
        df = pd.read_excel(ARQUIVO_EXCEL, engine='openpyxl')
        print(f"Sucesso: {len(df)} linhas lidas do arquivo '{ARQUIVO_EXCEL}'.")
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{ARQUIVO_EXCEL}' não encontrado. Verifique se o nome está correto e se ele está na mesma pasta.")
        sys.exit()
    except Exception as e:
        print(f"ERRO: Falha ao ler o arquivo Excel. Detalhes: {e}")
        sys.exit()

    # --- Passo 2: Preparar os dados ---
    # Adiciona a coluna ID se ela não existir
    if 'ID' not in df.columns:
        # Insere a coluna ID no início
        df.insert(0, 'ID', None)
        print("Coluna 'ID' não encontrada no Excel, adicionada automaticamente.")

    # Garante que a ordem das colunas está correta e renomeia se necessário
    # Isso corrige qualquer pequena diferença de nome entre o Excel e o BD
    if len(df.columns) != len(COLUNAS_ESPERADAS):
        print(f"ERRO: O número de colunas no Excel ({len(df.columns)}) é diferente do esperado ({len(COLUNAS_ESPERADAS)}).")
        print("Verifique seu arquivo Excel.")
        sys.exit()
    
    df.columns = COLUNAS_ESPERADAS
    print("Colunas do Excel alinhadas com a estrutura do banco de dados.")

    # --- Passo 3: Conectar e inserir no banco de dados ---
    try:
        # Conecta ao banco de dados
        conexao = sqlite3.connect(ARQUIVO_DB)
        cursor = conexao.cursor()

        # Limpa a tabela antes de inserir para evitar duplicatas
        cursor.execute(f"DELETE FROM {NOME_TABELA};")
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{NOME_TABELA}';")
        print(f"Tabela '{NOME_TABELA}' limpa com sucesso.")

        # Insere o DataFrame do pandas na tabela do SQLite
        # O 'if_exists='replace'' recria a tabela, mas vamos usar 'append'
        # já que limpamos manualmente e queremos manter a estrutura original.
        df.to_sql(NOME_TABELA, conexao, if_exists='append', index=False)

        # Confirma as alterações
        conexao.commit()
        
        # Fecha a conexão
        conexao.close()
        
        print("\n-----------------------------------------------------")
        print("MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"{len(df)} registros foram inseridos na tabela '{NOME_TABELA}'.")
        print("-----------------------------------------------------")

    except Exception as e:
        print(f"ERRO: Falha ao conectar ou inserir dados no banco de dados. Detalhes: {e}")
        sys.exit()

# --- Roda a função principal ---
if __name__ == "__main__":
    migrar_dados()