import hashlib
import re
from urllib.parse import urlparse, urljoin, parse_qs
from bs4 import BeautifulSoup
from collections import Counter, defaultdict


LONGEST_PAGE_LEN = -1
LONGEST_PAGE = ""
COMMON_WORDS = defaultdict(int)
BLACKLISTED_URLS = set()
VISITED_URLS = set()

PREVIOUSLY_SEEN_CONTENT_HASHES = set()

PAGES = 0
SUBDOMAINS = {}

STOPWORDS  = set([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", 
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", 
    "being", "below", "between", "both", "but", "by", "can't", "cannot", 
    "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", 
    "don't", "down", "during", "each", "few", "for", "from", "further", "had", 
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", 
    "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", 
    "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", 
    "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", 
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", 
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", 
    "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", 
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", 
    "the", "their", "theirs", "them", "themselves", "then", "there", "there's", 
    "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", 
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", 
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", 
    "when", "when's", "where", "where's", "which", "while", "who", "who's", 
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", 
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
])


ALLOWED_DOMAINS = ("ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu")

# Subdomains we've manually inspected and decided are traps / low-value.
BLOCKED_HOSTS = {
    "wics.ics.uci.edu",
    "ngs.ics.uci.edu",
    "seal.ics.uci.edu",
    "grape.ics.uci.edu",
    "gitlab.ics.uci.edu",
    "fano.ics.uci.edu",
}

BLOCKED_HOST_SUFFIXES = (
    ".ngs.ics.uci.edu",
)

MAX_URL_LENGTH = 250
MAX_PATH_SEGMENTS = 8
MAX_QUERY_PARAMS = 6
MAX_SEGMENT_LENGTH = 80
MAX_QUERY_PAGE = 20
MAX_PAGE_BYTES = 8 * 1024 * 1024
MIN_INFO_TOKENS = 60
MIN_UNIQUE_INFO_TOKENS = 20
MAX_PAGE_TOKENS = 50000

# File extensions we never want to fetch.
DISALLOWED_EXT = re.compile(
    r".*\.(css|js|bmp|gif|jpe?g|ico"
    r"|png|tiff?|mid|mp2|mp3|mp4|svg|webm|flv|m4a|sql|db"
    r"|wav|avi|mov|mpe?g|ram|m4v|mkv|ogg|ogv|pdf|ppsx|pps"
    r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
    r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
    r"|epub|dll|cnf|tgz|sha1"
    r"|thmx|mso|arff|rtf|jar|csv"
    r"|rm|smil|wmv|swf|wma|zip|rar|gz|war|apk|img|bak"
    r"|woff2?|ttf|eot|ics|mpg)$"
)

# Query keys that typically generate trap variants (sort/filter/session/wiki actions/etc.).
TRAP_QUERY_KEYS = {
    "do", "rev", "action", "sectok",          # DokuWiki
    "share", "replytocom", "redirect", "redirect_to", "s",   # WordPress/search
    "tab", "sort", "order", "filter", "view",  # generic faceted nav
    "ical", "outlook-ical", "eventdisplay",    # calendar exports
    "tribe-bar-date", "tribe_event_display", "tribe_events",  # The Events Calendar
    "format", "print", "version",
    "session", "sid", "phpsessid",
    "image", "media", "idx", "ns",             # DokuWiki media browsers
    "add-to-cart", "afg",
}

# Path fragments that point at machine-generated content with low value.
TRAP_PATH_FRAGMENTS = (
    "/files/", "/sampledata/",
    "/raw/", "/diff/", "/blame/",
    "/commit/", "/commits/", "/tree/", "/blob/",   # Git web UIs
    "/attachment/", "/attachments/",
    "/login", "/logout", "/signin", "/signout",
    "/wp-login", "/wp-admin",
    "/feed/", "/rss/", "/atom/",
    "/trackback/", "/cgi-bin/",
    "/~eppstein/pix",
    "/ca/rules/",
)


def in_scope(netloc):
    """Return True if netloc is exactly an allowed domain or a subdomain of one."""
    host = netloc.lower().split(":")[0]  # strip port if present
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)


def is_blocked_host(host):
    host = host.lower().split(":")[0]
    if host in BLOCKED_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES)


