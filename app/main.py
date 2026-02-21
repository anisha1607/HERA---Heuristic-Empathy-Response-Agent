from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from app.bart_guard import BartGuard, REFUSAL
# from app.ollama_client import OllamaClient
from app.groq_client import GroqClient
from app.prompts import SYSTEM_PROMPT

load_dotenv()

app = FastAPI(title="HERA")

guard = BartGuard()
# ollama = OllamaClient()
groq = GroqClient()

# LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.1:latest")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class ChatRequest(BaseModel):
    situation: str


class ChatResponse(BaseModel):
    response: str
    refused: bool
    guard_label: str
    guard_confidence: float


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(WEB_DIR / "app.js")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    situation = (req.situation or "").strip()
    if not situation:
        return ChatResponse(
            response="Please describe the situation you observe (one or two sentences is enough).",
            refused=False,
            guard_label="IN_DOMAIN_COACHING",
            guard_confidence=1.0,
        )

    refuse, res = guard.should_refuse(situation)
    if refuse:
        return ChatResponse(
            response=REFUSAL,
            refused=True,
            guard_label=res.label,
            guard_confidence=res.confidence,
        )

    # Keep the user prompt short to reduce latency.
    user_payload = f"""
    Parent situation:
    {situation}

    Write a supportive response the parent can read and use.
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]

    # Your OllamaClient should put temperature/num_predict inside "options".
    try:
        # output = ollama.chat(
        #     model=LLAMA_MODEL,
        #     messages=messages,
        #     temperature=0.25,
        #     num_predict=180,   # prevents long generations + timeouts
        # )
        output = groq.chat(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.25,
            max_tokens=180,
        )
    except Exception as e:
        # print("OLLAMA ERROR:", repr(e))
        print("GROQ ERROR:", repr(e))
        output = (
            "A) Tone check: I’m having trouble generating right now.\n"
            "B) Needs guess: Parent need: clarity. Teen need: safety.\n"
            "C) De-escalated message to send: Could you try again in a moment?\n"
            "D) One optional follow-up question: What outcome matters most to you here?"
        )

    # Lightweight post-check (no regex): block clearly harmful instructions.
    lower = output.lower()
    forbidden = [
        "keylogger",
        "stalkerware",
        "hack",
        "steal password",
        "track gps without",
        "monitor secretly",
    ]
    if any(term in lower for term in forbidden):
        return ChatResponse(
            response=REFUSAL,
            refused=True,
            guard_label="POSTCHECK_BLOCK",
            guard_confidence=1.0,
        )

    return ChatResponse(
        response=output.strip(),
        refused=False,
        guard_label=res.label,
        guard_confidence=res.confidence,
    )


def run():
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)