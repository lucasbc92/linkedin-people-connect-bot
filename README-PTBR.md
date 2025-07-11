# LinkedIn People Connection Bot

Uma ferramenta de automação em Python que ajuda você a se conectar com pessoas no LinkedIn enviando solicitações de conexão personalizadas com mensagens customizadas.

## Recursos

- 🚀 **Solicitações de Conexão Automatizadas**: Envia automaticamente solicitações de conexão para perfis com botões "Conectar"
- 📝 **Mensagens Personalizadas**: Template de mensagem customizável com extração de nome para personalização
- 🏃‍♂️ **Modo de Conexão Rápida**: Opção para enviar solicitações de conexão sem nota para processamento mais rápido
- 🛡️ **Proteção contra Limite de Convites**: Detecta e gerencia automaticamente os limites de convite do LinkedIn
- 👥 **Automação de Seguir**: Também segue perfis que têm botões "Seguir"
- 🔄 **Navegação Multi-página**: Processa automaticamente múltiplas páginas de resultados de busca
- 🔙 **Navegação Bidirecional**: Pode navegar para frente e para trás pelos resultados de busca
- 🎯 **Segmentação Inteligente**: Funciona com resultados de busca do LinkedIn para segmentar perfis específicos
- ⚡ **Suporte a Navegador Existente**: Pode funcionar com sua sessão do LinkedIn já aberta

## Pré-requisitos

- Python 3.7+
- Navegador Chrome
- ChromeDriver (gerenciado automaticamente pelo selenium)
- Conta ativa do LinkedIn

## Instalação

1. Clone este repositório:
```bash
git clone https://github.com/yourusername/linkedin-people-connection-bot.git
cd linkedin-people-connection-bot
```

2. Crie um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

### Método 1: Usando Sessão de Navegador Existente (Recomendado)

1. **Abra o Chrome com depuração habilitada**:
```bash
# No macOS/Linux:
google-chrome --remote-debugging-port=9222 --user-data-dir="$(mktemp -d)"

# No Windows:
chrome.exe --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome_debug"
```

2. **Navegue para o LinkedIn** no navegador aberto e faça login

3. **Realize sua busca** (ex: busque por "recrutador tech", "engenheiro de software", ou qualquer outro profissional que você queira se conectar)

4. **Execute a automação**:
```bash
python main.py
```

### Método 2: Nova Sessão de Navegador

Simplesmente execute o script sem a configuração de depuração:
```bash
python main.py
```

O script abrirá uma nova janela do Chrome onde você precisará fazer login manualmente e navegar até seus resultados de busca.

## Opções de Linha de Comando

- `-y`, `--yes`: Continua automaticamente além dos avisos de "próximo ao limite" (ainda para no limite máximo)
- `-m`, `--message`: Caminho para o arquivo de template de mensagem (padrão: message.txt)
- `-r`, `--reverse`: Navega em ordem reversa (usa o botão Anterior em vez de Próximo)
- `-n`, `--no-message`: Envia convites sem uma nota (processamento mais rápido)

Exemplos:
```bash
python main.py -y
python main.py -m custom_message.txt
python main.py -r  # Navega em ordem reversa (dos resultados mais recentes para os mais antigos)
python main.py -n  # Envia solicitações de conexão sem nota
python main.py -y -m my_template.txt -r
python main.py -y -n -r  # Continua automaticamente, sem notas, navegação reversa
```

## Customização de Mensagem

O template de mensagem é carregado do arquivo `message.txt` e pode ser customizado editando este arquivo:

```
Olá, {name}!
Sou Full Stack Developer focado em backend com 5+ anos de experiência, sendo os últimos 3 anos em Java Spring & React. Apaixonado por café, simplificar problemas complexos e entregar soluções robustas.
Espero que meu perfil desperte seu interesse!
```

