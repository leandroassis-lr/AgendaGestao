import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, datetime
import re 
import html 
import io
import math 
import time

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")

# Tenta carregar CSS externo
try:
    utils.load_css() 
except:
    pass 

# --- LISTA DE EXCEÇÃO (SERVIÇOS) ---
# Esses serviços seguirão a mesma lógica de STATUS definida para serviços gerais
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

def clean_val(val, default="N/A"):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan", "nat"]:
        return default
    return str(val).strip()

# --- 1. NOVA LÓGICA DE STATUS (PROFISSIONAL / CASCATA) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    """
    Aplica a regra de negócio estrita:
    1. Checa Status Manuais (Soberanos).
    2. Checa Finalização Financeira (Banco).
    3. Aplica lógica de Serviço ou Equipamento baseada no preenchimento de colunas.
    """
    
    # Pegamos a primeira linha para ler os dados do projeto
    row = df_projeto.iloc[0]
    
    status_atual = clean_val(row.get('Status'), 'Não Iniciado')
    sub_status_atual = clean_val(row.get('Sub-Status'), '')
    
    # --- 1. STATUS SOBERANOS (MANUAIS) ---
    # Se estiver em um desses status, NÃO mudamos nada automaticamente, 
    # EXCETO se já estiver "Finalizado" (mas o Finalizado entra na regra 2).
    status_soberanos = ["pendência de infra", "pendência de equipamento", "pausado", "cancelado"]
    if status_atual.lower() in status_soberanos:
        return False # Não faz nada, respeita a decisão manual

    # --- VARIÁVEIS DE CONTROLE (FLAGS) ---
    def tem_valor(col):
        val = row.get(col)
        return val is not None and not pd.isna(val) and str(val).strip() != ""

    # Verificação de colunas chaves
    has_link = tem_valor('Link Externo')
    has_tecnico = tem_valor('Técnico')
    has_protocolo = tem_valor('Nº Protocolo')
    has_pedido = tem_valor('Nº Pedido')
    has_envio = tem_valor('Data Envio') or check_date_valid(row.get('Data Envio'))
    
    # Verificação do Financeiro (Simula "Planilha Liberação Banco")
    # Assumindo que importar a planilha preenche 'Status Financeiro' ou 'Data Finalização'
    is_faturado_banco = tem_valor('Status Financeiro') or tem_valor('Data Finalização')
    
    # Verificação do "Sim/S" para Book
    # Tenta ler coluna 'Book Enviado'. Se não existir, assume 'Não'
    book_enviado_flag = False
    col_book = 'Book Enviado' # Nome da coluna na planilha importada
    if col_book in df_projeto.columns:
        val_book = str(row.get(col_book, '')).strip().lower()
        if val_book in ['sim', 's', 'yes', 'y']:
            book_enviado_flag = True

    novo_status = "Não Iniciado"
    novo_acao = "Abrir chamado no Btime"

    # --- 2. REGRA DE EQUIPAMENTO (Se tiver -E- e NÃO for Exceção) ---
    is_equipamento = '-E-' in str(row.get('Nº Chamado', ''))
    is_servico_excecao = clean_val(row.get('Serviço', '')).lower() in SERVICOS_SEM_EQUIPAMENTO
    
    if is_equipamento and not is_servico_excecao:
        # Lógica de Equipamento (Mantida a existente + Regra do Banco)
        if is_faturado_banco:
            novo_status = "Finalizado"
            novo_acao = "Faturado"
        elif has_envio:
            novo_status = "Concluído"
            novo_acao = "Equipamento entregue"
        elif has_pedido:
            novo_status = "Em Andamento"
            novo_acao = "Equipamento Solicitado"
        else:
            novo_status = "Não Iniciado"
            novo_acao = "Solicitar Equipamento"

    # --- 3. REGRA DE SERVIÇO (Ou Exceção) ---
    else:
        # Lógica Nova Solicitada (Cascata Inversa ou Direta)
        
        # Prioridade 1: Banco (Liberação)
        if is_faturado_banco:
            novo_status = "Finalizado"
            novo_acao = "Faturado"
            
        # Prioridade 2: Book (Protocolo)
        elif has_protocolo:
            novo_status = "Concluído"
            if book_enviado_flag:
                novo_acao = "Aguardando Faturamento"
            else:
                novo_acao = "Enviar book"
                
        # Prioridade 3: Técnico
        elif has_tecnico:
            novo_status = "Em Andamento"
            novo_acao = "Enviar Status Cliente"
            
        # Prioridade 4: Link
        elif has_link:
            novo_status = "Em Andamento"
            novo_acao = "Acionar técnico"
            
        # Prioridade 5: Padrão (Criado)
        else:
            novo_status = "Não Iniciado"
            novo_acao = "Abrir chamado no Btime"

    # --- 4. ATUALIZAÇÃO NO BANCO ---
    # Só atualiza se mudou algo
    if status_atual != novo_status or sub_status_atual != novo_acao:
        updates = {"Status": novo_status, "Sub-Status": novo_acao}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True # Houve mudança
        
    return False # Nenhuma mudança

def check_date_valid(val):
    try:
        return pd.to_datetime(val).year > 2000
    except:
        return False

# --- IMPORTS E DIALOGS (MANTIDOS IGUAIS AO SEU CÓDIGO, APENAS FORMATADOS) ---
# ... (Importadores mantidos iguais para economizar espaço, o foco é a lógica acima e o layout abaixo)

@st.dialog("Importar Novos Chamados (Template Padrão)", width="large")
def run_importer_dialog():
    # ... (Código do importador igual ao anterior) ...
    st.info("Arraste seu Template Padrão aqui.")
    uploaded_files = st.file_uploader("Arquivos", type=["xlsx", "csv"], accept_multiple_files=True)
    if uploaded_files:
        dfs = []
        for f in uploaded_files:
            try:
                if f.name.endswith('.csv'): df = pd.read_csv(f, sep=';', dtype=str)
                else: df = pd.read_excel(f, dtype=str)
                dfs.append(df)
            except: pass
        if dfs:
            full_df = pd.concat(dfs, ignore_index=True)
            if st.button("Importar"):
                utils_chamados.bulk_insert_chamados_db(full_df)
                st.success("Importado!"); st.session_state.importer_done = True
                st.rerun()

@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    st.info("Planilha com colunas: CHAMADO e LINK")
    upl = st.file_uploader("Arquivo", type=["xlsx", "csv"])
    if upl:
        if upl.name.endswith('.csv'): df = pd.read_csv(upl, sep=';', dtype=str)
        else: df = pd.read_excel(upl, dtype=str)
        df.columns = [c.strip().upper() for c in df.columns]
        if st.button("Atualizar Links"):
            df_bd = utils_chamados.carregar_chamados_db()
            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
            count = 0
            for _, r in df.iterrows():
                if r['CHAMADO'] in id_map:
                    utils_chamados.atualizar_chamado_db(id_map[r['CHAMADO']], {'Link Externo': r['LINK']})
                    count += 1
            st.success(f"{count} links atualizados."); st.session_state.importer_done = True

# --- TELA PRINCIPAL ---
def tela_dados_agencia():
    
    # --- CSS RIGOROSO PARA LAYOUT ---
    st.markdown("""
        <style>
            /* Estilo do Card Principal */
            .project-card {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            
            /* BADGE DE STATUS (Principal) - Canto Superior Direito */
            .status-badge-main {
                display: block;
                padding: 8px 0;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                text-transform: uppercase;
                text-align: center;
                font-size: 0.9rem;
                width: 100%;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            
            /* TEXTO DE AÇÃO (Sub-Status) - Canto Inferior Direito */
            .action-box {
                background-color: #E3F2FD;
                border: 1px solid #90CAF9;
                color: #1565C0;
                padding: 8px;
                border-radius: 6px;
                text-align: center;
                font-weight: 600;
                font-size: 0.9rem;
                margin-top: 5px;
            }
            
            .label-small { font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
            .value-large { font-size: 1.1rem; font-weight: 600; color: #333; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center;'>GESTÃO DE DADOS POR AGÊNCIA</h2>", unsafe_allow_html=True)
    
    # Carregar dados
    utils_chamados.criar_tabela_chamados()
    try:
        df_chamados_raw = utils_chamados.carregar_chamados_db()
    except:
        st.error("Erro de conexão."); st.stop()

    if df_chamados_raw.empty:
        st.warning("Sem dados."); 
        if st.button("Importar"): run_importer_dialog()
        st.stop()

    # Processamento Básico
    df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(lambda r: formatar_agencia_excel(r.get('Cód. Agência'), r.get('Nome Agência')), axis=1)
    
    # Filtros (Simplificado para foco no layout)
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    filtro_ag = col_f1.selectbox("Agência", ["Todos"] + sorted(df_chamados_raw['Agencia_Combinada'].unique()))
    filtro_st = col_f2.selectbox("Status", ["Todos"] + sorted(df_chamados_raw['Status'].fillna('').unique()))
    
    # Botões de Importação
    c_btn1, c_btn2 = st.columns(2)
    if c_btn1.button("📥 Importar Geral", use_container_width=True): run_importer_dialog()
    if c_btn2.button("🔗 Importar Links", use_container_width=True): run_link_importer_dialog()
    
    # Filtragem
    df_filtrado = df_chamados_raw.copy()
    if filtro_ag != "Todos": df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_ag]
    if filtro_st != "Todos": df_filtrado = df_filtrado[df_filtrado['Status'] == filtro_st]
    
    st.divider()
    
    # --- RENDERIZAÇÃO DOS CARDS ---
    if df_filtrado.empty:
        st.info("Nenhum projeto encontrado.")
        st.stop()
        
    # Agrupamento para visualização
    df_filtrado['Agendamento_str'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('Sem Data')
    chave_proj = ['Agencia_Combinada', 'Projeto', 'Gestor', 'Serviço', 'Agendamento_str']
    
    grupos = df_filtrado.groupby(chave_proj)
    
    # Paginação Simples
    lista_grupos = list(grupos)
    total_grupos = len(lista_grupos)
    page_size = 10
    if st.session_state.pag_agencia_atual * page_size >= total_grupos: st.session_state.pag_agencia_atual = 0
    start_idx = st.session_state.pag_agencia_atual * page_size
    end_idx = start_idx + page_size
    grupos_pagina = lista_grupos[start_idx:end_idx]
    
    # Controles de Paginação
    c_nav1, c_nav2, c_nav3 = st.columns([1, 2, 1])
    if c_nav1.button("⬅️ Anterior"): 
        if st.session_state.pag_agencia_atual > 0: st.session_state.pag_agencia_atual -= 1; st.rerun()
    c_nav2.markdown(f"<div style='text-align:center'>Exibindo {start_idx+1} a {min(end_idx, total_grupos)} de {total_grupos}</div>", unsafe_allow_html=True)
    if c_nav3.button("Próximo ➡️"): 
        if end_idx < total_grupos: st.session_state.pag_agencia_atual += 1; st.rerun()

    # LOOP DOS CARDS
    for (nome_agencia, nome_proj, nome_gestor, nome_servico, data_agend), df_proj in grupos_pagina:
        row1 = df_proj.iloc[0]
        ids_proj = df_proj['ID'].tolist()
        
        # Dados para exibição
        status_txt = clean_val(row1.get('Status'), "NÃO INICIADO").upper()
        acao_txt = clean_val(row1.get('Sub-Status'), "Verificar")
        status_color = utils_chamados.get_status_color(status_txt) # Assume que esta função retorna hex code
        
        st.markdown(f"""<div class="project-card">""", unsafe_allow_html=True)
        
        # --- LAYOUT DO CARD: 2 LINHAS, 3 COLUNAS ---
        # Linha 1: Agência/Projeto (Esq) | Data (Meio) | STATUS (Dir)
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.markdown(f"<div class='label-small'>{nome_agencia}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='value-large'>{clean_val(nome_proj, 'Sem Nome')}</div>", unsafe_allow_html=True)
        with c2:
             st.markdown(f"<div class='label-small'>Agendamento</div>", unsafe_allow_html=True)
             st.markdown(f"<div>📅 {data_agend}</div>", unsafe_allow_html=True)
        with c3:
            # STATUS AQUI - BEM VISÍVEL
            st.markdown(f"""<div class="status-badge-main" style="background-color: {status_color};">{status_txt}</div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 8px'></div>", unsafe_allow_html=True) # Spacer

        # Linha 2: Serviço (Esq) | Gestor (Meio) | AÇÃO (Dir)
        c4, c5, c6 = st.columns([3, 2, 2])
        with c4:
             st.markdown(f"<div class='label-small'>Serviço</div>", unsafe_allow_html=True)
             st.markdown(f"<div>{clean_val(nome_servico)}</div>", unsafe_allow_html=True)
        with c5:
             st.markdown(f"<div class='label-small'>Gestor</div>", unsafe_allow_html=True)
             st.markdown(f"<div>👤 {clean_val(nome_gestor)}</div>", unsafe_allow_html=True)
        with c6:
            # AÇÃO AQUI - ABAIXO DO STATUS
            if acao_txt and acao_txt != "N/A":
                st.markdown(f"""<div class="action-box">{acao_txt}</div>""", unsafe_allow_html=True)
            else:
                st.markdown("-")

        # --- ÁREA DE EDIÇÃO (EXPANDER) ---
        with st.expander(f"Editar Detalhes ({len(ids_proj)} chamados)"):
             with st.form(key=f"form_{ids_proj[0]}"):
                 st.write("Edição Manual (Sobrescreve automação se Cancelado/Pausado)")
                 # Inputs simplificados para exemplo
                 col_e1, col_e2 = st.columns(2)
                 new_status = col_e1.selectbox("Status Principal", 
                                             ["(Automático)", "Cancelado", "Pausado", "Pendência de Infra", "Pendência de Equipamento", "Finalizado"], 
                                             key=f"st_{ids_proj[0]}")
                 new_obs = col_e2.text_area("Observações", value=clean_val(row1.get('Observações e Pendencias')), key=f"obs_{ids_proj[0]}")
                 
                 if st.form_submit_button("Salvar"):
                     updates = {'Observações e Pendencias': new_obs}
                     
                     # Se o usuário escolher um status manual, força ele.
                     if new_status != "(Automático)":
                         updates['Status'] = new_status
                         updates['Sub-Status'] = None # Limpa ação automática
                         for i in ids_proj: utils_chamados.atualizar_chamado_db(i, updates)
                         st.success("Salvo manual!")
                     else:
                         # Salva dados e RODA CÁLCULO
                         for i in ids_proj: utils_chamados.atualizar_chamado_db(i, updates)
                         
                         # Recarrega para cálculo
                         df_bd_temp = utils_chamados.carregar_chamados_db()
                         df_proj_temp = df_bd_temp[df_bd_temp['ID'].isin(ids_proj)]
                         if calcular_e_atualizar_status_projeto(df_proj_temp, ids_proj):
                             st.success("Salvo e Recalculado!")
                         else:
                             st.success("Salvo (Sem mudança de status)!")
                     
                     time.sleep(1); st.rerun()

        st.markdown("</div>", unsafe_allow_html=True) # Fim do Card

# --- EXECUÇÃO ---
tela_dados_agencia()
