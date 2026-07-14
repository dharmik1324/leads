import sys
import os
import uuid
import threading
import pandas as pd
import io
from typing import Dict, List, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure the backend directory is in the Python search path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from scraper import scrape_maps_leads
from google_sheets import upload_leads_to_google_sheet

app = FastAPI(title="LeadScout AI API", version="1.0.0")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for scraping tasks
tasks: Dict[str, Dict[str, Any]] = {}

class ScrapeRequest(BaseModel):
    query: str
    limit: int = 20

class ExportRequest(BaseModel):
    task_id: str
    spreadsheet_name: str
    sheet_name: str = "Sheet1"

def run_scraper(task_id: str, query: str, limit: int):
    tasks[task_id]["logs"].append("Initializing Playwright browser agent...")
    
    def log_callback(message: str):
        tasks[task_id]["logs"].append(message)
        
    def stop_check_callback():
        return tasks[task_id].get("stop_requested", False)
        
    try:
        leads = scrape_maps_leads(
            query, 
            max_results=limit, 
            log_callback=log_callback, 
            stop_check_callback=stop_check_callback
        )
        tasks[task_id]["leads"] = leads
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["logs"].append(f"✨ Task finished successfully! Found {len(leads)} website-less business leads.")
    except InterruptedError:
        tasks[task_id]["status"] = "stopped"
        tasks[task_id]["logs"].append("🛑 Scraping task stopped by user.")
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["logs"].append(f"❌ Critical error during scraping: {str(e)}")

@app.post("/api/scrape")
def start_scrape(payload: ScrapeRequest):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id,
        "query": payload.query,
        "limit": payload.limit,
        "status": "running",
        "stop_requested": False,
        "logs": [f"🚀 Starting scraper task for query: '{payload.query}' (Max scan limit: {payload.limit})"],
        "leads": []
    }
    
    # Start the scraper in a separate thread to prevent blocking the event loop
    thread = threading.Thread(target=run_scraper, args=(task_id, payload.query, payload.limit))
    thread.daemon = True
    thread.start()
    
    return {"task_id": task_id, "status": "started"}

@app.post("/api/stop/{task_id}")
def stop_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    if tasks[task_id]["status"] != "running":
        return {"success": False, "message": "Task is not currently running."}
        
    tasks[task_id]["stop_requested"] = True
    tasks[task_id]["logs"].append("🛑 Stop request received. Aborting agent execution...")
    return {"success": True, "message": "Cancellation request submitted."}

@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    task = tasks[task_id]
    return {
        "task_id": task_id,
        "status": task["status"],
        "logs": task["logs"],
        "leads_count": len(task["leads"]),
        "leads": task["leads"]
    }

@app.get("/api/download/{task_id}")
def download_leads_csv(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    task = tasks[task_id]
    if not task["leads"]:
        raise HTTPException(status_code=400, detail="No leads data available for download.")
    
    df = pd.DataFrame(task["leads"])
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = Response(content=stream.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=leads_{task_id}.csv"
    return response

@app.post("/api/export")
def export_to_sheets(payload: ExportRequest):
    if payload.task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    task = tasks[payload.task_id]
    if not task["leads"]:
        raise HTTPException(status_code=400, detail="No leads data available to export.")
    
    df = pd.DataFrame(task["leads"])
    
    # Look for credentials.json in either the project root or the backend directory
    possible_creds = [
        os.path.join(os.path.dirname(backend_dir), "credentials.json"),
        os.path.join(backend_dir, "credentials.json"),
        "credentials.json"
    ]
    
    credentials_path = None
    for path in possible_creds:
        if os.path.exists(path):
            credentials_path = path
            break
            
    if not credentials_path:
        return {
            "success": False,
            "message": "Google Service Account 'credentials.json' not found in project root or backend/ directories."
        }
        
    logs_output = []
    def export_log(msg):
        logs_output.append(msg)
        
    success = upload_leads_to_google_sheet(
        df=df,
        spreadsheet_name=payload.spreadsheet_name,
        credentials_path=credentials_path,
        sheet_name=payload.sheet_name,
        log_callback=export_log
    )
    
    return {
        "success": success,
        "message": "\n".join(logs_output)
    }

# Mount static files folder to serve the frontend (must be registered last)
frontend_dir = os.path.join(os.path.dirname(backend_dir), "frontend")
dist_dir = os.path.join(frontend_dir, "dist")
if os.path.exists(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
elif os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
