# Backend

FastAPI uygulaması; arayüzü ve API'yi aynı yerel sunucudan verir.
Kurulum ve çalıştırma için [ana README](../README.md) dosyasına bak.

```text
backend/app/
├── main.py                 # Uygulama, güvenlik başlıkları, statik arayüz
├── config.py               # .env okuma
├── models.py               # Source ve ContentItem veri yapıları
├── migrate.py              # SQLite → PostgreSQL taşıma
├── api/
│   ├── daily_routes.py     # /api/recommendations
│   └── account_routes.py   # /api/auth/*, /api/saved
├── services/
│   ├── collection.py       # Akışları eşzamanlı okuma ve birleştirme
│   ├── content.py          # Ortak modele/tarihe dönüşüm, URL tekrarları
│   ├── recommendation_policy.py  # Konu eşleştirme, tazelik, kontenjanlar
│   ├── daily.py            # Günlük seçki, havuz temizliği, arka plan tamamlama
│   └── auth.py             # Hesap, parola özeti, oturum, kayıtlar
├── repositories/
│   ├── database.py         # PostgreSQL/SQLite bağlantısı ve şema
│   ├── daily.py            # Havuz, günlük seçkiler, önerilmiş URL'ler
│   └── users.py            # Kullanıcılar, oturumlar, kaydedilenler
└── sources/
    ├── rss.py              # RSS 2.0 / YouTube Atom indirme ve çözümleme
    ├── daily_catalog.py    # Akış kaynakları ve kullanıcı örnekleri
    └── curated_library.py  # Tek tek kontrol edilmiş yazılar
```

Komutları ana proje klasöründen çalıştır; `backend` bir Python paketidir.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Testler ağa bağlanmaz ve geçici SQLite kullanır. `.env` içinde
`TEST_DATABASE_URL` varsa aynı testler PostgreSQL'de de çalışır; o veritabanındaki
tablolar her testte boşaltılır.
