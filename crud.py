from sqlalchemy.orm import Session
from models import User, Problem, SolvedProblem


def get_or_create_user(db: Session, handle: str):
    user = db.query(User).filter(User.cf_handle == handle).first()
    if not user:
        user = User(cf_handle=handle)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_or_create_problem(db: Session, data: dict):
    problem = db.query(Problem).filter(
        Problem.contest_id == data["contest_id"],
        Problem.index == data["index"]
    ).first()

    if not problem:
        problem = Problem(
            contest_id=data["contest_id"],
            index=data["index"],
            name=data["name"],
            rating=data["rating"]
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)

    return problem


def add_solved_problem(db: Session, user, problem, data: dict):
    exists = db.query(SolvedProblem).filter(
        SolvedProblem.user_id == user.id,
        SolvedProblem.problem_id == problem.id
    ).first()

    if not exists:
        solved = SolvedProblem(
            user_id=user.id,
            problem_id=problem.id,
            solved_at=data["solved_at"],
            cf_submission_id=data["submission_id"]
        )
        db.add(solved)