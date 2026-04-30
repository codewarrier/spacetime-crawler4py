import requests
from bs4 import BeautifulSoup

response = requests.get("https://www.google.com/search?q=hwo+to+use+beautifulsoup+with+a+website&rlz=1C5AJCO_enUS1201US1201&oq=hwo+to+use+beautifulsoup+with+a+website&gs_lcrp=EgZjaHJvbWUyBggAEEUYOTIICAEQABgWGB4yCAgCEAAYFhgeMg0IAxAAGIYDGIAEGIoFMg0IBBAAGIYDGIAEGIoFMgcIBRAAGO8FMgoIBhAAGKIEGIkF0gEINTQ3NGowajeoAgCwAgA&sourceid=chrome&ie=UTF-8")
bs = BeautifulSoup(response, "html.parser")

for anchor in bs.find_all('a', href=True):
    print(anchor)