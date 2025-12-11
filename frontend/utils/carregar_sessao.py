import streamlit as st
import requests
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def carregar_sessao(session_id):
    """Busca os dados de uma sessão específica e carrega no estado"""
    try:
        resp = requests.get(f"{API_URL}/its/sessao/{session_id}")
        if resp.status_code == 200:
            dados = resp.json()

            # Atualiza o estado global do Streamlit
            st.session_state.session_id = dados["id"]
            st.session_state.topico_atual = dados["topico_atual"]
            st.session_state.chat_messages = dados["mensagens"]
            st.session_state.audios_sessao_atual = dados.get("audios_contexto", [])
            st.session_state.chat_iniciado = True

            # Força o 'mensagem_bot' para evitar que o chat tente reenviar msg de boas vindas
            if dados["mensagens"] and dados["mensagens"][-1]["role"] == "assistant":
                st.session_state.mensagem_bot = dados["mensagens"][-1]["content"]

            return True
        else:
            st.error("Erro ao carregar sessão.")
            return False
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return False
