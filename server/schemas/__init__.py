"""Pydantic schemas for request and response payloads.

Email validation is done with a small local check instead of the optional
`email-validator` package, so the project has no extra runtime dependency.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _check_email(value: str) -> str:
    value = str(value).strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("noto'g'ri e-pochta manzili")
    return value


EmailStr = Annotated[str, Field(), ]


# ------------------------------------------------------------------ auth / users
class UserCreate(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    role: str = "student"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _check_email(v)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        from server.models import ROLES

        if v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _check_email(v)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str | None) -> str | None:
        from server.models import ROLES

        if v is not None and v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    attempts_count: int = 0

# --------------------------------------------------------------------- questions
class QuestionCreate(BaseModel):
    source_id: int | None = None
    text: str = Field(min_length=3)
    options: list[str] = Field(default_factory=list, min_length=2, max_length=6)
    answer_index: int | None = None
    answer_text: str | None = None
    answer_all: bool = False
    notes: str | None = None
    topic: str = "Umumiy"
    difficulty: str = "medium"
    is_active: bool = True


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=3)
    options: list[str] | None = Field(default=None, min_length=2, max_length=6)
    answer_index: int | None = None
    answer_text: str | None = None
    answer_all: bool | None = None
    notes: str | None = None
    topic: str | None = None
    difficulty: str | None = None
    is_active: bool | None = None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    text: str
    options: list[str]
    answer_index: int | None
    answer_text: str | None
    answer_all: bool
    notes: str | None
    topic: str
    difficulty: str
    is_active: bool

    @property
    def is_gradable(self) -> bool:
        return self.answer_index is not None or self.answer_all


class QuestionImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    total_in_file: int
    graded: int
    ungraded: int


class QuestionPage(BaseModel):
    items: list[QuestionOut]
    total: int
    page: int
    pages: int
    per_page: int


# ------------------------------------------------------------------------ exams
class ExamCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    questions_per_block: int = Field(default=20, ge=1, le=200)
    time_limit_minutes: int = Field(default=30, ge=1, le=600)
    pass_percent: float = Field(default=60.0, ge=0, le=100)
    shuffle_options: bool = True
    shuffle_questions: bool = True
    is_published: bool = False
    question_ids: list[int] = Field(default_factory=list)


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    questions_per_block: int | None = Field(default=None, ge=1, le=200)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=600)
    pass_percent: float | None = Field(default=None, ge=0, le=100)
    shuffle_options: bool | None = None
    shuffle_questions: bool | None = None
    is_published: bool | None = None
    question_ids: list[int] | None = None


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    questions_per_block: int
    time_limit_minutes: int
    pass_percent: float
    shuffle_options: bool
    shuffle_questions: bool
    is_published: bool
    created_at: datetime
    question_count: int = 0
    attempt_count: int = 0
    average_score: float | None = None

    average_score: float | None = None



# --------------------------------------------------------------------- attempts
class AttemptStart(BaseModel):
    exam_id: int | None = None
    block_number: int = Field(default=1, ge=1)
    mode: str = "exam"  # "exam" or "practice"
    # Chosen in the start dialog. None keeps the exam's own default.
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None


class AnswerPayload(BaseModel):
    question_id: int
    position: int = 0
    selected_index: int | None = None
    time_spent_seconds: int = 0


class AttemptSubmit(BaseModel):
    answers: list[AnswerPayload] = Field(default_factory=list)
    time_spent_seconds: int = 0


class AttemptQuestionOut(BaseModel):
    position: int
    question_id: int
    text: str
    options: list[str]
    notes: str | None = None
    selected_index: int | None = None
    answer_index: int | None = None
    answer_text: str | None = None
    answer_all: bool = False
    is_correct: bool | None = None
    is_gradable: bool = True
    topic: str = "Umumiy"


class AttemptOut(BaseModel):
    id: int
    exam_id: int | None
    title: str
    block_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    time_limit_minutes: int
    time_spent_seconds: int
    total_questions: int
    correct_answers: int
    score_percent: float
    passed: bool
    mode: str = "exam"
    questions: list[AttemptQuestionOut] = Field(default_factory=list)


class AttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int | None
    title_snapshot: str
    block_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    score_percent: float
    correct_answers: int
    total_questions: int
    passed: bool
    time_spent_seconds: int


# -------------------------------------------------------------------- analytics
class TopicStat(BaseModel):
    topic: str
    total: int
    correct: int
    percent: float


class DifficultyStat(BaseModel):
    difficulty: str
    total: int
    correct: int
    percent: float


class QuestionStat(BaseModel):
    question_id: int
    source_id: int
    text: str
    attempts: int
    correct: int
    percent: float


class UserStat(BaseModel):
    user_id: int
    full_name: str
    email: str
    attempts: int
    average_score: float
    best_score: float


class AdminStats(BaseModel):
    users_total: int
    users_active: int
    students: int
    teachers: int
    admins: int
    questions_total: int
    questions_gradable: int
    questions_inactive: int
    exams_total: int
    exams_published: int
    attempts_total: int
    attempts_submitted: int
    average_score: float
    pass_rate: float
    attempts_today: int
    active_users_7d: int
    score_distribution: list[dict] = Field(default_factory=list)
    topic_stats: list[TopicStat] = Field(default_factory=list)
    difficulty_stats: list[DifficultyStat] = Field(default_factory=list)
    hardest_questions: list[QuestionStat] = Field(default_factory=list)
    top_users: list[UserStat] = Field(default_factory=list)
    recent_attempts: list[AttemptSummary] = Field(default_factory=list)
    daily_activity: list[dict] = Field(default_factory=list)


class SettingOut(BaseModel):
    key: str
    value: str


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_email: str | None
    action: str
    entity: str | None
    entity_id: str | None
    detail: str | None
    created_at: datetime


class ImportQuestionsIn(BaseModel):
    path: str | None = None
    activate_all: bool = True

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
