from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import db
from app.routers import auth_router, courses_router, exams_router, payments_router, admin_router, blog_router, about_router, subscriptions_router, testimonials_router, interview_router, learning_paths_router

app = FastAPI(title="Network Design Labs Platform API", version="1.0.0")

import os

# Parse allowed origins from environment or use defaults
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,https://robiulsunnyemon.github.io")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    if db.is_connected():
        await db.disconnect()

# Include routers
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(courses_router.router, prefix="/api/courses", tags=["Courses"])
app.include_router(exams_router.router, prefix="/api/exams", tags=["Practice Exams"])
app.include_router(payments_router.router, prefix="/api/payments", tags=["Payments"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin Operations"])
app.include_router(blog_router.router, prefix="/api/blog", tags=["Blog"])
app.include_router(about_router.router, prefix="/api/about", tags=["About Content"])
app.include_router(subscriptions_router.router, prefix="/api/subscriptions", tags=["Subscription Plans"])
app.include_router(testimonials_router.router, prefix="/api/testimonials", tags=["Testimonials"])
app.include_router(interview_router.router, prefix="/api/interviews", tags=["Interview Questions"])
app.include_router(learning_paths_router.router, prefix="/api/learning-paths", tags=["Learning Paths"])

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "database": db.is_connected()}