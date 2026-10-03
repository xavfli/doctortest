"""Django models mapped onto the tables FastAPI owns.

Two things make this unusual:

1. `users` has no `password` column — FastAPI stores `hashed_password` as
   `pbkdf2_sha256$rounds$salt$hash`. AdminUser maps that column directly and
   verifies the exact same format, so passwords stay valid in both apps.
2. Every model sets `managed = False`. SQLAlchemy owns the schema; Django must
   never create or alter these tables.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.contrib.auth.signals import user_logged_in

ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

STAFF_ROLES = {ROLE_ADMIN, ROLE_TEACHER}

# Matches server/core/security.py.
PBKDF2_ROUNDS = 260_000


def parse_pbkdf2(stored: str) -> tuple[int, bytes, bytes]:
    """Return (rounds, salt, hash) from `pbkdf2_sha256$rounds$salt$hash`."""
    parts = (stored or "").split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        raise ValueError("unsupported hash format")

    def decode(s: str) -> bytes:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    return int(parts[1]), decode(parts[2]), decode(parts[3])


def hash_pbkdf2(raw_password: str, rounds: int = PBKDF2_ROUNDS) -> str:
    """Hash exactly the way server/core/security.py does, so both apps agree."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw_password.encode(), salt, rounds)

    def enc(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).decode().rstrip("=")

    return "$".join(["pbkdf2_sha256", str(rounds), enc(salt), enc(dk)])


def update_last_login(sender, user, **kwargs) -> None:
    """Stand in for Django's `update_last_login` receiver.

    The default receiver writes to a `last_login` column that the shared
    `users` table does not have. Recording the login in the audit log gives
    the same history without touching the schema FastAPI owns.
    """
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_logs (user_id, user_email, action, entity,"
                " entity_id, detail) VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    user.id,
                    user.email,
                    "admin_login",
                    "user",
                    user.id,
                    f"{user.email} admin panelga kirdi",
                ],
            )
    except Exception:  # logging must never break login
        pass

class AdminUserManager(BaseUserManager):
    def get_by_natural_key(self, username: str):
        return self.get(email=(username or "").strip().lower())


