import streamlit as st
import requests
from PIL import Image
from areas.professor import render_professor_area
from areas.aluno import render_aluno_area
import os

# --- CONFIGURAÇÃO DA API ---
API_URL = os.getenv("API_URL", "http://backend:8000")

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="SigmaTeacher",
    page_icon="🎓", 
    layout="wide",
)

# --- LOGO / HEADER (CORREÇÃO DE DUPLICAÇÃO) ---
try:
    # 1. Tenta carregar a imagem (Ajuste o caminho se necessário)
    caminho_logo = os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo_sigma.png')
    logo = Image.open(caminho_logo) 
    
    # 2. Centraliza e exibe a imagem
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(logo, width='stretch')
        
except Exception:
    # 3. Fallback: Se não achar a imagem, mostra o texto
    st.markdown("<h1 style='text-align: center;'>🎓 Sigma Teacher</h1>", unsafe_allow_html=True)
    
st.divider() 

# --- CONFIGURAÇÃO DE SENHAS e ESTADO (Mantido) ---
CODIGO_PROFESSOR_FIXO = "admin123"

if "pagina_atual" not in st.session_state:
    st.session_state.pagina_atual = "home"
# ... (Mantenha o resto das inicializações de estado)

# --- FUNÇÕES AUXILIARES ---
def ir_para(pagina):
    st.session_state.pagina_atual = pagina

def logout():
    st.session_state.pagina_atual = "home"
    st.session_state.dados_aluno = None
    st.session_state.visualizando_chat_atualmente_aluno = False

# ==========================================
# LÓGICA DE NAVEGAÇÃO
# ==========================================

# 1. TELA INICIAL
if st.session_state.pagina_atual == "home":
    st.markdown("<h3 style='text-align: center;'>Bem-vindo ao SigmaTeacher</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_prof, col_aluno = st.columns(2)
        with col_prof:
            if st.button("👨‍🏫 Área do Professor", use_container_width=True):
                ir_para("login_prof")
                st.rerun()
        with col_aluno:
            if st.button("👨‍🎓 Área do Aluno", use_container_width=True):
                ir_para("login_aluno")
                st.rerun()

# 2. LOGIN PROFESSOR (etc.)
elif st.session_state.pagina_atual == "login_prof":
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.subheader("Acesso do Professor")
        senha = st.text_input("Senha Admin:", type="password")
        
        c_voltar, c_entrar = st.columns(2)
        if c_voltar.button("⬅ Voltar"):
            ir_para("home")
            st.rerun()
        
        if c_entrar.button("Entrar", type="primary"):
            if senha == CODIGO_PROFESSOR_FIXO:
                ir_para("area_prof")
                st.rerun()
            else:
                st.error("Senha incorreta.")

# 3. LOGIN ALUNO
elif st.session_state.pagina_atual == "login_aluno":
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.subheader("Acesso do Aluno")
        codigo = st.text_input("Digite seu Código de Acesso (ex: A7X92B):")
        
        c_voltar, c_entrar = st.columns(2)
        if c_voltar.button("⬅ Voltar"):
            ir_para("home")
            st.rerun()
            
        if c_entrar.button("Entrar", type="primary"):
            try:
                res = requests.get(f"{API_URL}/aluno/login/{codigo}")
                if res.status_code == 200:
                    st.session_state.dados_aluno = res.json()
                    st.session_state.dados_aluno_codigo = codigo
                    ir_para("area_aluno")
                    st.rerun()
                else:
                    st.error("Código inválido ou não encontrado.")
            except Exception as e:
                st.error(f"Erro de conexão com o servidor: {e}")

# 4. ÁREA PROFESSOR
elif st.session_state.pagina_atual == "area_prof":
    with st.sidebar:
        st.write("Logado como Professor")
        if st.button("Sair"):
            logout()
            st.rerun()
    render_professor_area()

# 5. ÁREA ALUNO
elif st.session_state.pagina_atual == "area_aluno":
    with st.sidebar:
        if st.session_state.dados_aluno:
            st.write(f"Aluno: **{st.session_state.dados_aluno['aluno_nome']}**")
        if st.button("Sair"):
            logout()
            st.rerun()
    render_aluno_area()

# --- RODAPÉ ---
st.divider()
st.caption("🎓 SigmaTeacher - Plataforma de Tutoria Inteligente")