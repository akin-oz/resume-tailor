// Opaque ID minting for experiences and stories.
//
// crypto.randomUUID() is safe across deletions — length-based IDs
// (e.g. `exp${experiences.length + 1}`) collide after a remove + re-add,
// which breaks the caller-minted ID contract the backend relies on.

export function newExperienceId(): string {
  return `exp-${crypto.randomUUID()}`;
}

export function newStoryId(experienceId: string): string {
  return `${experienceId}.${crypto.randomUUID()}`;
}
