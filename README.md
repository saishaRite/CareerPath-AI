# CareerPath AI

A runnable hackathon MVP for students: resume parsing, target-role/job-description skill-gap analysis, a weekly roadmap, project suggestions, mock interview feedback, progress tracking, and an application tracker.

## Stack
- FastAPI backend
- SQLite database (created automatically)
- Plain HTML/CSS/JavaScript frontend (no Node build required)
- Optional Gemini API integration; deterministic demo mode works without an API key

## Run on Windows (VS Code terminal / PowerShell)

1. Extract this ZIP and open the `careerpath-ai` folder in VS Code.
2. Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:
```powershell
pip install -r requirements.txt
```

4. Optional: copy `.env.example` to `.env` and add your Gemini API key. Never commit `.env`.
   Without a key, the app uses demo-mode analysis so you can still demonstrate the full workflow.

5. Start the app:
```powershell
uvicorn app.main:app --reload
```

6. Open http://127.0.0.1:8000
7. API documentation: http://127.0.0.1:8000/docs

## First demo workflow
1. Enter a student name and target role.
2. Paste a real job description.
3. Upload a PDF resume (or skip it and enter skills manually).
4. Click **Analyze my career fit**.
5. Generate the roadmap, complete tasks, try the interview coach, and add an application.

## Notes / limitations
- This is a hackathon prototype, not a production recruitment or employment assessment system.
- Demo mode uses transparent keyword-based heuristics. Gemini mode enhances explanations and structured recommendations.
- The readiness score is an indicative product metric, not a hiring probability.
- Local SQLite data is stored in `careerpath.db`.
- Resume files are processed for text extraction and not retained by default.
- Add authentication, cloud database, rate limits, malware scanning, privacy policy, and stronger authorization before real public use.
