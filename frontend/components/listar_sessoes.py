from datetime import datetime
import streamlit as st
import requests
import os
from utils.carregar_sessao import carregar_sessao

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def render_listar_sessoes(
    mostrar_botao_entrar: bool = True, mostrar_botao_visualizar_chat: bool = False
):
    _, col_top_2 = st.columns([4, 1])
    with col_top_2:
        if st.button(
            "🔄 Atualizar Lista",
            key="btn_atualizar_sessoes",
            use_container_width=True,
        ):
            st.rerun()

    # Busca sessões no backend
    try:
        resp = requests.get(f"{API_URL}/its/sessoes")
        if resp.status_code == 200:
            sessoes = resp.json()
        else:
            sessoes = []
            st.error("Não foi possível buscar as sessões.")
    except Exception:
        sessoes = []
        st.warning("Conecte o backend para ver as sessões.")

    if not sessoes:
        st.info("Nenhuma sessão encontrada. Peça ao professor para criar uma nova!")
    else:
        c1, c2, c3, c4 = st.columns([0.5, 4, 2, 1.5])
        c1.markdown("**ID**")
        c2.markdown("**Tópico / Data**")
        c3.markdown("**Status**")
        c4.markdown("**Ação**")

        st.divider()

        for sessao in sessoes:
            c1, c2, c3, c4 = st.columns([0.5, 4, 2, 1.5])

            with c1:
                st.write(f"#{sessao['id']}")

            with c2:
                st.markdown(f"**{sessao['topico']}**")

                data_raw = sessao.get("data_criacao")
                if data_raw:
                    try:
                        dt_obj = datetime.fromisoformat(data_raw)
                        data_fmt = dt_obj.strftime("%d/%m/%Y %H:%M")
                    except ValueError:
                        data_fmt = data_raw
                else:
                    data_fmt = "Data desconhecida"

                st.caption(f"📅 {data_fmt}")

            with c3:
                if sessao["status"] == "concluido":
                    st.markdown(":green[✅ **Concluído**]")
                else:
                    st.markdown(":blue[⏳ **Em andamento**]")

            with c4:
                if mostrar_botao_entrar:
                    if st.button("▶️ Entrar", key=f"btn_entrar_{sessao['id']}"):
                        if carregar_sessao(sessao["id"]):
                            st.success("Carregando...")
                            st.rerun()
                if mostrar_botao_visualizar_chat:
                    if st.button(
                        "💬 Visualizar Chat",
                        key=f"btn_visualizar_chat_{sessao['id']}",
                    ):
                        if carregar_sessao(sessao["id"]):
                            st.session_state.visualizando_chat_atualmente = True
                            st.rerun()
