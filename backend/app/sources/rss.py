"""RSS 2.0 akışını indir ve başlık/bağlantı/tarih alanlarını oku."""

from http.client import HTTPException
from html import unescape
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


TIMEOUT_SECONDS = 20
MAX_FEED_BYTES = 2 * 1024 * 1024  # Bu ilk kaynak için 2 MiB üst sınır.


class RssError(Exception):
    """İndirilemeyen veya okunamayan RSS kaynağı."""


def download_rss(url: str) -> bytes:
    """HTTP ile XML dosyasını indir; henüz haber alanlarını okuma."""
    request = Request(url, headers={"User-Agent": "GunlukKesif/0.1 (RSS learning project)"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            xml_data = response.read(MAX_FEED_BYTES + 1)
    except (OSError, HTTPException) as error:
        raise RssError(f"RSS kaynağı indirilemedi: {error}") from error

    if len(xml_data) > MAX_FEED_BYTES:
        raise RssError("RSS dosyası bu okuyucunun 2 MiB boyut sınırını aşıyor.")
    return xml_data


def parse_rss(xml_data: bytes) -> list[dict[str, str]]:
    """RSS 2.0 veya YouTube Atom; tam yazı/video yerine akış metaverisi."""
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError as error:
        raise RssError("Kaynak geçerli bir XML belgesi değil.") from error
    atom = "{http://www.w3.org/2005/Atom}"
    media = "{http://search.yahoo.com/mrss/}"
    channel = root.find("channel")
    if root.tag == "rss" and channel is not None:
        records = [(item.findtext("title", ""), item.findtext("link", ""),
                    item.findtext("pubDate", ""), item.findtext("description", ""))
                   for item in channel.findall("item")]
    elif root.tag == atom + "feed":
        records = []
        for item in root.findall(atom + "entry"):
            links = [link.get("href", "") for link in item.findall(atom + "link")
                     if link.get("rel", "alternate") == "alternate"]
            records.append((item.findtext(atom + "title", ""), links[0] if links else "",
                            item.findtext(atom + "published", ""),
                            item.findtext(media + "group/" + media + "description", "")))
    else:
        raise RssError("Kaynak RSS 2.0 veya Atom akışı değil.")
    articles = []
    for title, link, published_at, description in records:
        title, link = title.strip(), link.strip()
        try:
            parsed_link = urlsplit(link)
        except ValueError:
            continue
        if not title or parsed_link.scheme not in {"http", "https"} or not parsed_link.netloc:
            continue
        row = {"title": title, "link": link, "published_at": published_at.strip()}
        if description:
            row["description"] = unescape(re.sub(r"<[^>]+>", " ", description))[:3000].strip()
        articles.append(row)
    return articles
