import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import sql
import numpy as np
import re

# --- 1. GERENCIAMENTO DE CONEXÃO ---

@st.cache_resource
def _get_cached_connection_fin():
    try:
        secrets = st.secrets["postgres"]
        conn = psycopg2.connect(
            host=secrets["PGHOST"], 
            port=secrets["PGPORT"], 
            user=secrets["PGUSER"], 
            password=secrets["PGPASSWORD"], 
            dbname=secrets["PGDATABASE"],
            connect_timeout=10
        )
        conn.autocommit = False 
        return conn
    except Exception as e: 
        st.error(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def get_valid_conn_fin():
    conn = _get_cached_connection_fin()
    if conn is None or conn.closed != 0:
        st.cache_resource.clear() 
        conn = _get_cached_connection_fin() 
    return conn

# --- 2. CRIAÇÃO DAS TABELAS LPU ---

def criar_tabelas_lpu():
    """Cria as 3 tabelas para armazenar os preços da LPU, se não existirem."""
    conn = get_valid_conn_fin()
    if not conn: return
    
    try:
        with conn.cursor() as cur:
            # Tabela 1: Valores Fixos (por Serviço)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lpu_valores_fixos (
                    id SERIAL PRIMARY KEY,
                    servico TEXT UNIQUE NOT NULL,
                    valor NUMERIC(10, 2) DEFAULT 0.00
                );
            """)
            
            # Tabela 2: Preços de Equipamentos (Instalação)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lpu_equipamentos (
                    id SERIAL PRIMARY KEY,
                    equipamento TEXT UNIQUE NOT NULL,
                    codigo_equipamento TEXT,
                    sistema TEXT,
                    preco NUMERIC(10, 2) DEFAULT 0.00
                );
            """)
            
            # Tabela 3: Preços de Serviços de Equipamentos (D/R)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lpu_servicos_equip (
                    id SERIAL PRIMARY KEY,
                    equipamento TEXT UNIQUE NOT NULL,
                    codigo_equipamento TEXT,
                    sistema TEXT,
                    desativacao NUMERIC(10, 2) DEFAULT 0.00,
                    reinstalacao NUMERIC(10, 2) DEFAULT 0.00
                );
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao criar tabelas LPU: {e}")


# --- 3. IMPORTAÇÃO DA LPU ---

def _normalize_key(key):
    """Função interna para limpar chaves de texto (serviço/equipamento)"""
    if not isinstance(key, str): return ""
    return key.strip().lower()

