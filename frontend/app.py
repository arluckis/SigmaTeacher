import streamlit as st
from PIL import Image
from areas.professor import render_professor_area
from areas.aluno import render_aluno_area

st.set_page_config(
    page_title="SigmaTeacher",
    page_icon=Image.open("assets/logo_sigma.png"),
    layout="wide",
)


if "mostrar_professor" not in st.session_state:
    st.session_state.mostrar_professor = True
if "session_id" not in st.session_state:
    st.session_state.session_id = None


def alternar_area():
    st.session_state.mostrar_professor = not st.session_state.mostrar_professor


if st.session_state.mostrar_professor:
    btn_label = "Mudar para Área do Aluno"
else:
    btn_label = "Mudar para Área do Professor"

st.button(btn_label, on_click=alternar_area)

# --- LOGO PRINCIPAL ---
try:
    logo_principal = Image.open("assets/logo_sigma.png")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(logo_principal, width="stretch")
except FileNotFoundError:
    st.title("🎙️ Sigma Teacher")

st.divider()

if st.session_state.mostrar_professor:
    render_professor_area()

else:
    render_aluno_area()

st.divider()
st.caption("🎓 SigmaTeacher - Plataforma de Tutoria Inteligente")
