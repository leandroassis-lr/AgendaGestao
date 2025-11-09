import streamlit as st
import pandas as pd
from datetime import date, datetime 
import re
import html
import psycopg2
from psycopg2 import sql
import numpy as np 

# --- 1. FUNÇÃO DE CONEXÃO (Independente) ---
@st.cache_resource
def get_db_connection_chamados():
    """Cria uma conexão SÓ PARA ESTA PÁGINA."""
    try:
        secrets = st.secrets["postgres"]
        conn = psycopg2.connect(host=secrets["PGHOST"], port=secrets["PGPORT"], user=secrets["PGUSER"], password=secrets["PGPASSWORD"], dbname=secrets["PGDATABASE"])
        conn.autocommit = False # Desliga autocommit para transações
        return conn
    except KeyError as e: st.error(f"Erro Crítico: Credencial '{e}' não encontrada."); return None
    except Exception as e: st.error(f"Erro ao conectar ao DB: {e}"); return None

conn = get_db_connection_chamados() 

# --- 2. FUNÇÃO PARA CRIAR/ATUALIZAR A TABELA 'chamados' ---
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
                'data_abertura': 'DATE', 'data_fechamento': 'DATE',
                'status_chamado': 'TEXT', 'valor_chamado': 'NUMERIC(10, 2) DEFAULT 0.00',
                'status_financeiro': "TEXT DEFAULT 'Pendente'",
                'observacao': 'TEXT', 
                'log_chamado': 'TEXT',
                'analista': 'TEXT',
                'tecnico': 'TEXT',
                'prioridade': "TEXT DEFAULT 'Média'"
            }
            
            # Pega colunas que já existem
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chamados';")
            colunas_existentes = [row[0] for row in cur.fetchall()]
            
            # Adiciona as que faltam
            for coluna, tipo_coluna in colunas_necessarias.items():
                if coluna not in colunas_existentes:
                    st.warning(f"Atualizando BD (Chamados): Adicionando coluna '{coluna}'...")
                    cur.execute(f"ALTER TABLE chamados ADD COLUMN {coluna} {tipo_coluna};")
            conn.commit() # Comita as alterações de estrutura
            
    except Exception as e:
        st.error(f"Erro ao criar/verificar tabela 'chamados': {e}")
        try: conn.rollback()
        except: pass


# --- 3. FUNÇÃO PARA CARREGAR CHAMADOS ---
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
        
        rename_map = {
            'id': 'ID', 'chamado_id': 'Nº Chamado', 'agencia_id': 'Cód. Agência', 
            'agencia_nome': 'Nome Agência', 'agencia_uf': 'UF', 'servico': 'Serviço',
            'projeto_nome': 'Projeto', 'data_agendamento': 'Agendamento',
            'sistema': 'Sistema', 'cod_equipamento': 'Cód. Equip.', 'nome_equipamento': 'Equipamento',
            'quantidade': 'Qtd.', 'gestor': 'Gestor',
            'descricao': 'Descrição', 'data_abertura': 'Abertura', 'data_fechamento': 'Fechamento',
            'status_chamado': 'Status', 'valor_chamado': 'Valor (R$)',
            'status_financeiro': 'Status Financeiro',
            'observacao': 'Observação', 'log_chamado': 'Log do Chamado',
            'analista': 'Analista',
            'tecnico': 'Técnico',
            'prioridade': 'Prioridade'
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        
        if 'Analista' not in df.columns: df['Analista'] = None
        if 'Técnico' not in df.columns: df['Técnico'] = None
        if 'Prioridade' not in df.columns: df['Prioridade'] = 'Média'

        return df
    except Exception as e:
        st.error(f"Erro ao carregar chamados: {e}"); return pd.DataFrame()

# --- 4. FUNÇÃO PARA IMPORTAR CHAMADOS (COM A SUA CORREÇÃO) ---
def bulk_insert_chamados_db(df: pd.DataFrame):
    """ Importa um DataFrame de chamados para o banco (UPSERT). """
    if not conn: return False, 0
    
    # Mapeamento do Excel/CSV -> colunas do banco
    # (Este é o mapeamento que a Pagina_7 está enviando)
    column_map = {
        'Chamado': 'chamado_id',
        'Codigo_Ponto': 'agencia_id',
        'Nome': 'agencia_nome',
        'UF': 'agencia_uf',
        'Servico': 'servico',
        'Projeto': 'projeto_nome',
        'Data_Agendamento': 'data_agendamento',
        'Tipo_De_Solicitacao': 'sistema', # Mapeamento da Pagina_7
        'Sistema': 'cod_equipamento',     # Mapeamento da Pagina_7
        'Codigo_Equipamento': 'nome_equipamento', # Mapeamento da Pagina_7
        'Quantidade_Solicitada': 'quantidade',     # Mapeamento da Pagina_7
        'Substitui_Outro_Equipamento_(Sim/Não)': 'gestor' # Mapeamento da Pagina_7
    }
    
    df_to_insert = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    if 'chamado_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter a coluna 'Chamado' (ID do chamado).")
        return False, 0
    if 'agencia_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter a coluna 'Codigo_Ponto' (ID da Agência).")
        return False, 0

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
        'descricao', 'data_abertura', 'data_fechamento', 'status_chamado', 'valor_chamado',
        'analista', 'tecnico', 'prioridade' # Incluindo novas colunas
    ]
                       
    df_final = df_to_insert[[col for col in cols_to_insert if col in df_to_insert.columns]]
    
    values = []
    for record in df_final.to_records(index=False):
        processed_record = []
        for cell in record:
            if pd.isna(cell) or cell is pd.NaT:
                processed_record.append(None) # Trata NaT / NaN
            elif isinstance(cell, (np.int64, np.int32, np.int16, np.int8, pd.Int64Dtype.type)):
                processed_record.append(int(cell)) # Inteiro puro
            elif isinstance(cell, (np.float64, np.float32)):
                processed_record.append(float(cell)) # Float puro
            elif isinstance(cell, (pd.Timestamp, datetime, np.datetime64)):
                # --- A SUA CORREÇÃO APLICADA AQUI ---
                processed_record.append(pd.to_datetime(cell).date())
            else:
                processed_record.append(str(cell) if cell is not None else None) 
        values.append(tuple(processed_record))
    
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns)); placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))
    
    update_clause = sql.SQL(', ').join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in df_final.columns if col != 'chamado_id' 
    )
    query = sql.SQL("INSERT INTO chamados ({}) VALUES ({}) ON CONFLICT (chamado_id) DO UPDATE SET {}").format(cols_sql, placeholders, update_clause)

    try:
        with conn.cursor() as cur: 
            cur.executemany(query, values) 
        conn.commit() # Comita a transação
        st.cache_data.clear(); return True, len(values)
    except Exception as e: 
        conn.rollback() # Desfaz a transação em caso de erro
        st.error(f"Erro ao salvar chamados no banco: {e}"); return False, 0

