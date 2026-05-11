# Variabili d'ambiente Railway

Imposta queste variabili nella sezione **Variables** del progetto Railway.

## Obbligatorie

| Variabile | Esempio | Note |
|-----------|---------|------|
| `CLAUDE_API_KEY` | `sk-ant-...` | Chiave API Anthropic |
| `JWT_SECRET` | stringa random 32+ char | Usare `openssl rand -hex 32` |

## Opzionali

| Variabile | Default | Note |
|-----------|---------|------|
| `AI_MODEL` | `claude` | `claude` oppure `deepseek` |
| `JWT_EXPIRE_DAYS` | `30` | Scadenza token JWT |
| `DEEPSEEK_API_KEY` | — | Obbligatoria solo se `AI_MODEL=deepseek` |
| `TAVILY_API_KEY` | — | Obbligatoria solo se `SEARCH_ENABLED=true` |
| `SEARCH_ENABLED` | `false` | Abilita ricerca web via Tavily |
| `ALLOWED_ORIGINS` | `http://localhost:8000,http://localhost:3000` | Origini CORS consentite, separate da virgola. Aggiungere URL Vercel dopo deploy. |

## Database

| Variabile | Note |
|-----------|------|
| `DATABASE_URL` | Railway la genera automaticamente se aggiungi il plugin **PostgreSQL**. Senza plugin, l'app usa SQLite locale (dati non persistenti tra redeploy). |

> **Nota:** Railway fornisce `DATABASE_URL` nel formato `postgres://...`. Il codice la converte automaticamente in `postgresql+asyncpg://` per SQLAlchemy.

## Upload files

Railway ha filesystem effimero: gli upload si perdono al restart/redeploy. Per produzione reale usare Cloudflare R2 o AWS S3. Per test con il primo cliente il filesystem locale è sufficiente.