class AdminUser(AbstractBaseUser):
    """Maps 1:1 onto the FastAPI `users` table."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=160, blank=True)
    role = models.CharField(max_length=16, default=ROLE_STUDENT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    hashed_password = models.CharField(max_length=255, db_column="hashed_password")

    # The FastAPI table has no last_login column. AbstractBaseUser declares it
    # as a field, so it must be overridden to keep Django from selecting it.
    last_login = None

    # `new_password` is form-only: it shares the `hashed_password` column but must
    # never be written to SQL. AdminUserAdmin injects it into the change form
    # through get_form(), so it is not a model field.
    new_password = None

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = AdminUserManager()

    class Meta:
        managed = False
        db_table = "users"
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["id"]

    # --- password plumbing -------------------------------------------------
    @property
    def password(self) -> str:  # type: ignore[override]
        return self.hashed_password or ""

    @password.setter
    def password(self, value: str) -> None:
        self.hashed_password = value

    def set_password(self, raw_password: str) -> None:
        self.hashed_password = hash_pbkdf2(raw_password)

    def check_password(self, raw_password: str) -> bool:  # type: ignore[override]
        try:
            rounds, salt, expected = parse_pbkdf2(self.password)
        except (ValueError, IndexError):
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", raw_password.encode(), salt, rounds, dklen=len(expected)
        )
        return hmac.compare_digest(candidate, expected)

    # --- role-derived flags ------------------------------------------------
    @property
    def is_staff(self) -> bool:  # type: ignore[override]
        return bool(self.is_active) and self.role in STAFF_ROLES

    @property
    def is_superuser(self) -> bool:
        return self.role == ROLE_ADMIN

    # These are called as methods by the admin, so they must be methods rather
    # than the properties AbstractBaseUser declares. The user table has no
    # permission tables, so "admin role implies every permission" is the rule.
    def has_perm(self, perm, obj=None) -> bool:
        return self.role == ROLE_ADMIN

    def has_perms(self, perm_list, obj=None) -> bool:
        return self.role == ROLE_ADMIN

    def has_module_perms(self, app_label) -> bool:
        return self.role == ROLE_ADMIN

    def get_username(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return (self.full_name or self.email).split(" ")[0]

    def __str__(self) -> str:
        return f"{self.full_name or self.email} <{self.email}>"


class Question(models.Model):
    id = models.IntegerField(primary_key=True)
    source_id = models.IntegerField(null=True, blank=True)
    text = models.TextField()
    options = models.TextField(blank=True, default="[]")
    answer_index = models.IntegerField(null=True, blank=True)
    answer_text = models.TextField(null=True, blank=True)
    answer_all = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
    topic = models.CharField(max_length=120, default="Umumiy")
    difficulty = models.CharField(max_length=32, default="medium")
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "questions"
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ["source_id", "id"]

    def __str__(self) -> str:
        return f"#{self.source_id or self.id} {(self.text or '')[:70]}"


class Exam(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    questions_per_block = models.IntegerField(default=20)
    time_limit_minutes = models.IntegerField(default=30)
    pass_percent = models.FloatField(default=60.0)
    shuffle_options = models.BooleanField(default=True)
    shuffle_questions = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    created_by = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "exams"
        verbose_name = "Imtihon"
        verbose_name_plural = "Imtihonlar"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.title


class AppSetting(models.Model):
    # This table has no surrogate id; `key` is the primary key.
    key = models.CharField(max_length=120, primary_key=True)
    value = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "app_settings"
        verbose_name = "Sozlama"
        verbose_name_plural = "Sozlamalar"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class Attempt(models.Model):
    STATUS_CHOICES = (
        ("in_progress", "Jarayonda"),
        ("submitted", "Topshirilgan"),
        ("expired", "Vaqti tugagan"),
        ("abandoned", "Tashlab qoldirilgan"),
    )

    id = models.IntegerField(primary_key=True)
    exam = models.ForeignKey(
        Exam, null=True, blank=True, on_delete=models.DO_NOTHING,
        db_column="exam_id", related_name="attempts",
    )
    user = models.ForeignKey(
        "users.AdminUser", null=True, blank=True, on_delete=models.DO_NOTHING,
        db_column="user_id", related_name="attempts",
    )
    title_snapshot = models.CharField(max_length=200, blank=True)
    block_number = models.IntegerField(default=1)
    mode = models.CharField(max_length=16, default="exam")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="in_progress")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    time_limit_minutes = models.IntegerField(default=30)
    time_spent_seconds = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    score_percent = models.FloatField(null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    question_ids = models.TextField(blank=True, default="[]")
    option_order = models.TextField(blank=True, default="{}")

    class Meta:
        managed = False
        db_table = "attempts"
        verbose_name = "Urinish"
        verbose_name_plural = "Urinishlar"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"#{self.id} · {self.status}"

    @property
    def score_display(self) -> str:
        return "—" if self.score_percent is None else f"{self.score_percent:.0f}%"


class Answer(models.Model):
    id = models.IntegerField(primary_key=True)
    attempt = models.ForeignKey(
        Attempt, on_delete=models.DO_NOTHING, db_column="attempt_id",
        related_name="answers",
    )
    question = models.ForeignKey(
        Question, on_delete=models.DO_NOTHING, db_column="question_id",
        related_name="answers",
    )
    selected_index = models.IntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    time_spent_seconds = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "answers"
        verbose_name = "Javob"
        verbose_name_plural = "Javoblar"
        ordering = ["id"]


class ExamQuestion(models.Model):
    exam = models.ForeignKey(
        Exam, on_delete=models.DO_NOTHING, db_column="exam_id",
        related_name="links",
    )
    question = models.ForeignKey(
        Question, on_delete=models.DO_NOTHING, db_column="question_id",
        related_name="exam_links",
    )
    position = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "exam_questions"
        verbose_name = "Imtihon savoli"
        verbose_name_plural = "Imtihon savollari"
        ordering = ["position"]


class AuditLog(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(
        "users.AdminUser", null=True, blank=True, on_delete=models.DO_NOTHING,
        db_column="user_id", related_name="audit_logs",
    )
    action = models.CharField(max_length=80)
    user_email = models.CharField(max_length=160, blank=True)
    entity = models.CharField(max_length=60, blank=True)
    entity_id = models.IntegerField(null=True, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "audit_logs"
        verbose_name = "Amal logi"
        verbose_name_plural = "Amal loglari"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.created_at} · {self.action}"


# Django's stock receiver would write to a `last_login` column this table does
# not have; point the signal at our audit-log writer instead.
user_logged_in.disconnect(dispatch_uid="update_last_login")
user_logged_in.connect(update_last_login, dispatch_uid="osh_update_last_login")
