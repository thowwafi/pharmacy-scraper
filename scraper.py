from difflib import get_close_matches
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
import json
import ast
import argparse
from fuzzywuzzy import fuzz
import os
from slugify import slugify
from urllib.parse import urlparse, urljoin
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from Url import Url
import traceback
import re


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


HOME = os.getcwd()
DATA_PATH = "./source/client_list.csv"


def closeMatches(word, patterns):
    print(get_close_matches(word, patterns))


def validate_homepage(link, row):
    """
        Home page validation, determine whether the website is valid or not.
        Args:
            - link (string): website url
            - row (dict): row of pharmacy datas (name, street, zip_code, city)
        Return
            - Boolean (True or False)
    """
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
            res = soup(text=lambda t: word in t) # check if the word is in website content
            if res:
                got_it.append(True)
            else:
                got_it.append(False)
    return True in got_it


def get_suggestions_from_google_search(row, total):
    """
        Run google search

        Args:
            - row (dict): row of pharmacy datas (name, street, zip_code, city)
            - search_qty (int): total suggestions output from google search

        Returns:
            - web_button_link: url from button at sidebar of google search results
            - suggestions: list of urls from google search suggestions
    """
    options = ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(executable_path="./chromedriver", options=options)
    name = row['name']
    street = row['street']
    zip_code = row['zip']
    city = row['city']
    query = f"{name}+{street}+{zip_code}+{city}"
    query = query.replace("&", "and").replace(' ', '+')
    URL = f"https://google.com/search?q={query}"
    print("name", f"{name} {city}")
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    web_button = soup.find('a', class_='ab_button')
    web_button_link = None
    if web_button:
        web_button_link = web_button.get('href')
    suggestions = []
    for link in soup.findAll("h3")[:int(total)]:
        homepage_link = link.find_parent('a').get('href')
        suggestions.append(homepage_link)

    driver.quit()
    return web_button_link, suggestions


def read_data(path):
    """
        Read data from CSV
        Args:
            - path (string): file location
        Return:
            - pandas dataframe
    """

    return pd.read_csv(path, sep=";", encoding='cp1252')


