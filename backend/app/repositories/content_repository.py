"""
Accès en lecture au contenu pédagogique. Toutes les requêtes filtrent
explicitement `status == PUBLISHED` : un contenu en brouillon ou archivé
(§23 cahier fonctionnel) ne doit jamais fuiter via l'API publique, même si
la relation ORM sous-jacente ne le fait pas automatiquement.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import School, Skill
from app.models.content import Course, Lesson, Pathway
from app.models.enums import ContentStatus, QuizKind
from app.models.lab import Lab, lab_modes, lab_skills
from app.models.quiz import Quiz
from app.models.resource import Resource, resource_courses


class ContentRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Référentiel -----------------------------------------------------

    def list_schools(self) -> list[School]:
        return list(self.db.execute(select(School).order_by(School.name)).scalars())

    def list_skills(self, school_id: str | None = None) -> list[Skill]:
        stmt = select(Skill).order_by(Skill.name)
        if school_id:
            stmt = stmt.where(Skill.school_id == school_id)
        return list(self.db.execute(stmt).scalars())

    # --- Cours -----------------------------------------------------

    def list_courses(
        self, *, school_id: str | None = None, level: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Course], int]:
        base = select(Course).where(Course.status == ContentStatus.PUBLISHED)
        if school_id:
            base = base.where(Course.school_id == school_id)
        if level:
            base = base.where(Course.level == level)

        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        items = list(
            self.db.execute(base.order_by(Course.title).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def get_course(self, course_id: str) -> tuple[Course, list[Lesson]] | None:
        """Renvoie (cours, leçons publiées) sans muter la collection ORM
        `Course.lessons` : cette relation porte `cascade="all, delete-orphan"`,
        donc lui réaffecter une sous-liste filtrée serait dangereux (un
        `commit()` ultérieur sur la même session pourrait interpréter les
        leçons exclues comme orphelines et les supprimer). On renvoie plutôt
        les deux séparément, assemblées côté route/schéma."""
        course = self.db.execute(
            select(Course).where(Course.id == course_id, Course.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none()
        if course is None:
            return None

        lessons = list(
            self.db.execute(
                select(Lesson)
                .where(Lesson.course_id == course_id, Lesson.status == ContentStatus.PUBLISHED)
                .order_by(Lesson.position)
            ).scalars()
        )
        return course, lessons

    def get_course_resources(self, course_id: str) -> list[Resource]:
        """Bibliographie du cours (§ sources) — jonction resource_courses,
        jusqu'ici seedée mais jamais exposée par aucune route API."""
        return list(
            self.db.execute(
                select(Resource)
                .join(resource_courses, resource_courses.c.resource_id == Resource.id)
                .where(resource_courses.c.course_id == course_id, Resource.status == ContentStatus.PUBLISHED)
                .order_by(Resource.title)
            ).scalars()
        )

    def get_final_quiz_id(self, course_id: str) -> str | None:
        """Quiz FINAL publié rattaché à ce cours, s'il existe (§15 cahier
        fonctionnel). Utilisé pour afficher un bouton "Quiz final" sur la
        fiche cours — sans ça un quiz FINAL existant en base resterait
        inatteignable pour l'apprenant."""
        quiz_id = self.db.execute(
            select(Quiz.id).where(
                Quiz.course_id == course_id, Quiz.kind == QuizKind.FINAL, Quiz.status == ContentStatus.PUBLISHED
            )
        ).scalar_one_or_none()
        return str(quiz_id) if quiz_id else None

    # --- Parcours -----------------------------------------------------

    def list_pathways(
        self, *, level: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Pathway], int]:
        base = select(Pathway).where(Pathway.status == ContentStatus.PUBLISHED)
        if level:
            base = base.where(Pathway.level == level)

        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        items = list(
            self.db.execute(base.order_by(Pathway.title).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def get_pathway(self, pathway_id: str) -> tuple[Pathway, list[Course]] | None:
        """Renvoie (parcours, cours publiés) — même principe de prudence que
        get_course : on ne mute pas la collection ORM chargée, même si
        `Pathway.courses` est `viewonly=True` (donc en principe sans risque
        d'écriture), pour garder une seule règle simple dans tout le repository."""
        pathway = self.db.execute(
            select(Pathway)
            .options(selectinload(Pathway.courses))
            .where(Pathway.id == pathway_id, Pathway.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none()
        if pathway is None:
            return None

        published_courses = [c for c in pathway.courses if c.status == ContentStatus.PUBLISHED]
        return pathway, published_courses

    # --- Labs -----------------------------------------------------------

    def list_labs(
        self, *, school_id: str | None = None, level: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Lab], int]:
        base = select(Lab).where(Lab.status == ContentStatus.PUBLISHED)
        if school_id:
            base = base.where(Lab.school_id == school_id)
        if level:
            base = base.where(Lab.level == level)

        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        items = list(
            self.db.execute(base.order_by(Lab.title).limit(limit).offset(offset)).scalars()
        )
        return items, total

    def get_lab(self, lab_id: str) -> tuple[Lab, list[str], list[str]] | None:
        """Renvoie (lab, modes, skill_ids). modes/skills sont de simples
        tables d'association (Core Table, pas de relation ORM déclarée) :
        requêtes directes plutôt qu'une relation à ajouter aux modèles pour
        un besoin d'affichage aussi simple."""
        lab = self.db.execute(
            select(Lab).where(Lab.id == lab_id, Lab.status == ContentStatus.PUBLISHED)
        ).scalar_one_or_none()
        if lab is None:
            return None

        modes = list(self.db.execute(select(lab_modes.c.mode).where(lab_modes.c.lab_id == lab_id)).scalars())
        skill_ids = list(
            self.db.execute(select(lab_skills.c.skill_id).where(lab_skills.c.lab_id == lab_id)).scalars()
        )
        return lab, modes, skill_ids