### Recursos do Template:
- **Personalização de Nome**: Use `{name}` em qualquer lugar da mensagem para inserir o primeiro nome do destinatário
- **Limite de Caracteres**: Mensagens são automaticamente truncadas para 300 caracteres (limite do LinkedIn)
- **Fallback**: Se a extração de nome falhar, `{name}` é substituído por uma string vazia

### Exemplos:
- `"Olá {name}!"` → `"Olá João!"`
- `"Oi {name}, espero que esteja bem!"` → `"Oi Maria, espero que esteja bem!"`
- Se o nome não for encontrado: `"Olá {name}!"` → `"Olá !"`

## Recursos de Segurança

### Proteção contra Limite de Convites
- **Aviso Suave**: Quando próximo ao limite semanal, pede confirmação do usuário (a menos que a flag `-y` seja usada)
- **Limite Rígido**: Para automaticamente quando o limite semanal de convites é atingido
- **Verificação**: Confirma que cada convite foi enviado com sucesso antes de prosseguir

### Comportamento Humanizado
- Delays aleatórios entre ações (1-5 segundos)
- Rolagem para elementos antes de clicar
- Cliques baseados em JavaScript para evitar detecção

## Como Funciona

1. **Processamento de Página**: Escaneia a página atual em busca de botões "Conectar"
2. **Extração de Nome**: Tenta extrair o nome do destinatário do perfil
3. **Solicitação de Conexão**:
   - Com notas: Clica "Conectar" → "Adicionar nota" → preenche mensagem personalizada → envia
   - Sem notas: Clica "Conectar" → "Enviar sem nota" (quando a flag `-n` é usada)
4. **Seguindo**: Clica em qualquer botão "Seguir" na página
5. **Navegação**: Move para a próxima página (ou página anterior com a flag `-r`) de resultados
6. **Repetir**: Continua até que todas as páginas sejam processadas ou limites sejam atingidos

## Melhores Práticas

1. **Use Limites Conservadores**: Não exceda os limites semanais de convite do LinkedIn
2. **Personalize Mensagens**: Customize o template de mensagem para seu caso específico
3. **Segmente Especificamente**: Use os filtros de busca do LinkedIn para segmentar perfis relevantes
4. **Monitore o Uso**: Acompanhe sua contagem semanal de convites
5. **Respeite os Termos do LinkedIn**: Use esta ferramenta responsavelmente e de acordo com os termos de serviço do LinkedIn

## Solução de Problemas

### Problemas Comuns

1. **Problemas com ChromeDriver**:
   - Certifique-se de que o navegador Chrome está instalado
   - O script usa o gerenciamento integrado de ChromeDriver do selenium

2. **Falhas de Conexão**:
   - Verifique sua conexão com a internet
   - Verifique se você está logado no LinkedIn
   - Certifique-se de que a página de resultados de busca está carregada

3. **Elemento Não Encontrado**:
   - A interface do LinkedIn pode ter mudado
   - Tente atualizar a página e executar novamente

### Modo de Depuração

Adicione declarações print ou modifique o logging para ver o que está acontecendo:
```python
print(f"Processando botão {i+1}: {button.text}")
```

## Limitações

- O LinkedIn limita convites a ~100 por semana para contas gratuitas
- O script funciona com a interface atual do LinkedIn (sujeito a mudanças)
- Pode não funcionar com todos os layouts de página do LinkedIn
- Projetado para a interface desktop do LinkedIn

## Contribuindo

1. Faça um fork do repositório
2. Crie uma branch de feature
3. Faça suas alterações
4. Adicione testes se aplicável
5. Envie um pull request

## Aviso Legal

Esta ferramenta é apenas para uso educacional e pessoal. Os usuários são responsáveis por cumprir os Termos de Serviço do LinkedIn e leis aplicáveis. Os autores não são responsáveis por qualquer uso indevido ou consequências resultantes do uso desta ferramenta.

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.

## Suporte

Se você encontrar problemas ou tiver dúvidas, por favor abra uma issue no GitHub.