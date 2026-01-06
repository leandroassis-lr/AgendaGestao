import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, timedelta
import time

st.set_page_config(page_title="Detalhes - GESTÃO", page_icon="🔧", layout="wide")
utils.load_css()

# --- DIALOG DE EDIÇÃO (Necessário aqui também) ---
@st.dialog("📝 Editar Chamado", width="large")
def open_chamado_dialog(row_dict):
    st.markdown(f"### Editando Chamado: {row_dict.get('Nº Chamado')}")
    
    with st.form("form_edit_chamado"):
        c1, c2 = st.columns(2)
        with c1:
            novo_status = st.selectbox("Status", ["AGENDADO", "EM ANDAMENTO", "CONCLUÍDO", "PENDÊNCIA", "CANCELADO"], index=0)
            novo_substatus = st.text_input("Sub-Status (Ação)", value=str(row_dict.get('Sub-Status','')))
            novo_analista = st.text_input("Analista", value=str(row_dict.get('Analista','')))
            novo_tecnico = st.text_input("Técnico", value=str(row_dict.get('Técnico','')))
        with c2:
            val_ag = row_dict.get('Agendamento')
            d_ag = pd.to_datetime(val_ag).date() if pd.notna(val_ag) else None
            novo_agendamento = st.date_input("Agendamento", value=d_ag)
            
            val_fech = row_dict.get('Fechamento')
            d_fech = pd.to_datetime(val_fech).date() if pd.notna(val_fech) else None
            nova_finalizacao = st.date_input("Fechamento", value=d_fech)
            
            nova_obs = st.text_area("Observação", value=str(row_dict.get('Observação','')))

        if st.form_submit_button("💾 Salvar Alterações"):
            dados = {
                'Status': novo_status,
                'Sub-Status': novo_substatus,
                'Analista': novo_analista,
                'Técnico': novo_tecnico,
                'Agendamento': novo_agendamento,
                'Fechamento': nova_finalizacao,
                'Observação': nova_obs
            }
            utils_chamados.atualizar_chamado_db(row_dict['ID'], dados)
            st.success("Salvo!")
            time.sleep(1)
            st.rerun()

def main():
    st.title("🔧 Detalhes do Projeto")
    
    # Botão de Voltar
    if st.button("⬅️ Voltar para Visão Geral"):
        st.switch_page("app.py") # Nome do seu arquivo principal

    df = utils_chamados.carregar_chamados_db()
    if df.empty: st.warning("Sem dados."); return

    # --- FILTROS ---
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    
    # Filtro Data
    c_tit, c_date = st.columns([4, 1.5])
    with c_date:
        df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce')
        d_min = df['Agendamento'].min() if pd.notna(df['Agendamento'].min()) else date.today()
        d_max = df['Agendamento'].max() if pd.notna(df['Agendamento'].max()) else date.today()
        filtro_data = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY")

    # Aplica Data
    df_opcoes = df.copy()
    if len(filtro_data) == 2:
        df_opcoes = df_opcoes[(df_opcoes['Agendamento'].dt.date >= filtro_data[0]) & (df_opcoes['Agendamento'].dt.date <= filtro_data[1])]

    # Recebe Projeto do Cockpit
    padrao = []
    if "sel_projeto" in st.session_state:
        if st.session_state["sel_projeto"] in df_opcoes['Projeto'].unique():
            padrao = [st.session_state["sel_projeto"]]
        del st.session_state["sel_projeto"]

    # Selects
    op_proj = sorted(df_opcoes['Projeto'].dropna().unique().tolist())
    op_ag = sorted(df_opcoes['Nome Agência'].dropna().unique().tolist())
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: busca = st.text_input("Busca", placeholder="Chamado, ID...")
    with c2: f_ag = st.multiselect("Agência", op_ag)
    with c3: f_proj = st.multiselect("Projeto", op_proj, default=padrao)
    with c4: f_act = st.multiselect("Ação", sorted(df_opcoes['Sub-Status'].dropna().astype(str).unique().tolist()))
    st.markdown('</div>', unsafe_allow_html=True)

    # Filtra Final
    df_view = df_opcoes.copy()
    if busca: df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)]
    if f_ag: df_view = df_view[df_view['Nome Agência'].isin(f_ag)]
    if f_proj: df_view = df_view[df_view['Projeto'].isin(f_proj)]
    if f_act: df_view = df_view[df_view['Sub-Status'].isin(f_act)]

    st.markdown(f"**Resultados:** {len(df_view)}")

    # Tabela
    colunas_visiveis = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Sub-Status', 'Agendamento', 'Analista', 'Técnico']
    colunas_finais = [c for c in colunas_visiveis if c in df_view.columns]
    
    st.dataframe(df_view[colunas_finais], use_container_width=True, hide_index=True)
    
    # Editor (Selecionar para Editar)
    st.divider()
    st.subheader("✏️ Edição Rápida")
    chamados_disp = df_view['Nº Chamado'].unique().tolist()
    sel_chamado = st.selectbox("Selecione um chamado para editar:", [""] + chamados_disp)
    
    if sel_chamado:
        row = df_view[df_view['Nº Chamado'] == sel_chamado].iloc[0].to_dict()
        if st.button("Abrir Editor"):
            open_chamado_dialog(row)

if __name__ == "__main__":
    main()
