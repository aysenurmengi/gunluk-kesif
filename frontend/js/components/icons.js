const paths = {
  "arrow-down": '<path d="M12 5v14m7-7-7 7-7-7"/>',
  "arrow-up-right": '<path d="M7 17 17 7M7 7h10v10"/>',
  "arrow-left": '<path d="m14 6-6 6 6 6"/>', "arrow-right": '<path d="m10 6 6 6-6 6"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M8 16H3v5"/>',
  bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
  check: '<path d="m20 6-11 11-5-5"/>', play: '<path d="m7 4 13 8-13 8z"/>',
  text: '<path d="M4 6h16M4 12h16M4 18h10"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
};
export function icon(name, size = 16) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ""}</svg>`;
}
