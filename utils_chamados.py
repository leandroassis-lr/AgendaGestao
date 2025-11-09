import streamlit as st
import pandas as pd
from datetime import date, datetime 
import re
import html
import psycopg2
from psycopg2 import sql
import numpy as np 

# Importa a conexão de banco de dados do utils original
try:
    from utils import conn, get_color_for_name, _to_date_safe
except ImportError:
    st.error("ERRO CRÍTICO: O arquivo principal utils.py não foi encontrado.")
    st.stop()

# --- 1. FUNÇÃO PARA CRIAR/ATUALIZAR A TABELA 'chamados' ---
def criar_tabela_chamados():
    """Cria a tabela 'chamados' e adiciona colunas ausentes se não existirem."""
    if not conn: return
    try:
        with conn.cursor() as cur:
            # Cria a tabela base
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chamados (
                    id SERIAL PRIMARY KEY,
                    chamado_id TEXT UNIQUE
                );
            """)
            
            # Dicionário de todas as colunas que a tabela DEVE ter
            colunas_necessarias = {
                'agencia_id': 'TEXT', 'agencia_nome': 'TEXT', 'agencia_uf': 'TEXT',
                'servico': 'TEXT', 'projeto_nome': 'TEXT', 'data_agendamento': 'DATE',
                'sistema': 'TEXT', 'cod_equipamento': 'TEXT', 'nome_equipamento': 'TEXT',
                'quantidade': 'INTEGER', 'gestor': 'TEXT', 'descricao': 'TEXT',
                'data_abertura': 'DATE', 'data_fechamento': 'DATE', 'status_chamado': 'TEXT',
                'valor_chamado': 'NUMERIC(10, 2) DEFAULT 0.00',
                'status_financeiro': "TEXT DEFAULT 'Pendente'",
                'observacao': 'TEXT', 
                'log_chamado': 'TEXT'
            }
            
            # Pega colunas que já existem
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chamados';")
            colunas_existentes = [row[0] for row in cur.fetchall()]
            
            # Adiciona as que faltam
            for coluna, tipo_coluna in colunas_necessarias.items():
                if coluna not in colunas_existentes:
                    st.warning(f"Atualizando BD (Chamados): Adicionando coluna '{coluna}'...")
                    cur.execute(f"ALTER TABLE chamados ADD COLUMN {coluna} {tipo_coluna};")
                    st.success(f"Coluna '{coluna}' adicionada.")
            
    except Exception as e:
        st.error(f"Erro ao criar/verificar tabela 'chamados': {e}")


# --- 2. FUNÇÃO PARA CARREGAR CHAMADOS ---
@st.cache_data(ttl=60)
def carregar_chamados_db(agencia_id_filtro=None):
    """ Carrega chamados, opcionalmente filtrados por ID de agência. """
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM chamados"
        params = []
        if agencia_id_filtro and agencia_id_filtro != "Todas":
            match = re.search(r'(\d+)', agencia_id_filtro)
            agencia_id_num = match.group(1).lstrip('0') if match else agencia_id_filtro
            query += " WHERE agencia_id = %s"
            params.append(agencia_id_num)
        query += " ORDER BY data_agendamento DESC, id DESC"
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        # Renomeia colunas do BD para nomes amigáveis
        rename_map = {
            'id': 'ID', 'chamado_id': 'Nº Chamado', 'agencia_id': 'Cód. Agência', 
            'agencia_nome': 'Nome Agência', 'agencia_uf': 'UF', 'servico': 'Serviço',
            'projeto_nome': 'Projeto', 'data_agendamento': 'Agendamento',
            'sistema': 'Sistema', 'cod_equipamento': 'Cód. Equip.', 'nome_equipamento': 'Equipamento',
            'quantidade': 'Qtd.', 'gestor': 'Gestor',
            'descricao': 'Descrição', 'data_abertura': 'Abertura', 'data_fechamento': 'Fechamento',
            'status_chamado': 'Status', 'valor_chamado': 'Valor (R$)',
            'status_financeiro': 'Status Financeiro',
            'observacao': 'Observação', 'log_chamado': 'Log do Chamado'
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        return df
    except Exception as e:
        st.error(f"Erro ao carregar chamados: {e}"); return pd.DataFrame()

# --- 3. FUNÇÃO PARA IMPORTAR CHAMADOS (COM CORREÇÃO DE TIPO) ---
def bulk_insert_chamados_db(df: pd.DataFrame):
    """ Importa um DataFrame de chamados para o banco (UPSERT). """
    if not conn: return False, 0
    
    # Mapeamento do Excel/CSV -> colunas do banco
    column_map = {
        'Chamado': 'chamado_id',
        'Codigo_Ponto': 'agencia_id',
        'Nome': 'agencia_nome',
        'UF': 'agencia_uf',
        'Servico': 'servico',
        'Projeto': 'projeto_nome',
        'Data_Agendamento': 'data_agendamento',
        'Tipo_De_Solicitacao': 'sistema', # M
        'Sistema': 'cod_equipamento',     # N
        'Codigo_Equipamento': 'nome_equipamento', # O
        'Quantidade_Solicitada': 'quantidade',     # Q
        'Substitui_Outro_Equipamento_(Sim/Não)': 'gestor' # T
    }
    
    df_to_insert = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    if 'chamado_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter a coluna 'Chamado' (ID do chamado).")
        return False, 0
    if 'agencia_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter a coluna 'Codigo_Ponto' (ID da Agência).")
        return False, 0

    # --- Tratamento de Tipos ---
    cols_data = ['data_abertura', 'data_fechamento', 'data_agendamento']
    for col in cols_data:
        if col in df_to_insert.columns:
            df_to_insert[col] = pd.to_datetime(df_to_insert[col], errors='coerce', dayfirst=True)
        else:
            df_to_insert[col] = None 

    if 'valor_chamado' in df_to_insert.columns:
         df_to_insert['valor_chamado'] = pd.to_numeric(df_to_insert['valor_chamado'], errors='coerce').fillna(0.0)
    if 'quantidade' in df_to_insert.columns:
         df_to_insert['quantidade'] = pd.to_numeric(df_to_insert['quantidade'], errors='coerce').astype('Int64')

    cols_to_insert = [
        'chamado_id', 'agencia_id', 'agencia_nome', 'agencia_uf', 'servico', 'projeto_nome', 
        'data_agendamento', 'sistema', 'cod_equipamento', 'nome_equipamento', 'quantidade', 'gestor',
        'descricao', 'data_abertura', 'data_fechamento', 'status_chamado', 'valor_chamado'
    ]
                      
    df_final = df_to_insert[[col for col in cols_to_insert if col in df_to_insert.columns]]
    
    # --- CORREÇÃO DEFINITIVA (v6) - Trata DATAS e NÚMEROS ---
    values = []
    for record in df_final.to_records(index=False):
        processed_record = []
        for cell in record:
            if pd.isna(cell) or cell is pd.NaT:
                processed_record.append(None) # Converte NaT, NaN, pd.NA para None
            elif isinstance(cell, (np.int64, np.int32, np.int16, np.int8, pd.Int64Dtype.type)):
                processed_record.append(int(cell)) # Converte numpy int/Int64 para python int
            elif isinstance(cell, (np.float64, np.float32)):
                processed_record.append(float(cell)) # Converte numpy float para python float
            elif isinstance(cell, (pd.Timestamp, datetime, np.datetime64)):
                processed_record.append(cell.date()) # Converte datetime para date
            else:
                processed_record.append(cell) 
        values.append(tuple(processed_record))
    # --- FIM DA CORREÇÃO ---
    
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns)); placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))
    
    update_clause = sql.SQL(', ').join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in df_final.columns if col != 'chamado_id' 
    )
    query = sql.SQL("INSERT INTO chamados ({}) VALUES ({}) ON CONFLICT (chamado_id) DO UPDATE SET {}").format(cols_sql, placeholders, update_clause)

    try:
        with conn.cursor() as cur: cur.executemany(query, values) 
        st.cache_data.clear(); return True, len(values)
    except Exception as e: 
        st.error(f"Erro ao salvar chamados no banco: {e}"); conn.rollback(); return False, 0

# --- 4. FUNÇÃO PARA SALVAR EDIÇÕES DE CHAMADOS ---
def atualizar_chamado_db(chamado_id, updates: dict):
    """ Atualiza um chamado existente no banco de dados e gera log. """
    if not conn: return False
    
    # Esta função usa o session_state, então o login é necessário
    usuario_logado = st.session_state.get('usuario', 'Sistema') 
    
    try:
        with conn.cursor() as cur:
            # 1. Buscar dados atuais
            cur.execute("""
                SELECT data_agendamento, data_fechamento, observacao, log_chamado 
                FROM chamados WHERE chamado_id = %s
            """, (chamado_id,))
            current_data_tuple = cur.fetchone()
            if not current_data_tuple:
                st.error(f"Erro: Chamado com ID {chamado_id} não encontrado.")
                return False

            current_agendamento, current_fechamento, current_obs, current_log = current_data_tuple
            current_log = current_log or "" 

            # Prepara dados da atualização (usa a função do utils.py)
            db_updates_raw = utils._normalize_and_sanitize(updates)
            
            # --- Geração do Log ---
            log_entries = []; hoje_str = date.today().strftime('%d/%m/%Y')
            
            # Compara Data Agendamento
            new_agendamento_str = db_updates_raw.get('data_agendamento')
            new_agendamento_date = None
            if new_agendamento_str:
                try: new_agendamento_date = datetime.strptime(new_agendamento_str, '%Y-%m-%d').date()
                except ValueError: new_agendamento_date = current_agendamento
            if new_agendamento_date != current_agendamento:
                data_antiga_str = current_agendamento.strftime('%d/%m/%Y') if isinstance(current_agendamento, date) else "N/A"
                data_nova_str = new_agendamento_date.strftime('%d/%m/%Y') if isinstance(new_agendamento_date, date) else "N/A"
                log_entries.append(f"Em {hoje_str} por {usuario_logado}: Agendamento de '{data_antiga_str}' para '{data_nova_str}'.")

            # Compara Data Fechamento
            new_fechamento_str = db_updates_raw.get('data_fechamento')
            new_fechamento_date = None
            if new_fechamento_str:
                try: new_fechamento_date = datetime.strptime(new_fechamento_str, '%Y-%m-%d').date()
                except ValueError: new_fechamento_date = current_fechamento
            if new_fechamento_date != current_fechamento:
                data_antiga_str = current_fechamento.strftime('%d/%m/%Y') if isinstance(current_fechamento, date) else "N/A"
                data_nova_str = new_fechamento_date.strftime('%d/%m/%Y') if isinstance(new_fechamento_date, date) else "N/A"
                log_entries.append(f"Em {hoje_str} por {usuario_logado}: Fechamento de '{data_antiga_str}' para '{data_nova_str}'.")

            # Compara Observação
            new_obs = db_updates_raw.get('observacao')
            if new_obs is not None and new_obs != (current_obs or ""):
                log_entries.append(f"Em {hoje_str} por {usuario_logado}: Observações atualizadas.")
            
            # Monta log final
            log_final = current_log; 
            if log_entries: log_final += ("\n" if current_log else "") + "\n".join(log_entries)
            db_updates_raw['log_chamado'] = log_final if log_final else None 
            
            # Prepara query
            updates_final = {k: v for k, v in db_updates_raw.items() if v is not None or k == 'log_chamado' or k == 'observacao'} 
            set_clause = sql.SQL(', ').join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in updates_final.keys())
            query = sql.SQL("UPDATE chamados SET {} WHERE chamado_id = {}").format(set_clause, sql.Placeholder())
            vals = list(updates_final.values()) + [chamado_id]
            
            cur.execute(query, vals)

        st.cache_data.clear(); return True
    except Exception as e:
        st.toast(f"Erro CRÍTICO ao atualizar chamado ID {chamado_id}: {e}", icon="🔥"); conn.rollback(); return False