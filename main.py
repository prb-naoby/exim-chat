
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules import database, auth_utils
from modules.scheduler import start_scheduler, stop_scheduler
from api import routes
import os
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Initialize Database...")
    database.init_database()

    
    # Create default admin if not exists
    admin_user = database.get_user_by_username("admin")
    if not admin_user:
        print("Creating default admin user...")
        # Default password for admin - SHOULD BE CHANGED IN PRODUCTION
        admin_pwd = auth_utils.get_password_hash("admin123") 
        database.add_user("admin", admin_pwd, "admin")
        print("Admin user created (username: admin, password: admin123)")
    
    # Start ingestion scheduler
    print("Starting ingestion scheduler...")
    start_scheduler()
    print("Scheduler started - ingestion pipelines will run every 30 minutes")
    
    yield
    # Shutdown
    print("Stopping scheduler...")
    stop_scheduler()
    print("Shutting down...")

app = FastAPI(title="EXIM Chat API", lifespan=lifespan)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Mount Routes
app.include_router(routes.router)

@app.get("/")
async def root():
    return {"message": "Welcome to EXIM Chat API"}
