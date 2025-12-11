from datetime import datetime
import streamlit as st
import requests
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def render_its_chat(
    mostrar_audios: bool = True,
    mostrar_entrada_resposta: bool = True,
):
    # Inicializar estado da sessão
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = None

    if "chat_iniciado" not in st.session_state:
        st.session_state.chat_iniciado = False

    if not st.session_state.chat_iniciado or not st.session_state.session_id:
        st.info(
            "📌 Nenhuma sessão ativa. Selecione uma sessão para entrar na aba 'Lista de sessões disponíveis'."
        )
    else:
        if mostrar_audios:
            audios_contexto = st.session_state.get("audios_sessao_atual", [])

            with st.expander(
                "📚 Ver conteúdo das aulas originais (Transcrição)", expanded=False
            ):
                if audios_contexto:
                    for audio in audios_contexto:
                        with st.expander(
                            f"📝 {audio['filename_original']}",
                            expanded=False,
                        ):
                            data_audio_raw = audio.get("data_criacao")
                            try:
                                dt_obj = datetime.fromisoformat(data_audio_raw)
                                data_fmt = dt_obj.strftime("%d/%m/%Y %H:%M")
                            except ValueError:
                                data_fmt = data_audio_raw

                            st.caption(f"Data: {data_fmt}")

                            st.text_area(
                                "Conteúdo da aula:",
                                value=audio["transcricao"],
                                height=10,
                                disabled=True,
                                key=f"view_only_{audio['id']}",
                            )

                    st.divider()
                else:
                    st.info("Nenhum áudio vinculado a esta sessão.")

        st.divider()
        # Exibir informações da sessão
        col1, col2, _ = st.columns([1, 8, 1])
        with col1:
            st.write(f"**ID da sessão:** {st.session_state.session_id}")
        with col2:
            st.markdown(
                f"<div style='text-align: center; font-weight: bold;'>Tópico: {st.session_state.topico_atual}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Container para o chat
        chat_container = st.container(height=400, border=True)

        with chat_container:
            # Exibir mensagens do histórico
            for message in st.session_state.chat_messages:
                if message["role"] == "user":
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(message["content"])
                else:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(message["content"])

            # Se é a primeira mensagem, mostrar a mensagem inicial do bot
            if (
                not st.session_state.chat_messages
                and "mensagem_bot" in st.session_state
            ):
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(st.session_state.mensagem_bot)
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": st.session_state.mensagem_bot}
                )

        if mostrar_entrada_resposta:
            # Input do usuário
            st.divider()

            col1, col2 = st.columns([4, 1])

            st.markdown(
                """
                <style>
                button[kind="primary"] {
                    margin-top: 28px;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            with col1:
                user_input = st.text_input(
                    "Sua resposta:",
                    placeholder="Digite sua resposta aqui...",
                    key="user_input_its",
                )

            with col2:
                send_button = st.button("📤 Enviar", type="primary", width="stretch")

            # Processar resposta do usuário
            if send_button and user_input:
                # Adicionar mensagem do usuário
                st.session_state.chat_messages.append(
                    {"role": "user", "content": user_input}
                )

                # Enviar para backend
                with st.spinner("⏳ Processando resposta..."):
                    try:
                        response = requests.post(
                            f"{API_URL}/its/chat",
                            json={
                                "session_id": st.session_state.session_id,
                                "mensagem": user_input,
                            },
                            timeout=60,
                        )

                        if response.status_code == 200:
                            dados = response.json()

                            # Adicionar resposta do bot
                            st.session_state.chat_messages.append(
                                {"role": "assistant", "content": dados["mensagem_bot"]}
                            )

                            # Atualizar status
                            st.session_state.topico_atual = dados.get(
                                "topico_atual", st.session_state.topico_atual
                            )

                            # Se a sessão foi concluída
                            if dados.get("status_atual") == "concluido":
                                st.success(
                                    "🎉 Parabéns! Você completou a sessão de tutoria!"
                                )
                                st.balloons()

                            st.rerun()
                        else:
                            erro_msg = response.json().get(
                                "detail", "Erro desconhecido"
                            )
                            st.error(f"❌ Erro: {erro_msg}")
                    except requests.exceptions.Timeout:
                        st.error("⏱️ Timeout: A resposta demorou muito.")
                    except Exception as e:
                        st.error(f"❌ Erro ao enviar resposta: {str(e)}")
