import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from matplotlib import text
from collections import Counter

PAGES = set()
MAX_WORDS = 0
LONGEST_PAGE = ""
COUNTS = Counter()
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

INVALID_EXTENSIONS = {
    'css', 'js', 'bmp', 'gif', 'jpeg', 'jpg', 'ico', 'png', 'tiff', 'mid', 
    'mp2', 'mp3', 'mp4', 'wav', 'avi', 'mov', 'mpg', 'mpeg', 'ram', 'm4v', 'mkv', 
    'ogg', 'ogv', 'pdf', 'ps', 'eps', 'tex', 'ppt', 'pptx', 'doc', 'docx', 
    'xls', 'xlsx', 'names', 'data', 'dat', 'exe', 'bz2', 'tar', 'msi', 'bin', 
    '7z', 'psd', 'dmg', 'iso', 'epub', 'dll', 'cnf', 'tgz', 'sha1', 'thmx', 
    'mso', 'arff', 'rtf', 'jar', 'csv', 'rm', 'smil', 'wmv', 'swf', 'wma', 
    'zip', 'rar', 'gz'
}

EXT_PATTERN = re.compile(r".*\.(" + "|".join(INVALID_EXTENSIONS) + r")$", re.IGNORECASE)

def scraper(url, resp):
    links = extract_next_links(url, resp) 
    return [link for link in links if is_valid(link)]   #is this a zelda reference

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
    

    global PAGES
    global MAX_WORDS
    global LONGEST_PAGE
    global COUNTS
    global SUBDOMAINS

    links = list()
    if resp.status != 200 or resp.raw_response is None:
        print(f"Error fetching {url}: {resp.error}")
        return links            # needs to be changed here
    
    try:
        beautiful_soup = BeautifulSoup(resp.raw_response.content, 'lxml')
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return links

    for anchor in beautiful_soup.find_all('a', href = True): # anchor is the hyperlink tag
        href = anchor['href'] # the attribute of anchor that has the actual link
        full_url = urljoin(url, href).split('#')[0] # this makes the partial links like /page into full links
        
        if is_valid(full_url):
            links.append(full_url)
    
    for tag in beautiful_soup(['script', 'style']):
        tag.decompose()
    paras = list(beautiful_soup.stripped_strings)



    
    # Q1
    PAGES.add(url)


    # Q2
    word_count = sum(len(p.split()) for p in paras)
    if word_count > MAX_WORDS:
        globals()['MAX_WORDS'] = word_count
        globals()['LONGEST_PAGE'] = url.split('#')[0]


    # Q3
    page_text = " ".join(paras)
    tokens = []
    rawWords = re.findall(r"[a-z][a-z']*", page_text.lower())  # why we are using regex: to get lowercase letters only
    # without this, "hello,", "hello.", and "hello" become three different keys for ex
    for word in rawWords:
        if word not in STOPWORDS and len(word) > 1:
            tokens.append(word)
    COUNTS.update(tokens)


    #Q4
    host = urlparse(url).hostname or ""
    if host.endswith(".uci.edu"):
        if host not in SUBDOMAINS and len(SUBDOMAINS[host] >= )
            SUBDOMAINS[host] = set()
            
            
        SUBDOMAINS[host].add(url.split('#')[0])
    
    return links
    
def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
       
        host = parsed.hostname or ""
        if host in SUBDOMAINS and len(SUBDOMAINS[host]) > 1000:
            return False
    
        query_lower = parsed.query.lower()
        if any(action in query_lower for action in ["do=", "rev=", "action=", "sectok="]):
            return False

        target_path = parsed.path.lower()
        if EXT_PATTERN.match(target_path):
            return False

        if ["wics", "ngs", "gitlab", "grape", "doku", "calendar", "event"] in host:
            return False

        return True
    except TypeError:
        print ("TypeError for ", parsed)
        raise

def report():

    print(f"unique pgs {len(PAGES)}")

    print(f"longest pg {LONGEST_PAGE} with {MAX_WORDS} words")
    
    print("common 50 words")
    for word, count in sorted(COUNTS.items(), key=lambda item: item[1], reverse=True)[:50]:
        print(f"{word}: {count}")
        
    print("subdomains and their pg cts")
    for host in sorted(SUBDOMAINS):
        print(f"{host}, {len(SUBDOMAINS[host])}")
