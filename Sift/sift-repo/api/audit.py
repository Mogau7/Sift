import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

SKIP = {"script", "style", "noscript", "template"}


class Page(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = urlparse(base).hostname or ""
        self.title = ""; self.in_title = False
        self.meta = {}; self.canonical = ""; self.lang = ""; self.viewport = False
        self.h1 = []; self.h2 = 0; self._h1 = None
        self.imgs = 0; self.noalt = 0
        self.internal = 0; self.external = 0; self.nofollow = 0
        self.ld = 0; self.words = 0; self._skip = 0; self._ld = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in SKIP:
            self._skip += 1
            self._ld = tag == "script" and "ld+json" in a.get("type", "").lower()
            if self._ld: self.ld += 1
        elif tag == "html": self.lang = a.get("lang", "")
        elif tag == "title": self.in_title = True
        elif tag == "meta":
            k = (a.get("name") or a.get("property") or "").lower()
            if k: self.meta[k] = a.get("content", "")
            if k == "viewport": self.viewport = True
        elif tag == "link" and "canonical" in a.get("rel", "").lower(): self.canonical = a.get("href", "")
        elif tag == "h1": self._h1 = ""
        elif tag == "h2": self.h2 += 1
        elif tag == "img":
            self.imgs += 1
            if not a.get("alt", "").strip(): self.noalt += 1
        elif tag == "a" and a.get("href"):
            host = urlparse(urljoin("https://" + self.base, a["href"])).hostname or ""
            same = host.removeprefix("www.") == self.base.removeprefix("www.")
            if a["href"].startswith(("mailto:", "tel:", "#", "javascript:")): return
            if same: self.internal += 1
            else: self.external += 1
            if "nofollow" in a.get("rel", "").lower(): self.nofollow += 1

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip: self._skip -= 1; self._ld = False
        elif tag == "title": self.in_title = False
        elif tag == "h1" and self._h1 is not None: self.h1.append(self._h1.strip()); self._h1 = None

    def handle_data(self, d):
        if self.in_title: self.title += d
        if self._h1 is not None: self._h1 += d
        if not self._skip: self.words += len(re.findall(r"\w+", d))


def grade(fetch):
    p = Page(fetch["final_url"]); p.feed(fetch.get("html", ""))
    title = " ".join(p.title.split()); desc = " ".join(p.meta.get("description", "").split())
    robots = (p.meta.get("robots", "") + " " + fetch.get("x_robots", "")).lower()
    issues, passed = [], []

    def bad(sev, title_, fix): issues.append({"sev": sev, "title": title_, "fix": fix})

    if fetch["status"] != 200: bad("high", f"The page answered with status {fetch['status']}", "Search engines only index pages that return 200. Fix the route or redirect it somewhere that does.")
    if not fetch.get("html"): bad("high", "The response was not an HTML page", "Point Sift at a normal web page, not a file or an API.")
    if "noindex" in robots: bad("high", "This page tells search engines not to index it", "Remove the noindex directive if you want it to appear in results.")
    else: passed.append("Page is allowed to be indexed")
    if not title: bad("high", "No title tag", "Add a unique title of roughly 30 to 60 characters that says what the page is.")
    elif not 30 <= len(title) <= 60: bad("mid", f"Title is {len(title)} characters", "Aim for 30 to 60 so it is not cut off in results.")
    else: passed.append("Title length is fine")
    if not desc: bad("mid", "No meta description", "Write 70 to 160 characters that make someone want to click.")
    elif not 70 <= len(desc) <= 160: bad("low", f"Meta description is {len(desc)} characters", "Between 70 and 160 reads best in results.")
    else: passed.append("Meta description length is fine")
    if len(p.h1) == 0: bad("high", "No H1 heading", "Give the page one H1 that matches what people searched for.")
    elif len(p.h1) > 1: bad("mid", f"{len(p.h1)} H1 headings", "Keep one H1 and use H2 for the sections under it.")
    else: passed.append("Exactly one H1")
    if not p.canonical: bad("mid", "No canonical link", "Add a canonical URL so duplicates of this page do not compete with it.")
    else: passed.append("Canonical link present")
    if not p.viewport: bad("mid", "No viewport tag", "Without it the page is treated as not mobile friendly.")
    else: passed.append("Viewport tag present")
    if not p.lang: bad("low", "No lang attribute on the html tag", "Add lang=\"en\" or whichever language you write in.")
    if p.imgs and p.noalt / p.imgs > .2: bad("mid", f"{p.noalt} of {p.imgs} images have no alt text", "Describe each meaningful image in a few words.")
    elif p.imgs: passed.append("Images have alt text")
    if p.words < 300: bad("mid", f"Only about {p.words} words of visible text", "Thin pages struggle to rank. Say more, or merge this page into a stronger one.")
    else: passed.append("Enough text on the page")
    if not (p.meta.get("og:title") and p.meta.get("og:image")): bad("low", "Missing Open Graph tags", "Add og:title, og:description and og:image so shared links look right.")
    else: passed.append("Open Graph tags present")
    if not p.ld: bad("low", "No structured data", "Add JSON-LD that describes the page (Article, Product, Organization).")
    else: passed.append("Structured data found")
    if fetch["redirects"] > 2: bad("mid", f"{fetch['redirects']} redirects before the page loads", "Link straight to the final URL.")
    if fetch["bytes"] > 1_500_000: bad("mid", "The HTML is very heavy", "Over 1.5 MB of markup slows crawling. Trim inline scripts and data.")
    if fetch["ms"] > 2500: bad("low", f"Slow response ({fetch['ms']} ms)", "Server time over 2.5 seconds hurts crawling and visitors.")
    if not fetch["final_url"].startswith("https://"): bad("high", "The page is not served over HTTPS", "Move to HTTPS and redirect the old address.")

    order = {"high": 0, "mid": 1, "low": 2}; issues.sort(key=lambda i: order[i["sev"]])
    score = max(0, 100 - sum({"high": 15, "mid": 8, "low": 3}[i["sev"]] for i in issues))
    return {"url": fetch["final_url"], "status": fetch["status"], "ms": fetch["ms"], "score": score, "issues": issues, "passed": passed,
            "stats": {"title": len(title), "description": len(desc), "words": p.words, "images": p.imgs, "noalt": p.noalt,
                      "internal": p.internal, "external": p.external, "h2": p.h2}}
