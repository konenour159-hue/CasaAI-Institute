"""
Enums Python miroir exact des types ENUM créés dans schema.sql.

Chaque enum est utilisé avec sqlalchemy.Enum(..., name=...) pour que
SQLAlchemy réutilise le type PostgreSQL existant plutôt que d'en recréer un.
"""
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    # ADMIN : gestion du contenu pédagogique uniquement (cours, leçons,
    # import PDF). Pas d'accès aux utilisateurs, à la progression globale,
    # ni aux certifications.
    ADMIN = "ADMIN"
    # SUPER_ADMIN : sur-ensemble d'ADMIN. Accès en plus à la gestion des
    # utilisateurs (dont suppression), à la progression globale des
    # apprenants, et à la gestion des certifications. Ne participe pas aux
    # cours en tant qu'apprenant (convention d'usage : compte LEARNER
    # séparé si besoin — voir app/api/deps.py pour le détail des
    # dépendances d'autorisation associées à chaque rôle).
    SUPER_ADMIN = "SUPER_ADMIN"
    LEARNER = "LEARNER"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"


class ContentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class QuizKind(str, enum.Enum):
    PRACTICE = "PRACTICE"
    VALIDATION = "VALIDATION"
    FINAL = "FINAL"


class CertificationRequirementType(str, enum.Enum):
    COURSE = "COURSE"
    MIN_SCORE = "MIN_SCORE"
    LAB = "LAB"
    SKILL = "SKILL"
    EVIDENCE = "EVIDENCE"
    FINAL_PROJECT = "FINAL_PROJECT"


class UserCertificationStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    ELIGIBLE = "ELIGIBLE"
    ISSUED = "ISSUED"
    REVOKED = "REVOKED"


class LessonProgressStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class NotificationType(str, enum.Enum):
    NEW_ACTIVITY = "NEW_ACTIVITY"
    COURSE_COMPLETED = "COURSE_COMPLETED"
    QUIZ_PASSED = "QUIZ_PASSED"
    CERTIFICATION_ISSUED = "CERTIFICATION_ISSUED"
    NEW_CONTENT = "NEW_CONTENT"
    FEEDBACK = "FEEDBACK"
    REMINDER = "REMINDER"


class AIMessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class LessonDepthKey(str, enum.Enum):
    ESSENTIAL = "ESSENTIAL"
    TECHNICAL = "TECHNICAL"
    MATHEMATICS = "MATHEMATICS"
    IMPLEMENTATION = "IMPLEMENTATION"
    ARCHITECTURE = "ARCHITECTURE"
    GOVERNANCE = "GOVERNANCE"
