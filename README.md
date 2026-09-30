# Günlük Keşif

**Canlı site:** https://gunluk-kesif.vercel.app/

Her gün, merak ettiğin konularda az ama iyi içerik: Türkçe makaleler, bloglar,
videolar ve güncel haberlerden oluşan kısa bir günlük seçki.

## Neler sunuyor?

- **Günlük seçki:** Her gün yeni bir liste hazırlanır; daha önce önerilen içerik tekrar gelmez.
- **Konular:** Güncel, Teknoloji, Bilim, Ekonomi, Finans, Kitap, Yemek ve Spor.
  İlgini çeken konuları seçebilir, yazı veya videoya göre süzebilirsin.
- **Karışık içerik:** Her konuda bir yeni gelişme, izlemeye değer bir video ve
  konuyu derinlemesine anlatan bir yazı hedeflenir.
- **Güncel haberler:** Türkiye ve dünyadan dengeli, farklı yayıncılardan haberler.
- **Geçmiş seçkiler:** Takvimden önceki günlerin seçkilerine dönebilirsin.
- **Kaydettiklerim:** Hesap açıp beğendiğin içerikleri kaydedebilir, istediğin
  cihazdan yeniden ulaşabilirsin.

## Nasıl seçiliyor?

İçerikler Evrim Ağacı, Matematiksel, Mahfi Eğilmez, Mesele Ekonomi, Barış Özcan,
Socrates Dergi, Edebiyat Haber, BBC Türkçe, TRT Haber gibi Türkçe kaynakların
akışlarından toplanır. Seçim, açık ve test edilmiş kurallarla yapılır:

- Kaynağın kalitesi ve konusu,
- Başlığın bir şeyi açıklayıp açıklamadığı ("neden", "nasıl", "rehber" gibi),
- İçeriğin ne kadar güncel olduğu,
- Yayıncı çeşitliliği.

Reklam, tık tuzağı başlıklar, yatırım turu duyuruları ve magazin elenir.
Ücretli yapay zekâ kullanılmaz.

## Teknik

- **Backend:** Python, FastAPI, PostgreSQL (Neon)
- **Frontend:** Derleme adımı olmayan HTML, CSS ve JavaScript
- **Yayın:** Vercel; seçki her gece zamanlanmış görevle hazırlanır
- **Güvenlik:** Parolalar scrypt ile özetlenir, oturumlar HttpOnly çerezle tutulur
