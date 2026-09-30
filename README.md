# Günlük Keşif

Türkçe makale, blog ve videoları öne çıkaran günlük içerik seçkisi.
Ücretli LLM kullanılmaz. Arayüz, Günlük Keşif v2 koyu tasarımına göre hazırlanmıştır.

## Çalıştırma

Proje klasöründe, önce eski sunucuyu Ctrl+C ile kapat:

```powershell
.\.venv\Scripts\python.exe serve.py
```

Arayüz: http://127.0.0.1:8000 — API belgeleri: http://127.0.0.1:8000/docs

Temiz kurulumda önce:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

API anahtarı gerekmez. `.env` yoksa veritabanı SQLite'tır (`data/discovery.sqlite3`).
Sunucu açılırken hangi veritabanını kullandığını yazar.

### PostgreSQL

`psql -U postgres` ile uygulamaya ayrı bir kullanıcı ve veritabanı aç:

```sql
CREATE ROLE gunluk_kesif LOGIN PASSWORD 'kendi-parolan';
CREATE DATABASE gunluk_kesif OWNER gunluk_kesif;
CREATE DATABASE gunluk_kesif_test OWNER gunluk_kesif; -- isteğe bağlı, testler için
```

`.env.example` dosyasını `.env` adıyla kopyalayıp parolayı yaz. Mevcut SQLite
arşivini taşımak için sunucu kapalıyken `python -m backend.app.migrate` çalıştır
(SQLite dosyasına yazmaz, tekrar çalıştırılabilir). `.env` ve `data/` git'e girmez.

## Günlük kullanım

- Ana sayfa bugünün seçkisini açar. Her başlıkta minimum iki içerik hedeflenir.
- Güncel hedefi 6 Türkiye/dünya haberi; Spor hedefi 3 gelişme veya branş içeriğidir.
- Ekonomi, Finans, Teknoloji, Kitap, Yemek ve Moda için hedef ikişer içeriktir.
- Konu ve Yazı/Video filtreleri mevcut günlük listeyi süzer.
- Yedi günlük takvim ve Geçmiş seçkiler menüsü kayıtlı eski günleri açar.
- Kayıt bulunmayan takvim günleri pasiftir; geçmiş içerik uydurulmaz.
- Tam seçkide Yenile aynı listeyi döndürür. Eksik konu varsa 15 dakika sonra kaynaklar
  arka planda yeniden okunur; sayfa beklemez, tamamlanan kartlar sonraki yenilemede görünür.
- Ertesi gün daha önce önerilen URL'ler elenir.
- Veriler PostgreSQL'de (`DATABASE_URL`) veya `data/discovery.sqlite3` içinde saklanır. Uygulama kapansa da arşiv kalır.
- Kaydettiklerim ve yer imi simgesi hesap ister: giriş yapmadan tıklayınca giriş/hesap
  oluşturma penceresi açılır. Kaydet'e basarak girdiysen o içerik hemen kaydedilir.
- Kaydettiklerin hesabında (veritabanında) saklanır; başka gün veya tarayıcıda da görünür.
  Hesaplardan önce bu tarayıcıda kaydedilenler ilk girişte hesaba aktarılır.
- Konu tercihlerin bu tarayıcıda tutulur. [Hesaplar ve oturum](docs/accounts.md).
- Tarayıcı/site verileri silinirse konu tercihleri ve oturum silinir; kaydettiklerin hesabında kalır.

İlk gün arşivde yalnızca Bugün görünür. Günlük kayıt o gün ilk erişimde oluşturulur;
bilgisayar kapalıyken otomatik çalışma yoktur. Yeni günlük RSS toplaması internet
ister; kaydedilmiş günler kaynaklara yeniden bağlanmadan açılır.

## Kaynak kapsamı ve tercihler

Teknoloji ve ekonomi önerileri kullanıcının verdiği örneklerin tarzına göre
süzülür. Farklı yayıncılar önceliklidir; iki içerik tamamlanamıyorsa aynı yayıncıdan
farklı bir içerik seçilebilir. Güncel'de yayıncı başına en fazla üç haber alınır.
Kartlarda seçim gerekçesi görünür.

Güncel teknoloji 30 gün, piyasa yorumları 7 gün ile sınırlıdır. Eski tarih/temel
konu anlatımları yalnızca içerik düzeyinde gerekçelendirilmişse önerilir.
Bebar Bilim, Mesele Ekonomi ve Evrim Ağacı örnekleri referans alındı. DataCamp
örneği erişim engeli nedeniyle bekleyen referans olarak saklandı; aktif öneri değil.

