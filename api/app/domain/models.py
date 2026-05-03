"""Domain model for Resume Tailor.

The vocabulary the rest of the app speaks. Mirrored to TypeScript via the
generated OpenAPI schema; do not duplicate by hand on the frontend.

Design rules enforced here:

* Every entity has a stable, opaque ID (`EntityId`). The AI returns IDs,
  never free text. The tailor pipeline validates that every returned ID
  exists in the input pool and drops the rest — the model cannot smuggle
  in invented bullets.
* `extra="forbid"` everywhere: typos in client payloads fail loudly instead
  of silently dropping fields.
* `alias_generator=to_camel` + `populate_by_name=True`: Python stays
  snake_case, the wire format (and OpenAPI / generated TS types) is
  camelCase, and clients sending either form work. Centralized on
  ``_Strict`` so individual models don't sprinkle `Field(alias=...)`.
* Partial dates (`YYYY` or `YYYY-MM`) are common on resumes and `date` is
  too strict; we use a regex-validated string and let `end=None` mean
  "Present". Months are constrained to 01-12.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
from pydantic.alias_generators import to_camel

# --- Aliases ---------------------------------------------------------------

EntityId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.\-]+$",
        description="Stable, opaque entity ID. AI returns these; never free text.",
    ),
]

# Documentation alias — same constraints, clearer at use sites.
StoryId = EntityId

PartialDate = Annotated[
    str,
    Field(
        pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$",
        description="ISO partial date: YYYY or YYYY-MM (months 01-12).",
        examples=["2023", "2023-06"],
    ),
]

Keyword = Annotated[
    str,
    Field(
        min_length=1,
        max_length=60,
        description="A user-attached tag, e.g. 'product management'.",
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

TailorTiebreaker = Literal["input_order", "length_desc", "length_asc"]
"""How stub mode breaks ties when bullets share a keyword-overlap score.

* ``input_order`` — preserve the order the user typed (default; tests-friendly).
* ``length_desc`` — longer bullets first (often the more substantive ones).
* ``length_asc`` — shorter bullets first (denser one-pagers).
"""


class _Strict(BaseModel):
    """Common config for every domain model.

    * ``extra="forbid"`` — typos in client payloads surface as 422s.
    * ``str_strip_whitespace`` — leading/trailing whitespace never lies in wait.
    * ``alias_generator=to_camel`` + ``populate_by_name=True`` — wire format is
      camelCase (matching JS/TS conventions and the eventual generated TS
      types), but clients can also send snake_case for a friendly transition.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


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
    """A single accomplishment bullet authored by the user.

    `keywords` are user-attached tags (e.g. "ownership", "product management",
    "mentoring"). They drive stub-mode ranking via JD overlap and are passed
    to the AI as additional context when a key is configured. Free-form so the
    user controls their own taxonomy; matching is case-insensitive.
    """

    id: StoryId
    text: str = Field(min_length=1, max_length=400)
    keywords: list[Keyword] = Field(
        default_factory=list,
        max_length=20,
        description="User-attached tags. Ranked against the JD in stub mode.",
    )


class Experience(_Strict):
    id: EntityId
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
        max_length=1000,
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


class TailorSettings(_Strict):
    """User-controlled knobs persisted client-side and sent per request.

    Kept separate from ``ResumeInput`` and ``JobDescription`` so the resume
    payload stays a pure description of facts, and so a future settings UI
    has a single, discoverable surface to bind to.
    """

    tiebreaker: TailorTiebreaker = "input_order"


class TailorRequest(_Strict):
    resume: ResumeInput
    jd: JobDescription
    settings: TailorSettings = Field(default_factory=TailorSettings)


class TailoredExperience(_Strict):
    """Per-experience selection: ordered IDs from the input pool."""

    experience_id: EntityId
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


# --- Resume parsing --------------------------------------------------------


class ParsedContact(_Strict):
    """Parser output — relaxed shape (anything may be missing).

    The frontend pre-fills the form with this and lets the user edit
    before submitting through the strict ``Contact`` validator.
    """

    name: str = ""
    email: str = ""
    phone: str | None = None
    location: str | None = None
    website: str | None = None
    linkedin: str | None = None
    github: str | None = None


class ParsedStory(_Strict):
    text: str
    keywords: list[str] = Field(default_factory=list)


class ParsedExperience(_Strict):
    company: str = ""
    title: str = ""
    location: str | None = None
    # Raw strings — parser preserves what it found, frontend reformats to
    # the strict YYYY/YYYY-MM PartialDate before submitting.
    start: str = ""
    end: str | None = None
    stories: list[ParsedStory] = Field(default_factory=list)


class ParsedEducation(_Strict):
    school: str = ""
    degree: str = ""
    field: str | None = None
    start: str | None = None
    end: str | None = None
    notes: str | None = None


class ParseWarning(_Strict):
    """A non-fatal hint to the user: 'we couldn't find X, please add it'."""

    field: str
    message: str


class ParsedResume(_Strict):
    """Best-effort structured extraction from a PDF resume."""

    contact: ParsedContact = Field(default_factory=ParsedContact)
    profile_seed: str = ""
    experiences: list[ParsedExperience] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    warnings: list[ParseWarning] = Field(default_factory=list)


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
    pdf: bool
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
    "EntityId",
    "Experience",
    "HealthStatus",
    "JobDescription",
    "Keyword",
    "ParseWarning",
    "ParsedContact",
    "ParsedEducation",
    "ParsedExperience",
    "ParsedResume",
    "ParsedStory",
    "PartialDate",
    "Problem",
    "RenderFormat",
    "RenderRequest",
    "ResumeInput",
    "Story",
    "StoryId",
    "TailorRequest",
    "TailorResult",
    "TailorSettings",
    "TailorTiebreaker",
    "TailoredExperience",
    "TemplateId",
    "TemplateMeta",
]
