"""Pure-Python resume parsing — text extraction + heuristic structuring.

No LLM. The technique stack predates them: PDF text → section detection
via header matching → per-section parsers (regex for emails/phones/dates,
bullet-character detection, a few layout heuristics).

This works on ~80% of standard single-column resumes. Multi-column
layouts and image-only PDFs degrade. The output is a *starting point* —
the frontend pre-fills the form and the user reviews/edits before
tailoring, so partial parses are acceptable. Where we know we missed
something we surface a ``ParseWarning``.

Design: the pipeline is a sequence of pure stages, each tested
independently. The PDF I/O lives in one function (``extract_pdf_text``)
and everything downstream is ``list[str] -> ParsedResume``.
"""

from __future__ import annotations

import re

import pypdfium2 as pdfium

from .models import (
    ParsedContact,
    ParsedEducation,
    ParsedExperience,
    ParsedResume,
    ParsedStory,
    ParseWarning,
)

# --- Regex patterns -------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Phone: 7+ digits, optional country code, common separators. Tight enough
# to skip years and ZIPs, loose enough for international formats.
_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}(?:[\s.-]?\d{1,4})?"
)

_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:linkedin\.com|github\.com|gitlab\.com|[a-z0-9-]+\.(?:dev|io|com|org|net|me|co))"
    r"/?[A-Za-z0-9._/?=&%-]*",
    re.I,
)

_MONTH = (
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\.?"
)
_DATE_TOKEN = rf"(?:{_MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}}-\d{{2}}|\d{{4}})"
_DATE_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*[-–—]\s*(?P<end>{_DATE_TOKEN}|Present|Current|Now|Today)",
    re.I,
)

_BULLET_CHARS = "•‣▪◦●○◆■□–—-*+>·▶►"
_BULLET_RE = re.compile(rf"^[\s ]*[{re.escape(_BULLET_CHARS)}]\s+(.+)$")

# Lines that look like a date by themselves (no other text).
_DATE_ONLY_RE = re.compile(rf"^\s*{_DATE_RANGE_RE.pattern}\s*$", re.I)


# --- Section header detection --------------------------------------------

_SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "summary": (
        "summary",
        "profile",
        "about",
        "about me",
        "objective",
        "professional summary",
        "career summary",
    ),
    "experience": (
        "experience",
        "work experience",
        "employment",
        "employment history",
        "work history",
        "professional experience",
        "career history",
    ),
    "education": (
        "education",
        "academic background",
        "academic history",
    ),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "technologies",
    ),
}


def _detect_section(line: str) -> str | None:
    """If ``line`` is a section header, return the section's canonical name."""
    norm = re.sub(r"[^a-z\s]", "", line.lower()).strip()
    if not norm or len(norm.split()) > 4:
        return None
    for section, headers in _SECTION_PATTERNS.items():
        if norm in headers:
            return section
    return None


# --- Stage 1: PDF text extraction ----------------------------------------


def extract_pdf_text(pdf_bytes: bytes) -> list[str]:
    """Extract non-empty lines from a PDF, preserving order.

    Plain text is enough for single-column resumes. Multi-column
    layouts come out interleaved — caller may detect via subsequent
    heuristics and surface a warning.
    """
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        lines: list[str] = []
        for page in pdf:
            tp = page.get_textpage()
            text = tp.get_text_range()
            for raw in text.splitlines():
                stripped = raw.strip()
                if stripped:
                    lines.append(stripped)
        return lines
    finally:
        pdf.close()


# --- Stage 2: split into sections ----------------------------------------


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Group lines under their nearest detected section header.

    Lines before the first detected header go under ``"header"`` (the
    contact block at the top of the resume).
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        section = _detect_section(line)
        if section:
            current = section
            sections.setdefault(current, [])
        else:
            sections[current].append(line)
    return sections


# --- Stage 3: per-section parsers ----------------------------------------


_SEGMENT_RE = re.compile(r"\s+[·•|]\s+")


