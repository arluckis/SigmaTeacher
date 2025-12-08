import its

transcricao = """
Se vocês observarem o mapa da Europa no início do século XIX, vão notar algo curioso: quase todo o continente estava sob influência direta ou indireta de Napoleão Bonaparte. Ele era mais do que um general brilhante — era alguém obcecado por reorganizar a Europa segundo sua própria lógica.

Depois de assumir o poder na França, em 1799, ele se aproveitou do desgaste da Revolução Francesa para se apresentar como a figura capaz de restaurar ordem e estabilidade. E, de fato, centralizou o Estado, reformou leis — o Código Napoleônico é exemplo disso — e ampliou a burocracia.

O problema é que essa ambição tinha um limite: outros países não estavam dispostos a aceitar uma França hegemônica. As guerras napoleônicas foram, no fundo, reações em cadeia a cada movimento expansionista dele. A campanha da Rússia, por exemplo, mostrou o ponto em que estratégia militar se transforma em imprudência: logística falha, clima extremo e perda massiva de soldados.

No fim, o Congresso de Viena, em 1815, reorganizou a Europa tentando desfazer o que Napoleão tinha construído. Mas, ironicamente, muitas das reformas inspiradas por ele continuaram, mesmo depois de sua queda.
"""
pdfs = ["napoleao_bonaparte.pdf"]

# Execução do ITS
modelo_dominio = its.etapa_0_prep_modelo_dominio(
    transcricao_audio=transcricao, caminhos_pdf=pdfs, n_topicos=5
)
chat_its = its.sistema_tutoria_inteligente_genai(modelo_dominio)
