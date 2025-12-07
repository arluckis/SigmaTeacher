from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import whisper
import shutil
import os
import uuid # Para gerar nomes únicos para os arquivos
from typing import List

# --- 1. CONFIGURAÇÃO DO BANCO DE DADOS (SQLite) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./meus_audios.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define a tabela do banco
class AudioLog(Base):
    __tablename__ = "audios"
    
    id = Column(Integer, primary_key=True, index=True)
    filename_original = Column(String) # Nome que o usuário mandou
    caminho_arquivo = Column(String)   # Onde salvamos no disco
    transcricao = Column(Text)         # O texto gerado pelo Whisper

# Cria o arquivo do banco de dados se não existir
Base.metadata.create_all(bind=engine)

# --- 2. CONFIGURAÇÃO DO WHISPER ---
print("Carregando modelo...")
modelo = whisper.load_model("small") # Usando o Medium como você validou

# --- 3. CONFIGURAÇÃO DO APP ---
app = FastAPI()

# Cria a pastinha para salvar os arquivos físicos
os.makedirs("uploads", exist_ok=True)

# Dependência para pegar a sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/transcrever-e-salvar")
async def processar_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    
    # A. Gerar um nome único (para não sobrescrever arquivos com mesmo nome)
    # Ex: "audio.mp3" vira "f47ac10b-58cc...audio.mp3"
    nome_unico = f"{uuid.uuid4()}_{file.filename}"
    caminho_final = f"uploads/{nome_unico}"
    
    # B. Salvar o arquivo na pasta 'uploads'
    with open(caminho_final, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # C. Transcrever
    print(f"Transcrevendo {caminho_final}...")
    resultado = modelo.transcribe(
        caminho_final, 
        language="pt", 
        temperature=0
    )
    texto_extraido = resultado["text"]
    
    # D. Salvar no Banco de Dados
    novo_registro = AudioLog(
        filename_original=file.filename,
        caminho_arquivo=caminho_final,
        transcricao=texto_extraido
    )
    
    db.add(novo_registro)
    db.commit()     # Confirma a gravação
    db.refresh(novo_registro) # Atualiza para pegar o ID gerado
    
    return {
        "status": "sucesso",
        "id_banco": novo_registro.id,
        "transcricao": texto_extraido
    }

# Rota extra: Listar tudo que já foi salvo
@app.get("/listar-audios")
def listar(db: Session = Depends(get_db)):
    audios = db.query(AudioLog).all()
    return audios


@app.post("/upload-arquivo")
async def upload_arquivos(files: List[UploadFile] = File(...), listAudios: List[int] = [], db: Session = Depends(get_db)):
    for file in files:
        print(file.name)
    for id in listAudios:
        print(id)