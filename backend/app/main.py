from fastapi import FastAPI

app = FastAPI(
    title="CareRelay API",
    description="Backend API for the CareRelay home-care handoff system.",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "CareRelay API is running",
        "status": "ok"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
