// Günleri UTC öğleninde hesaplamak, saat dilimi ve yaz saati kaymalarını önler.
export function todayInTurkey() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Istanbul", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const part = (name) => parts.find((p) => p.type === name).value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}
const parseDay = (day) => new Date(`${day}T12:00:00Z`);
export function dateLabels(day, today = day) {
  const date = parseDay(day);
  const format = (options) => new Intl.DateTimeFormat("tr-TR", { ...options, timeZone: "UTC" }).format(date);
  return {
    day: date.getUTCDate(), weekday: format({ weekday: "long" }),
    month: format({ month: "long", year: "numeric" }),
    full: format({ dateStyle: "long" }),
    title: day === today ? "Bugünün keşifleri" : `${format({ day: "numeric", month: "long" })} seçkisi`,
    issue: Math.floor((date - Date.UTC(date.getUTCFullYear(), 0, 1)) / 86400000) + 1,
  };
}
export function calendarDays(today, availableDates) {
  const available = new Set([...availableDates, today]);
  return Array.from({ length: 7 }, (_, index) => {
    const date = parseDay(today);
    date.setUTCDate(date.getUTCDate() - 6 + index);
    const value = date.toISOString().slice(0, 10);
    return { value, day: date.getUTCDate(), available: available.has(value),
      label: value === today ? "Bugün" : new Intl.DateTimeFormat("tr-TR", { weekday: "short", timeZone: "UTC" }).format(date),
      full: dateLabels(value).full };
  });
}
