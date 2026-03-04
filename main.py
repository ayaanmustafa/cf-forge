from database import engine, SessionLocal
from models import Base, User, Bucket, BucketProblem, Problem, SolvedProblem
from routers import user
from fastapi import HTTPException, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from cf_service import fetch_all_problems
import os
from sqlalchemy import text

app = FastAPI()

# CORS configuration - allow localhost for development and production frontend
allowed_origins = [
    "https://cf-forge-frontend.vercel.app/",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176"
]

# Add production frontend URLs from environment if provided
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(user.router)

class CreateBucketRequest(BaseModel):
    handle: str
    name: str

class AddProblemToBucketRequest(BaseModel):
    problem_id: int

class AddProblemRequest(BaseModel):
    contest_id: int
    index: str
    name: str
    rating: int | None = None

class RenameBucketRequest(BaseModel):
    new_name: str

class TrackUnsolvdProblemRequest(BaseModel):
    handle: str
    contest_id: int
    index: str
    name: str
    rating: int | None = None

@app.get("/")
def root():
    return {"message": "CF Forge Backend Running"}

@app.get("/health")
def health_check():
    """Health check endpoint with database connectivity verification"""
    try:
        # Try to connect to the database
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy",
            "service": "CF Forge Backend",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "CF Forge Backend",
            "database": "disconnected",
            "error": str(e)
        }, 503

@app.post("/bucket")
def create_bucket(request: CreateBucketRequest):
    db: Session = SessionLocal()

    user = db.query(User).filter(User.cf_handle == request.handle).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    bucket = Bucket(user_id=user.id, name=request.name)
    db.add(bucket)
    db.commit()
    db.refresh(bucket)

    return {
        "bucket_id": bucket.id,
        "name": bucket.name
    }

