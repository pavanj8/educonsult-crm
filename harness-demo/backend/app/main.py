from email_validator import EmailNotValidError, validate_email
from fastapi import Depends, FastAPI, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student Registration API")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/students/register", response_model=schemas.StudentOut, status_code=201)
def register_student(payload: schemas.StudentCreate, db: Session = Depends(get_db)):
    try:
        validate_email(payload.email, check_deliverability=False)
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email format")

    existing = db.query(models.Student).filter(models.Student.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    student = models.Student(
        name=payload.name,
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
        age=payload.age,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/students/{student_id}", response_model=schemas.StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@app.get("/students", response_model=list[schemas.StudentOut])
def list_students(db: Session = Depends(get_db)):
    return db.query(models.Student).order_by(models.Student.id).all()
