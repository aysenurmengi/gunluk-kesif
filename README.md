
Projeyi ziyaret etmek için; https://gunluk-kesif.vercel.app/

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

## Vercel'de yayınlama

`vercel.json` ve `pyproject.toml` hazırdır; Vercel FastAPI uygulamasını
`backend.app.main:app` üzerinden tek bir fonksiyon olarak çalıştırır (bölge: Frankfurt).

1. Vercel'de **Add New → Project** ile GitHub deposunu içe aktar ve dağıt.
2. Projede **Storage → Create Database → Neon (Postgres)** seç, bölgeyi
   Frankfurt (`aws-eu-central-1`) yap ve projeye bağla. `DATABASE_URL` otomatik eklenir.
3. **Settings → Environment Variables** altında en az 16 karakterlik rastgele bir
   `CRON_SECRET` ekle, sonra **Deployments → Redeploy** yap.

Tablolar ilk istekte oluşur. Vercel'in dosya sistemi kalıcı olmadığından orada
SQLite kullanılmaz; `DATABASE_URL` yoksa uygulama açık bir hatayla durur.
Zamanlanmış görevler (`/api/cron/daily`) Türkiye saatiyle yaklaşık 00:10'da yeni
günün seçkisini hazırlar; 08:10, 14:10 ve 19:10'da eksik konuları tamamlamayı dener
(ücretsiz planda saat içinde herhangi bir dakikada çalışabilir). Yerelde bu işi
sunucudaki arka plan iş parçacığı yapar.

## Günlük kullanım

- Ana sayfa bugünün seçkisini açar. Her başlıkta minimum iki içerik hedeflenir.
- Güncel hedefi 6 Türkiye/dünya haberidir.
- Diğer konularda hedef üç içeriktir: bir gelişme, bir video, bir derinlemesine yazı (en az iki).
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

Seçim ücretli yapay zekâ kullanmayan, açık kurallarla yapılır
(`backend/app/services/recommendation_policy.py`, politika sürümü 4):

- **Rol karışımı:** Güncel dışındaki her konuda bir *gelişme* (son bir haftanın
  önemli haberi/duyurusu), bir *video* ve bir *derinlik* (açıklayan/inceleyen yazı)
  hedeflenir. Kartta "Yeni gelişme", "İzlemeye değer" veya "Biraz derinleş" yazar.
- **Kaynak profili:** Her akışın yakın olduğu konular ve 1-3 arası kalite seviyesi
  vardır (`SOURCE_PROFILES`). Profil konuya ağırlık katar ama tek başına yetmez:
  içerikte konuya dair bir işaret olmalıdır (kitap sitesindeki konu dışı bir yazı kitap sayılmaz).
- **Kalite puanı:** kaynak seviyesi + başlıktaki açıklayıcı işaretler ("neden",
  "nasıl", "rehber", soru biçimi, tarih/kültür) + açıklama uzunluğu; tık tuzağı emojiler
  ve yayınevi tanıtımı puan düşürür. Yatırım turu duyurusu, anlık altın fiyatı, reklam,
  canlı yayın, burç yorumu gibi başlıklar hiç önerilmez.
- **Çeşitlilik:** Farklı yayıncılar önceliklidir; en az iki içerik tamamlanamıyorsa aynı
  yayıncıdan başka bir içerik seçilebilir. Güncel'de yayıncı başına en fazla üç haber alınır.

Kurallar 30.09.2026'da toplanan 213 aday elle etiketlenerek ayarlandı. Elle seçilmiş
içerikler tükendiğinde (ikinci günden itibaren) seçilenlerin iyi olma oranı eski kurallarda
%67, yeni kurallarda %88; iyi adayların bulunma oranı %32'den %96'ya çıktı.
Bu ölçüm tek günlük veriye dayanır; farklı günlerde sonuç değişebilir.

Tazelik: güncel haber 3 gün, spor haberi 7 gün, gelişme rolü 7 gün, piyasa yorumu 7 gün,
teknoloji/ekonomi 30 gün, bilim/kitap/yemek 60 gün. Eski temel konu anlatımları yalnızca
elle incelenmişse önerilir.

Konular: Güncel, Teknoloji, Bilim, Ekonomi, Finans, Kitap, Yemek, Spor. Moda ve giyim
30.09.2026'da kaldırıldı; geçmiş günlerdeki ve kaydedilmiş eski moda kartları görünmeye devam eder.

Akışlar: Evrim Ağacı (yazı ve YouTube), Matematiksel (bilim); Barış Özcan (teknoloji/bilim);
Webrazzi (teknoloji);
Mahfi Eğilmez, Mesele Ekonomi, TRT Haber Ekonomi (ekonomi/finans); Edebiyat Haber,
Kitap Haber (kitap); Lezzet, Yemek.com YouTube (yemek);
Socrates Dergi, TRT Spor YouTube, TRT Haber Spor (spor); BBC Türkçe, TRT Gündem/Dünya
(güncel). DW Türkçe ve ShiftDelete denendi; ölçümde uygun içerik çıkmadığı için eklenmedi.

Minimum iki uygun yeni içerik bulunamazsa `topic_shortfalls` ile eksik konu gösterilir;
tekrar veya uydurma kartla sayı doldurulmaz.
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

Teknoloji; yapay zekâ, yazılım, donanım ve teknolojinin gündelik hayata etkisi.
Bilim; doğa bilimleri, uzay, matematik, iklim ve bilimsel keşifler. Ekonomi; enflasyon, büyüme, istihdam ve ekonomik tarih. Finans; bütçe, birikim,
piyasalar ve yatırım araçlarının temel kavramları. Spor; spor dünyasındaki
gelişmeler, branş kuralları/teknikleri ve spor kültürüdür. Dünya haberleri şu an
Türkçe okunabilen BBC Türkçe ve TRT Dünya'dan gelir; Guardian'ın İngilizce akışı
kontrol edildi, Türkçe dil tercihi nedeniyle etkin kataloğa eklenmedi.
