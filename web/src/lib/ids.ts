// Opaque ID minting for experiences and stories.
//
// crypto.randomUUID() is safe across deletions — length-based IDs
// (e.g. `exp${experiences.length + 1}`) collide after a remove + re-add,
// which breaks the caller-minted ID contract the backend relies on.
//
// Story IDs are NOT namespaced under their experience ID: that would
// produce ~77-char strings that violate the backend's 64-char EntityId
// cap, and the join is data-structural (each Experience holds its own
// stories), not string-parse, so a flat UUID is sufficient.

export function newExperienceId(): string {
  return `exp-${crypto.randomUUID()}`;
}

export function newStoryId(): string {
  return `s-${crypto.randomUUID()}`;
}