# --- 5. FUNÇÃO PARA SALVAR EDIÇÕES DE CHAMADOS ---
def atualizar_chamado_db(chamado_id_interno, updates: dict):
    """ Atualiza um chamado existente no banco de dados e gera log. """
    if not conn: return False
    
    usuario_logado = st.session_state.get('usuario', 'Sistema') 
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT data_agendamento, data_fechamento, observacao, log_chamado,
                       sistema, servico, nome_equipamento, quantidade, status_financeiro,
                       analista, tecnico, prioridade, status_chamado, projeto_nome, gestor,
                       agencia_id, data_abertura
                FROM chamados WHERE id = %s
            """, (chamado_id_interno,))
            current_data_tuple = cur.fetchone()
            if not current_data_tuple:
                st.error(f"Erro: Chamado com ID interno {chamado_id_interno} não encontrado.")
                return False

            (current_agendamento, current_fechamento, current_obs, current_log,
             current_sistema, current_servico, current_equip, current_qtd, current_fin,
             current_analista, current_tecnico, current_prioridade, current_status,
             current_projeto, current_gestor, current_agencia_id, current_abertura) = current_data_tuple
             
            current_log = current_log or "" 

            db_updates_raw = {}
            for key, value in updates.items():
                k = str(key).lower().replace(" ", "_")
                if "agendamento" in k: k = "data_agendamento"
                elif "finalizacao" in k or "fechamento" in k: k = "data_fechamento"
                elif "observacao" in k: k = "observacao"
                elif "sistema" in k: k = "sistema"
                elif "servico" in k: k = "servico"
                elif "equipamento" in k: k = "nome_equipamento"
                elif "quantidade" in k: k = "quantidade"
                elif "financeiro" in k: k = "status_financeiro"
                elif "analista" in k: k = "analista"
                elif "tecnico" in k: k = "tecnico"
                elif "prioridade" in k: k = "prioridade"
                elif "status" in k: k = "status_chamado" 
                elif "projeto" in k: k = "projeto_nome"
                elif "gestor" in k: k = "gestor"
                elif "agencia" in k: k = "agencia_id" 
                elif "abertura" in k: k = "data_abertura"
                
                if isinstance(value, (datetime, date)): db_updates_raw[k] = value.strftime('%Y-%m-%d')
                elif pd.isna(value): db_updates_raw[k] = None
                else: db_updates_raw[k] = str(value)

            log_entries = []; hoje_str = date.today().strftime('%d/%m/%Y')
            
            def log_change(field_name, new_val, old_val, is_date=False):
                if new_val is None: new_val = "" 
                if old_val is None: old_val = "" 
                
                if is_date:
                    try: new_val_date = datetime.strptime(new_val, '%Y-%m-%d').date() if new_val else None
                    except ValueError: new_val_date = old_val
                    if new_val_date != old_val:
                        old_str = old_val.strftime('%d/%m/%Y') if isinstance(old_val, date) else "N/A"
                        new_str = new_val_date.strftime('%d/%m/%Y') if isinstance(new_val_date, date) else "N/A"
                        log_entries.append(f"Em {hoje_str} por {usuario_logado}: {field_name} de '{old_str}' para '{new_str}'.")
                elif str(new_val).strip() != str(old_val).strip():
                       log_entries.append(f"Em {hoje_str} por {usuario_logado}: {field_name} de '{old_val}' para '{new_val}'.")

            # Log para todos os campos
            log_change("Agendamento", db_updates_raw.get('data_agendamento'), current_agendamento, is_date=True)
            log_change("Abertura", db_updates_raw.get('data_abertura'), current_abertura, is_date=True)
            log_change("Fechamento", db_updates_raw.get('data_fechamento'), current_fechamento, is_date=True)
            log_change("Observação", db_updates_raw.get('observacao'), current_obs)
            log_change("Sistema", db_updates_raw.get('sistema'), current_sistema)
            log_change("Serviço", db_updates_raw.get('servico'), current_servico)
            log_change("Equipamento", db_updates_raw.get('nome_equipamento'), current_equip)
            log_change("Quantidade", db_updates_raw.get('quantidade'), current_qtd)
            log_change("Status Financeiro", db_updates_raw.get('status_financeiro'), current_fin)
            log_change("Analista", db_updates_raw.get('analista'), current_analista)
            log_change("Técnico", db_updates_raw.get('tecnico'), current_tecnico)
            log_change("Prioridade", db_updates_raw.get('prioridade'), current_prioridade)
            log_change("Status", db_updates_raw.get('status_chamado'), current_status)
            log_change("Projeto", db_updates_raw.get('projeto_nome'), current_projeto)
            log_change("Gestor", db_updates_raw.get('gestor'), current_gestor)
            log_change("Agência ID", db_updates_raw.get('agencia_id'), current_agencia_id)
            
            log_final = current_log; 
            if log_entries: log_final += ("\n" if current_log else "") + "\n".join(log_entries)
            
            updates_final = {}
            for k in db_updates_raw:
                if k in [
                    'data_agendamento', 'data_fechamento', 'observacao', 'sistema', 
                    'servico', 'nome_equipamento', 'quantidade', 'status_financeiro',
                    'analista', 'tecnico', 'prioridade', 'status_chamado', 'projeto_nome',
                    'gestor', 'agencia_id', 'data_abertura'
                ]:
                    updates_final[k] = db_updates_raw[k]

            if not updates_final and not log_entries:
                return True 

            updates_final['log_chamado'] = log_final if log_final else None
            
            set_clause = sql.SQL(', ').join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in updates_final.keys())
            query = sql.SQL("UPDATE chamados SET {} WHERE id = {}").format(set_clause, sql.Placeholder())
            vals = list(updates_final.values()) + [chamado_id_interno]
            
            cur.execute(query, vals)
            conn.commit() # Comita a atualização do chamado
        
        return True
    except Exception as e:
        conn.rollback() # Desfaz a atualização do chamado
        st.toast(f"Erro CRÍTICO ao atualizar chamado ID {chamado_id_interno}: {e}", icon="🔥"); 
        return False

# --- 6. Funções de Cor (Independentes) ---
def get_status_color(status):
    s = str(status or "").strip().lower()
    if 'finalizad' in s or 'fechado' in s or 'concluido' in s: return "#66BB6A" 
    elif 'pendencia' in s or 'pendência' in s: return "#FFA726" 
    elif 'nao iniciad' in s or 'não iniciad' in s: return "#B0BEC5" 
    elif 'cancelad' in s: return "#EF5350" 
    elif 'pausad' in s: return "#FFEE58" 
    else: return "#64B5F6"  

def get_color_for_name(name_str):
    COLORS_LIST = ["#D32F2F", "#1976D2", "#388E3C", "#F57C00", "#7B1FA2", "#00796B", "#C2185B", "#5D4037", "#455A64"]
    if name_str is None or name_str == "N/A": return "#555" 
    name_normalized = str(name_str).strip().upper() 
    if not name_normalized: return "#555"
    try:
        hash_val = hash(name_normalized); color_index = hash_val % len(COLORS_LIST)
        return COLORS_LIST[color_index]
    except Exception: return "#555"