def has_repeated_segments(path):
    """True if any path segment repeats 3+ times (catches /a/b/a/b/a/b loops)."""
    segs = [s for s in path.split("/") if s]
    if not segs:
        return False

    counts = Counter(segs)
    if any(c >= 3 for c in counts.values()):
        return True

    n = len(segs)
    for window in range(1, (n // 3) + 1):
        for start in range(0, n - (3 * window) + 1):
            pattern = segs[start:start + window]
            if pattern == segs[start + window:start + (2 * window)] == segs[start + (2 * window):start + (3 * window)]:
                return True

    return False



def scraper(url, resp):
    global PAGES

    if resp.status != 200:
        BLACKLISTED_URLS.add(url)
        return []

    raw = getattr(resp, "raw_response", None)
    content = getattr(raw, "content", b"") or b""
    if len(content) > MAX_PAGE_BYTES:
        BLACKLISTED_URLS.add(url)
        return []
    if not is_html_like_response(raw):
        BLACKLISTED_URLS.add(url)
        return []

    if resp.status == 200:
        if url in BLACKLISTED_URLS:
            return []
        elif exact_duplicate(resp):
            BLACKLISTED_URLS.add(url)
            return []

    if resp.status == 200:
        token_list = tokenize(resp)
        if not has_informative_content(token_list):
            BLACKLISTED_URLS.add(url)
            return []
        PAGES += 1
        update_longest_page(url, len(token_list))
        update_common_words(token_list)
        print_report()
        
    
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]


def exact_duplicate(resp):
    try:
        soup = BeautifulSoup(resp.raw_response.content, 'html.parser')

        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        text = soup.get_text()
        
        text = ' '.join(text.split())

        content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        
        if content_hash in PREVIOUSLY_SEEN_CONTENT_HASHES:
            return True
        else:
            PREVIOUSLY_SEEN_CONTENT_HASHES.add(content_hash)
            return False

    except Exception as e:
        print(f"Error when checking duplicate: {e}" )
        return False

def update_longest_page(url, length):
    global LONGEST_PAGE_LEN
    global LONGEST_PAGE
    if length > LONGEST_PAGE_LEN:
        LONGEST_PAGE_LEN = length
        LONGEST_PAGE = url

def update_common_words(token_list):
    for token in token_list:
        if len(token) > 2 and token not in STOPWORDS:
            COMMON_WORDS[token] += 1


def has_informative_content(token_list):
    if len(token_list) < MIN_INFO_TOKENS:
        return False
    if len(token_list) > MAX_PAGE_TOKENS:
        return False

    informative_tokens = [t for t in token_list if len(t) > 2 and t not in STOPWORDS]
    if len(informative_tokens) < MIN_INFO_TOKENS:
        return False

    if len(set(informative_tokens)) < MIN_UNIQUE_INFO_TOKENS:
        return False

    return True


def is_html_like_response(raw_response):
    if raw_response is None:
        return False
    headers = getattr(raw_response, "headers", None)
    if not headers:
        return True

    content_type = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
    if not content_type:
        return True

    content_type = content_type.lower()
    return ("text/html" in content_type) or ("application/xhtml+xml" in content_type)


def tokenize(resp):
    try:
        bs_parser = BeautifulSoup(resp.raw_response.content, features='html.parser')
        tokens = []

        currWord = ""
        for char in bs_parser.get_text():
            if char.isalpha():
                currWord += char
            else:
                if currWord:
                    tokens.append(currWord.lower())
                currWord = ""
        if currWord:
            tokens.append(currWord.lower())

        return tokens
    except AttributeError:
        return []
    



def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    
    global VISITED_URLS

    links = []

    
    VISITED_URLS.add(url)

    global LONGEST_PAGE
    global SUBDOMAINS


    parsed = urlparse(url)
    path = parsed.path 
    host = parsed.hostname or ""

    if host not in SUBDOMAINS:
        SUBDOMAINS[host] = set()
    SUBDOMAINS[host].add(url.split("#")[0])

    if "/files/" in path or "/sampledata/" in path:
        BLACKLISTED_URLS.add(url)
        return []

    try:
        beautiful_soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return links


    for anchor in beautiful_soup.find_all('a', href = True): # anchor is the hyperlink tag
        href = anchor.get('href')
        if not href:
            continue
        try:
            full_url = urljoin(url, href)
        except (TypeError, ValueError):
            continue
        full_url = full_url.split('#', 1)[0].strip()
        if not full_url:
            continue

        if is_valid(full_url):
            links.append(full_url)


    return links
    
def is_valid(url):
    # Decide whether to crawl this url or not.
    # If you decide to crawl it, return True; otherwise return False.
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False

    # Scheme + scope.
    if parsed.scheme not in ("http", "https"):
        return False
    if not in_scope(parsed.netloc):
        return False

    # Manually blocked hosts.
    host = parsed.netloc.lower().split(":")[0]
    if is_blocked_host(host):
        return False

    # Hard URL-shape limits — single biggest trap killer.
    if len(url) > MAX_URL_LENGTH:
        return False
    path_segs = [s for s in parsed.path.split("/") if s]
    if len(path_segs) > MAX_PATH_SEGMENTS:
        return False
    if any(len(seg) > MAX_SEGMENT_LENGTH for seg in path_segs):
        return False
    params = parse_qs(parsed.query)
    if len(params) > MAX_QUERY_PARAMS:
        return False

    # Trap query keys (any match rejects).
    if any(k.lower() in TRAP_QUERY_KEYS for k in params):
        return False
    if "page" in params:
        for value in params["page"]:
            if value.isdigit() and int(value) > MAX_QUERY_PAGE:
                return False

    # Trap path fragments.
    path_lower = parsed.path.lower()
    if any(frag in path_lower for frag in TRAP_PATH_FRAGMENTS):
        return False

    # Structural traps.
    if has_repeated_segments(parsed.path):
        return False
    if is_calendar_trap(parsed):
        return False

    # Pagination cap: /page/N where N is large.
    m = re.search(r"/page/(\d+)", path_lower)
    if m and int(m.group(1)) > 20:
        return False

    # Already visited.
    if url in VISITED_URLS:
        return False

    # File-extension blacklist.
    if DISALLOWED_EXT.match(path_lower):
        return False

    return True


def is_calendar_trap(parsed):
    path = parsed.path.lower()

    # Common calendar/event paths can generate unbounded monthly/day views.
    if "/events/" in path or "/calendar/" in path:
        return True

    # Date-shaped paths such as /2026/05/06/ often indicate archive/calendar traversal.
    if re.search(r"/(19|20)\d{2}/\d{1,2}(/\d{1,2})?(/|$)", path):
        return True

    return False

def print_report():

    print(f"unique pgs {PAGES}")

    print(f"longest pg {LONGEST_PAGE} with {LONGEST_PAGE_LEN} words")
    
    print("common 50 words")
    for word, count in sorted(COMMON_WORDS.items(), key=lambda item: item[1], reverse=True)[:50]:
        print(f"{word}: {count}")
        
    print("subdomains and their pg cts")
    for host in sorted(SUBDOMAINS):
        print(f"{host}, {len(SUBDOMAINS[host])}")