def importar_lpu(df_fixo: pd.DataFrame, df_servico: pd.DataFrame, df_equip: pd.DataFrame):
    """Limpa as tabelas LPU e insere os novos dados (com cabeçalhos normalizados)."""
    conn = get_valid_conn_fin()
    if not conn: return False, "Falha na conexão"
    
    # Normalizar cabeçalhos
    df_fixo.columns = [str(col).strip().upper() for col in df_fixo.columns]
    df_servico.columns = [str(col).strip().upper() for col in df_servico.columns]
    df_equip.columns = [str(col).strip().upper() for col in df_equip.columns]

    try:
        with conn.cursor() as cur:
            
            # --- 1. Processar Valores Fixos ---
            cur.execute("TRUNCATE lpu_valores_fixos RESTART IDENTITY;")
            
            if 'TIPO DO SERVIÇO' in df_fixo.columns and 'VALOR' in df_fixo.columns:
                vals_fixo = [
                    (_normalize_key(row['TIPO DO SERVIÇO']), pd.to_numeric(row['VALOR'], errors='coerce'))
                    for _, row in df_fixo.iterrows()
                ]
                vals_fixo = [(s, float(v)) for s, v in vals_fixo if s and pd.notna(v)]
                
                query_fixo = "INSERT INTO lpu_valores_fixos (servico, valor) VALUES (%s, %s) ON CONFLICT (servico) DO UPDATE SET valor = EXCLUDED.valor"
                cur.executemany(query_fixo, vals_fixo)
            
            # --- 2. Processar Equipamentos (Preço) ---
            cur.execute("TRUNCATE lpu_equipamentos RESTART IDENTITY;")
            
            if 'EQUIPAMENTO' in df_equip.columns and 'PRECO' in df_equip.columns:
                vals_equip = [
                    (
                        _normalize_key(row['EQUIPAMENTO']),
                        str(row.get('CODIGOEQUIPAMENTO', '')), 
                        str(row.get('SISTEMA', '')),
                        pd.to_numeric(row['PRECO'], errors='coerce') 
                    )
                    for _, row in df_equip.iterrows()
                ]
                vals_equip = [(e, c, s, float(p)) for e, c, s, p in vals_equip if e and pd.notna(p)]
                
                query_equip = "INSERT INTO lpu_equipamentos (equipamento, codigo_equipamento, sistema, preco) VALUES (%s, %s, %s, %s) ON CONFLICT (equipamento) DO UPDATE SET codigo_equipamento = EXCLUDED.codigo_equipamento, sistema = EXCLUDED.sistema, preco = EXCLUDED.preco"
                cur.executemany(query_equip, vals_equip)

            # --- 3. Processar Serviços de Equipamentos (D/R) ---
            cur.execute("TRUNCATE lpu_servicos_equip RESTART IDENTITY;")
            
            if 'EQUIPAMENTO' in df_servico.columns:
                vals_serv = [
                    (
                        _normalize_key(row['EQUIPAMENTO']),
                        str(row.get('CODIGOEQUIPAMENTO', '')),
                        str(row.get('SISTEMA', '')),
                        pd.to_numeric(row.get('DESATIVAÇÃO'), errors='coerce'),
                        pd.to_numeric(row.get('REINSTALAÇÂO'), errors='coerce')
                    )
                    for _, row in df_servico.iterrows()
                ]
                # Converte para float nativo e trata NaNs
                vals_serv_clean = []
                for e, c, s, d, r in vals_serv:
                    if e and (pd.notna(d) or pd.notna(r)):
                        d_val = float(d) if pd.notna(d) else 0.0
                        r_val = float(r) if pd.notna(r) else 0.0
                        vals_serv_clean.append((e, c, s, d_val, r_val))

                query_serv = "INSERT INTO lpu_servicos_equip (equipamento, codigo_equipamento, sistema, desativacao, reinstalacao) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (equipamento) DO UPDATE SET codigo_equipamento = EXCLUDED.codigo_equipamento, sistema = EXCLUDED.sistema, desativacao = EXCLUDED.desativacao, reinstalacao = EXCLUDED.reinstalacao"
                cur.executemany(query_serv, vals_serv_clean)

        conn.commit()
        st.cache_data.clear() 
        return True, "LPU importada com sucesso."
    
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao importar LPU: {e}"
        
# --- 4. FUNÇÕES DE LEITURA LPU (PARA A PÁGINA) ---

@st.cache_data(ttl=3600) 
def carregar_lpu_fixo():
    """Carrega LPU Fixo como um dicionário para consulta rápida."""
    conn = get_valid_conn_fin()
    if not conn: return {}
    try:
        df = pd.read_sql("SELECT servico, valor FROM lpu_valores_fixos", conn)
        return df.set_index(df['servico'].str.lower())['valor'].to_dict()
    except Exception as e:
        st.error(f"Erro ao carregar LPU Fixo: {e}")
        return {}

@st.cache_data(ttl=3600)
def carregar_lpu_servico():
    """Carrega LPU Serviço (D/R) como um dicionário para consulta rápida."""
    conn = get_valid_conn_fin()
    if not conn: return {}
    try:
        df = pd.read_sql("SELECT equipamento, desativacao, reinstalacao FROM lpu_servicos_equip", conn)
        df.set_index(df['equipamento'].str.lower(), inplace=True)
        df['desativacao'] = df['desativacao'].fillna(0.0)
        df['reinstalacao'] = df['reinstalacao'].fillna(0.0)
        return df[['desativacao', 'reinstalacao']].to_dict('index')
    except Exception as e:
        st.error(f"Erro ao carregar LPU Serviço: {e}")
        return {}

