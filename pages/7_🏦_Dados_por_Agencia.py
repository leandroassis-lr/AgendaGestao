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

try:
    utils.load_css() 
except:
    pass 

# --- LISTA DE EXCEÇÃO (SERVIÇOS) ---
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
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan", "nat", ""]:
        return default
    return str(val).strip()

# --- LÓGICA CASCATA DE STATUS (CORRIGIDA) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    row = df_projeto.iloc[0]
    
    # 1. Normalização
    status_atual = clean_val(row.get('Status'), 'Não Iniciado').strip()
    sub_status_atual = clean_val(row.get('Sub-Status'), '').strip()
    
    # 2. Status Manuais (Soberanos)
    # Se o status for um desses, NADA muda automaticamente.
    status_manuais = ["pendência de infra", "pendência de equipamento", "pausado", "cancelado"]
    if status_atual.lower() in status_manuais:
        # Apenas garante que o sub-status não fique com lixo antigo se não quiser
        return False 

    # 3. Variáveis de Verificação
    def has(col): 
        return pd.notna(row.get(col)) and str(row.get(col)).strip() != ""

    has_link = has('Link Externo')
    has_tecnico = has('Técnico')
    has_protocolo = has('Nº Protocolo')
    has_pedido = has('Nº Pedido')
    has_envio = has('Data Envio')
    
    # Simulando "Planilha Liberação Banco" através do Status Financeiro preenchido
    is_banco_ok = has('Status Financeiro') 
    
    # Verificação do "Sim/S" para Book
    book_ok = False
    col_book = 'Book Enviado' # Assume que sua planilha tem essa coluna ou similar
    if col_book in df_projeto.columns:
        val_book = str(row.get(col_book, '')).strip().lower()
        if val_book in ['sim', 's', 'yes']: book_ok = True

    # 4. Definição dos Novos Status (CASCATA)
    novo_status = "Não Iniciado"
    novo_acao = "Abrir chamado no Btime"

    # Regra para Equipamentos (Se tiver -E- e não for exceção)
    is_equip = '-E-' in str(row.get('Nº Chamado', ''))
    is_serv_exc = clean_val(row.get('Serviço', '')).lower() in SERVICOS_SEM_EQUIPAMENTO
    
    if is_equip and not is_serv_exc:
        # Mantendo a lógica existente de equipamento + Banco
        if is_banco_ok:
            novo_status = "Finalizado"; novo_acao = "Faturado"
        elif has_envio:
            novo_status = "Concluído"; novo_acao = "Equipamento entregue"
        elif has_pedido:
            novo_status = "Em Andamento"; novo_acao = "Equipamento Solicitado"
        else:
            novo_status = "Não Iniciado"; novo_acao = "Solicitar Equipamento"
    else:
        # Lógica Geral / Serviços (Prioridades Inversas)
        
        # 1. Finalizado (Banco)
        if is_banco_ok:
            novo_status = "Finalizado"
            novo_acao = "Faturado"
        
        # 2. Concluído (Protocolo/Book)
        elif has_protocolo:
            novo_status = "Concluído"
            if book_ok:
                novo_acao = "Aguardando Faturamento"
            else:
                novo_acao = "Enviar book"
        
        # 3. Em Andamento (Técnico)
        elif has_tecnico:
            novo_status = "Em Andamento"
            novo_acao = "Enviar Status Cliente"
            
        # 4. Em Andamento (Link)
        elif has_link:
            novo_status = "Em Andamento"
            novo_acao = "Acionar técnico"
            
        # 5. Default
        else:
            novo_status = "Não Iniciado"
            novo_acao = "Abrir chamado no Btime"

    # 5. Aplicação
    if status_atual != novo_status or sub_status_atual != novo_acao:
        updates = {"Status": novo_status, "Sub-Status": novo_acao}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

# --- 1. DIALOGS (Mantidos) ---
@st.dialog("Importar Novos Chamados (Template Padrão)", width="large")
def run_importer_dialog():
    st.info("Arraste seu Template Padrão (.xlsx ou .csv). Colunas: CHAMADO e N° AGENCIA.")
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
            full = pd.concat(dfs, ignore_index=True)
            if st.button("Iniciar Importação"):
                utils_chamados.bulk_insert_chamados_db(full)
                st.success("Importado!"); st.session_state.importer_done = True
                st.rerun()

