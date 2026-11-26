"""cleanchain_mcp: servidor MCP (stdio) do CleanChain (no app instalado: cleanchain-backend --mcp).

Uma ponte, e só isso: recebe as chamadas de qualquer cliente MCP (Claude Desktop, Claude
Code, Cursor, VS Code, outros agentes), encontra o app do CleanChain aberto pelo runtime.json
e repassa ao backend dele (rotas /api/mcp/*). Não lê nem apaga arquivos do usuário: a
leitura vem das análises que o app já fez, e limpezas viram PROPOSTAS que o usuário aprova
no próprio app.
"""
