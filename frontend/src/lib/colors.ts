/** Stable per-subject colour. Same hue set and same char-sum as core.py used,
 *  so a subject keeps its colour across reloads, machines and exports. */
export const PALETTE = [210, 145, 32, 275, 0, 190, 95, 315, 250, 55, 170, 290]

export function hueFor(label: string): number {
  let sum = 0
  for (const ch of label) sum += ch.codePointAt(0) ?? 0
  return PALETTE[sum % PALETTE.length]
}