@st.cache_data(ttl=3600)
def carregar_lpu_equipamento():
    """Carrega LPU Equipamento (Preço) como um dicionário."""
    conn = get_valid_conn_fin()
    if not conn: return {}
    try:
        df = pd.read_sql("SELECT equipamento, preco FROM lpu_equipamentos", conn)
        df['preco'] = df['preco'].fillna(0.0)
        return df.set_index(df['equipamento'].str.lower())['preco'].to_dict()
    except Exception as e:
        st.error(f"Erro ao carregar LPU Equipamento: {e}")
        return {}

# --- 5. TABELA DE BOOKS (ACUMULATIVO) ---

def criar_tabela_books():
    """Cria a tabela para rastrear os books de faturamento, se não existir."""
    conn = get_valid_conn_fin()
    if not conn: return
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS books_faturamento (
                    id SERIAL PRIMARY KEY,
                    chamado TEXT UNIQUE NOT NULL,
                    servico TEXT,
                    sistema TEXT,
                    protocolo TEXT,
                    data_conclusao DATE,
                    book_pronto TEXT,
                    data_envio DATE
                );
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao criar tabela books_faturamento: {e}")

def importar_planilha_books(df_books: pd.DataFrame):
    """Importa/Atualiza books (Modo Acumulativo - Mantém histórico)."""
    conn = get_valid_conn_fin()
    if not conn: return False, "Falha na conexão"
    
    df_books.columns = [str(col).strip().upper() for col in df_books.columns]
    
    if 'CHAMADO' not in df_books.columns:
        return False, "Erro: Coluna 'CHAMADO' não encontrada."
    if 'PROTOCOLO' not in df_books.columns:
        return False, "Erro: Coluna 'PROTOCOLO' não encontrada."
        
    try:
        with conn.cursor() as cur:
            # SEM TRUNCATE - para não apagar o histórico
            
            vals_books = []
            for _, row in df_books.iterrows():
                
                data_conc = pd.to_datetime(row.get('DATA CONCLUSAO'), errors='coerce')
                data_env = pd.to_datetime(row.get('DATA ENVIO'), errors='coerce')
                
                d_conc = data_conc.date() if pd.notna(data_conc) else None
                d_env = data_env.date() if pd.notna(data_env) else None
                    
                vals_books.append((
                    str(row['CHAMADO']),
                    str(row.get('SERVIÇO', '')),
                    str(row.get('SISTEMA', '')),
                    str(row.get('PROTOCOLO', '')),
                    d_conc,
                    str(row.get('BOOK PRONTO?', '')),
                    d_env
                ))
            
            query = """
                INSERT INTO books_faturamento 
                (chamado, servico, sistema, protocolo, data_conclusao, book_pronto, data_envio) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chamado) DO UPDATE SET
                    servico = EXCLUDED.servico,
                    sistema = EXCLUDED.sistema,
                    protocolo = EXCLUDED.protocolo,
                    data_conclusao = EXCLUDED.data_conclusao,
                    book_pronto = EXCLUDED.book_pronto,
                    data_envio = EXCLUDED.data_envio
            """
            cur.executemany(query, vals_books)
            
        conn.commit()
        st.cache_data.clear()
        return True, f"{len(vals_books)} registros de book processados (Histórico mantido)."
        
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao importar books: {e}"
        
