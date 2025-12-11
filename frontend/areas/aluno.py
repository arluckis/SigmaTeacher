import streamlit as st
import os

from components.its_chat import render_its_chat
from components.listar_sessoes import render_listar_sessoes

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def render_aluno_area():
    if not st.session_state.visualizando_chat_atualmente_aluno:
        st.header("📖 Lista de sessões disponíveis")
        st.write("Selecione uma sessão abaixo para continuar seus estudos.")

        st.divider()

        if st.session_state.session_id:
            st.info(
                f"Sessão ativa atualmente: **#{st.session_state.session_id} - {st.session_state.topico_atual}**"
            )

        render_listar_sessoes()
    else:
        st.header("💬 SigmaTeacher Chat - Sessão de Tutoria")

        st.button("Voltar para listagem de sessões", on_click=alternar_visualizar_chat)

        render_its_chat()


def alternar_visualizar_chat():
    st.session_state.visualizando_chat_atualmente_aluno = (
        not st.session_state.visualizando_chat_atualmente_aluno
    )