def parse_contact(header_lines: list[str]) -> ParsedContact:
    """Find name + contact details in the header block.

    Many resumes pack multiple things onto a single line separated by
    ``·`` / ``•`` / ``|``. We scan both the whole line (for email/phone)
    and each segment (for location and per-host URL matching).
    """
    contact = ParsedContact()
    for line in header_lines:
        if not contact.email and (m := _EMAIL_RE.search(line)):
            contact.email = m.group(0)
        # URL/phone scans must not see the host within an email address.
        line_no_email = _EMAIL_RE.sub(" ", line)
        if not contact.phone and (m := _PHONE_RE.search(line_no_email)):
            digits = sum(c.isdigit() for c in m.group(0))
            # Avoid matching years (4 digits) or ZIPs.
            if digits >= 7:
                contact.phone = m.group(0).strip()
        for m in _URL_RE.finditer(line_no_email):
            url = m.group(0).strip()
            url_full = url if url.startswith("http") else f"https://{url}"
            if "linkedin.com" in url.lower() and not contact.linkedin:
                contact.linkedin = url_full
            elif "github.com" in url.lower() and not contact.github:
                contact.github = url_full
            elif not contact.website:
                contact.website = url_full

    # Name = first line that's not contact metadata, looks like a name
    # (1-5 capitalized words).
    if not contact.name:
        for line in header_lines:
            line_no_email = _EMAIL_RE.sub(" ", line).strip()
            if not line_no_email:
                continue
            if _URL_RE.search(line_no_email):
                continue
            if _PHONE_RE.search(line_no_email) and sum(c.isdigit() for c in line_no_email) >= 7:
                continue
            words = line_no_email.split()
            if not 1 <= len(words) <= 5:
                continue
            if all(w[0].isupper() for w in words if w[:1].isalpha()):
                contact.name = line_no_email
                break

    # Location: scan each ·/•/| segment of compound contact lines for a
    # "City, ST" or "City, Country" pattern.
    if not contact.location:
        for line in header_lines:
            for seg in _SEGMENT_RE.split(line):
                cand = _EMAIL_RE.sub(" ", seg).strip(" |·•-")
                if not cand or _URL_RE.search(cand):
                    continue
                if _PHONE_RE.search(cand) and sum(c.isdigit() for c in cand) >= 7:
                    continue
                if "," in cand and len(cand.split(",")) <= 3 and len(cand) <= 60:
                    contact.location = cand
                    break
            if contact.location:
                break

    return contact


def parse_summary(lines: list[str]) -> str:
    """Join summary lines into a single paragraph."""
    return " ".join(line.strip() for line in lines if line.strip())


