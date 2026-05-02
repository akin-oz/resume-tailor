import type { ResumeInput } from "./types";

// Default seed data shown on first load. Replaced by user input as soon
// as they edit anything; persisted to localStorage between sessions.
export const sampleResume: ResumeInput = {
  contact: {
    name: "Ada Lovelace",
    email: "ada@example.com",
    location: "London, UK",
  },
  profileSeed:
    "Backend engineer with eight years building payment platforms. Led teams of three to seven, owned services from design through production rollout, and care a lot about clean APIs and observability.",
  experiences: [
    {
      id: "exp1",
      company: "Acme Payments",
      title: "Senior Backend Engineer",
      start: "2021-01",
      stories: [
        {
          id: "s1",
          text: "Designed payments API used by 12 internal services.",
          keywords: ["api design", "ownership"],
        },
        {
          id: "s2",
          text: "Mentored two engineers through promotion.",
          keywords: ["mentoring", "leadership"],
        },
        {
          id: "s3",
          text: "Cut p99 latency 40% by rewriting the auth path.",
          keywords: ["performance"],
        },
      ],
    },
  ],
  skills: ["Python", "PostgreSQL", "FastAPI", "Kubernetes"],
};
