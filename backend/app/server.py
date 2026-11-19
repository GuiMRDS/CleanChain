"""API do CleanChain.

    uv run uvicorn app.server:app --reload --port 8000

POST /api/chat         {"message", "thread_id", "ui_state"?}  →  NDJSON (eventos do agente + {"type":"ui"} / {"type":"approval"})
POST /api/chat/approval {"thread_id", "approve": bool}          →  NDJSON (retoma o agente após o usuário aprovar/recusar)
GET  /api/drives       →  discos locais [{root, letter, label, total, used, free}]
POST /api/scan         {"path": opcional}                      →  NDJSON: {"type":"progress",...}* → {"type":"result","scan":{...}}
POST /api/scan/cancel  →  interrompe o scan em andamento
POST /api/transcribe   multipart "audio"                       →  {"text": "..."} (voz → texto, Whisper na Groq/OpenAI)
GET  /api/scan/latest  →  último scan salvo (404 se ainda não houver)
GET  /api/folder/files?path=...&dirs=true  →  arquivos diretos (+ subpastas medidas) da pasta, só dentro da área escaneada
GET  /api/system       →  disco do sistema, RAM e temporários (rodapé)
GET  /api/health       →  {"ok": true, "model": "...", "home": "<pasta do usuário>"}
"""

from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from app.agent import build_agent
from app.drives import list_drives, memory, system_drive, temp_usage, used_bytes_for
from app.files import inside, list_files
from app.speech import transcribe_audio
from app.storage import load_latest, save_scan
from app.stream import stream_events
from app.tools.disk_scan import scan, scan_disk

app = FastAPI(title="CleanChain Agent")

# A API só atende a própria máquina: Host local (barra DNS rebinding) e, em requisições
# que mudam algo, Origin local (barra sites abertos no navegador chamando 127.0.0.1).
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(LOCAL_HOSTS))