@st.dialog("🔗 Importar Links em Massa", width="medium")
def run_link_importer_dialog():
    st.info("Planilha com: CHAMADO e LINK.")
    upl = st.file_uploader("Arquivo", type=["xlsx", "csv"])
    if upl:
        if upl.name.endswith('.csv'): df = pd.read_csv(upl, sep=';', dtype=str)
        else: df = pd.read_excel(upl, dtype=str)
        df.columns = [c.strip().upper() for c in df.columns]
        if st.button("Atualizar Links"):
            df_bd = utils_chamados.carregar_chamados_db()
            id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
            c = 0
            for _, r in df.iterrows():
                if r['CHAMADO'] in id_map:
                    utils_chamados.atualizar_chamado_db(id_map[r['CHAMADO']], {'Link Externo': r['LINK']})
                    c+=1
            st.success(f"{c} links atualizados."); st.session_state.importer_done = True

@st.dialog("⬇️ Exportar", width="small")
def run_exporter_dialog(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    st.download_button("Baixar Excel", data=buffer.getvalue(), file_name="dados.xlsx")

# --- TELA PRINCIPAL (VISUAL RESTAURADO) ---
def tela_dados_agencia():
    
    # CSS original ajustado para correção de posicionamento
    st.markdown("""
        <style>
            .card-status-badge { 
                background-color: #B0BEC5; color: white; padding: 5px 10px; 
                border-radius: 15px; font-weight: bold; font-size: 0.8rem; 
                display: inline-block; width: 100%; text-align: center; 
            }
            .card-action-text { 
                text-align: center; font-size: 0.85em; font-weight: 600; 
                color: #1565C0; background-color: #E3F2FD; 
                padding: 4px; border-radius: 5px; border: 1px solid #BBDEFB;
            } 
            .project-card {
                border: 1px solid #e0e0e0; border-radius: 8px; 
                padding: 10px; margin-bottom: 10px; background-color: white;
            }
            .section-title-center { text-align: center; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    
    utils_chamados.criar_tabela_chamados()
    try:
        df_raw = utils_chamados.carregar_chamados_db()
    except:
        st.stop()

    if df_raw.empty:
        if st.button("📥 Importar"): run_importer_dialog()
        st.stop()

    if 'Cód. Agência' in df_raw.columns:
        df_raw['Agencia_Combinada'] = df_raw.apply(lambda r: formatar_agencia_excel(r['Cód. Agência'], r['Nome Agência']), axis=1)

    # Filtros
    agencia_list = ["Todos"] + sorted(df_raw['Agencia_Combinada'].unique())
    
    c1, c2, c3 = st.columns([6, 2, 1])
    with c2: 
        if st.button("📥 Importar", use_container_width=True): run_importer_dialog()
        if st.button("🔗 Links", use_container_width=True): run_link_importer_dialog()
    with c3:
        if st.button("⬇️ Exportar"): st.session_state.show_export_popup = True
    
    if st.session_state.get("show_export_popup"): run_exporter_dialog(df_raw)

    with st.expander("🔎 Filtros"):
        filtro_agencia = st.selectbox("Agência", agencia_list, on_change=lambda: st.session_state.update(pag_agencia_atual=0))
    
    df_filtrado = df_raw.copy()
    if filtro_agencia != "Todos": df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    
    # KPI
    st.markdown("### 📊 Resumo")
    c1, c2 = st.columns(2)
    c1.metric("Chamados", len(df_filtrado))
    
    # --- NIVEL 1: AGÊNCIAS (Paginado) ---
    df_filtrado['Agendamento_str'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('Sem Data')
    chave_projeto = ['Projeto', 'Gestor', 'Serviço', 'Agendamento_str']
    
    agencias_unicas = sorted(df_filtrado['Agencia_Combinada'].unique())
    total_ag = len(agencias_unicas)
    ITENS_PAG = 10
    if st.session_state.pag_agencia_atual * ITENS_PAG >= total_ag: st.session_state.pag_agencia_atual = 0
    
    inicio = st.session_state.pag_agencia_atual * ITENS_PAG
    fim = inicio + ITENS_PAG
    agencias_pag = agencias_unicas[inicio:fim]

    # Navegação
    col_n1, col_n2, col_n3 = st.columns([1, 2, 1])
    if col_n1.button("⬅️ Ant"): st.session_state.pag_agencia_atual -= 1; st.rerun()
    col_n2.markdown(f"<div style='text-align:center'>Pág {st.session_state.pag_agencia_atual+1}</div>", unsafe_allow_html=True)
    if col_n3.button("Prox ➡️"): st.session_state.pag_agencia_atual += 1; st.rerun()

    for nome_agencia in agencias_pag:
        df_ag = df_filtrado[df_filtrado['Agencia_Combinada'] == nome_agencia]
        
        # Card Nível 1
        st.markdown('<div class="project-card" style="background-color: #f8f9fa;">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([4, 2, 2])
        c1.markdown(f"#### {nome_agencia}")
        c3.markdown(f"**{len(df_ag)} Chamados**")
        
        # --- NIVEL 2: PROJETOS ---
        with st.expander("Ver Projetos"):
            grupos_proj = df_ag.groupby(chave_projeto)
            for (nm_proj, nm_gestor, nm_servico, dt_agend), df_proj in grupos_proj:
                row1 = df_proj.iloc[0]
                status_txt = clean_val(row1.get('Status'), "NÃO INICIADO")
                acao_txt = clean_val(row1.get('Sub-Status'), "")
                cor_status = utils_chamados.get_status_color(status_txt)
                
                st.markdown('<div class="project-card">', unsafe_allow_html=True)
                
                # LINHA 1 DO CARD PROJETO
                l1c1, l1c2, l1c3 = st.columns([3, 2, 2])
                l1c1.markdown(f"**{clean_val(nm_proj).upper()}**")
                l1c2.markdown(f"📅 {dt_agend}")
                # STATUS NA DIREITA (TOPO)
                l1c3.markdown(f"""<div class="card-status-badge" style="background-color: {cor_status};">{status_txt.upper()}</div>""", unsafe_allow_html=True)
                
                # LINHA 2 DO CARD PROJETO
                l2c1, l2c2, l2c3 = st.columns([3, 2, 2])
                l2c1.markdown(f"Serviço: {clean_val(nm_servico)}")
                l2c2.markdown(f"Gestor: {clean_val(nm_gestor)}")
                # AÇÃO NA DIREITA (BAIXO) - CORREÇÃO SOLICITADA
                if acao_txt:
                    l2c3.markdown(f"""<div class="card-action-text">{acao_txt}</div>""", unsafe_allow_html=True)
                else:
                    l2c3.markdown("-")

                # --- NIVEL 3: FORMULÁRIO E CHAMADOS ---
                with st.expander(f"Editar {len(df_proj)} Chamados (ID: {row1['ID']})"):
                    ids_proj = df_proj['ID'].tolist()
                    fk = f"f_lote_{row1['ID']}"
                    with st.form(fk):
                        st.write("Edição em Lote")
                        c_a, c_b = st.columns(2)
                        
                        # Lógica para o dropdown não resetar se for Manual
                        status_opts = ["(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
                        st_atual_norm = status_txt.title() if status_txt.lower() in [s.lower() for s in status_opts] else "(Status Automático)"
                        try: idx_st = [s.lower() for s in status_opts].index(st_atual_norm.lower())
                        except: idx_st = 0
                        
                        novo_st = c_a.selectbox("Status", status_opts, index=idx_st)
                        nova_obs = c_b.text_area("Obs", value=clean_val(row1.get('Observações e Pendencias')))
                        
                        if st.form_submit_button("Salvar Projeto"):
                            upd = {'Observações e Pendencias': nova_obs}
                            
                            recalc = False
                            if novo_st != "(Status Automático)":
                                upd['Status'] = novo_st
                                upd['Sub-Status'] = None # Limpa ação se for manual
                                recalc = False
                                if novo_st == "Finalizado":
                                     # Se for finalizado manual, verificar data
                                     pass 
                            else:
                                recalc = True
                            
                            for i in ids_proj: utils_chamados.atualizar_chamado_db(i, upd)
                            
                            if recalc:
                                # Recarrega e calcula
                                df_bd = utils_chamados.carregar_chamados_db()
                                df_p = df_bd[df_bd['ID'].isin(ids_proj)]
                                calcular_e_atualizar_status_projeto(df_p, ids_proj)
                            
                            st.success("Salvo!"); time.sleep(1); st.rerun()

                    # LISTA DE CHAMADOS INDIVIDUAIS
                    st.divider()
                    for _, r_ch in df_proj.iterrows():
                        with st.expander(f"Chamado: {r_ch['Nº Chamado']}"):
                            with st.form(f"f_ind_{r_ch['ID']}"):
                                lk = st.text_input("Link", value=clean_val(r_ch.get('Link Externo')))
                                if st.form_submit_button("Salvar Chamado"):
                                    if utils_chamados.atualizar_chamado_db(r_ch['ID'], {'Link Externo': lk}):
                                        # Tenta recalcular automação ao salvar link
                                        df_bd = utils_chamados.carregar_chamados_db()
                                        df_p = df_bd[df_bd['ID'].isin(ids_proj)]
                                        calcular_e_atualizar_status_projeto(df_p, ids_proj)
                                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True) # Fim Card Projeto
        
        st.markdown('</div>', unsafe_allow_html=True) # Fim Card Agencia

tela_dados_agencia()
