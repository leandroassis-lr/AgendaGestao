import streamlit as st
import pandas as pd
import utils # Importa seu arquivo utils
from datetime import date, timedelta # Importações padrão

st.set_page_config(page_title="Importar Projetos - GESTÃO", page_icon="📦", layout="wide")
try:
    utils.load_css() # Tenta carregar o CSS
except:
    pass # Ignora se falhar (ex: app.py não carregou)

def tela_importacao():
    st.markdown("<div class='section-title-center'>IMPORTAR PROJETOS EM LOTE</div>", unsafe_allow_html=True)
    
    # --- 1. TEXTO ATUALIZADO ---
    st.info("""
        Esta ferramenta permite cadastrar múltiplos projetos de uma vez a partir de uma planilha Excel.
        - Preencha a coluna **'Agendamento'** (formato **AAAA-MM-DD**) para agendar o projeto.
        - Deixe o **'Agendamento'** em branco para enviar o projeto ao **Backlog**.
    """)
    st.divider()

    # --- Passo 1: Baixar o Modelo ---
    st.subheader("Passo 1: Baixe a planilha modelo")
    # --- 2. TEXTO ATUALIZADO ---
    st.markdown("Preencha a planilha com os dados. 'Projeto' e 'Agência' são obrigatórios.")
    
    # Esta função (utils.generate_excel_template_bytes) PRECISA estar atualizada no seu utils.py
    try:
        template_bytes = utils.generate_excel_template_bytes()
        st.download_button(
            label="📥 Baixar Modelo Excel",
            data=template_bytes,
            file_name="modelo_importacao_projetos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Erro ao gerar modelo: {e}")
        st.error("Verifique se a função 'generate_excel_template_bytes' está correta no seu utils.py.")
    
    st.divider()

    # --- Passo 2: Fazer o Upload ---
    st.subheader("Passo 2: Envie a planilha preenchida")
    uploaded_file = st.file_uploader("Selecione o arquivo Excel", type=["xlsx", "xls"])

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("Arquivo carregado com sucesso! Verifique a pré-visualização abaixo.")
            
            # --- 3. VALIDAÇÃO ATUALIZADA ---
            # Remove linhas onde 'Projeto' ou 'Agência' estão vazios
            original_rows = len(df)
            df.dropna(subset=['Projeto', 'Agência'], inplace=True)
            dropped_rows = original_rows - len(df)
            if dropped_rows > 0:
                st.warning(f"{dropped_rows} linhas foram ignoradas por não conterem 'Projeto' ou 'Agência'.")
            
            st.dataframe(df, use_container_width=True)

            if st.button("▶️ Iniciar Importação", type="primary"):
                if df.empty:
                    st.error("A planilha não contém dados válidos para importar.")
                    return
                    
                with st.spinner("Importando projetos... Por favor, aguarde."):
                    usuario_logado = st.session_state.get('usuario', 'N/A')
                    # Esta função (bulk_insert) PRECISA estar atualizada no utils.py
                    sucesso, num_importados = utils.bulk_insert_projetos_db(df, usuario_logado)
                
                if sucesso:
                    st.success(f"🎉 {num_importados} projetos importados com sucesso!")
                    st.balloons()
                else:
                    st.error("A importação falhou. Verifique os erros acima (pode ser um erro de data) e o formato da sua planilha.")

        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.warning("Verifique se o arquivo é um Excel válido (.xlsx) e se não está corrompido.")

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    # Tenta carregar o usuário do app principal se a página foi recarregada
    # (Isso é um 'hack' para páginas, pode não ser 100% seguro)
    try:
        if st.query_params.get("user_email"):
            st.session_state.logado = True
            st.session_state.usuario_email = st.query_params.get("user_email")
            st.session_state.usuario = st.query_params.get("user_name")
    except:
        pass # Ignora se falhar

if not st.session_state.get("logado", False):
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

# Garante que 'usuario' existe na sessão para o 'bulk_insert'
if 'usuario' not in st.session_state:
     st.session_state.usuario = 'N/A' # Fallback

tela_importacao()
