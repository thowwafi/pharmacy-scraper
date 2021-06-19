from difflib import get_close_matches
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import InvalidArgumentException
import json
import ast
import argparse
from fuzzywuzzy import process
from fuzzywuzzy import fuzz
import os
from slugify import slugify
from urllib.parse import urlparse
import requests
from urllib3 import request
from Url import Url


HOME = os.getcwd()


def closeMatches(word, patterns):
    print(get_close_matches(word, patterns))


def get_subpages(driver, homepage_link):
    driver.get(homepage_link)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = []
    for link in soup.find_all('a', href=True):
        if 'https' not in link.get('href'):
            a_href = homepage_link + link.get('href')
        else:
            a_href = link.get('href')
        print("subpage", a_href)
        links.append(a_href)
    return links


def validate_homepage(link, row):
    session = requests.Session()
    session.trust_env = False
    response = session.get(link, verify=False)
    web_status = response.status_code
    got_it = []
    if web_status == 200:
        web_content = response.content
        soup = BeautifulSoup(web_content, 'html.parser')
        words = [row['name'], row['street'], row['zip'], row['city']]
        for word in words:
            res = soup(text=lambda t: word in t)
            # matches = closeMatches(word, soup.text.split(' '))
            if res:
                print('data', word)
                got_it.append(True)
            else:
                got_it.append(False)
    return True in got_it


def google_search(row, total, additional_params):
    driver = webdriver.Chrome(executable_path="./chromedriver")
    name = row['name']
    street = row['street']
    zip_code = row['zip']
    city = row['city']
    if additional_params:
        query = f"{name}+{street}+{zip_code}+{city}+{additional_params}"
    else:
        query = f"{name}+{street}+{zip_code}+{city}"
    query = query.replace("&", "and").replace(' ', '+')
    URL = f"https://google.com/search?q={query}"
    print("name", f"{name} {city}")
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    suggestions = []
    web_button = soup.find('a', class_='ab_button')
    web_button_link = None
    if web_button:
        web_button_link = web_button.get('href')
    for link in soup.findAll("h3")[:int(total)]:
        homepage_link = link.find_parent('a').get('href')
        # domain = urlparse(homepage_link).netloc
        # if not domain.startswith("http"):
        #     domain = f"{urlparse(homepage_link).scheme}://{domain}"
        # import pdb; pdb.set_trace()

        suggestions.append(homepage_link)
    # import pdb; pdb.set_trace()
    driver.quit()
    return web_button_link, suggestions


def read_data(path):
    return pd.read_csv(path, sep=";", encoding='cp1252')


def get_validated_urls(web_button_link, suggestions):
    validated_urls = []
    if web_button_link:
        is_valid = validate_homepage(web_button_link, row)
        if is_valid:
            print("valid", web_button_link)
            validated_urls.append({
                "url": web_button_link,
                "score": 100
            })
    for suggestion_link in suggestions:
        ratio = fuzz.ratio(row['name']+row['city'], suggestion_link)
        url_not_scraped = all(url['url'] != suggestion_link for url in validated_urls)
        if ratio > 50 and url_not_scraped:
            is_valid = validate_homepage(suggestion_link, row)
            if is_valid:
                print("valid", suggestion_link)
                validated_urls.append({
                    "url": suggestion_link,
                    "score": ratio
                })
    return validated_urls


def check_validated_urls(folder_path, file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return bool(data.get('suggestions'))


DATA_PATH = "./source/client_list.csv"
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-qty', required=True)
    # parser.add_argument('--start-over', nargs='?', const=1, type=bool)
    parser.add_argument('--start-index', nargs='?', const=1, type=int, default=0)
    parser.add_argument('--end-index', nargs='?', const=1, type=int, default=0)
    parser.add_argument('--continue-scraper', nargs='?', const=True, type=bool, default=False)
    args = parser.parse_args()

    search_qty = args.search_qty
    start_index = args.start_index
    end_index = args.end_index
    continue_scraper = args.continue_scraper
    print("search_qty", search_qty)
    print("start_index", start_index)
    print("end_index", end_index)
    print('continue_scraper', continue_scraper)
    df = read_data(DATA_PATH)
    if end_index == 0:
        end_index = 20
    for index, row in df.iterrows():
        if index >= start_index and  index <= end_index:
            slug_name = f"{slugify(row['name'])}-{slugify(row['city'])}"
            folder_path = os.path.join(HOME, "data", slug_name)
            file_path = os.path.join(folder_path, slug_name+".json")
            if continue_scraper:
                existed = check_validated_urls(folder_path, file_path)
                if existed:
                    continue
            additional_params = ''
            web_button_link, suggestions = google_search(row, search_qty, additional_params)
            validated_urls = get_validated_urls(web_button_link, suggestions)
            if not validated_urls:
                additional_params = 'address'
                web_button_link, suggestions = google_search(row, search_qty, additional_params)
                validated_urls = get_validated_urls(web_button_link, suggestions)

            str_row = row.to_json()
            row_json = ast.literal_eval(str_row)
            row_json['suggestions'] = validated_urls
            row_json['_id'] = index

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            with open(file_path, 'w', encoding='utf-8') as fn:
                json.dump(row_json, fn, indent=4, ensure_ascii=False)
