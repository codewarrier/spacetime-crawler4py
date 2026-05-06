import hashlib
import re
from urllib.parse import urlparse, urljoin
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
    global MAX_WORDS
    if len > LONGEST_PAGE_LEN:
        LONGEST_PAGE_LEN = len
        LONGEST_PAGE = url
        MAX_WORDS = len

def update_common_words(token_list):
    for token in token_list:
        if token not in STOPWORDS:
            COMMON_WORDS[token] += 1


def tokenize(resp):
    try:
        bs_parser = BeautifulSoup(resp.raw_response.content, features='html.parser')
        tokens = []

        currWord = ""
        for char in bs_parser.get_text():
            if char.isalnum() and char.isascii():
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
    if url in VISITED_URLS:
        return links
    
    VISITED_URLS.add(url)

    global MAX_WORDS
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
    
def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:

        parsed = urlparse(url)
        netloc = parsed.netloc
        path = parsed.path
        query = parsed.query

        allowed_domains = (".ics.uci.edu", ".cs.uci.edu", ".informatics.uci.edu", ".stat.uci.edu")
        if not any(domain in netloc for domain in allowed_domains):
            return False

        
        if parsed.scheme not in set(["http", "https"]):
            return False

        
        if any(action in query for action in ["do=", "rev=", "action=", "sectok="]):
            return False

        if re.match(r"^.*?(/.+?/).*?\1.*$|^.*?/(.+?/)\2.*$", path):
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
    except TypeError:
        print ("TypeError for ", parsed)
        raise

def print_report():

    print(f"unique pgs {PAGES}")

    print(f"longest pg {LONGEST_PAGE} with {LONGEST_PAGE_LEN} words")
    
    print("common 50 words")
    for word, count in sorted(COMMON_WORDS.items(), key=lambda item: item[1], reverse=True)[:50]:
        print(f"{word}: {count}")
        
    print("subdomains and their pg cts")
    for host in sorted(SUBDOMAINS):
        print(f"{host}, {len(SUBDOMAINS[host])}")