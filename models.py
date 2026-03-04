from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    cf_handle = Column(String, unique=True, index=True, nullable=False)

    solved_problems = relationship("SolvedProblem", back_populates="user")
    buckets = relationship("Bucket", back_populates="user")
    tags = relationship("Tag", back_populates="user")


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer)
    index = Column(String)
    name = Column(String)
    rating = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("contest_id", "index", name="unique_problem"),
    )

    solved_by = relationship("SolvedProblem", back_populates="problem")


class SolvedProblem(Base):
    __tablename__ = "solved_problems"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    problem_id = Column(Integer, ForeignKey("problems.id"))

    solved_at = Column(DateTime, default=datetime.utcnow)

    # CF metadata
    cf_submission_id = Column(Integer, nullable=True)

    # Lazy-cached CF code
    cf_solution_code = Column(Text, nullable=True)

    # Personal additions
    user_note = Column(Text, nullable=True)
    user_solution_code = Column(Text, nullable=True)

    user = relationship("User", back_populates="solved_problems")
    problem = relationship("Problem", back_populates="solved_by")
    tags = relationship("ProblemTag", back_populates="solved_problem", cascade="all, delete-orphan")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, default="#3b82f6")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_user_tag_name"),
    )

    user = relationship("User", back_populates="tags")
    problems = relationship("ProblemTag", back_populates="tag", cascade="all, delete-orphan")

class ProblemTag(Base):
    __tablename__ = "problem_tags"

    id = Column(Integer, primary_key=True)
    solved_problem_id = Column(Integer, ForeignKey("solved_problems.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("solved_problem_id", "tag_id", name="unique_problem_tag"),
    )

    solved_problem = relationship("SolvedProblem", back_populates="tags")
    tag = relationship("Tag", back_populates="problems")

class Bucket(Base):
    __tablename__ = "buckets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_user_bucket_name"),
    )

    user = relationship("User", back_populates="buckets")

    problems = relationship(
        "BucketProblem",
        back_populates="bucket",
        cascade="all, delete-orphan"
    )

class BucketProblem(Base):
    __tablename__ = "bucket_problems"

    id = Column(Integer, primary_key=True)
    bucket_id = Column(Integer, ForeignKey("buckets.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("bucket_id", "problem_id", name="unique_bucket_problem"),
    )

    bucket = relationship("Bucket", back_populates="problems")
    problem = relationship("Problem")