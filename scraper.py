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

ALLOWED_DOMAINS = ("ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu")

DISALLOWED_EXT = re.compile(
    r".*\.(css|js|bmp|gif|jpe?g|ico|png|tiff?|mid|mp2|mp3|mp4"
    r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf|ps|eps|tex"
    r"|ppt|pptx|doc|docx|xls|xlsx|names|data|dat|exe|bz2|tar"
    r"|msi|bin|7z|psd|dmg|iso|epub|dll|cnf|tgz|sha1|thmx|mso"
    r"|arff|rtf|jar|csv|rm|smil|wmv|swf|wma|zip|rar|gz|war"
    r"|apk|img|sql|bak|svg|webp|woff2?|ttf|eot|ics|ppsx|mpg|pps|db|webm|flv|m4a)$"
)

# Query keys that typically generate trap variants (sort/filter/session/wiki actions/etc.).
TRAP_QUERY_KEYS = {
    "do", "rev", "action", "sectok",          # DokuWiki
    "share", "replytocom", "redirect_to",      # WordPress
    "tab", "sort", "order", "filter", "view",  # generic faceted nav
    "ical", "outlook-ical", "eventdisplay",    # calendar exports
    "format", "print", "version",
    "session", "sid", "phpsessid",
    "image", "media", "idx", "ns",             # DokuWiki media browsers
    "add-to-cart", "afg",                       # storefront/forms
}

# Path fragments that point at machine-generated content with low value.
TRAP_PATH_FRAGMENTS = (
    "/files/", "/sampledata/",
    "/raw/", "/diff/", "/blame/",
    "/commit/", "/commits/", "/tree/", "/blob/",      # Git web UIs
    "/attachment/", "/attachments/",
    "/login", "/logout", "/signin", "/signout",
    "/wp-login", "/wp-admin",
    "/feed/", "/rss/", "/atom/",
    "/trackback/", "/cgi-bin/",
)

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

def in_scope(netloc: str) -> bool:
    netloc = netloc.lower().split(":")[0]  # strip port if present
    return any(netloc == d or netloc.endswith("." + d) for d in ALLOWED_DOMAINS)


def has_repeated_segments(path: str) -> bool:
    """True if any path segment repeats 3+ times (e.g. /a/b/a/b/a/b/)."""
    segs = [s for s in path.split("/") if s]
    if not segs:
        return False
    counts = Counter(segs)
    return any(c >= 3 for c in counts.values())

def scraper(url, resp):
    global PAGES

    if resp.status != 200:
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

def update_longest_page(url, len):
    global LONGEST_PAGE_LEN
    global LONGEST_PAGE
    if len > LONGEST_PAGE_LEN:
        LONGEST_PAGE_LEN = len
        LONGEST_PAGE = url

def update_common_words(token_list):
    for token in token_list:
        if len(token) > 2 and token not in STOPWORDS:
            COMMON_WORDS[token] += 1


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
        href = anchor['href'] # the attribute of anchor that has the actual link
        full_url = urljoin(url, href).split('#')[0] # this makes the partial links like /page into full links
        
        if is_valid(full_url):
            links.append(full_url)


    return links
    
def is_valid(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False

    # Scheme + scope.
    if parsed.scheme not in ("http", "https"):
        return False
    if not in_scope(parsed.netloc):
        return False

    # Hard URL-shape limits — single biggest trap killer.
    if len(url) > 250:
        return False
    path_segs = [s for s in parsed.path.split("/") if s]
    if len(path_segs) > 8:
        return False

    params = parse_qs(parsed.query)
    if len(params) > 4:
        return False

    # Specific trap signals.
    if any(k.lower() in TRAP_QUERY_KEYS for k in params):
        return False
    path_lower = parsed.path.lower()
    if any(frag in path_lower for frag in TRAP_PATH_FRAGMENTS):
        return False
    if has_repeated_segments(parsed.path):
        return False
    if is_calendar_trap(parsed):
        return False

    # Pagination explosion: /page/N/ where N is large.
    m = re.search(r"/page/(\d+)", path_lower)
    if m and int(m.group(1)) > 20:
        return False

    # File-extension blacklist.
    if DISALLOWED_EXT.match(path_lower):
        return False

    return True


def is_calendar_trap(parsed):
    path = parsed.path.lower()
    query = parsed.query.lower()

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