def _split_into_blocks(lines: list[str]) -> list[list[str]]:
    """Split a section into per-entry blocks.

    Heuristic: a new entry starts at the first non-bullet line that
    follows a run of bullets. That handles the typical
    ``[title, dates, bullets..., next-title, next-dates, bullets...]``
    layout. Entries without bullets stay together until the next bullet
    sequence ends.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    last_was_bullet = False
    for line in lines:
        is_bullet = bool(_BULLET_RE.match(line))
        if not is_bullet and last_was_bullet and current:
            blocks.append(current)
            current = []
        current.append(line)
        last_was_bullet = is_bullet
    if current:
        blocks.append(current)
    return blocks


def _extract_bullets(lines: list[str]) -> tuple[list[ParsedStory], list[str]]:
    """Pull bullet-character lines out as stories. Return (stories, leftover)."""
    stories: list[ParsedStory] = []
    leftover: list[str] = []
    for line in lines:
        if m := _BULLET_RE.match(line):
            stories.append(ParsedStory(text=m.group(1).strip()))
        else:
            leftover.append(line)
    return stories, leftover


def _extract_date_range(lines: list[str]) -> tuple[str, str | None, list[str]]:
    """Find the first date range; return (start, end, lines_with_date_removed)."""
    for i, line in enumerate(lines):
        if m := _DATE_RANGE_RE.search(line):
            start = m.group("start")
            end_raw = m.group("end")
            end: str | None = (
                None if end_raw.lower() in {"present", "current", "now", "today"} else end_raw
            )
            # Strip the date range out; if the line is now empty, drop it.
            cleaned = (line[: m.start()] + line[m.end() :]).strip(" |·•-–—")
            new_lines = list(lines)
            if cleaned:
                new_lines[i] = cleaned
            else:
                new_lines.pop(i)
            return start, end, new_lines
    return "", None, lines


def _split_title_company(text: str) -> tuple[str, str]:
    """Split 'Title at Company' / 'Title | Company' / 'Title — Company' etc."""
    for sep in (" | ", " · ", " at ", " @ ", " — ", " – ", " - "):
        if sep in text:
            left, right = text.split(sep, 1)
            return left.strip(), right.strip()
    return text.strip(), ""


def parse_experience(lines: list[str]) -> tuple[list[ParsedExperience], list[ParseWarning]]:
    """Split experience section into per-job blocks."""
    warnings: list[ParseWarning] = []
    out: list[ParsedExperience] = []

    for block in _split_into_blocks(lines):
        if not block:
            continue
        stories, header = _extract_bullets(block)
        start, end, header = _extract_date_range(header)
        # Two common shapes after dates removed:
        #   ["Senior Engineer | Acme"]                        → one line
        #   ["Senior Engineer", "Acme"] or ["Acme", ...]      → multi-line
        title = ""
        company = ""
        location: str | None = None
        if header:
            first = header[0]
            t, c = _split_title_company(first)
            if c:
                title, company = t, c
            else:
                title = t
                if len(header) >= 2:
                    # Second line: company, possibly with location after a comma/pipe.
                    second = header[1]
                    for sep in (" | ", " · ", " — ", " – ", " - ", ", "):
                        if sep in second:
                            company, location = second.split(sep, 1)
                            company = company.strip()
                            location = location.strip()
                            break
                    else:
                        company = second
        out.append(
            ParsedExperience(
                title=title,
                company=company,
                location=location,
                start=start,
                end=end,
                stories=stories,
            )
        )

    if not out:
        warnings.append(ParseWarning(field="experience", message="No experience entries detected."))
    return out, warnings


def parse_education(lines: list[str]) -> tuple[list[ParsedEducation], list[ParseWarning]]:
    """Split education section into per-entry blocks."""
    warnings: list[ParseWarning] = []
    out: list[ParsedEducation] = []
    if not lines:
        return out, warnings

    for block in _split_into_blocks(lines):
        if not block:
            continue
        # Drop bullets — education usually doesn't have them, and any
        # leftover description goes into notes.
        stories, header = _extract_bullets(block)
        start, end, header = _extract_date_range(header)
        if not header:
            continue
        # First line: usually degree or school.
        first = header[0]
        # Try to split degree/school on common separators.
        degree, school = "", ""
        for sep in (" — ", " – ", " - ", " | ", " at ", ", "):
            if sep in first:
                degree, school = first.split(sep, 1)
                degree, school = degree.strip(), school.strip()
                break
        else:
            # Fallback: degree on line 1, school on line 2.
            degree = first
            if len(header) >= 2:
                school = header[1]
        notes_parts = [s.text for s in stories]
        if len(header) > 2:
            notes_parts.extend(header[2:])
        notes = " ".join(notes_parts) if notes_parts else None
        out.append(ParsedEducation(degree=degree, school=school, start=start, end=end, notes=notes))

    return out, warnings


def parse_skills(lines: list[str]) -> list[str]:
    """Skills can be comma/semicolon-separated, bullet-listed, or one-per-line."""
    out: list[str] = []
    for raw in lines:
        line = _BULLET_RE.match(raw)
        text = line.group(1) if line else raw
        # Split on commas, semicolons, pipes, bullets within the line.
        for chunk in re.split(r"[,;|·•]+", text):
            s = chunk.strip()
            if s and len(s) <= 60:
                out.append(s)
    # De-duplicate, preserve order.
    seen: set[str] = set()
    dedup: list[str] = []
    for s in out:
        key = s.lower()
        if key not in seen:
            dedup.append(s)
            seen.add(key)
    return dedup


# --- Top-level orchestrator ----------------------------------------------


def parse_resume_lines(lines: list[str]) -> ParsedResume:
    """Pure: list of lines → ParsedResume."""
    sections = split_sections(lines)
    contact = parse_contact(sections.get("header", []))
    profile_seed = parse_summary(sections.get("summary", []))
    experiences, exp_warnings = parse_experience(sections.get("experience", []))
    education, edu_warnings = parse_education(sections.get("education", []))
    skills = parse_skills(sections.get("skills", []))

    warnings = list(exp_warnings) + list(edu_warnings)
    if not contact.name:
        warnings.append(ParseWarning(field="contact.name", message="Could not detect a name."))
    if not contact.email:
        warnings.append(ParseWarning(field="contact.email", message="Could not detect an email."))
    if not skills:
        warnings.append(ParseWarning(field="skills", message="No skills section detected."))

    return ParsedResume(
        contact=contact,
        profile_seed=profile_seed,
        experiences=experiences,
        education=education,
        skills=skills,
        warnings=warnings,
    )


def parse_pdf(pdf_bytes: bytes) -> ParsedResume:
    """End-to-end: PDF bytes → ParsedResume."""
    lines = extract_pdf_text(pdf_bytes)
    return parse_resume_lines(lines)
