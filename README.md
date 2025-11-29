# Sigma Teacher 

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Whisper](https://img.shields.io/badge/OpenAI_Whisper-000000?style=for-the-badge&logo=openai&logoColor=white)

> **Plataforma inteligente para transcrição e gestão de aulas usando Inteligência Artificial.**

O **Sigma Teacher** é uma aplicação Full-Stack que permite aos professores gravar suas aulas e obter transcrições precisas automaticamente utilizando o modelo **Whisper da OpenAI**. Todo o histórico é salvo em banco de dados para consulta futura.

---

## -> Funcionalidades:

- **Gravação de Voz:** Interface nativa para gravar aulas diretamente no navegador.
- **Upload de Arquivos:** Suporte para `.mp3`, `.wav`, `.m4a` e `.ogg`.
- **IA Transcritora:** Utiliza o modelo `Small` (ou `Medium`) do OpenAI Whisper para gerar textos com alta fidelidade em Português.
- **Banco de Dados:** Armazenamento automático do histórico de transcrições e caminhos dos arquivos.
- **Dockerizado:** O projeto roda isolado em containers, sem necessidade de instalar dependências na máquina local.

---

## -> Tecnologias Utilizadas:

- **Backend:** Python + FastAPI
- **Frontend:** Streamlit (Python)
- **IA:** OpenAI Whisper + FFmpeg
- **Banco de Dados:** SQLite + SQLAlchemy
- **Infraestrutura:** Docker & Docker Compose

---

## -> Como rodar o projeto?

### Pré-requisitos

- Ter o Docker Desktop instalado e rodando.

### Passo a Passo

***1. Clone o repositório***

```Bash
git clone [https://github.com/SEU_USUARIO/sigma-teacher.git](https://github.com/SEU_USUARIO/sigma-teacher.git)
cd sigma-teacher
```


***2. Suba os containers***

```Bash
docker-compose up --build
```


- Nota: Na primeira execução, o sistema irá baixar a imagem Linux e o modelo de IA (aprox. 1GB).

Acesse a aplicação Abra seu navegador e acesse: 👉 http://localhost:8501

## -> Solução de Problemas (Troubleshooting)
***O Backend cai com erro "Killed" ou "Exit Code 137"***


- Motivo: Isso ocorre porque o modelo de IA consome muita memória RAM.

- Solução: Abra o Docker Desktop > Settings > Resources.

Aumente o limite de Memory para pelo menos 4GB.

Reinicie os containers.

***O Frontend mostra erro "Connection Refused"***

Motivo: Significa que o Backend ainda não terminou de carregar o modelo de IA. 

Solução: Aguarde aparecer a mensagem Application startup complete no terminal antes de tentar transcrever.

## -> Tecnologias
- Backend: Python 3.10, FastAPI, Uvicorn

- Frontend: Streamlit, Streamlit-Mic-Recorder

- Processamento de Áudio: FFmpeg, OpenAI Whisper

- Banco de Dados: SQLite, SQLAlchemy

- Infraestrutura: Docker Compose

## -> Licença
***Projeto desenvolvido como requisito avaliativo da disciplina Inteligência Artificial para Educação (UFRN), sob orientação do Prof. Adelson Dias.***

***Desenvolvido por:***

- LUCAS RAFAEL ARRUDA DE AMORIM;
- MARIANA RAQUEL DE MORAIS;
- VINÍCIUS CÉSAR NEVES DE BRITO E
- YAGO GOMES DA SILVA.

## -> Capturas de Tela:

<img width="1440" height="900" alt="Captura de Tela 2025-11-29 às 20 11 36" src="https://github.com/user-attachments/assets/1441f089-c431-44f9-9289-f035dab72f8e" />
<img width="1440" height="900" alt="Captura de Tela 2025-11-29 às 20 11 42" src="https://github.com/user-attachments/assets/983fb5da-dea7-4a99-9c59-15971278e12e" />
