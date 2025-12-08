import json
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
if API_KEY is not None:
    print("API_KEY carregada com sucesso.")
else:
    print("API_KEY não encontrada nas variáveis de ambiente.")

genai.configure(api_key=API_KEY)
llm = genai.GenerativeModel("models/gemini-2.5-flash")


def carregar_json(json_str):
    if not json_str:
        return {}
    return json.loads(json_str)


def salvar_json(obj_dict):
    return json.dumps(obj_dict, ensure_ascii=False)


def get_text_from_message(message):
    """
    Extrai o texto de uma mensagem no histórico,
    independentemente de ser um objeto 'Content' ou um 'dict'.
    """
    if isinstance(message, dict):
        # É um dicionário
        try:
            return message["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return ""
    else:
        # É um objeto
        try:
            return message.parts[0].text
        except (AttributeError, IndexError):
            return ""


def upload_e_processar_arquivo(caminho_arquivo):
    """Faz o upload do arquivo para a API do Gemini e aguarda o processamento."""
    print(f"--- Uploading: {caminho_arquivo} ---")
    arquivo = genai.upload_file(caminho_arquivo)

    # Aguardar o arquivo estar ativo (processado)
    while arquivo.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        arquivo = genai.get_file(arquivo.name)

    if arquivo.state.name == "FAILED":
        raise ValueError(f"O processamento do arquivo {caminho_arquivo} falhou.")

    print(f"\nArquivo pronto: {arquivo.name}")
    return arquivo


# --- Modelo de Domínio ---
def etapa_0_prep_modelo_dominio(
    transcricao_audio="",
    caminhos_pdf=None,
    n_topicos=10,
    audiencia="1° ano do ensino médio",
):
    """
    Gera o Modelo de Domínio, extraindo informações da transcrição e PDFs fornecidos,
    em tópicos, cada um com explicação, pré-requisito, e exercício.
    """
    if caminhos_pdf is None:
        caminhos_pdf = []

    # 1. Preparar os arquivos PDF (Upload para o Gemini)
    arquivos_processados = []
    for caminho in caminhos_pdf:
        try:
            arq = upload_e_processar_arquivo(caminho)
            arquivos_processados.append(arq)
        except Exception as e:
            print(f"Erro ao processar PDF {caminho}: {e}")

    # 2. Construir o Prompt de Sistema e Instruções
    prompt_texto = f"""
    Você é um especialista pedagógico encarregado de criar um currículo.
    Sua tarefa é analisar o CONTEÚDO FORNECIDO (transcrição de áudio e documentos) e 
    estruturar um Modelo de Domínio.

    AUDIÊNCIA ALVO: {audiencia}
    
    INSTRUÇÕES:
    1. Analise o texto da transcrição e o conteúdo dos PDFs anexos.
    2. Identifique os {n_topicos} tópicos mais importantes abordados nestes materiais.
    3. Para cada tópico, gere:
       - (1) Uma explicação simples baseada no material.
       - (2) Pré-requisitos (outros tópicos desta lista necessários para entender o atual).
       - (3) Um exercício para avaliar a compreensão.
    
    IMPORTANTE: 
    - Limite-se ao escopo do material fornecido. Se o material for insuficiente, infira o mínimo necessário para manter a coerência.
    - O formato da sua saída DEVE ser estritamente um JSON válido.
    """

    # Exemplo de JSON
    exemplo_base_conhecimento = {
        "conceito_chave_do_texto": {
            "explicacao": "Explicação extraída do contexto fornecido...",
            "pre_requisitos": [],
            "exercicio": "Pergunta baseada no texto?",
        },
        "conceito_avancado": {
            "explicacao": "...",
            "pre_requisitos": ["conceito_chave_do_texto"],
            "exercicio": "...",
        },
    }
    prompt_texto += f"\n Exemplo de Formato JSON:\n {json.dumps(exemplo_base_conhecimento, indent=4)}"

    # 3. Montar a lista de conteúdos para o modelo (Multimodal)
    conteudo_envio = [prompt_texto]

    if transcricao_audio:
        conteudo_envio.append(
            f"\n--- INÍCIO DA TRANSCRIÇÃO DO ÁUDIO ---\n{transcricao_audio}\n--- FIM DA TRANSCRIÇÃO ---\n"
        )

    # Adicionar os objetos de arquivo PDF
    conteudo_envio.extend(arquivos_processados)

    print("--- Gerando Modelo de Domínio baseado nos arquivos/áudio... ---")

    # 4. Chamada ao LLM
    # Nota: passamos uma lista contendo strings e objetos de arquivo
    resposta_modelo = llm.generate_content(conteudo_envio).text

    # 5. Tratamento da Resposta (Regex e JSON Load - mantido do seu código)
    match = re.search(r"\{.*\}", resposta_modelo, re.DOTALL)

    if not match:
        print(f"--- ERRO: LLM não retornou JSON ---\n{resposta_modelo}")
        return {}

    json_limpo = match.group(0)

    try:
        modelo_dominio_em_dict = carregar_json(json_limpo)
        return modelo_dominio_em_dict
    except json.JSONDecodeError:
        print(f"--- ERRO: JSON MAL FORMADO --- \n{json_limpo}")
        return {}


# --- Modelo do Aluno ---
def etapa_0_inicializar_aluno(modelo_dominio):
    """
    Inicializando o modelo do aluno como nível de maestria em cada um dos todos tópicos.
    """
    modelo_aluno = {topico: "iniciante" for topico in modelo_dominio}
    return modelo_aluno


# --- Modelo Pedagógico ---
def etapa_1_selecao_proximo_topico(modelo_aluno):
    """
    Usa o LLM para decidir qual a próxima tarefa (Macro-Adaptação).
    """
    prompt_selecao_tarefa = f"""
    Você é um Sistema de Tutoria Inteligente.
    Decida o próximo tópico a ser ensinado com base no Modelo do Aluno a seguir:
    **Modelo do Aluno**:\n {json.dumps(modelo_aluno, indent=4)}\n
    Pense passo a passo para tomar sua decisão:
    1. Analise o histórico para entender o que o aluno já aprendeu.
    2. Com base na sua análise, identifique o próximo conceito mais lógico a ser ensinado, somente ensinando um tópico se os pré-requisitos forem julgados como aprendidos.
    3. Retorne sua decisão em um formato JSON com a chave "proximo_topico" (elemento presente nos Tópicos Disponíveis) e "raciocinio" (2-3 frases ultra-concisas).
    """

    resposta_em_texto = llm.generate_content(prompt_selecao_tarefa).text
    match = re.search(r"\{.*\}", resposta_em_texto, re.DOTALL)

    if not match:
        print(f"--- ERRO: LLM não retornou JSON ---\n{resposta_em_texto}")
        return {
            "proximo_topico": "ERRO_NO_JSON",
            "raciocinio": "Falha ao encontrar JSON na resposta do LLM.",
        }

    json_limpo = match.group(0)

    try:
        decisao_em_dict = carregar_json(json_limpo)
        return decisao_em_dict
    except json.JSONDecodeError as e:
        print(f"--- ERRO: JSON MAL FORMADO --- \n{json_limpo}")
        print(f"Erro específico: {e}")
        return {
            "proximo_topico": "ERRO_NO_JSON",
            "raciocinio": "Falha ao decodificar o JSON retornado pelo LLM.",
        }


def etapa_3_avaliacao_interacao_inicial(historico, modelo_aluno, topico_atual):
    """
    Usa o LLM para avaliar a resposta inicial e atualizar o modelo do aluno.
    """
    mensagem_usuario = get_text_from_message(historico[-1])
    pergunta_exercicio = get_text_from_message(historico[-2])

    prompt_avaliacao = f"""
    Você é um professor e avaliador em um Sistema de Tutoria Inteligente (ITS).
    Sua tarefa é avaliar a resposta de um aluno e atualizar seu modelo de conhecimento.

    Contexto atual:
    - Tópico Sendo Ensinado: "{topico_atual}"
    - Pergunta/Exercício feito ao aluno: "{pergunta_exercicio}"
    - Resposta do aluno: "{mensagem_usuario}"
    - Modelo do Aluno (Estado Atual):
    {json.dumps(modelo_aluno, indent=4)}

    Instruções de Avaliação:
    Pense passo a passo:
    1.  Avaliação Cognitiva (Correção): A resposta do aluno está "correta", "parcialmente_correta" ou "incorreta"?
    2.  Avaliação Cognitiva (Maestria): Com base na qualidade da resposta, qual deve ser o *novo* nível de maestria do aluno no tópico "{topico_atual}"?
        - Os níveis de maestria são: "iniciante", "intermediário", "avançado".
        - Se o aluno era "iniciante" e respondeu bem, atualize para "intermediário".
        - Se o aluno era "intermediário" e respondeu mal, ele pode regredir para "iniciante".
    3.  Avaliação Emocional (Estimativa): Com base no tom e conteúdo da resposta, estime o estado afetivo do aluno (ex: "confiante", "confuso", "frustrado", "neutro").
    4.  Raciocínio: Escreva 1-2 frases concisas explicando o porquê da sua avaliação (para feedback).

    Formato da Saída:
    Responda APENAS com um objeto JSON. Não inclua ```json ou qualquer outro texto.
    O JSON deve ter as seguintes chaves:
    - "topico_avaliado": (string, o tópico que você avaliou, ex: "{topico_atual}")
    - "correcao": (string, ex: "correta", "parcialmente_correta", "incorreta")
    - "raciocinio_avaliacao": (string, sua explicação concisa)
    - "novo_nivel_maestria": (string, o *novo* nível de maestria para este tópico, ex: "intermediário")
    - "estado_afetivo_estimado": (string, ex: "confuso")
    """

    try:
        resposta_bruta = llm.generate_content(prompt_avaliacao).text

        match = re.search(r"\{.*\}", resposta_bruta, re.DOTALL)

        if not match:
            avaliacao = {
                "erro": "Falha ao encontrar JSON na resposta.",
                "raciocinio_avaliacao": "Ocorreu um erro interno.",
            }
            return avaliacao, modelo_aluno

        json_limpo = match.group(0)
        avaliacao_json = carregar_json(json_limpo)

        novo_nivel = avaliacao_json.get("novo_nivel_maestria")
        topico_avaliado = avaliacao_json.get("topico_avaliado")

        if novo_nivel and topico_avaliado == topico_atual:
            modelo_aluno[topico_atual] = novo_nivel

        # Retornar a avaliação e o modelo atualizado
        return avaliacao_json, modelo_aluno

    except json.JSONDecodeError:
        avaliacao = {
            "erro": "Falha ao decodificar o JSON.",
            "raciocinio_avaliacao": "Ocorreu um erro interno de decodificação.",
        }
        return avaliacao, modelo_aluno  # Retorna o modelo antigo
    except Exception:
        avaliacao = {
            "erro": "Erro inesperado na Etapa 3.",
            "raciocinio_avaliacao": "Ocorreu um erro geral.",
        }
        return avaliacao, modelo_aluno


def etapa_45_decidir_e_gerar_feedback(exercicio, resposta_aluno):
    """
    Usa o LLM para avaliar a resposta e gerar feedback adaptativo (Micro-Adaptação).
    """
    prompt_feedback = f"""
    --- Decisão de feedback ---
    Como ITS, Avalie a resposta do aluno e forneça um feedback útil.
    Não precisa dizer "Olá" ou qualquer tipo de saudação, você já está inserido no contexto de uma conversa.
    Exercício Proposto: *"{exercicio}"*
    Resposta do Aluno: **"{resposta_aluno}"**
    Pense passo a passo:
    1. A resposta está correta?.
    2. Se incorreta, identifique o equívoco.
    3. Gere uma dica sem dar a resposta.
    4. Formule sua resposta final para o aluno.
    ----------------------------
    Responda somente com o feedback
    Dê o feedback direto para o aluno (sem JSON).
    Feedback:
    """
    return llm.generate_content(prompt_feedback).text


# --- Modelo do Aluno ---
def etapa_7_atualizacao_pos_feedback(chat, modelo_aluno):
    """
    Atualiza o modelo do aluno com base no último ciclo de conversa.
    """
    if len(chat.history) >= 3:
        # Atualize o modelo do aluno com  base n as últimas três mensagens do
        # historico: interacao inicial, feedback, e interacao final do ciclo.
        ciclo_interacao = chat.history[-3:]
        msg_aluno_inicial = get_text_from_message(ciclo_interacao[0])
        msg_tutor_feedback = get_text_from_message(ciclo_interacao[1])
        msg_aluno_final_reacao = get_text_from_message(ciclo_interacao[2])

        prompt_reavaliacao = f"""
        Você é um psicopedagogo e avaliador em um Sistema de Tutoria Inteligente.
        Sua tarefa é fazer um reajuste fino do modelo do aluno.

        O aluno acabou de passar por um ciclo de avaliação. O modelo dele foi
        atualizado, mas queremos analisar sua reação final para confirmar
        se a atualização foi correta.

        Ciclo de Interação:
        1.  Aluno (Resposta Inicial): "{msg_aluno_inicial}"
        2.  Tutor (Feedback): "{msg_tutor_feedback}"
        3.  Aluno (Reação ao Feedback): "{msg_aluno_final_reacao}"

        Modelo do Aluno (Estado Pós-Etapa 3):
        {json.dumps(modelo_aluno, indent=2)}

        Instruções de Reavaliação:
        Pense passo a passo:
        1.  Inferir Tópico: Qual tópico principal (chave do Modelo do Aluno)
            foi discutido neste ciclo?
        2.  Analisar Reação: A "Reação ao Feedback" do aluno (mensagem 3)
            indica confiança e compreensão (ex: "Entendi!", "Obrigado", "Legal!")
            ou indica confusão, insegurança ou acerto casual
            (ex: "Ainda estou confuso", "Por que?", "Nossa, acertei no chute")?
        3.  Decidir Reajuste: Se a reação indicar confusão, a atualização
            anterior (refletida no Modelo do Aluno) foi prematura e deve ser
            rebaixada.
        4.  Sugerir Nível: Se for rebaixar, sugira o nível anterior na hierarquia
            (iniciante -> intermediário -> avançado). Ex: Se estava "intermediário",
            sugira "iniciante".

        Formato da Saída:
        Responda APENAS com um objeto JSON com as seguintes chaves:
        - "topico_inferido": (string, a chave do tópico, ex: "equacoes_primeiro_grau")
        - "reacao_aluno": (string, ex: "confusa", "positiva", "neutra")
        - "necessita_reajuste": (boolean, True se a reação contradiz a maestria)
        - "novo_nivel_sugerido": (string, o nível para rebaixar, ex: "iniciante", ou "null" se não houver reajuste)
        - "raciocinio": (string, sua breve explicação)

        SEMPRE responda de acordo com o formato acima, mesmo se a resposta do aluno não fizer sentido.
        """
        try:
            resposta_bruta = llm.generate_content(prompt_reavaliacao).text
            match = re.search(r"\{.*\}", resposta_bruta, re.DOTALL)

            if not match:
                print(
                    f"--- ERRO (Etapa 7): LLM NÃO RETORNOU JSON --- \n{resposta_bruta}"
                )
                return modelo_aluno

            json_limpo = match.group(0)
            reavaliacao_json = carregar_json(json_limpo)

            necessita_reajuste = reavaliacao_json.get("necessita_reajuste", False)

            if necessita_reajuste:
                topico = reavaliacao_json.get("topico_inferido")
                novo_nivel = reavaliacao_json.get("novo_nivel_sugerido")
                raciocinio = reavaliacao_json.get("raciocinio", "N/A")

                if topico and novo_nivel and topico in modelo_aluno:
                    print("--- (Etapa 7) REAJUSTE FINO APLICADO ---")
                    print(f"    Tópico: {topico}")
                    print(f"    Nível Anterior: {modelo_aluno[topico]}")
                    print(f"    Novo Nível: {novo_nivel}")
                    print(f"    Motivo: {raciocinio}")
                    modelo_aluno[topico] = novo_nivel
                else:
                    print(
                        "--- (Etapa 7) Advertência: Reajuste falhou. Tópico/Nível ausente no JSON."
                    )
            else:
                print(
                    f"--- (Etapa 7) Confirmação: Nível de maestria mantido. {reavaliacao_json.get('raciocinio', '')} ---"
                )

            return modelo_aluno

        except json.JSONDecodeError:
            print(f"--- ERRO (Etapa 7): JSON MAL FORMADO --- \n{json_limpo}")
            return modelo_aluno
        except Exception as e:
            print(f"--- ERRO (Etapa 7): Erro inesperado --- \n{e}")
            return modelo_aluno


def sistema_tutoria_inteligente_genai(modelo_dominio):
    """
    Inicia uma nova sessão de tutoria.
    """
    prompt_sistema = {
        "role": "model",
        "parts": [
            {
                "text": "Você é um Sistema de Tutoria Inteligente (ITS) amigável e encorajador."
            }
        ],
    }
    chat = llm.start_chat(history=[prompt_sistema])

    modelo_aluno = etapa_0_inicializar_aluno(modelo_dominio)

    # Enquanto houver topicos a aprender...
    while modelo_aluno:
        # Etapa 1
        decisao = etapa_1_selecao_proximo_topico(modelo_aluno)
        topico_atual = decisao.get("proximo_topico")

        explicacao = modelo_dominio[topico_atual]["explicacao"]
        exercicio = modelo_dominio[topico_atual]["exercicio"]

        print(explicacao)
        print(exercicio)

        chat.history.append(
            {
                "role": "model",
                "parts": [
                    {"text": f"Explicação: {explicacao}; Exercício: {exercicio}"}
                ],
            }
        )

        # Etapa 2
        mensagem_usuario = input("Usuário: ")

        chat.history.append(
            {"role": "user", "parts": [{"text": f"Explicação: {mensagem_usuario}"}]}
        )

        # Etapa 3
        avaliacao, modelo_aluno = etapa_3_avaliacao_interacao_inicial(
            chat, modelo_aluno, topico_atual
        )

        # Etapas 4 e 5
        feedback = etapa_45_decidir_e_gerar_feedback(chat, exercicio)

        print(feedback)

        # Etapa 6
        mensagem_usuario = input("Usuário: ")  # etapa_7

        chat.history.append({"role": "user", "parts": [{"text": mensagem_usuario}]})

        # Etapa 7
        modelo_aluno = etapa_7_atualizacao_pos_feedback(chat, modelo_aluno)

        # Condição de parada: ter aprendido todos os tópicos
        if modelo_aluno[topico_atual] == "avançado":
            # Removendo tópico já aprendido
            modelo_aluno.pop(topico_atual)

    return chat