@app.post("/bucket/{bucket_id}/add")
def add_problem_to_bucket(bucket_id: int, request: AddProblemToBucketRequest):
    db: Session = SessionLocal()

    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")

    problem = db.query(Problem).filter(Problem.id == request.problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # prevent duplicates
    existing = db.query(BucketProblem).filter(
        BucketProblem.bucket_id == bucket_id,
        BucketProblem.problem_id == request.problem_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Problem already in bucket")

    bucket_problem = BucketProblem(
        bucket_id=bucket_id,
        problem_id=request.problem_id
    )

    db.add(bucket_problem)
    db.commit()

    return {"message": "Problem added"}

@app.get("/bucket/{handle}")
def get_buckets(handle: str):
    db: Session = SessionLocal()

    user = db.query(User).filter(User.cf_handle == handle).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = []
    
    for bucket in user.buckets:
        total_problems = len(bucket.problems)
        
        # Count solved problems
        solved_count = 0
        unsolved_count = 0
        avg_rating = 0
        rating_sum = 0
        
        for bp in bucket.problems:
            problem = bp.problem
            
            # Check if this problem is in user's solved list
            is_solved = db.query(SolvedProblem).filter(
                SolvedProblem.user_id == user.id,
                SolvedProblem.problem_id == problem.id
            ).first() is not None
            
            if is_solved:
                solved_count += 1
            else:
                unsolved_count += 1
            
            if problem.rating:
                rating_sum += problem.rating
        
        if total_problems > 0:
            avg_rating = rating_sum / total_problems
        
        result.append({
            "id": bucket.id,
            "name": bucket.name,
            "total_problems": total_problems,
            "solved_problems": solved_count,
            "unsolved_problems": unsolved_count,
            "average_rating": round(avg_rating, 1)
        })
    
    return result

@app.get("/bucket/view/{bucket_id}")
def view_bucket(bucket_id: int):
    db: Session = SessionLocal()

    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")

    # Get SolvedProblems for the bucket's user with tags
    solved_problems = db.query(SolvedProblem).join(
        BucketProblem,
        BucketProblem.problem_id == SolvedProblem.problem_id
    ).filter(
        BucketProblem.bucket_id == bucket_id,
        SolvedProblem.user_id == bucket.user_id
    ).all()

    results = []
    for sp in solved_problems:
        p = sp.problem
        tags = [
            {
                "id": pt.id,
                "tag": {
                    "id": pt.tag.id,
                    "name": pt.tag.name,
                    "color": pt.tag.color
                }
            }
            for pt in sp.tags
        ]
        results.append({
            "id": sp.id,
            "problem": {
                "id": p.id,
                "contest_id": p.contest_id,
                "index": p.index,
                "name": p.name,
                "rating": p.rating
            },
            "user_note": sp.user_note,
            "cf_submission_id": sp.cf_submission_id,
            "user_solution_code": sp.user_solution_code,
            "solved_at": sp.solved_at,
            "tags": tags
        })

    return results

@app.post("/problem/add")
def add_problem(request: AddProblemRequest):
    db: Session = SessionLocal()

    existing = db.query(Problem).filter(
        Problem.contest_id == request.contest_id,
        Problem.index == request.index
    ).first()

    if existing:
        return {"problem_id": existing.id, "message": "Already exists"}

    problem = Problem(
        contest_id=request.contest_id,
        index=request.index,
        name=request.name,
        rating=request.rating
    )

    db.add(problem)
    db.commit()
    db.refresh(problem)

    return {"problem_id": problem.id}

@app.delete("/bucket/{bucket_id}/remove/{problem_id}")
def remove_problem_from_bucket(bucket_id: int, problem_id: int):
    db: Session = SessionLocal()

    bucket_problem = db.query(BucketProblem).filter(
        BucketProblem.bucket_id == bucket_id,
        BucketProblem.problem_id == problem_id
    ).first()

    if not bucket_problem:
        raise HTTPException(status_code=404, detail="Problem not in bucket")

    db.delete(bucket_problem)
    db.commit()

    return {"message": "Problem removed"}

@app.put("/bucket/{bucket_id}/rename")
def rename_bucket(bucket_id: int, request: RenameBucketRequest):
    db: Session = SessionLocal()

    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")

    bucket.name = request.new_name
    db.commit()

    return {"message": "Bucket renamed"}

@app.delete("/bucket/{bucket_id}")
def delete_bucket(bucket_id: int):
    db: Session = SessionLocal()

    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")

    db.delete(bucket)
    db.commit()

    return {"message": "Bucket deleted"}

@app.get("/bucket/{bucket_id}/stats")
def bucket_stats(bucket_id: int):
    db: Session = SessionLocal()

    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")

    # total problems
    total = db.query(BucketProblem).filter(
        BucketProblem.bucket_id == bucket_id
    ).count()

    # ratings aggregation
    ratings_query = db.query(
        func.avg(Problem.rating),
        func.max(Problem.rating)
    ).join(
        BucketProblem,
        BucketProblem.problem_id == Problem.id
    ).filter(
        BucketProblem.bucket_id == bucket_id,
        Problem.rating != None
    ).first()

    avg_rating = ratings_query[0]
    max_rating = ratings_query[1]

    # solved count
    solved_count = db.query(SolvedProblem).join(
        BucketProblem,
        BucketProblem.problem_id == SolvedProblem.problem_id
    ).filter(
        BucketProblem.bucket_id == bucket_id,
        SolvedProblem.user_id == bucket.user_id
    ).distinct(SolvedProblem.problem_id).count()

    unsolved_count = total - solved_count

    return {
        "total_problems": total,
        "solved_count": solved_count,
        "unsolved_count": unsolved_count,
        "average_rating": round(avg_rating, 2) if avg_rating else None,
        "max_rating": max_rating
    }

@app.get("/search/problems")
def search_all_problems(min_rating: int = 800, max_rating: int = 3500, contest_id: int | None = None, name: str | None = None, skip: int = 0, limit: int = 50):
    """Search all Codeforces problems with pagination and optional filters"""
    try:
        problems = fetch_all_problems(min_rating, max_rating)
        
        # Filter by contest if provided
        if contest_id:
            problems = [p for p in problems if p["contest_id"] == contest_id]
        
        # Filter by name or index if provided
        if name:
            search_term = name.lower()
            problems = [p for p in problems if search_term in p["name"].lower() or search_term in p["index"].lower()]
        
        total = len(problems)
        paginated = problems[skip:skip + limit]
        return {
            "problems": paginated,
            "total": total,
            "skip": skip,
            "limit": limit,
            "contest_id": contest_id,
            "name": name
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/problem/track")
def track_unsolved_problem(request: TrackUnsolvdProblemRequest):
    """Add an unsolved problem to user's database for tracking"""
    db: Session = SessionLocal()

    # Get or create user
    user = db.query(User).filter(User.cf_handle == request.handle).first()
    if not user:
        user = User(cf_handle=request.handle)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Get or create problem
    problem = db.query(Problem).filter(
        Problem.contest_id == request.contest_id,
        Problem.index == request.index
    ).first()
    
    if not problem:
        problem = Problem(
            contest_id=request.contest_id,
            index=request.index,
            name=request.name,
            rating=request.rating
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)

    # Check if user is already tracking this problem
    existing = db.query(SolvedProblem).filter(
        SolvedProblem.user_id == user.id,
        SolvedProblem.problem_id == problem.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already tracking this problem")

    # Create a tracking entry (unsolved, no cf_submission_id)
    solved_problem = SolvedProblem(
        user_id=user.id,
        problem_id=problem.id,
        cf_submission_id=None  # Mark as unsolved/tracked
    )
    db.add(solved_problem)
    db.commit()
    db.refresh(solved_problem)

    return {
        "solved_problem_id": solved_problem.id,
        "problem_id": problem.id,
        "message": "Problem added to your tracking list"
    }