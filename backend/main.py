import os
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from database import get_db_connection
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user_id
)

def get_real_client_ip(request: Request) -> str:
    # Handle X-Forwarded-For if behind a reverse proxy/load balancer
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

# Set up rate limiter with reverse proxy IP support
limiter = Limiter(key_func=get_real_client_ip)
app = FastAPI(title="Job Application Tracker")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get(
        "ALLOWED_ORIGINS", "https://application-tracker-iota.vercel.app"
    ).split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)

COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "True").lower() == "true"

# Pydantic Schemas
class UserAuth(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

class ApplicationCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = "wishlist"
    date_applied: Optional[date] = None
    link: Optional[str] = Field(None, max_length=2048)
    notes: Optional[str] = Field(None, max_length=5000)

class ApplicationUpdate(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = Field(None, max_length=255)
    status: str
    date_applied: Optional[date] = None
    link: Optional[str] = Field(None, max_length=2048)
    notes: Optional[str] = Field(None, max_length=5000)

# Middleware for standard security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com;"
    )
    return response

# Serve Frontend Pages and Assets
@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("frontend/index.html")

@app.get("/login", response_class=HTMLResponse)
async def read_login():
    return FileResponse("frontend/login.html")

@app.get("/signup", response_class=HTMLResponse)
async def read_signup():
    return FileResponse("frontend/signup.html")

@app.get("/style.css")
async def get_css():
    return FileResponse("frontend/style.css")

@app.get("/app.js")
async def get_js():
    return FileResponse("frontend/app.js")

@app.get("/login.js")
async def get_login_js():
    return FileResponse("frontend/login.js")

@app.get("/signup.js")
async def get_signup_js():
    return FileResponse("frontend/signup.js")

# Auth Endpoints
@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/15 minutes")
async def signup(request: Request, user_auth: UserAuth):
    email = user_auth.email.strip().lower()
    password = user_auth.password
    
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Parameterized check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")
            
        # Create user with hashed password
        hashed_pw = hash_password(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (email, hashed_pw)
        )
        user_id = cursor.fetchone()[0]
        
    return {"message": "Account created successfully", "user_id": user_id}

@app.post("/auth/login")
@limiter.limit("5/15 minutes")
async def login(request: Request, response: Response, user_auth: UserAuth):
    email = user_auth.email.strip().lower()
    password = user_auth.password
    
    # Generic error message to prevent email enumeration
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        
    if not row:
        # Prevent timing attacks by running a dummy password verification
        verify_password("dummy", "$2b$12$DummyHashDummyHashDummyHashDummyHashDummyHashDummyH")
        raise generic_error
        
    user_id, hashed_pw = row
    if not verify_password(password, hashed_pw):
        raise generic_error
        
    # Generate tokens
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    
    # Set HTTPOnly cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=900 # 15 minutes
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=604800 # 7 days
    )
    
    return {"message": "Login successful"}

@app.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token"
        )
        
    user_id = decode_token(refresh_token, "refresh")
    
    # Issue a new access token
    new_access_token = create_access_token(user_id)
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=900
    )
    return {"message": "Access token refreshed"}

@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", httponly=True, secure=COOKIE_SECURE, samesite="strict")
    response.delete_cookie("refresh_token", httponly=True, secure=COOKIE_SECURE, samesite="strict")
    return {"message": "Logged out successfully"}

@app.get("/auth/me")
async def get_me(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": row[0]}

# Applications API
@app.get("/applications")
async def list_applications(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, company, role, status, date_applied, link, notes, created_at 
               FROM applications 
               WHERE user_id = %s 
               ORDER BY created_at DESC""",
            (user_id,)
        )
        rows = cursor.fetchall()
        
    applications = []
    for r in rows:
        applications.append({
            "id": r[0],
            "company": r[1],
            "role": r[2],
            "status": r[3],
            "date_applied": r[4].isoformat() if r[4] else None,
            "link": r[5],
            "notes": r[6],
            "created_at": r[7].isoformat()
        })
    return applications

@app.post("/applications", status_code=status.HTTP_201_CREATED)
async def create_application(app_data: ApplicationCreate, user_id: int = Depends(get_current_user_id)):
    status_options = ['wishlist', 'applied', 'interview', 'offer', 'rejected']
    app_status = app_data.status or "wishlist"
    if app_status not in status_options:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {status_options}")
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO applications (user_id, company, role, status, date_applied, link, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id, company, role, status, date_applied, link, notes, created_at""",
            (user_id, app_data.company, app_data.role, app_status, app_data.date_applied, app_data.link, app_data.notes)
        )
        r = cursor.fetchone()
        
    return {
        "id": r[0],
        "company": r[1],
        "role": r[2],
        "status": r[3],
        "date_applied": r[4].isoformat() if r[4] else None,
        "link": r[5],
        "notes": r[6],
        "created_at": r[7].isoformat()
    }

@app.put("/applications/{app_id}")
async def update_application(app_id: int, app_data: ApplicationUpdate, user_id: int = Depends(get_current_user_id)):
    status_options = ['wishlist', 'applied', 'interview', 'offer', 'rejected']
    if app_data.status not in status_options:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {status_options}")
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Parameterized update ensuring ownership check
        cursor.execute(
            """UPDATE applications 
               SET company = %s, role = %s, status = %s, date_applied = %s, link = %s, notes = %s
               WHERE id = %s AND user_id = %s
               RETURNING id, company, role, status, date_applied, link, notes, created_at""",
            (app_data.company, app_data.role, app_data.status, app_data.date_applied, app_data.link, app_data.notes, app_id, user_id)
        )
        r = cursor.fetchone()
        
    if not r:
        raise HTTPException(status_code=404, detail="Application not found or unauthorized")
        
    return {
        "id": r[0],
        "company": r[1],
        "role": r[2],
        "status": r[3],
        "date_applied": r[4].isoformat() if r[4] else None,
        "link": r[5],
        "notes": r[6],
        "created_at": r[7].isoformat()
    }

@app.delete("/applications/{app_id}")
async def delete_application(app_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Parameterized delete ensuring ownership check
        cursor.execute(
            "DELETE FROM applications WHERE id = %s AND user_id = %s RETURNING id",
            (app_id, user_id)
        )
        r = cursor.fetchone()
        
    if not r:
        raise HTTPException(status_code=404, detail="Application not found or unauthorized")
        
    return {"message": "Application deleted successfully"}
