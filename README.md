# Captura de Leads — Epiq / ForExperts

## O que este projeto faz
- Uma única tela para o funcionário capturar dados do lead (foto do crachá com preenchimento automático, campos editáveis, gravação de voz transcrita, tags de interesse, classificação A/B/C/D).
- Uma tela de cadastro (`/cadastro.html`) onde cada funcionário edita seus próprios dados e foto.
- Ao salvar o lead: envia e-mail (com o PDF do folder) pelo Brevo, saindo com o e-mail do funcionário como remetente, e envia o mesmo PDF + o contato (vCard) do funcionário pelo WhatsApp via Evolution API.

## Passo a passo para publicar (Railway)

### 1. Criar o repositório no GitHub
Suba esta pasta inteira para um novo repositório em `massardfreeagents` (ex: `epiq-leads-feira`).

### 2. Criar o serviço no Railway
1. No Railway, "New Project" → "Deploy from GitHub repo" → selecione o repositório.
2. Em **Settings → Root Directory**, aponte para `/backend`.
3. Em **Settings → Start Command**, use:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

### 3. Adicionar um banco Postgres
No mesmo projeto Railway: "New" → "Database" → "PostgreSQL". Ele já injeta a variável `DATABASE_URL` automaticamente no serviço se estiverem no mesmo projeto (confirme em Variables).

### 4. Configurar as variáveis de ambiente
Em **Variables** do serviço backend, adicione (veja `.env.example`):
- `GEMINI_API_KEY` — mesma chave usada no expense-agent
- `GROQ_API_KEY` — mesma chave usada no ComplianceMessage_Whatsapp
- `BREVO_API_KEY` — sua chave da conta Brevo
- `EVOLUTION_BASE_URL`, `EVOLUTION_INSTANCE`, `EVOLUTION_API_KEY` — mesmos do ComplianceMessage_Whatsapp
- `FOLDER_PDF_PATH=folder_temp.pdf` (deixe assim por enquanto)

### 5. Subir o PDF temporário do folder
Coloque o arquivo do folder na pasta `/backend` com o nome `folder_temp.pdf` antes de fazer o commit (ou suba depois via um redeploy). Assim que você tiver o PDF definitivo, é só substituir o arquivo e reiniciar o serviço.

### 6. Verificar remetentes no Brevo (IMPORTANTE — fazer antes da feira)
No painel do Brevo → **Senders, Domains & Dedicated IPs → Senders → Add a Sender**, cadastre os 6 e-mails abaixo. O Brevo manda um e-mail de confirmação para cada um — cada funcionário precisa clicar no link de confirmação usando o próprio e-mail da Epiq:

- bruno.massard@epiqglobal.com
- yuri.medeiros@epiqglobal.com
- barbara.andrade@epiqglobal.com
- andre.moreira@epiqglobal.com
- rafael.nakashima@epiqglobal.com
- thiago.casagrande@epiqglobal.com

**Sem essa verificação, o envio de e-mail falha.** Faça isso o quanto antes — pode levar um tempo até todos confirmarem.

### 7. Rodar o script de cadastro dos funcionários
No Railway, abra o terminal do serviço (ou rode localmente com `DATABASE_URL` configurada) e execute:
```
python seed_employees.py
```
Isso cadastra os 6 funcionários no banco (nome, e-mail, telefone).

### 8. Testar
Acesse a URL pública que o Railway gerar para o serviço. Adicione à tela de início do celular (Safari: compartilhar → "Adicionar à Tela de Início"; Chrome Android: menu → "Adicionar à tela inicial") para abrir como se fosse um app.

## Pontos de atenção
- **WhatsApp**: adicione um intervalo entre disparos em massa se for reenviar para muitos leads de uma vez — o número já teve restrição temporária em testes anteriores. Este app dispara 1 lead por vez (uso normal em feira), então o risco é baixo, mas evite testar em rajada.
- **Nomes dos endpoints da Evolution API** (`sendMedia`, `sendContact`) podem variar conforme a versão da sua instância — se der erro 404 nesses envios, me avise o retorno exato que eu ajusto.
- **E-mail pode cair em spam** — o domínio epiqglobal.com não autoriza o Brevo via SPF/DKIM, então isso é esperado (você já estava ciente).
