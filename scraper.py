import requests
from bs4 import BeautifulSoup
import pandas as pd
import webbrowser


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0"
MOBILE_USER_AGENT = "Mozilla/5.0 (Linux; Android 7.0; SM-G930V Build/NRD90M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.125 Mobile Safari/537.36"


def google_search(name):
    query = name.replace(' ', '+')
    URL = f"https://google.com/search?q={query}"
    headers = {"user-agent": USER_AGENT}

    resp = requests.get(URL, headers=headers)
    if resp.status_code == 200:
        print(name)

        soup = BeautifulSoup(resp.text, "html.parser")
        linkElements = soup.select('.r a')
        # print(linkElements)
        linkToOpen = min(2, len(linkElements))
        for i in range(linkToOpen):
            print(linkElements[i].get('href'))
            webbrowser.open(linkElements[i].get('href'))



def run_scraper():
    df = pd.read_csv("./data/client_list.csv", sep=";", encoding='cp1252')
    for index, row in df.iterrows():
        if index < 5:
            google_search(row['name'])


if __name__ == '__main__':
    run_scraper()
