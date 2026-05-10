# TecnicoAI

Chatbot AI per tecnici elettricisti e meccanici italiani. Prima di rispondere a domande tecniche, l'AI chiede informazioni di chiarimento (tensione di rete, potenza, ambiente, ecc.) per fornire risposte precise e conformi alle normative CEI/IEC.

## Avvio in locale

```bash
git clone https://github.com/cicciocarioca10/TecnicoAI.git
cd TecnicoAI

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Modifica .env con le tue chiavi API

uvicorn main:app --reload
```

API disponibile su `http://localhost:8000` · Docs su `http://localhost:8000/docs`

Apri `frontend/index.html` nel browser (file locale o via un server statico).

## Variabili d'ambiente

Crea un file `.env` nella root del progetto:

```env
CLAUDE_API_KEY=sk-ant-...      # Chiave API Anthropic (obbligatoria per modello claude)
DEEPSEEK_API_KEY=sk-...        # Chiave API DeepSeek (obbligatoria per modello deepseek)
AI_MODEL=claude                # Modello di default: "claude" oppure "deepseek"
```

## Deploy

### Backend → Railway

1. Crea un account su [railway.app](https://railway.app) e collega il repository GitHub
2. Railway rileva automaticamente `railway.json` e `Procfile`
3. Imposta le variabili d'ambiente nella sezione *Variables* del progetto Railway:
   - `CLAUDE_API_KEY`
   - `DEEPSEEK_API_KEY`
   - `AI_MODEL`
4. Railway assegna un URL pubblico tipo `https://tecnicoai-production.up.railway.app`

### Frontend → Vercel

1. Crea un account su [vercel.com](https://vercel.com) e importa il repository
2. Imposta la *Root Directory* su `frontend`
3. Deploy type: **Static** (nessun build necessario)
4. Prima del deploy, modifica `BACKEND_URL` in `frontend/index.html`:
   ```js
   const BACKEND_URL = 'https://tecnicoai-production.up.railway.app';
   ```
5. Vercel pubblica il frontend e aggiorna automaticamente ad ogni push

## Cambiare modello AI

Nel file `.env` (locale) o nelle variabili Railway (produzione):

```env
AI_MODEL=deepseek   # usa DeepSeek
AI_MODEL=claude     # usa Claude (default)
```

Il modello può anche essere selezionato per-richiesta tramite API: aggiungi `"model": "deepseek"` nel body della chiamata a `/api/chat`.

## Test

```bash
pytest tests/ -v
```

37 test coprono le API REST, il servizio AI (mock) e il question engine.
