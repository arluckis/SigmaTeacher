import json
import re


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


# --- Modelo de Domínio ---
def etapa_0_prep_modelo_dominio(
    llm, dominio, n_topicos=10, audiencia="1° ano do ensino médio"
):
    """
    Define o Modelo de Domínio em tópicos, cada um com explicação, pré-requisito, e exercício.
    """
    prompt_dominio = f"""
    Você é especializado no domínio `{dominio}`.
    Pense nos {n_topicos} tópicos mais relevantes para a audiência "{audiencia}".
    Para cada tópico, precisará de (1) uma explicação espontâneamente simples,
    (2) a lista dos outros tópicos que são pré-requisitos deste tópico e (3) um
    exercício para avaliar a compreensão do tópico.
    As explicações e exercícios devem ser auto-contidos, não referenciando outras frases.
    O formato da sua saída deverá ser um json válido.
    """
    # Exemplo para servir de base para construção automática de novas bases de conhecimento
    exemplo_base_conhecimento = {
        "soma_fracoes": {
            "explicacao": "Para somar frações, primeiro encontre um denominador comum. Depois, some os numeradores.",
            "pre_requisitos": ["denominador_comum"],
            "exercicio": "Quanto é 1/2 + 1/4?",
        },
        "denominador_comum": {
            "explicacao": "O denominador comum é um múltiplo compartilhado pelos denominadores de duas ou mais frações.",
            "pre_requisitos": [],
            "exercicio": "Qual é o menor denominador comum para 1/3 e 1/5?",
        },
        "subtracao_fracoes": {
            "explicacao": "A subtração de frações segue a mesma lógica da soma: encontre um denominador comum e depois subtraia os numeradores.",
            "pre_requisitos": ["denominador_comum", "soma_fracoes"],
            "exercicio": "Quanto é 3/4 - 1/4?",
        },
    }
    # Transformar o dicionário acima em uma string mais legível:
    exemplo_base_conhecimento = json.dumps(exemplo_base_conhecimento, indent=4)
    prompt_dominio += f"\n Exemplo:\n {exemplo_base_conhecimento}"
    # Gerar modelo de domínio
    modelo_dominio = llm.generate_content(prompt_dominio).text

    match = re.search(r"\{.*\}", modelo_dominio, re.DOTALL)

    if not match:
        print(f"--- ERRO: LLM não retornou JSON ---\n{modelo_dominio}")
        return {
            "ERRO": {
                "explicacao": "Erro na resposta da LLM",
                "pre_requisitos": [],
                "exercicio": "",
            }
        }

    json_limpo = match.group(0)

    try:
        modelo_dominio_em_dict = json.loads(json_limpo)
        return modelo_dominio_em_dict
    except json.JSONDecodeError as e:
        print(f"--- ERRO: JSON MAL FORMADO --- \n{json_limpo}")
        print(f"Erro específico: {e}")
        return {
            "ERRO": {
                "explicacao": "Erro na resposta da LLM",
                "pre_requisitos": [],
                "exercicio": "",
            }
        }


# --- Modelo do Aluno ---
def etapa_0_inicializar_aluno(modelo_dominio):
    """
    Inicializando o modelo do aluno como nível de maestria em cada um dos todos tópicos.
    """
    modelo_aluno = {topico: "iniciante" for topico in modelo_dominio}
    return modelo_aluno


# --- Modelo Pedagógico ---
def etapa_1_selecao_proximo_topico(llm, modelo_aluno):
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
        decisao_em_dict = json.loads(json_limpo)
        return decisao_em_dict
    except json.JSONDecodeError as e:
        print(f"--- ERRO: JSON MAL FORMADO --- \n{json_limpo}")
        print(f"Erro específico: {e}")
        return {
            "proximo_topico": "ERRO_NO_JSON",
            "raciocinio": "Falha ao decodificar o JSON retornado pelo LLM.",
        }


def etapa_3_avaliacao_interacao_inicial(llm, chat, modelo_aluno, topico_atual):
    """
    Usa o LLM para avaliar a resposta inicial e atualizar o modelo do aluno.
    """
    mensagem_usuario = get_text_from_message(chat.history[-1])
    pergunta_exercicio = get_text_from_message(chat.history[-2])

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
        avaliacao_json = json.loads(json_limpo)

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


def etapa_45_decidir_e_gerar_feedback(chat, exercicio):
    """
    Usa o LLM para avaliar a resposta e gerar feedback adaptativo (Micro-Adaptação).
    """
    resposta_aluno = get_text_from_message(chat.history[-1])
    prompt_feedback = f"""
    --- Decisão de feedback ---
    Como ITS, Avalie a resposta do aluno e forneça um feedback útil.
    Exercício Proposto: *"{exercicio}"*
    Resposta do Aluno: **"{resposta_aluno}"**
    Pense passo a passo:
    1. A resposta está correta?.
    2. Se incorreta, identifique o equívoco.
    3. Gere uma dica sem dar a resposta.
    4. Formule sua resposta final para o aluno.
    ----------------------------
    Responda somente com o feedback

    Feedback:
    """
    resposta = chat.send_message(prompt_feedback)
    return resposta.text


# --- Modelo do Aluno ---
def etapa_7_atualizacao_pos_feedback(llm, chat, modelo_aluno):
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
            reavaliacao_json = json.loads(json_limpo)

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


def sistema_tutoria_inteligente_genai(llm, modelo_dominio):
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
        decisao = etapa_1_selecao_proximo_topico(llm, modelo_aluno)
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
            llm, chat, modelo_aluno, topico_atual
        )

        # Etapas 4 e 5
        feedback = etapa_45_decidir_e_gerar_feedback(chat, exercicio)

        print(feedback)

        # Etapa 6
        mensagem_usuario = input("Usuário: ")  # etapa_7

        chat.history.append({"role": "user", "parts": [{"text": mensagem_usuario}]})

        # Etapa 7
        modelo_aluno = etapa_7_atualizacao_pos_feedback(llm, chat, modelo_aluno)

        # Condição de parada: ter aprendido todos os tópicos
        if modelo_aluno[topico_atual] == "avançado":
            # Removendo tópico já aprendido
            modelo_aluno.pop(topico_atual)

    return chat
