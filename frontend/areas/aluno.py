import streamlit as st
import os

from components.its_chat import render_its_chat
from components.listar_sessoes import render_listar_sessoes

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def render_aluno_area():
    aba_sessoes, aba_chat = st.tabs(
        [
            "📖 Lista de sessões disponíveis",
            "💬 SigmaTeacher Chat",
        ]
    )

    with aba_sessoes:
        st.header("📖 Lista de sessões disponíveis")
        st.write("Selecione uma sessão abaixo para continuar seus estudos.")

        st.divider()

        if st.session_state.session_id:
            st.info(
                f"Sessão ativa atualmente: **#{st.session_state.session_id} - {st.session_state.topico_atual}**"
            )

        render_listar_sessoes()

    with aba_chat:
        st.header("💬 SigmaTeacher Chat - Sessão de Tutoria")

        render_its_chat()
