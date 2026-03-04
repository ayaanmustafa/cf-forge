from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from database import SessionLocal
from models import User, Problem, SolvedProblem, Tag, ProblemTag
from schemas import SolvedProblemOut
from crud import (
    get_or_create_user,
    get_or_create_problem,
    add_solved_problem
)
from cf_service import (
    fetch_solved_problems,
    fetch_submission_code
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# SYNC ENDPOINT POST /sync/tourist
@router.post("/sync/{handle}")
def sync_user(handle: str, db: Session = Depends(get_db)):
    user = get_or_create_user(db, handle)
    solved_list = fetch_solved_problems(handle)

    for data in solved_list:
        problem = get_or_create_problem(db, data)
        add_solved_problem(db, user, problem, data)

    db.commit()

    return {"status": "sync complete", "count": len(solved_list)}



# GET SOLVED WITH FILTERING + PAGINATION
#GET /solved/tourist?min_rating=1400&max_rating=1800
#GET /solved/tourist?after=2024-01-01T00:00:00
#GET /solved/tourist?skip=0&limit=20
#GET /solution/12

@router.get("/solved/{handle}", response_model=list[SolvedProblemOut])
def get_solved_problems(
    handle: str,
    min_rating: Optional[int] = Query(None),
    max_rating: Optional[int] = Query(None),
    after: Optional[datetime] = Query(None),
    before: Optional[datetime] = Query(None),
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.cf_handle == handle).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = (
        db.query(SolvedProblem)
        .options(joinedload(SolvedProblem.problem))
        .join(Problem)
        .filter(SolvedProblem.user_id == user.id)
    )

    if min_rating is not None:
        query = query.filter(Problem.rating >= min_rating)

    if max_rating is not None:
        query = query.filter(Problem.rating <= max_rating)


    if after is not None:
        query = query.filter(SolvedProblem.solved_at >= after)

    if before is not None:
        query = query.filter(SolvedProblem.solved_at <= before)

    # Pagination
    results = (
        query
        .order_by(SolvedProblem.solved_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return results


# GET SOLUTION (LAZY CACHE)
@router.get("/solution/{solved_id}")
def get_solution(solved_id: int, db: Session = Depends(get_db)):

    solved = (
        db.query(SolvedProblem)
        .options(joinedload(SolvedProblem.problem))
        .filter(SolvedProblem.id == solved_id)
        .first()
    )

    if not solved:
        raise HTTPException(status_code=404, detail="Solved problem not found")

    # If already cached
    if solved.cf_solution_code:
        return {
            "source": "cached",
            "code": solved.cf_solution_code
        }

    # Otherwise fetch and cache
    if not solved.cf_submission_id:
        raise HTTPException(status_code=400, detail="No submission ID stored")

    code = fetch_submission_code(
        solved.problem.contest_id,
        solved.cf_submission_id
    )

    if not code:
        raise HTTPException(status_code=500, detail="Could not fetch code")

    solved.cf_solution_code = code
    db.commit()

    return {
        "source": "fetched",
        "code": code
    }



# Request schemas
class NoteRequest(BaseModel):
    note: str

class TagRequest(BaseModel):
    name: str
    color: str = "#3b82f6"

class AddTagToProblemRequest(BaseModel):
    tag_id: int

# ADD NOTE
@router.post("/note/{solved_id}")
def add_note(
    solved_id: int,
    request: NoteRequest,
    db: Session = Depends(get_db)
):

    solved = db.query(SolvedProblem).filter(
        SolvedProblem.id == solved_id
    ).first()

    if not solved:
        raise HTTPException(status_code=404, detail="Not found")

    solved.user_note = request.note
    db.commit()

    return {"status": "note saved"}

# GET TAGS FOR USER
@router.get("/tags/{handle}")
def get_tags(handle: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.cf_handle == handle).first()

    if not user:
        return [] 
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color
        }
        for tag in user.tags
    ]

# CREATE TAG
@router.post("/tags/{handle}")
def create_tag(handle: str, request: TagRequest, db: Session = Depends(get_db)):
    user = get_or_create_user(db, handle)
    
    # Check if tag already exists
    existing = db.query(Tag).filter(
        Tag.user_id == user.id,
        Tag.name == request.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")
    
    tag = Tag(user_id=user.id, name=request.name, color=request.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color
    }

# DELETE TAG
@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    db.delete(tag)
    db.commit()
    
    return {"status": "tag deleted"}

# ADD TAG TO PROBLEM
@router.post("/solved/{solved_id}/tag")
def add_tag_to_problem(solved_id: int, request: AddTagToProblemRequest, db: Session = Depends(get_db)):
    solved = db.query(SolvedProblem).filter(SolvedProblem.id == solved_id).first()
    if not solved:
        raise HTTPException(status_code=404, detail="Solved problem not found")
    
    tag = db.query(Tag).filter(Tag.id == request.tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Check if already tagged
    existing = db.query(ProblemTag).filter(
        ProblemTag.solved_problem_id == solved_id,
        ProblemTag.tag_id == request.tag_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Tag already added to this problem")
    
    problem_tag = ProblemTag(solved_problem_id=solved_id, tag_id=request.tag_id)
    db.add(problem_tag)
    db.commit()
    
    return {"status": "tag added"}

# REMOVE TAG FROM PROBLEM
@router.delete("/solved/{solved_id}/tag/{tag_id}")
def remove_tag_from_problem(solved_id: int, tag_id: int, db: Session = Depends(get_db)):
    problem_tag = db.query(ProblemTag).filter(
        ProblemTag.solved_problem_id == solved_id,
        ProblemTag.tag_id == tag_id
    ).first()
    
    if not problem_tag:
        raise HTTPException(status_code=404, detail="Tag not on this problem")
    
    db.delete(problem_tag)
    db.commit()
    
    return {"status": "tag removed"}