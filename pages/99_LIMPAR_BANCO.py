import streamlit as st
import utils_chamados
import time

st.set_page_config(page_title="LIMPEZA DE DADOS", page_icon="🔥")

st.title("🔥 Ferramenta de Limpeza do Banco de Dados")
st.warning("Esta página é temporária. Use-a apenas UMA VEZ para apagar todos os dados.")
st.error("⚠️ CUIDADO: Esta ação é IRREVERSÍVEL e vai apagar TODOS os chamados do banco de dados.")

confirm_delete = st.checkbox("Eu confirmo que desejo apagar todos os dados permanentemente.")

if confirm_delete:
    if st.button("🔴 LIMPAR TODO O BANCO DE DADOS AGORA (AÇÃO IRREVERSÍVEL)", use_container_width=True):
        
        # 1. Verifica se a função existe (que você adicionou na Etapa 1)
        if not hasattr(utils_chamados, 'limpar_tabela_chamados'):
            st.error("Erro: A função 'limpar_tabela_chamados' não foi encontrada em 'utils_chamados.py'.")
            st.error("Por favor, adicione a função de limpeza ao seu utils_chamados.py primeiro (Etapa 1).")
            st.stop()
            
        # 2. Executa a limpeza
        with st.spinner("Limpando banco de dados..."):
            if utils_chamados.limpar_tabela_chamados():
                st.success("Banco de dados limpo com sucesso! A página pode ser fechada.")
                st.balloons()
                st.cache_data.clear()
                st.cache_resource.clear()
            else:
                st.error("Falha ao limpar o banco de dados.")
else:
    st.info("Marque a caixa de confirmação para habilitar o botão de limpeza.")

st.divider()
st.markdown("### Após usar, delete este arquivo (`99_LIMPAR_BANCO.py`) da sua pasta `pages/`.")
