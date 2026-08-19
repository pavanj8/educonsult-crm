from fastapi import FastAPI

app = FastAPI(title="EduConsult CRM")


@app.get("/health")
def health():
    return {"status": "ok"}
