# Wiring Diagram Extraction Platform

This project delivers a working MVP for automotive electrical wiring diagram extraction and technical validation.

## Architecture

- Frontend: React + Vite + Tailwind
- Backend: FastAPI + SQLModel + SQLite
- Processing: document parsing, OCR fallback, connectivity heuristics, validation rules

## Quick start

1. Create and activate a Python environment.
2. Install backend dependencies: `pip install -r backend/requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Run backend: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
5. Run frontend: `cd frontend && npm run dev`

## Key capability

- Upload PDF and image documents
- Extract text and create a structured extraction summary
- Save connection candidates to SQLite
- Validate basic wiring issues and export JSON payloads

## Notes

This is an MVP designed to be extended with more accurate computer-vision and AI-based pin-to-pin tracing.