Evrim Ağacı RSS ve Mesele Ekonomi Atom akışları farklı yayıncılardan aday sağlar.
Bebar Bilim için doğrulanan örnek video var; otomatik kanal akışı henüz yok.
BBC Türkçe, TRT Gündem/Dünya/Spor ve Matematiksel RSS akışları da okunur.
Lezzet (yemek), ELLE Türkiye (moda), Kitap Haber (kitap) ve Mahfi Eğilmez (ekonomi)
akışları elle seçilmiş listenin tükenmemesi için eklendi; yazılar yine tek tek süzülür.
Finans bölümünde piyasa yorumları ve kontrol edilmiş SPK/ING eğitim içerikleri vardır.
Yemek, moda ve kitapta uygun yeni yazı sayısı akışlara bağlıdır; eksik günler `topic_shortfalls` ile görünür.

Bu bir kurallı ilk sürümdür; örneklerden otomatik öğrenen bir model veya tüm
interneti tarayan arama motoru değildir. Minimum iki uygun yeni içerik bulunamazsa
`topic_shortfalls` ile eksik konu gösterilir; tekrar veya uydurma kartla sayı doldurulmaz.
[Tercihler ve sınırlamalar](docs/selection-preferences.md).

Bugünün eski politikayla üretilmiş seçkisi sunucuyu yeniden başlatınca ilk erişimde
bir kez yenilenir. Geçmiş günler ve önerilmiş URL geçmişi korunur. Veritabanını silme.

Günlük API: `/api/recommendations`; geçmiş gün: `/api/recommendations?day=2026-09-30`.
Hesap ve kaydedilenler: `/api/auth/*`, `/api/saved`. Tüm uç noktalar `/docs` adresinde listelenir.

## Testler

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
node frontend/tests/api.test.js
node frontend/tests/preferences.test.js
node frontend/tests/account.test.js
```

PostgreSQL testleri yalnızca `TEST_DATABASE_URL` tanımlıysa çalışır; aksi halde atlanır.

Testler canlı ağa bağlanmadan geçici SQLite kullanır. Günlük tutarlılık, tekrar
engelleme, arşiv, eşzamanlı istekler, kaynak hataları ve frontend veri dönüşümü sınanır.

Ayrıntılı belgeler `docs/` klasöründedir: mimari, seçim kuralları, hesaplar, veritabanı
ve arayüz. Bu klasör yereldir ve git deposuna eklenmez; bağlantılar yalnızca yerel kopyada açılır.

## Kaynak notları

Tarih kartı seçki tarihini ve toplam içerik sayısını, liste başlığı filtrelenmiş sayıyı gösterir. Kaynak
indirme notları “Seçki notları” açılarak okunur; kaydın hazırlandığı ana aittir.
Bir akış o gün indirilemese de aynı yayıncının kayıtlı içeriği gösterilebilir.
Teknoloji başlığı eski arşivdeki Yapay zekâ kayıtlarını da kapsar. İlk açılışta
bütün konular seçilidir; sonraki açılışlarda bu tarayıcıdaki tercihin hatırlanır.
Tasarımı görmek için açık sayfayı Ctrl+F5 ile yenileyebilirsin.

## Arayüz

Koyu zemin, mor başlıklar, yeşil vurgular ve Archivo yazı tipi tasarım referansından
uyarlandı. Masaüstünde dikey kaydırma kart şeridini ilerletir; mobilde yatay
kaydırma ve oklar kullanılır. Kaydettiklerim ızgara görünümündedir. İşletim
sistemindeki hareketi azalt ayarı animasyonları kapatır ve ızgaraya geçer.

Yeni npm paketi veya derleme adımı gerekmez. Fontlar lisanslarıyla birlikte
projenin içinde sunulur. [Arayüzün dosya düzeni ve davranışı](docs/frontend-design.md).

## Konu kapsamı

Ekonomi; enflasyon, büyüme, istihdam ve ekonomik tarih. Finans; bütçe, birikim,
piyasalar ve yatırım araçlarının temel kavramları. Spor; spor dünyasındaki
gelişmeler, branş kuralları/teknikleri ve spor kültürüdür. Dünya haberleri şu an
Türkçe okunabilen BBC Türkçe ve TRT Dünya'dan gelir; Guardian'ın İngilizce akışı
kontrol edildi, Türkçe dil tercihi nedeniyle etkin kataloğa eklenmedi.
