"""Unfold (django-unfold) registration for the shared database."""
from __future__ import annotations

import json

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin.choice_filters import BooleanRadioFilter
from unfold.contrib.filters.admin.text_filters import FieldTextFilter
from unfold.sites import UnfoldAdminSite

from admin_site.users.models import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_TEACHER,
    AdminUser,
    Answer,
    AppSetting,
    Attempt,
    AuditLog,
    Exam,
    ExamQuestion,
    Question,
)


def _options_display(raw: str) -> str:
    """Render the JSON option list as an A/B/C/D list."""
    try:
        items = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return raw or "—"
    if not items:
        return "—"
    letters = "ABCDEFGH"
    lines = [f"{letters[i]}. {t}" for i, t in enumerate(items)]
    return format_html("<div>{}</div>", format_html("<br>".join, lines))


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = ("source_id", "short_text", "answer_index", "answer_all", "topic", "is_active")
    list_filter = (("is_active", BooleanRadioFilter), ("topic", FieldTextFilter), ("difficulty", FieldTextFilter))
    search_fields = ("text", "topic", "notes")
    list_per_page = 50
    ordering = ("source_id", "id")
    readonly_fields = ("options_preview",)
    fieldsets = (
        (None, {"fields": ("source_id", "text", "topic", "difficulty", "is_active")}),
        ("Javoblar", {"fields": ("options", "options_preview", "answer_index", "answer_text", "answer_all")}),
        ("Qo‘shimcha", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    @admin.display(description="Qisqa matn")
    def short_text(self, obj: Question) -> str:
        text = (obj.text or "").strip()
        return text[:80] + ("…" if len(text) > 80 else "")

    @admin.display(description="Variantlar ko‘rinishi")
    def options_preview(self, obj: Question):
        return _options_display(obj.options)


@admin.register(Exam)
class ExamAdmin(ModelAdmin):
    list_display = ("id", "title", "questions_per_block", "time_limit_minutes", "pass_percent", "is_published")
    list_filter = (("is_published", BooleanRadioFilter),)
    search_fields = ("title", "description")
    list_editable = ("is_published",)


class AdminUserForm(forms.ModelForm):
    """Change form with a write-only `new_password` box.

    The field is declared here rather than on the model, so it never becomes a
    column and can never be written to SQL by accident. Leaving it blank keeps
    the existing password.
    """

    new_password = forms.CharField(
        label="Yangi parol",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Bo‘sh qoldirilsa parol o‘zgarmaydi.",
    )

    class Meta:
        model = AdminUser
        exclude = ("hashed_password",)


@admin.register(AdminUser)
class AdminUserAdmin(ModelAdmin):
    form = AdminUserForm
    list_display = ("id", "email", "full_name", "role", "is_active", "attempts_count")
    list_filter = (("role", FieldTextFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("email", "full_name")
    list_editable = ("role", "is_active")
    readonly_fields = ("created_at", "password_state")
    exclude = ("hashed_password",)
    # `new_password` is injected by get_form() below, so it must be listed here
    # to render but is never written to the database (it is form-only).
    fieldsets = (
        (None, {"fields": ("email", "full_name", "role", "is_active")}),
        ("Parol", {"fields": ("password_state", "new_password"),
                   "description": "Parol FastAPI bilan bir xil PBKDF2 formatida saqlanadi."}),
        ("Qo‘shimcha", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="Parol holati")
    def password_state(self, obj: AdminUser):
        if not obj or not obj.hashed_password:
            return "Yo‘q"
        return "Saqlangan (PBKDF2)"

    def save_model(self, request, obj, form, change):
        """Hash a typed password into `hashed_password`.

        The field is form-only, so it never reaches the model or the SQL layer.
        """
        raw = (form.cleaned_data.get("new_password") or "").strip()
        if raw:
            obj.set_password(raw)
        super().save_model(request, obj, form, change)

    @admin.display(description="Urinishlar")
    def attempts_count(self, obj: AdminUser) -> int:
        return Attempt.objects.filter(user_id=obj.id).count()


@admin.register(Attempt)
class AttemptAdmin(ModelAdmin):
    list_display = ("id", "user", "title_snapshot", "status", "score_display", "correct_answers", "total_questions", "started_at")
    list_filter = (("status", FieldTextFilter), ("mode", FieldTextFilter))
    search_fields = ("title_snapshot", "user__email", "user__full_name")
    readonly_fields = ("question_ids", "option_order", "score_display")
    list_per_page = 50
    fields = ("id", "user", "exam", "title_snapshot", "block_number", "mode", "status",
              "total_questions", "correct_answers", "score_percent", "passed",
              "time_spent_seconds", "started_at", "finished_at", "question_ids", "option_order")


@admin.register(Answer)
class AnswerAdmin(ModelAdmin):
    list_display = ("id", "attempt", "question", "selected_index", "is_correct")
    list_filter = (("is_correct", BooleanRadioFilter),)
    list_per_page = 100


@admin.register(ExamQuestion)
class ExamQuestionAdmin(ModelAdmin):
    list_display = ("exam", "question", "position")


@admin.register(AppSetting)
class AppSettingAdmin(ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "value")


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ("created_at", "user", "action", "entity", "entity_id")
    list_filter = (("action", FieldTextFilter),)
    search_fields = ("action", "detail")
    readonly_fields = ("id", "user", "user_email", "action", "entity", "entity_id", "detail", "created_at")
    list_per_page = 100

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


admin.site.site_header = "OSH — Boshqaruv paneli"
admin.site.site_title = "OSH admin"
admin.site.index_title = "Boshqaruv"



def _stats() -> list[dict]:
    """Summary numbers for the dashboard, read straight from the shared tables."""
    from django.db.models import Avg

    total_q = Question.objects.count()
    gradable = Question.objects.filter(is_active=True).exclude(answer_index=None).count()
    submitted = Attempt.objects.filter(status="submitted")
    avg = submitted.aggregate(v=Avg("score_percent"))["v"]
    live = Attempt.objects.filter(status="in_progress").count()

    return [
        {"label": "Savollar", "value": total_q, "hint": f"{gradable} ta baholanadigan"},
        {"label": "Foydalanuvchilar", "value": AdminUser.objects.count(), "hint": "barchasi"},
        {"label": "Imtihonlar", "value": Exam.objects.count(),
         "hint": f"{Exam.objects.filter(is_published=True).count()} ta e’lon qilingan"},
        {"label": "Topshirilgan", "value": submitted.count(), "hint": f"jarayonda: {live}"},
        {"label": "O‘rtacha ball", "value": "—" if avg is None else f"{avg:.0f}%",
         "hint": "o‘rtacha natija"},
        {"label": "Amal loglari", "value": AuditLog.objects.count(), "hint": "kayd etilgan amal"},
    ]


def dashboard_callback(request, context):
    """Unfold hook (DASHBOARD_CALLBACK) that injects the summary cards."""
    context["stats"] = _stats()
    context["osh_quick_links"] = [
        ("Savollar", "admin:users_question_changelist"),
        ("Imtihonlar", "admin:users_exam_changelist"),
        ("Foydalanuvchilar", "admin:users_adminuser_changelist"),
        ("Urinishlar", "admin:users_attempt_changelist"),
        ("Sozlamalar", "admin:users_appsetting_changelist"),
    ]
    return context


class OSHAdminSite(UnfoldAdminSite):
    """Unfold site that keeps the default index but shows our summary cards."""


# Install our subclass so `admin.site.urls` binds to the themed site.
admin.site.__class__ = OSHAdminSite




