from datetime import datetime
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
                    if st.button("▶️ Entrar", key=f"btn_entrar_{sessao['id']}"):
                        if carregar_sessao(sessao["id"]):
                            st.success("Carregando...")
                            st.rerun()

    with aba_chat:
        st.header("💬 SigmaTeacher Chat - Sessão de Tutoria")

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
                            try:
                                dt_obj = datetime.fromisoformat(data_raw)
                                data_fmt = dt_obj.strftime("%d/%m/%Y %H:%M")
                            except ValueError:
                                data_fmt = data_raw

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
            col1, col2, col3 = st.columns([1, 8, 1])
            with col1:
                st.write(f"**ID da sessão:** {st.session_state.session_id}")
            with col2:
                st.markdown(
                    f"<div style='text-align: center; font-weight: bold;'>Tópico: {st.session_state.topico_atual}</div>",
                    unsafe_allow_html=True,
                )

            with col3:
                st.markdown("<div style='text-align: right;'>", unsafe_allow_html=True)
                if st.button("🔄 Nova Sessão", key="nova_sessao_btn"):
                    st.session_state.chat_iniciado = False
                    st.session_state.session_id = None
                    st.session_state.chat_messages = []
                    st.rerun()

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
