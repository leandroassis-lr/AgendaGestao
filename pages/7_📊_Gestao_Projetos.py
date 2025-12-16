import streamlit as st
import pandas as pd
import utils_chamados
import time
import io
from datetime import date

st.set_page_config(page_title="Gestão de Projetos", page_icon="🏗️", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
        .stExpander { border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .block-container { padding-top: 2rem; }
        .chamado-btn { text-align: left; width: 100%; margin: 2px 0; }
        div[data-testid="stDialog"] { width: 60vw; }
    </style>
""", unsafe_allow_html=True)

# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- FUNÇÕES AUXILIARES ---
def _to_date_safe(val):
    if pd.isna(val) or val == "": return None
    try: return pd.to_datetime(val).date()
    except: return None

# Função para calcular Status do PROJETO (Pai) baseado nos chamados (Filhos)
def calcular_status_projeto_agrupado(df_grupo):
    # Lógica Provisória (ajustaremos depois conforme sua regra)
    status_lista = df_grupo['Status'].dropna().str.lower().tolist()
    
    if not status_lista or all(s == 'não iniciado' for s in status_lista):
        return "Não Iniciado"
    if all(s in ['finalizado', 'concluído', 'cancelado'] for s in status_lista):
        return "Finalizado"
    if 'em andamento' in status_lista:
        return "Em Andamento"
    
    return "Em Andamento" # Default

# --- POP-UP (DIALOG) DO CHAMADO INDIVIDUAL ---
@st.dialog("Detalhes Operacionais do Chamado", width="large")
def editar_chamado_dialog(row_dict, id_chamado):
    # Prepara dados
    row = pd.Series(row_dict)
    form_key = f"pop_{id_chamado}"
    
    st.markdown(f"### 🎫 {row.get('Nº Chamado')}")
    st.caption(f"Projeto: {row.get('Projeto')} | Agência: {row.get('Nome Agência')}")
    
    with st.form(key=form_key):
        # 1. Status e Datas
        c1, c2, c3 = st.columns(3)
        st_atual = row.get('Status', 'Não Iniciado')
        c1.text_input("Status Atual", value=st_atual, disabled=True)
        
        n_ab = c2.date_input("📅 Abertura", value=_to_date_safe(row.get('Abertura')), format="DD/MM/YYYY")
        n_ag = c3.date_input("🗓️ Agendamento", value=_to_date_safe(row.get('Agendamento')), format="DD/MM/YYYY")

        # 2. Informações Técnicas
        c4, c5, c6 = st.columns(3)
        c4.text_input("Serviço", value=row.get('Serviço', ''), disabled=True) # Serviço costuma vir fixo do projeto
        n_si = c5.text_input("Sistema", value=row.get('Sistema', ''))
        n_fi = c6.date_input("🏁 Finalização", value=_to_date_safe(row.get('Fechamento')), format="DD/MM/YYYY")

        # 3. Observações
        n_ob = st.text_area("📝 Observações / Pendências", value=row.get('Observações e Pendencias', ''), height=100)

        # 4. Links e Protocolos
        st.markdown("---")
        l1, l2 = st.columns([1, 1])
        n_link = row.get('Link Externo', '')
        
        with l1:
            n_link = st.text_input("Link Externo (URL)", value=n_link)
            if n_link:
                st.link_button("🔗 Acessar Link Externo", n_link)
        
        with l2:
            n_pt = st.text_input("Nº Protocolo", value=row.get('Nº Protocolo', ''))
        
        # 5. Descrição / Itens
        st.markdown("---")
        st.markdown("**📦 Descrição / Itens:**")
        desc_texto = str(row.get('Equipamento', '')).replace("|", "\n").replace(" | ", "\n")
        if not desc_texto or desc_texto == 'nan': desc_texto = str(row.get('Descrição', ''))
        st.info(desc_texto if desc_texto else "Sem itens registrados.")

        # Botão Salvar (Individual)
        if st.form_submit_button("💾 Salvar Alterações deste Chamado"):
            updates = {
                "Data Abertura": n_ab, "Data Agendamento": n_ag, "Data Finalização": n_fi,
                "Sistema": n_si, "Observações e Pendencias": n_ob,
                "Link Externo": n_link, "Nº Protocolo": n_pt
            }
            # Se tiver data de finalização, sugere status (regra simples)
            if n_fi and st_atual in ['Não Iniciado', 'Em Andamento']:
                updates['Status'] = 'Concluído'
            
            if utils_chamados.atualizar_chamado_db(id_chamado, updates):
                st.success("Chamado atualizado!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Erro ao salvar.")

# --- CARREGAMENTO E SIDEBAR ---
df = utils_chamados.carregar_chamados_db()

with st.sidebar:
    st.header("Ações")
    # Seus botões de importação e exportação (mantive os mesmos)
    if st.button("➕ Importar Chamados"): pass # (Chame sua função run_importer_dialog aqui se tiver o import)
    
    st.divider()
    st.header("📤 Exportação")
    if st.button("📥 Baixar Base (.xlsx)"):
        df_export = utils_chamados.carregar_chamados_db()
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Base')
            st.download_button("Salvar Excel", data=output.getvalue(), file_name=f"Backup_{date.today()}.xlsx")

    st.header("Filtros")
    # Filtros Globais
    lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    filtro_analista = st.selectbox("Filtrar por Analista", lista_analistas)

if df.empty:
    st.warning("Sem dados.")
    st.stop()

# Aplica Filtros
df_view = df.copy()
if filtro_analista != "Todos": df_view = df_view[df_view['Analista'] == filtro_analista]

# Normaliza colunas para agrupamento
df_view['Agencia_Fmt'] = df_view.apply(lambda x: f"{str(x['Cód. Agência']).split('.')[0]} - {x['Nome Agência']}", axis=1)
df_view['Projeto'] = df_view['Projeto'].fillna("Sem Projeto")

# --- LISTAGEM AGRUPADA (PROJETO x AGÊNCIA) ---
st.title("Gestão Operacional de Projetos")
st.markdown(f"<small>{len(df_view)} chamados encontrados</small>", unsafe_allow_html=True)

# Agrupa
grupos = df_view.groupby(['Agencia_Fmt', 'Projeto'])

for (agencia, projeto), df_grupo in grupos:
    
    # 1. Cabeçalho do Projeto (Dados Macro)
    qtd_chamados = len(df_grupo)
    status_projeto = calcular_status_projeto_agrupado(df_grupo)
    
    # Gera um ID de Projeto Visual (Ex: AG5631-PROJETO-X)
    cod_ag = str(df_grupo.iloc[0]['Cód. Agência']).split('.')[0]
    id_projeto_visual = f"ID: {cod_ag}-{str(projeto)[:3].upper()}"

    # Cores do Status
    cor_st = "grey"
    if status_projeto == "Em Andamento": cor_st = "blue"
    elif status_projeto == "Concluído": cor_st = "green"
    elif status_projeto == "Finalizado": cor_st = "darkgreen"

    label_expander = f"🏢 **{agencia}** | 📁 **{projeto}** | 🏷️ {id_projeto_visual} | {qtd_chamados} Chamados"
    
    with st.expander(label_expander, expanded=False):
        
        # --- CONFIGURAÇÕES GERAIS DO PROJETO (Afeta todos os chamados do grupo) ---
        c_p1, c_p2, c_p3, c_p4 = st.columns([1.5, 1.5, 1.5, 1.5])
        
        # Status do Projeto (Visual ou Manual se quiser forçar)
        c_p1.markdown(f"**Status Projeto:** <span style='color:{cor_st}; font-weight:bold'>{status_projeto}</span>", unsafe_allow_html=True)
        
        # Carrega listas para Selectbox
        try:
            df_tc = utils_chamados.carregar_config_db("tecnicos"); l_tc = sorted(df_tc.iloc[:,0].dropna().tolist()) if not df_tc.empty else []
            df_us = utils_chamados.carregar_usuarios_db(); l_an = sorted(df_us["Nome"].dropna().tolist()) if not df_us.empty else []
        except: l_tc=[]; l_an=[]

        # Valores Atuais (Pega do primeiro chamado do grupo, pois devem ser iguais)
        atual_an = df_grupo.iloc[0]['Analista']
        atual_tc = df_grupo.iloc[0]['Técnico']
        atual_ge = df_grupo.iloc[0]['Gestor']

        # Inputs de Grupo (Se mudar aqui, salva em TODOS os chamados do grupo)
        with st.form(key=f"form_prj_{cod_ag}_{projeto}"):
            k1, k2, k3, k4 = st.columns(4)
            novo_an = k1.selectbox("Analista (Projeto)", [""]+l_an, index=(l_an.index(atual_an)+1) if atual_an in l_an else 0)
            novo_tc = k2.selectbox("Técnico (Projeto)", [""]+l_tc, index=(l_tc.index(atual_tc)+1) if atual_tc in l_tc else 0)
            novo_ge = k3.text_input("Gestor (Projeto)", value=atual_ge if pd.notna(atual_ge) else "")
            
            if k4.form_submit_button("💾 Atualizar Equipe"):
                # Atualiza todos os IDs desse grupo
                ids_grupo = df_grupo['ID'].tolist()
                count = 0
                for i_d in ids_grupo:
                    upd = {'Analista': novo_an, 'Técnico': novo_tc, 'Gestor': novo_ge}
                    utils_chamados.atualizar_chamado_db(i_d, upd)
                    count += 1
                st.toast(f"Equipe atualizada em {count} chamados!")
                time.sleep(1)
                st.rerun()

        st.divider()

        # --- LISTA DE CHAMADOS (LINHAS) ---
        st.markdown("###### 🎫 Chamados Vinculados:")
        
        # Cabeçalho da Lista
        cols = st.columns([1.5, 2, 2, 1.5, 2])
        cols[0].markdown("**ID Chamado**")
        cols[1].markdown("**Serviço**")
        cols[2].markdown("**Sistema**")
        cols[3].markdown("**Status**")
        cols[4].markdown("**Ação**")

        for _, row_chamado in df_grupo.iterrows():
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.5, 2, 2, 1.5, 2])
            
            num_chamado = row_chamado['Nº Chamado']
            cc1.markdown(f"**{num_chamado}**")
            cc2.caption(f"{row_chamado.get('Serviço', '-')}")
            cc3.caption(f"{row_chamado.get('Sistema', '-')}")
            
            st_ch = row_chamado.get('Status', '-')
            cor_badge = "grey"
            if st_ch == "Concluído": cor_badge = "green"
            elif st_ch == "Em Andamento": cor_badge = "blue"
            
            cc4.markdown(f":{cor_badge}[{st_ch}]")
            
            # Botão que abre o Dialog
            if cc5.button("✏️ Detalhes", key=f"btn_{row_chamado['ID']}"):
                editar_chamado_dialog(row_chamado.to_dict(), row_chamado['ID'])
        
        st.markdown("<br>", unsafe_allow_html=True)
