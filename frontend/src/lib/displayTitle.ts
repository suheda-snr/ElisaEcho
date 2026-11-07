/**
 * Display-only cleanup of a conversation title: collapses whitespace and removes stray spaces
 * before punctuation ("place . Can" -> "place. Can"). The stored title is never changed.
 */
export function displayTitle(raw: string): string {
  return raw
    .replace(/\s+/g, ' ')
    .replace(/\s+([.,!?;:])/g, '$1')
    .trim()
}
