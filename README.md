# HERA — Empathy Coach (BART Guard + Llama via Groq)

HERA helps parents turn an **observed situation** into a calm, de-escalated message they can send to their teen using Non-Violent Communication.

The app uses a **safety guard + LLM pipeline**:
1) A BART zero-shot classifier filters unsafe or out-of-scope requests  
2) A Llama model (via Groq) generates the empathetic response  
3) A lightweight post-check blocks harmful instructions

---

## ✨ What the App Does

**Input:**  
One or two sentences describing a parent-teen situation you observed.

**Output:**  
A short empathetic coaching response that:
- acknowledges the parent’s feelings  
- infers the teen’s underlying needs  
- produces a ready-to-send de-escalated message  
- optionally asks one gentle reflection question

**Automatic refusal for:**
- spying / hacking / monitoring requests  
- legal advice  
- medical diagnosis  
- harmful or adversarial content  

If detected, the app returns a scripted refusal message.

## Tech
- Backend: FastAPI
- Frontend: Simple HTML/JS
- Pre-LLM backstop: **BART MNLI** zero-shot classifier (`facebook/bart-large-mnli`)
- Generator LLM: **Llama** via Groq (OpenAI-compatible chat completions API)
- Package manager: **uv**

## Setup
1) Create env
Create a `.env` file (in the project root) with at least:
```bash
GROQ_API_KEY=YOUR_KEY_HERE
```

Optional:
```bash
GROQ_MODEL=llama-3.1-8b-instant
GUARD_THRESHOLD=0.60
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

2) Install dependencies
```bash
uv venv
uv pip install fastapi uvicorn python-dotenv transformers torch requests pydantic
```

3) Run the app
```bash
uv run uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000

## Notes on GCP deployment
- Run FastAPI on Cloud Run or a VM.
- The LLM runs via Groq; set `GROQ_API_KEY` (and optionally `GROQ_MODEL`) as environment variables in your deployment.
- The BART guard runs on CPU (latency will be higher); GPU improves speed.
