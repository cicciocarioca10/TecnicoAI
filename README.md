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

## Tipi di schema supportati

Clicca il pulsante 📐 nella barra di input per generare uno schema tecnico.

| Tipo | Dominio | Motore | Formato |
|------|---------|--------|---------|
| ⚡ Elettrico | `elettrico` | SVG / Graphviz | A4 / A3 |
| 🔧 PLC/Controllo | `plc` | Graphviz | A3 PDF |
| 💨 Pneumatico | `pneumatico` | SVG / Graphviz | A4 / A3 |
| 💧 Idraulico | `idraulico` | SVG / Graphviz | A4 / A3 |
| ⚙️ Meccatronico | `meccatronico` | Graphviz | A3 PDF |
| 🌐 Fieldbus | `fieldbus` | Graphviz | A3 PDF |
| 🛡️ Safety | `safety` | Graphviz | A3 PDF |
| 🤖 Auto | `auto` | Automatico | - |

**Come funziona:** TecnicoAI analizza la conversazione e sceglie automaticamente il motore di rendering:
- **Schema semplice (SVG):** per impianti civili e automazioni con meno di 15 componenti
- **Schema industriale (Graphviz):** per PLC, MCC, robotica, magazzini automatici e impianti complessi

### Esempi di prompt per ogni dominio

**Cella robotica pick & place:**
```
Ho una cella robotica pick&place con robot KUKA a 6 assi, due cilindri pneumatici per gripper,
safety fence con scanner laser SICK, PLC Siemens S7-1500 in modalità PROFINET,
inverter per nastro di alimentazione 400V 5.5kW. Crea lo schema.
```

**Magazzino automatico con trasportatori:**
```
Magazzino automatico con 3 trasportatori a rulli 400V, 2 sollevatori servo-motorizzati,
PLC Allen-Bradley ControlLogix, rete EtherNet/IP, lettori barcode, sensori finecorsa
induttivi, quadro MCC con 8 inverter Danfoss. Genera lo schema di automazione.
```

**Quadro MCC 400V con 8 motori:**
```
Quadro MCC 400V con 8 utenze motore da 1.5 a 22kW, interruttori motorizzati ABB,
contattori con relè termici, 3 inverter per pompe variabili, misuratore di energia
multimetro Schneider PM5100, PLC di supervisione con Modbus TCP. Schema elettrico.
```

**Circuito pneumatico:**
```
Impianto pneumatico per pressa industriale: compressore 10bar, serbatoio 200L,
essiccatore, FRL, valvola proporzionale 5/2 Festo per cilindro principale 100x400mm,
4 cilindri di bloccaggio 50x200mm con valvole 5/2 a solenoide, pressostati di controllo.
```

## Installazione dipendenze sistema (per rendering schemi)

```bash
# Linux / WSL2 (Ubuntu)
sudo apt-get install -y graphviz libcairo2-dev libpango1.0-dev

# macOS
brew install graphviz cairo pango

# Windows
choco install graphviz
```
