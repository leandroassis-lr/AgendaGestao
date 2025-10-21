import streamlit as st
import pandas as pd
from datetime import date
import utils

st.set_page_config(page_title="Backlog - GESTÃO", page_icon="📥", layout="wide")
utils.load_css()

def tela_backlog():
    st.markdown("<div class='section-title-center'>BACKLOG DE PROJETOS</div>", unsafe_allow_html=True)
    st.info("Aqui estão os projetos que ainda não possuem uma data de agendamento definida. Defina uma data e clique em 'Agendar' para movê-lo para a agenda principal.")
    
    df_backlog = utils.carregar_projetos_sem_agendamento_db()

    if df_backlog.empty:
        st.success("🎉 Ótimo trabalho! Não há projetos no backlog.")
        return

    for _, row in df_backlog.iterrows():
        project_id = row['ID']
        
        st.markdown("---")
        col_info, col_form = st.columns([3, 2])

        with col_info:
            st.markdown(f"**Projeto:** {row.get('Projeto', 'N/A')}")
            st.markdown(f"**Analista:** {row.get('Analista', 'N/A')}")
            st.markdown(f"**Agência:** {row.get('Agência', 'N/A')}")
            st.caption(f"ID: {project_id}")

        with col_form:
            with st.form(f"form_agendar_{project_id}"):
                nova_data = st.date_input(
                    "Nova Data de Agendamento", 
                    value=date.today(), 
                    key=f"data_{project_id}",
                    min_value=date.today(),
                    format="DD/MM/YYYY"
                )
                if st.form_submit_button("📅 Agendar Projeto", use_container_width=True):
                    updates = {"Agendamento": nova_data}
                    if utils.atualizar_projeto_db(project_id, updates):
                        st.success(f"Projeto ID {project_id} agendado para {nova_data.strftime('%d/%m/%Y')}!")
                        st.rerun()
                    else:
                        st.error("Ocorreu um erro ao agendar o projeto.")

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

tela_backlog()
