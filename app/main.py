import json
import os
from pathlib import Path
from datetime import date

import fitz
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .database import Base, engine, get_db
from . import models, schemas
from .services import (
    analyze,
    generate_roadmap,
    recommend_projects,
    evaluate_answer,
    gemini_is_configured,
)

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "static"
UPLOAD_LIMIT = 5 * 1024 * 1024

# Load .env from the project root, not from whichever directory starts Uvicorn.
load_dotenv(BASE / ".env", override=False)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CareerPath AI",
    version="1.0.0",
    description="Student career development hackathon MVP",
)


@app.get("/api/health")
def health():
    configured = gemini_is_configured()
    return {
        "status": "ok",
        "ai_mode": "Gemini configured" if configured else "Local fallback",
        "ai_configured": configured,
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash") if configured else None,
    }


@app.post("/api/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF resume.")
    data = await file.read()
    if len(data) > UPLOAD_LIMIT:
        raise HTTPException(413, "PDF must be 5 MB or smaller.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception:
        raise HTTPException(400, "Could not read this PDF. Try exporting it again.")
    if not text.strip():
        raise HTTPException(400, "No selectable text found. Scanned PDFs are not supported in this MVP.")
    return {"filename": file.filename, "text": text[:20000]}


@app.post("/api/analyze")
def create_analysis(payload: schemas.AnalyzeRequest, db: Session = Depends(get_db)):
    result = analyze(payload.target_role, payload.job_description, payload.resume_text, payload.manual_skills)
    student = db.query(models.Student).first()
    if not student:
        student = models.Student(name=payload.name[:120], email="")
        db.add(student)
        db.flush()
    else:
        student.name = payload.name[:120]
    assessment = models.Assessment(
        student_id=student.id,
        target_role=payload.target_role,
        job_description=payload.job_description[:12000],
        resume_text=payload.resume_text[:20000],
        current_skills=json.dumps(result["current_skills"]),
        missing_skills=json.dumps(result["missing_skills"]),
        readiness_score=result["score"],
        analysis_json=json.dumps(result),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    result["assessment_id"] = assessment.id
    return result


@app.get("/api/analysis/latest")
def latest_analysis(db: Session = Depends(get_db)):
    item = db.query(models.Assessment).order_by(desc(models.Assessment.id)).first()
    if not item:
        return None
    return json.loads(item.analysis_json)


@app.post("/api/roadmap/generate")
def create_roadmap(db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).order_by(desc(models.Assessment.id)).first()
    if not assessment:
        raise HTTPException(400, "Run career analysis first.")
    for old in db.query(models.Task).filter_by(assessment_id=assessment.id).all():
        db.delete(old)
    data = json.loads(assessment.missing_skills)
    tasks = generate_roadmap(assessment.target_role, data)
    saved = []
    for t in tasks:
        task = models.Task(
            assessment_id=assessment.id,
            week_number=int(t.get("week", 1)),
            title=str(t.get("title", "Learning task"))[:240],
            description=str(t.get("description", ""))[:2000],
            resource=str(t.get("resource", ""))[:500],
        )
        db.add(task)
        db.flush()
        saved.append({
            "id": task.id,
            "week": task.week_number,
            "title": task.title,
            "description": task.description,
            "resource": task.resource,
            "status": task.status,
        })
    db.commit()
    return {"tasks": saved}


@app.get("/api/roadmap")
def get_roadmap(db: Session = Depends(get_db)):
    tasks = db.query(models.Task).order_by(models.Task.week_number, models.Task.id).all()
    return [{
        "id": t.id,
        "week": t.week_number,
        "title": t.title,
        "description": t.description,
        "resource": t.resource,
        "status": t.status,
    } for t in tasks]


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    if payload.status not in ["todo", "done"]:
        raise HTTPException(400, "Status must be todo or done.")
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found.")
    task.status = payload.status
    db.commit()
    return {"id": task.id, "status": task.status}


@app.get("/api/projects")
def projects(db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).order_by(desc(models.Assessment.id)).first()
    if not assessment:
        return {"projects": []}
    return {"projects": recommend_projects(assessment.target_role, json.loads(assessment.missing_skills))}


@app.post("/api/interview/evaluate")
def interview(payload: schemas.InterviewRequest, db: Session = Depends(get_db)):
    if len(payload.answer.strip()) < 10:
        raise HTTPException(400, "Write at least 10 characters before submitting.")
    try:
        result = evaluate_answer(payload.target_role, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    record = models.Interview(
        target_role=payload.target_role,
        question=payload.question,
        answer=payload.answer[:5000],
        score=result["score"],
        feedback=json.dumps(result),
    )
    db.add(record)
    db.commit()
    return result


@app.get("/api/interview/history")
def interview_history(db: Session = Depends(get_db)):
    rows = db.query(models.Interview).order_by(desc(models.Interview.id)).limit(20).all()
    return [{"id": x.id, "role": x.target_role, "question": x.question, "score": x.score} for x in rows]


@app.post("/api/applications")
def add_application(payload: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    if payload.status not in ["Saved", "Applied", "Interview", "Offer", "Rejected"]:
        raise HTTPException(400, "Invalid application status.")
    item = models.Application(
        company=payload.company[:180],
        position=payload.position[:180],
        status=payload.status,
        applied_date=payload.applied_date or date.today().isoformat(),
        notes=payload.notes[:2000],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "company": item.company,
        "position": item.position,
        "status": item.status,
        "applied_date": item.applied_date,
        "notes": item.notes,
    }


@app.get("/api/applications")
def list_applications(db: Session = Depends(get_db)):
    rows = db.query(models.Application).order_by(desc(models.Application.id)).all()
    return [{
        "id": x.id,
        "company": x.company,
        "position": x.position,
        "status": x.status,
        "applied_date": x.applied_date,
        "notes": x.notes,
    } for x in rows]


@app.patch("/api/applications/{application_id}")
def update_application(application_id: int, payload: schemas.ApplicationUpdate, db: Session = Depends(get_db)):
    item = db.get(models.Application, application_id)
    if not item:
        raise HTTPException(404, "Application not found.")
    if payload.status is not None:
        if payload.status not in ["Saved", "Applied", "Interview", "Offer", "Rejected"]:
            raise HTTPException(400, "Invalid application status.")
        item.status = payload.status
    if payload.notes is not None:
        item.notes = payload.notes[:2000]
    db.commit()
    return {"id": item.id, "status": item.status, "notes": item.notes}


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