@app.middleware("http")
async def only_local_origins(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        from urllib.parse import urlparse

        if (urlparse(origin).hostname or "") not in LOCAL_HOSTS:
            return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
    return await call_next(request)
agent, model_label = build_agent()  # um agente para o processo; a memória separa por thread_id

SCAN_DEPTH = 6  # níveis de pastas guardados no JSON (o sunburst desenha os 4 primeiros)
SCAN_TOP_N = 10  # maiores subpastas por pasta; o resto vira "outros"
SCAN_TIME_BUDGET_S = 30 * 60.0  # scan profundo: teto de segurança (o usuário pode cancelar antes)
FOLDER_DIRS_BUDGET_S = 8.0  # medição de subpastas ao abrir pastas fundas
NDJSON_HEADERS = {"Cache-Control": "no-cache"}


def _line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- chat


class UiState(BaseModel):
    open_folder: str | None = Field(default=None, max_length=1000)  # pasta aberta no sunburst


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(min_length=1, max_length=100)
    ui_state: UiState | None = None  # o que o usuário está vendo na tela


@app.get("/api/health")
def health():
    return {"ok": True, "model": model_label, "home": str(Path.home())}


@app.get("/api/system")
def system():
    """Dados reais do rodapé: disco do sistema, RAM e pasta de temporários."""
    return {"disk": system_drive(), "memory": memory(), "temp": temp_usage()}


@app.post("/api/chat")
def chat(req: ChatRequest):
    def ndjson():
        ui_state = req.ui_state.model_dump() if req.ui_state else None
        for event in stream_events(agent, req.message, req.thread_id, ui_state):
            yield _line(event)

    # Gerador síncrono: o FastAPI roda em thread separada, sem travar o servidor.
    return StreamingResponse(ndjson(), media_type="application/x-ndjson", headers=NDJSON_HEADERS)


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    approve: bool


@app.post("/api/chat/approval")
def chat_approval(req: ApprovalRequest):
    """Decisão do usuário sobre uma ação pausada (ex.: apagar arquivos)."""

    def ndjson():
        for event in stream_events(agent, None, req.thread_id, decision="approve" if req.approve else "reject"):
            yield _line(event)

    return StreamingResponse(ndjson(), media_type="application/x-ndjson", headers=NDJSON_HEADERS)


# ---------------------------------------------------------------- scan


class ScanRequest(BaseModel):
    path: str | None = Field(default=None, max_length=500)  # padrão: pasta do usuário


_scan_lock = threading.Lock()
_scan_stop: threading.Event | None = None  # scan em andamento (um por vez)


@app.get("/api/drives")
def drives():
    return {"drives": list_drives(), "home": str(Path.home())}


@app.post("/api/scan/cancel")
def cancel_scan():
    with _scan_lock:
        if _scan_stop:
            _scan_stop.set()
            return {"cancelled": True}
    return {"cancelled": False}


@app.post("/api/scan")
def run_scan(req: ScanRequest):
    global _scan_stop
    path = req.path or str(Path.home())
    events: queue.Queue = queue.Queue()
    stop = threading.Event()
    with _scan_lock:  # um novo scan interrompe o anterior
        if _scan_stop:
            _scan_stop.set()
        _scan_stop = stop
    expected = used_bytes_for(path)  # disco inteiro → dá para estimar o %

    def worker():
        global _scan_stop
        try:
            # Chama a ferramenta de scan; progresso, cancelamento e limites vão pela config.
            raw = scan_disk.invoke(
                {"path": path, "max_depth": SCAN_DEPTH},
                config={"configurable": {
                    "on_progress": lambda p: events.put({"type": "progress", **p}),
                    "time_budget_s": SCAN_TIME_BUDGET_S,
                    "top_n": SCAN_TOP_N,
                    "stop": stop,
                    "expected_bytes": expected,
                }},
            )
            result = json.loads(raw)
            if "error" in result:
                events.put({"type": "error", "text": result["error"]})
            elif result.get("cancelled"):
                events.put({"type": "cancelled"})  # não salva análise incompleta
            else:
                result["file"] = save_scan(result)
                events.put({"type": "result", "scan": result})
        except Exception as err:
            events.put({"type": "error", "text": f"{type(err).__name__}: {err}"})
        finally:
            with _scan_lock:
                if _scan_stop is stop:
                    _scan_stop = None
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def ndjson():
        yield _line({"type": "start", "path": path, "expected_bytes": expected})
        while (event := events.get()) is not None:
            yield _line(event)

    return StreamingResponse(ndjson(), media_type="application/x-ndjson", headers=NDJSON_HEADERS)


@app.get("/api/folder/files")
def folder_files(path: str, limit: int = 100, dirs: bool = False):
    """Arquivos diretos de uma pasta, do maior para o menor.

    Com dirs=true também mede as subpastas (scan rápido de 1 nível) — usado para pastas
    mais fundas do que o JSON do scan guarda. Só aceita pastas dentro da raiz do último scan.
    """
    latest = load_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="Nenhum scan salvo ainda.")
    root = os.path.normcase(os.path.realpath(latest["root"])).rstrip("\\/")
    target = os.path.realpath(path)
    if not inside(target, root):
        raise HTTPException(status_code=403, detail="Pasta fora da área escaneada.")
    if not os.path.isdir(target):
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")

    try:
        out = list_files(target, limit=limit)
    except OSError as err:
        raise HTTPException(status_code=403, detail=f"Sem permissão para ler a pasta: {err.strerror}") from err
    if dirs:
        sub = scan(target, max_depth=1, top_n=60, time_budget_s=FOLDER_DIRS_BUDGET_S)
        out["dirs"] = [
            {"name": c["name"], "path": c["path"], "bytes": c["bytes"], "files": c["files"]}
            for c in sub.get("tree", {}).get("children", [])
        ]
        out["partial"] = sub.get("partial", False)
    return out


@app.get("/api/scan/latest")
def latest_scan():
    scan_data = load_latest()
    if not scan_data:
        raise HTTPException(status_code=404, detail="Nenhum scan salvo ainda.")
    return scan_data


# ---------------------------------------------------------------- voz


MAX_AUDIO_BYTES = 20 * 1024**2


@app.post("/api/transcribe")
def transcribe(audio: UploadFile = File(...)):
    """Transcreve a fala do usuário (pt-BR) para o campo do chat."""
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Áudio vazio.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Áudio muito longo.")
    try:
        text = transcribe_audio(audio.filename or "fala.webm", data)
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err
    except Exception as err:  # erro do provedor (cota, formato de áudio…)
        raise HTTPException(status_code=502, detail=f"Falha na transcrição: {str(err)[:200]}") from err
    return {"text": text}
