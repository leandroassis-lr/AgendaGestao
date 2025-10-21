import streamlit as st
import pandas as pd
import utils

st.set_page_config(page_title="Importar Projetos - GESTÃO", page_icon="📦", layout="wide")
utils.load_css()

def tela_importacao():
    st.markdown("<div class='section-title-center'>IMPORTAR PROJETOS EM LOTE</div>", unsafe_allow_html=True)
    st.info("""
        Esta ferramenta permite cadastrar múltiplos projetos de uma vez a partir de uma planilha Excel.
        Todos os projetos importados serão adicionados à tela de **Backlog** (não agendados).
    """)
    st.divider()

    # --- Passo 1: Baixar o Modelo ---
    st.subheader("Passo 1: Baixe a planilha modelo")
    st.markdown("Preencha a planilha com os dados dos seus projetos. Apenas a coluna 'Projeto' é obrigatória.")
    
    template_bytes = utils.generate_excel_template_bytes()
    st.download_button(
        label="📥 Baixar Modelo Excel",
        data=template_bytes,
        file_name="modelo_importacao_projetos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.divider()

    # --- Passo 2: Fazer o Upload ---
    st.subheader("Passo 2: Envie a planilha preenchida")
    uploaded_file = st.file_uploader("Selecione o arquivo Excel", type=["xlsx", "xls"])

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("Arquivo carregado com sucesso! Verifique a pré-visualização abaixo.")
            
            # Remove linhas onde a coluna 'Projeto' está vazia
            df.dropna(subset=['Projeto'], inplace=True)
            
            st.dataframe(df, use_container_width=True)

            if st.button("▶️ Iniciar Importação", type="primary"):
                with st.spinner("Importando projetos... Por favor, aguarde."):
                    usuario_logado = st.session_state.get('usuario', 'N/A')
                    sucesso, num_importados = utils.bulk_insert_projetos_db(df, usuario_logado)
                
                if sucesso:
                    st.success(f"🎉 {num_importados} projetos importados com sucesso para o Backlog!")
                    st.balloons()
                else:
                    st.error("A importação falhou. Verifique os erros acima e o formato da sua planilha.")

        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.warning("Verifique se o arquivo é um Excel válido e se não está corrompido.")

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

tela_importacao()
