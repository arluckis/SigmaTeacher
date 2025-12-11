import streamlit as st
import requests
import os

# Importamos os componentes necessários
from components.its_chat import render_its_chat
from utils.carregar_sessao import carregar_sessao # <--- Importando seu arquivo

API_URL = os.getenv("API_URL", "http://backend:8000")

def render_aluno_area():
    # 1. Se o aluno já entrou no chat, mostra o chat
    if st.session_state.visualizando_chat_atualmente_aluno:
        if st.button("⬅ Voltar para Minhas Atividades"):
            st.session_state.visualizando_chat_atualmente_aluno = False
            st.session_state.dados_quiz_atual = None # Limpa o quiz anterior
            st.rerun()
            
        render_its_chat()
        return

    # 2. Tela Inicial (Lista de Atividades)
    dados = st.session_state.get("dados_aluno")
    if not dados:
        st.error("Sessão expirada. Faça login novamente.")
        return

    st.header(f"👋 Olá, {dados['aluno_nome']}")
    st.caption(f"Turma: {dados['turma_nome']}")
    st.divider()

    st.subheader("📅 Suas Atividades Pendentes")
    
    # Busca lista atualizada de atividades (opcional, mas recomendado)
    try:
        # Recarrega a lista para garantir que está atualizada
        res = requests.get(f"{API_URL}/aluno/login/{st.session_state.dados_aluno_codigo}") # Assumindo que guardamos o código
        if res.status_code == 200:
            atividades = res.json().get("atividades", [])
        else:
            atividades = dados.get("atividades", [])
    except:
        atividades = dados.get("atividades", [])
    
    if not atividades:
        st.info("🎉 Você não tem atividades pendentes.")
    else:
        for ativ in atividades:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{ativ['topico']}**")
                    st.caption(f"Status: {ativ['status']} | Data: {ativ['data'][:10]}")
                with c2:
                    # --- AQUI ESTÁ A MUDANÇA ---
                    if st.button("▶️ COMEÇAR", key=f"btn_{ativ['id']}", use_container_width=True):
                        with st.spinner("Carregando atividade..."):
                            # Usa a sua função para carregar tudo
                            sucesso = carregar_sessao(ativ['id'])
                            
                            if sucesso:
                                st.session_state.visualizando_chat_atualmente_aluno = True
                                st.session_state.dados_quiz_atual = None # Força recarregar o quiz novo
                                st.rerun()