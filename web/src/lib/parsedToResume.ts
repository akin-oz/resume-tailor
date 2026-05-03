import type { ParsedResume, ResumeInput } from "../types";

import { coerceDate } from "./dates";
import { newExperienceId, newStoryId } from "./ids";

/**
 * Convert a `ParsedResume` (the relaxed shape from the backend parser)
 * into the strict `ResumeInput` the form binds to.
 *
 * Two transformations the form needs:
 *   1. Mint fresh, opaque IDs for experiences and stories. The parser
 *      doesn't know about IDs; the form does.
 *   2. Coerce free-form date strings ("Jan 2021" / "1/2021" / "2021")
 *      into the strict `YYYY[-MM]` PartialDate format the backend's
 *      Pydantic validator accepts.
 */
export function parsedToResume(parsed: ParsedResume, fallbackName: string): ResumeInput {
  return {
    contact: {
      name: parsed.contact.name || fallbackName,
      email: parsed.contact.email || "",
      phone: parsed.contact.phone ?? null,
      location: parsed.contact.location ?? null,
      linkedin: parsed.contact.linkedin ?? null,
      github: parsed.contact.github ?? null,
      website: parsed.contact.website ?? null,
    },
    profileSeed: parsed.profileSeed,
    experiences: parsed.experiences.map((e) => {
      const expId = newExperienceId();
      return {
        id: expId,
        company: e.company,
        title: e.title,
        location: e.location ?? null,
        start: coerceDate(e.start),
        end: coerceDate(e.end) || null,
        stories: e.stories.map((s) => ({
          id: newStoryId(),
          text: s.text,
          keywords: s.keywords,
        })),
      };
    }),
    skills: parsed.skills,
  };
}
