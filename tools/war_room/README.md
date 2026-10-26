# 🎙️ Squad War Room • Tech Jobs Radar

Ambiente apartado para condução de ritos ágeis da Squad (@SM, @TL, @QA, @PO) com **Zero Consumo de Cota do Antigravity**, **Zero Tokens de Áudio**, **Vozes Neurais Brasileiras Gratuitas (`edge-tts`)** e sincronização bidirecional em tempo real com o **Obsidian Vault**.

---

## 🏗️ Arquitetura & Especificações Técnicas

### 1. Zero Cota & Zero Tokens de Áudio
- **TTS (Agentes):** Microsoft `edge-tts` com 4 vozes neurais brasileiras ultra-naturais:
  - `📋 @SM` (Scrum Master): `pt-BR-FranciscaNeural` (`rate: +8%`)
  - `👨‍💻 @TL` (Tech Lead EY): `pt-BR-AntonioNeural` (`rate: +5%`)
  - `🧪 @QA` (Data Quality): `pt-BR-AntonioNeural` (`pitch: -14Hz`, `rate: +7%` — timbre grave analítico)
  - `🎯 @PO` (Product Owner EY): `pt-BR-ThalitaMultilingualNeural` (`rate: +5%`)
- **STT (Desenvolvedor):** Web Speech API nativa do navegador (`webkitSpeechRecognition`, `lang: pt-BR`), com Push-to-Talk via botão ou atalho no teclado (segurar **Barra de Espaço**).
- **Barge-in Instantâneo:** Se o usuário clicar em **⏹️ Calar Agente** ou começar a falar no microfone, qualquer áudio do agente em reprodução é interrompido imediatamente.

### 2. Amarração de Modelos & Níveis de Raciocínio (`ThinkingConfig`)
Cada agente opera com seu modelo e orçamento de tokens de raciocínio amarrados estritamente ao seu papel:
- **`@SM`**: `gemini-2.5-flash` | `thinking_budget: 0` (ou LOW) — Resposta ultra-rápida (<1s) para Daily e Planning.
- **`@QA`**: `gemini-2.5-flash` | `thinking_budget: 2048` (MEDIUM) — Crivo das 7 heurísticas adversariais e testes de idempotência.
- **`@PO`**: `gemini-2.5-flash` | `thinking_budget: 2048` (MEDIUM) — Geração de bullets Google XYZ e casos STAR.
- **`@TL`**: `gemini-2.5-flash` | `thinking_budget: 4096` (HIGH) — Design review socrático e sabatina técnica EY (Big 4 DNA).

### 3. Modo Dual Output
O retorno é sempre dividido em:
- `spoken_reply`: Fala coloquial direta (2 a 4 frases, sintetizada em voz neural).
- `markdown_notes`: Notas técnicas completas no painel de anotações (perguntas socráticas, checklists de DoD/DoR, bullets STAR).
- `board_action`: Ação opcional para atualizar o status de tickets no arquivo `Sprint Ativa.md` do Obsidian.

### 4. Modo Local / Fallback Offline Inteligente
Se nenhuma `GEMINI_API_KEY` estiver configurada no `.env`, o servidor não quebra; ativa o **Motor de Ritos Local**, que lê o `Sprint Ativa.md`, conduz os 6 ritos da Squad e sintetiza todas as vozes neurais normalmente!

---

## 🚀 Como Iniciar

Execute o script de inicialização rápida:

```bash
cd /home/nova/Projetos-Pessoais/tech-jobs-radar/tools/war_room
./start_war_room.sh
```

Acesse no seu navegador: **`http://localhost:8765`**

---

## 🧪 Suíte de Testes Automatizados

Para rodar os testes com `pytest`:

```bash
cd /home/nova/Projetos-Pessoais/tech-jobs-radar/tools/war_room
pytest test_war_room.py -v
```

---

## 📁 Estrutura de Arquivos

```
tools/war_room/
├── server.py              # Backend FastAPI com endpoints REST e TTS
├── chat_engine.py         # Orquestrador de agentes com ThinkingConfig e Dual Output
├── tts_service.py         # Síntese edge-tts com vozes pt-BR, pitch e cache em disco
├── obsidian_manager.py    # Leitura e sincronização bidirecional do Obsidian Vault
├── requirements.txt       # Dependências Python
├── start_war_room.sh      # Script bash de inicialização (executável)
├── test_war_room.py       # Suíte de testes automatizados (pytest)
└── static/
    ├── index.html         # Interface Dark Mode executivo (layout 3 colunas)
    ├── style.css          # Estilos com soundwaves animadas e tema executivo
    └── app.js             # Lógica cliente (Web Speech API, TTS, Push-to-Talk, Barge-in)
```
