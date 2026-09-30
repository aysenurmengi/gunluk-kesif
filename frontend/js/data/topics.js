// Konu kimliği, adı ve kart renginin tonu. Örnek içerik yok.
// "retired" konular seçicide görünmez ve yeni öneri almaz; geçmiş günlerdeki
// ve kaydedilmiş eski kartlar yine çizilebilsin diye tanımları durur.
export const topics = [
  { id: "guncel", hue: 25, name: "Güncel haberler" },
  { id: "teknoloji", hue: 250, name: "Teknoloji" },
  { id: "bilim", hue: 330, name: "Bilim" },
  { id: "ekonomi", hue: 155, name: "Ekonomi" },
  { id: "finans", hue: 100, name: "Finans" },
  { id: "yemek", hue: 70, name: "Yemek" },
  { id: "moda", hue: 345, name: "Moda ve giyim", retired: true },
  { id: "kitap", hue: 295, name: "Kitap" },
  { id: "spor", hue: 200, name: "Spor" },
];
export const activeTopics = topics.filter((topic) => !topic.retired);
