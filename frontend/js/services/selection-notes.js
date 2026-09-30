// Bunlar seçki hazırlanırken alınan notlardır; anlık bağlantı durumu değildir.
export function selectionNotes(sources, errors, skippedItemCount = 0) {
  const notes = [];
  const failed = sources.filter((source) => Object.hasOwn(errors, source.id));
  if (failed.length) {
    notes.push(`Bu seçki hazırlanırken ${failed.map((source) => source.name).join(", ")} kaynağından yeni içerik alınamadı. Daha önce kaydedilmiş içerikler yine gösterilebilir. Bu not kaydın oluşturulduğu ana aittir.`);
  }
  if (skippedItemCount) notes.push(`${skippedItemCount} içerik, konu veya bağlantı bilgisi geçersiz olduğu için gösterilemiyor.`);
  return notes;
}
