"""Domain model for Resume Tailor.

The vocabulary the rest of the app speaks. Mirrored to TypeScript via the
generated OpenAPI schema; do not duplicate by hand on the frontend.

Design rules enforced here:

* Every `Story` has a stable `id`. The AI returns IDs, never free text. The
  tailor pipeline validates that every returned ID exists in the input pool
  and drops the rest — the model cannot smuggle in invented bullets.
* `extra="forbid"` everywhere: typos in client payloads fail loudly instead
  of silently dropping fields.
* Partial dates (`YYYY` or `YYYY-MM`) are common on resumes and `date` is
  too strict; we use a regex-validated string and let `end=None` mean
  "Present".
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

# --- Aliases ---------------------------------------------------------------

StoryId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.\-]+$",
        description="Stable, opaque ID used by the AI to reference a story.",
    ),
]

PartialDate = Annotated[
    str,
    Field(
        pattern=r"^\d{4}(-\d{2})?$",
        description="ISO partial date: YYYY or YYYY-MM.",
        examples=["2023", "2023-06"],
    ),
]

Archetype = Literal[
    "backend",
    "frontend",
    "fullstack",
    "data",
    "ml",
    "platform",
    "mobile",
    "generalist",
]

TemplateId = Literal["modern", "classic", "compact"]
RenderFormat = Literal["html", "pdf"]


class _Strict(BaseModel):
    """Common config: forbid unknown fields, strip surrounding whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Inputs (what the user types) ------------------------------------------


class Contact(_Strict):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=120)
    website: HttpUrl | None = None
    linkedin: HttpUrl | None = None
    github: HttpUrl | None = None


class Story(_Strict):
    """A single accomplishment bullet authored by the user."""

    id: StoryId
    text: str = Field(min_length=1, max_length=400)


class Experience(_Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    company: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    start: PartialDate
    end: PartialDate | None = Field(default=None, description="None means 'Present'.")
    stories: list[Story] = Field(default_factory=list)


class Education(_Strict):
    school: str = Field(min_length=1, max_length=160)
    degree: str = Field(min_length=1, max_length=120)
    field: str | None = Field(default=None, max_length=120)
    start: PartialDate | None = None
    end: PartialDate | None = None
    notes: str | None = Field(default=None, max_length=240)


class ResumeInput(_Strict):
    """The user's verified facts. The single source of truth."""

    contact: Contact
    profile_seed: str = Field(
        min_length=20,
        max_length=600,
        description=(
            "User's own one-paragraph self-summary. The model may rephrase "
            "but may not introduce facts not present here or in stories."
        ),
    )
    experiences: list[Experience] = Field(min_length=1)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list, max_length=80)


# --- Tailor request / response --------------------------------------------


class JobDescription(_Strict):
    text: str = Field(min_length=50, max_length=20_000)
    archetype_override: Archetype | None = None


class TailorRequest(_Strict):
    resume: ResumeInput
    jd: JobDescription


class TailoredExperience(_Strict):
    """Per-experience selection: ordered IDs from the input pool."""

    experience_id: str
    story_ids: list[StoryId]


class TailorResult(_Strict):
    profile: str = Field(
        min_length=1,
        description="45-75 words, banned-phrase filtered, fact-grounded.",
    )
    experiences: list[TailoredExperience]
    skills: list[str] = Field(
        description="Reordered subset of input.skills, filtered to JD relevance."
    )
    archetype_used: Archetype
    keywords_injected: list[str] = Field(
        default_factory=list,
        description="JD vocabulary present in the chosen bullets/profile.",
    )
    dropped_story_ids: list[StoryId] = Field(
        default_factory=list,
        description="IDs the model returned that were not in the input pool.",
    )
    profile_fallback_used: bool = Field(
        default=False,
        description="True when the model's profile failed validation and "
        "we fell back to a clean truncation of profile_seed.",
    )


# --- Render request --------------------------------------------------------


class RenderRequest(_Strict):
    resume: ResumeInput
    tailored: TailorResult
    template_id: TemplateId
    format: RenderFormat = "pdf"


# --- Templates -------------------------------------------------------------


class TemplateMeta(_Strict):
    id: TemplateId
    name: str
    description: str
    preview_url: str


# --- Health & errors -------------------------------------------------------


class HealthStatus(_Strict):
    status: Literal["ok", "degraded"]
    playwright: bool
    openai: bool


class Problem(_Strict):
    """RFC 7807 problem+json."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    retry_after: int | None = Field(
        default=None, description="Seconds. Echoes the Retry-After header for 503s."
    )


__all__ = [
    "Archetype",
    "Contact",
    "Education",
    "Experience",
    "HealthStatus",
    "JobDescription",
    "PartialDate",
    "Problem",
    "RenderFormat",
    "RenderRequest",
    "ResumeInput",
    "Story",
    "StoryId",
    "TailorRequest",
    "TailorResult",
    "TailoredExperience",
    "TemplateId",
    "TemplateMeta",
]
