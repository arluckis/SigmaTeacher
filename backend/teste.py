import its
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
if API_KEY is not None:
    print("API_KEY loaded successfully.")
else:
    print("API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)
llm = genai.GenerativeModel("models/gemini-2.5-flash")

# Execução do ITS
modelo_dominio = its.etapa_0_prep_modelo_dominio(llm, "biologia")
chat_its = its.sistema_tutoria_inteligente_genai(llm, modelo_dominio)
