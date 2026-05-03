// Hand-written domain types matching the backend's camelCase wire format.
// Mirrors api/app/domain/models.py — keep them in sync until openapi-typescript
// codegen lands.

export type Archetype =
  | "backend"
  | "frontend"
  | "fullstack"
  | "data"
  | "ml"
  | "platform"
  | "mobile"
  | "generalist";

export type TemplateId = "modern" | "classic" | "compact";
export type RenderFormat = "html" | "pdf";
export type Tiebreaker = "input_order" | "length_desc" | "length_asc";

export interface Contact {
  name: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  website?: string | null;
  linkedin?: string | null;
  github?: string | null;
}

export interface Story {
  id: string;
  text: string;
  keywords: string[];
}

export interface Experience {
  id: string;
  company: string;
  title: string;
  location?: string | null;
  start: string;
  end?: string | null;
  stories: Story[];
}

export interface Education {
  school: string;
  degree: string;
  field?: string | null;
  start?: string | null;
  end?: string | null;
  notes?: string | null;
}

export interface ResumeInput {
  contact: Contact;
  profileSeed: string;
  experiences: Experience[];
  education?: Education[];
  skills?: string[];
}

export interface JobDescription {
  text: string;
  archetypeOverride?: Archetype | null;
}

export interface TailorSettings {
  tiebreaker: Tiebreaker;
}

export interface TailorRequest {
  resume: ResumeInput;
  jd: JobDescription;
  settings?: TailorSettings;
}

export interface TailoredExperience {
  experienceId: string;
  storyIds: string[];
}

export interface TailorResult {
  profile: string;
  experiences: TailoredExperience[];
  skills: string[];
  archetypeUsed: Archetype;
  keywordsInjected: string[];
  droppedStoryIds: string[];
  profileFallbackUsed: boolean;
}

export interface RenderRequest {
  resume: ResumeInput;
  tailored: TailorResult;
  templateId: TemplateId;
  format: RenderFormat;
}

export interface TemplateMeta {
  id: TemplateId;
  name: string;
  description: string;
  previewUrl: string;
}

// --- Parser output (ParsedResume from /api/parse) -----------------------
// Relaxed shape — anything may be missing. Frontend converts to ResumeInput
// (with minted IDs and date format coercion) after the user reviews.

export interface ParsedContact {
  name: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  website?: string | null;
  linkedin?: string | null;
  github?: string | null;
}

export interface ParsedStory {
  text: string;
  keywords: string[];
}

export interface ParsedExperience {
  company: string;
  title: string;
  location?: string | null;
  start: string;
  end?: string | null;
  stories: ParsedStory[];
}

export interface ParsedEducation {
  school: string;
  degree: string;
  field?: string | null;
  start?: string | null;
  end?: string | null;
  notes?: string | null;
}

export interface ParseWarning {
  field: string;
  message: string;
}

export interface ParsedResume {
  contact: ParsedContact;
  profileSeed: string;
  experiences: ParsedExperience[];
  education: ParsedEducation[];
  skills: string[];
  warnings: ParseWarning[];
}