def check_suggestion_exists(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return bool(data.get('suggestions'))
    return False


def get_link_of_subpages(homepage_url):
    """
        Get sub page links from website content
        Args:
            - homepage_url (string): website url
        Return:
            - list of subpage urls
    """
    print('homepage_url', homepage_url)
    response = requests.get(homepage_url, verify=False)
    urls = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        a_tags = soup.find_all('a', href=True)
        links = [i.get('href') for i in a_tags]
        links = sorted(list(set(links)))
        links = [i for i in links if i.startswith('http') or i.startswith('/')]
        homepage_domain = urlparse(homepage_url).netloc
        for link in links:
            a_href = urljoin(homepage_url, link)
            domain = urlparse(a_href).netloc
            if domain == homepage_domain:
                urls.append(a_href)
    urls = sorted(list(set(urls)))
    return urls


def makeDirIfNotExists(path):
    """
        Make directory if not exists
        Args:
            - path (string): location of folder
    """
    if not os.path.exists(path):
        os.makedirs(path)


def write_output_to_json(path, data):
    """
        Write data to json file
        Args:
            - path (string): location of the file
            - data (list/dict): data
    """
    with open(path, 'w', encoding='utf-8') as fn:
        json.dump(data, fn, indent=4, ensure_ascii=False)


def remove_external_links(links):
    """
        Remove external links.
        Args:
            - links (list): list of subpages link
        Return:
            - only internal links
    """
    for link in links:
        urlparsed = urlparse(link)


def get_text_content_of_page(sub_url):
    """
        Read content of url
        Args:
            - sub_url (string): link of sub url
        Return:
            dict of url and text of website
    """
    print('sub_url', sub_url)
    resp = requests.get(sub_url, verify=False)

    soup = BeautifulSoup(resp.content, 'html.parser')
    body_raw = soup.get_text()

    # format the text
    body_raw = re.compile(r"\n").sub(" ", body_raw)
    body_raw = re.compile(r"\t").sub(" ", body_raw)
    body_raw = re.compile(r"\r").sub(" ", body_raw)
    body_raw = re.sub(' +', ' ', body_raw) # remove multiple spaces
    body_text = body_raw.strip()
    return {
        "url": sub_url,
        "text": body_text
    }


def create_file_path_for_subpage(sub_url, pharmacy_folder, index):
    """
        Prepare file path for subpages
        Args:
            - suburl (string): address of subpages url
            - pharmacy_folder (string): parent folder of subpages
            - index (int): number of iteration of subpages
        Return:
            - json file path
    """
    parsed = urlparse(sub_url)
    slug_domain = slugify(parsed.netloc)
    subpath = os.path.join(pharmacy_folder, 'subpages', slug_domain)
    makeDirIfNotExists(subpath)
    filename = f"{index}-{parsed.path}-{parsed.params}-{parsed.query}-{parsed.fragment}"
    if len(filename) > 100: # handle OS error filename too long
        filename = filename[:100]
    slug_subpage_filename = slugify(filename)
    if parsed.path == "/": # handle root of homepage
        slug_subpage_filename = '1-home'
    return os.path.join(subpath, slug_subpage_filename + ".json")


def run_scraper(row, continue_scraper, search_qty, slug_name, df_index):
    """
        Run Web Scraper
        Args:
            - row (dict): row of pharmacy datas (name, street, zip_code, city)
            - continue_scraper (bool): skip pharmacy that already scraped or start over from the beginning
            - search_qty (int): total suggestions output from google search
            - slug_name (string): name of pharmacy folder output
            - df_index (int): dataframe index
    """
    # 1. Initialize folder for output data
    pharmacy_folder = os.path.join(HOME, "data", slug_name)
    overview_path = os.path.join(pharmacy_folder, 'overview')
    makeDirIfNotExists(overview_path)

    # 2. Initialize file name for output data
    file_path = os.path.join(overview_path, slug_name+".json")

    # 3. Continue scraper to another pharmacy if data already scraped
    if continue_scraper and check_suggestion_exists(file_path):
        return

    # 4. Run google search
    validated_urls = []
    web_button_link, suggestions = get_suggestions_from_google_search(row, search_qty)
    if web_button_link: # Web button link considered as the desired home page url
        valid_url = {
            "url": web_button_link,
            "score": 100
        }
        validated_urls.append(valid_url)

    # 5. Check suggestion urls
    for suggestion_link in suggestions:
        ratio = fuzz.ratio(row['name']+row['city'], suggestion_link) # run fuzzy wuzzy with name and city
        url_not_scraped = all(url['url'] != suggestion_link for url in validated_urls) # check if url is not duplicate
        if ratio > 50 and url_not_scraped:
            is_valid = validate_homepage(suggestion_link, row)
            if is_valid:
                valid_url = {
                    "url": suggestion_link,
                    "score": ratio
                }
                validated_urls.append(valid_url)

    # 6. Check for subpages for every suggestions
    for valid_url in validated_urls:
        valid_url['subpages'] = get_link_of_subpages(valid_url.get('url'))

    # 7. Prepare dictionary for overview output    
    str_row = row.to_json()
    row_json = ast.literal_eval(str_row)
    row_json['suggestions'] = validated_urls
    row_json['_id'] = df_index

    # 8. Write data to json file output
    write_output_to_json(file_path, row_json)

    # 9. Get subpages contents
    for sub_urls in row_json.get('suggestions'):
        for index, sub_url in enumerate(sub_urls.get('subpages'), start=1):
            subpage_dict = get_text_content_of_page(sub_url)
            filepath = create_file_path_for_subpage(sub_url, pharmacy_folder, index)
            write_output_to_json(filepath, subpage_dict)


if __name__ == '__main__':
    # set argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-qty', required=True)
    parser.add_argument('--end-index', nargs='?', const=1, type=int, default=0)
    parser.add_argument('--continue-scraper', nargs='?', const=True, type=bool, default=False)
    args = parser.parse_args()

    search_qty = args.search_qty
    end_index = args.end_index
    continue_scraper = args.continue_scraper
    print("search_qty", search_qty)
    print('continue_scraper', continue_scraper)
    print("end_index", end_index)

    # read data from CSV file
    df = read_data(DATA_PATH)
    df = df.dropna() # there is one NaN data at index 3338

    if end_index == 0:
        end_index = len(df) # set index to the last data

    errors = []
    for index, row in df.iterrows():
        if index <= end_index:
            print('index', index)
            slug_name = f"{slugify(row['name'])}-{slugify(row['city'])}"
            try:
                run_scraper(row, continue_scraper, search_qty, slug_name, index)
            except Exception as e: # catch any errors
                tb = traceback.format_exc()
                error_string = slug_name + " " + tb
                folder_path = os.path.join(HOME, "log")
                errors_path = os.path.join(folder_path, 'errors.txt')
                with open(errors_path, "a") as myfile:
                    myfile.write(error_string)
                print('e', e)
                import pdb; pdb.set_trace()
                continue