@st.cache_data(ttl=60) 
def carregar_books_db():
    conn = get_valid_conn_fin()
    cols_padrao = ['chamado', 'book_pronto', 'servico', 'sistema', 'data_envio']
    if not conn: return pd.DataFrame(columns=cols_padrao)
    
    try:
        df = pd.read_sql("SELECT * FROM books_faturamento", conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar books: {e}")
        return pd.DataFrame(columns=cols_padrao)
        
# --- 6. TABELA DE LIBERAÇÃO FATURAMENTO (ACUMULATIVO) ---

def criar_tabela_liberacao():
    """Cria a tabela para armazenar o espelho de faturamento do banco."""
    conn = get_valid_conn_fin()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS faturamento_liberado (
                    id SERIAL PRIMARY KEY,
                    chamado TEXT UNIQUE NOT NULL,
                    codigo_ponto TEXT,
                    nome_ponto TEXT,
                    uf_agencia TEXT,
                    cidade_agencia TEXT,
                    nome_sistema TEXT,
                    servico TEXT,
                    tipo_servico TEXT,
                    cod_equipamento TEXT,
                    nome_equipamento TEXT,
                    qtd_liberada NUMERIC(10,2),
                    valor_unitario NUMERIC(10,2),
                    total NUMERIC(10,2),
                    protocolo_atendimento TEXT,
                    nome_projeto TEXT,
                    nome_usuario TEXT
                );
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao criar tabela faturamento_liberado: {e}")

def importar_planilha_liberacao(df: pd.DataFrame):
    """Importa liberação (Modo Acumulativo + Conversão Segura de Tipos)."""
    conn = get_valid_conn_fin()
    if not conn: return False, "Falha na conexão"
    
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    if 'CHAMADO' not in df.columns:
        return False, "Erro: Coluna 'CHAMADO' não encontrada."

    try:
        with conn.cursor() as cur:
            # SEM TRUNCATE
            
            vals = []
            for _, row in df.iterrows():
                
                # Conversão segura de tipos
                def safe_num(col_name):
                    val = row.get(col_name)
                    try:
                        v_float = float(pd.to_numeric(val, errors='coerce'))
                        return v_float if not np.isnan(v_float) else 0.0
                    except:
                        return 0.0
                
                vals.append((
                    str(row.get('CHAMADO', '')),
                    str(row.get('CODIGO_DO_PONTO', '')),
                    str(row.get('NOME_PONTO', '')),
                    str(row.get('UFAGENCIA', '')),
                    str(row.get('CIDADEAGENCIA', '')),
                    str(row.get('NOME_SISTEMA', '')),
                    str(row.get('SERVICO', '')),
                    str(row.get('TIPO_SERVICO', '')),
                    str(row.get('CODIGO_DO_EQUIPAMENTO', '')),
                    str(row.get('NOME_EQUIPAMENTO', '')),
                    safe_num('QUANTIDADE_LIBERADA'),
                    safe_num('VALORUNITARIO'),
                    safe_num('TOTAL'),
                    str(row.get('PROTOCOLOATENDIMENTO', '')),
                    str(row.get('NOME_PROJETO', '')),
                    str(row.get('NOMEUSUARIO', ''))
                ))

            query = """
                INSERT INTO faturamento_liberado 
                (chamado, codigo_ponto, nome_ponto, uf_agencia, cidade_agencia, nome_sistema, servico, tipo_servico, cod_equipamento, nome_equipamento, qtd_liberada, valor_unitario, total, protocolo_atendimento, nome_projeto, nome_usuario)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chamado) DO UPDATE SET
                    qtd_liberada = EXCLUDED.qtd_liberada,
                    valor_unitario = EXCLUDED.valor_unitario,
                    total = EXCLUDED.total,
                    protocolo_atendimento = EXCLUDED.protocolo_atendimento,
                    servico = EXCLUDED.servico
            """
            cur.executemany(query, vals)
        
        conn.commit()
        st.cache_data.clear()
        return True, f"{len(vals)} registros de liberação processados (Histórico mantido)."
        
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao importar liberação: {e}"

@st.cache_data(ttl=60)
def carregar_liberacao_db():
    """Carrega a tabela de liberação para conciliação."""
    conn = get_valid_conn_fin()
    if not conn: return pd.DataFrame()
    try:
        return pd.read_sql("SELECT * FROM faturamento_liberado", conn)
    except Exception as e:
        st.error(f"Erro ao carregar liberação: {e}")
        return pd.DataFrame()
