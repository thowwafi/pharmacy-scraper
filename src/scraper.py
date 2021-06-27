from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
import json
import argparse
from fuzzywuzzy import fuzz
import os
from slugify import slugify
from urllib.parse import urlparse, urljoin
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import traceback
import re
from pharmacy import Pharmacy, makeDirIfNotExists
from datetime import datetime
from difflib import get_close_matches

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

SRC = os.getcwd()
HOME = os.path.dirname(SRC)
DATA_PATH = "../data/client_list.csv"


def write_errors(error_str):
    """
        Write error message to error log file
        Args:
            - error_str (str): error message
    """
    log_folder_path = os.path.join(HOME, "log")
    makeDirIfNotExists(log_folder_path)
    errors_path = os.path.join(log_folder_path, 'errors.txt') # create log file
    with open(errors_path, "a") as myfile:
        myfile.write(error_str)


def validate_homepage(link, pharmacy):
    """
        Home page validation, determine whether the website is valid or not.
        Args:
            - link (str): website url
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
        words = [pharmacy.name, pharmacy.street, pharmacy.zip_code, pharmacy.city]
        for word in words:
            matches = get_close_matches(word, soup.get_text().split())

            if matches:
                got_it.append(True)
            else:
                got_it.append(False)
    return True in got_it


def get_suggestions_from_google_search(pharmacy, search_qty):
    """
        Run google search

        Args:
            - row (dict): row of pharmacy datas (name, street, zip_code, city)
            - search_qty (int): total suggestions output from google search

        Returns:
            - web_button_link: url from button at sidebar of google search results
            - suggestions: list of urls from google search suggestions
    """
    # initialize chrome webdriver for selenium bot
    options = ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(executable_path="../driver/chromedriver", options=options)

    query = f"{pharmacy.name}+{pharmacy.street}+{pharmacy.zip_code}+{pharmacy.city}"
    query = query.replace("&", "and").replace(' ', '+') # handle space and character of query search
    URL = f"https://google.com/search?q={query}"
    print("name", f"{pharmacy.name} {pharmacy.city}")
    
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    """
    # search button with class ab_button and make sure have "website" word inside of it
    # English: "Website"
    # Indonesian: "Situs web"
    # German: "Webseite"
    # r"[W]eb" = text has "web" word
    # re.I = IGNORE CASE
    """
    pattern = re.compile(r"[W]eb", re.I)
    web_buttons = soup.find_all('a', class_='ab_button', text=pattern)
    web_button_link = None
    if web_buttons:
        web_button_link = web_buttons[0].get('href')

    # get list of suggestions by h3 tag in google search results and get the url of it
    # quantity of suggestions is based on search_qty argument
    suggestions = []
    for link in soup.findAll("h3")[:int(search_qty)]:
        homepage_link = link.find_parent('a').get('href')
        suggestions.append(homepage_link)

    driver.quit()
    return web_button_link, suggestions


def read_data(path):
    """
        Read data from CSV
        Args:
            - path (str): file location
        Return:
            - pandas dataframe
    """

    return pd.read_csv(path, sep=";", encoding='cp1252')


def get_all_subpages(url, pharmacy, home_url, max_pages, continue_scraper):
    """
        Get all subpages recursively
        Args:
            - url (str): url page that need to be scraped
            - pharmacy (obj): pharmacy data object
            - home_url (str): home page url for foldering purpose
            - max_pages (int): maximum pages to be scraped
            - continue_scraper (bool): continue the scraper or start over
    """
    urls = get_links_from_subpages(url) # get all links in current page
    write_to_file(urls, pharmacy, home_url, max_pages, continue_scraper) # store to json file url list
    for link in urls:
        filepath = pharmacy.prepare_file_path_for_subpage(link) # create filename json by slugify from url string
        if os.path.exists(filepath): # handle infinite loop
            print('link', link)
            break
        get_all_subpages(link, pharmacy, home_url, max_pages, continue_scraper)


def write_to_file(links, pharmacy, home_url, max_pages, continue_scraper):
    """
        Save text content as a json
        Args:
            - links (list): list of url in current page
            - pharmacy (obj): pharmacy data object
            - home_url (str): home page url for foldering purpose
            - max_pages (int): maximum pages to be scraped
            - continue_scraper (bool): continue the scraper or start over
    """
    url_list_path = pharmacy.create_url_list_file(home_url)

    with open(url_list_path, 'r') as f:
        data_urls = json.load(f)

    sublinks = data_urls.get("sublinks")
    for link in links:

        if link not in sublinks and len(os.listdir(pharmacy.domain_path)) <= max_pages:
            filepath = pharmacy.prepare_file_path_for_subpage(link)
            if continue_scraper and os.path.exists(filepath):
                continue
            print('link', link)
            response = requests.get(link, verify=False)
            body_text = get_text_content_of_page(response.content)
            data_url = {
                "url": link,
                "text": body_text
            }
            with open(filepath, 'w', encoding='utf-8') as fn:
                json.dump(data_url, fn, indent=4, ensure_ascii=False)
            sublinks.append(link)
            with open(url_list_path, 'w', encoding='utf-8') as fn:
                json.dump(data_urls, fn, indent=4, ensure_ascii=False)


def get_links_from_subpages(home_url):
    """
        Get sub page links from website content
        Args:
            - homepage_url (str): website url
        Return:
            - list of subpage urls
    """
    response = requests.get(home_url, verify=False)
    extensions = ('.pdf', '.jpg', '.png', '.mp4', '.wmv', '.gif', '.jpeg')
    registrations = ('login', 'register', 'account', 'password')
    external_links = ('mailto:', 'tel:', 'javascript:')
    urls = []
    soup = BeautifulSoup(response.content, 'html.parser')
    a_tags = soup.find_all('a', href=True)
    links = [i.get('href') for i in a_tags]
    links = sorted(list(set(links)))
    # remove url like: https://www.achillesapotheke.de/s/cc_images/cache_2414881223.jpg?t=1302626702
    links = [i for i in links if all(ext not in i for ext in extensions)]
    links = [i for i in links if all(reg not in i for reg in registrations)]
    links = [i for i in links if not i.startswith(external_links)]
    links = [i for i in links if not i.startswith('#')]
    homepage_domain = urlparse(home_url).netloc
    for link in links:
        a_href = urljoin(home_url, link)
        domain = urlparse(a_href).netloc
        if domain == homepage_domain:
            urls.append(a_href)

    deduplicated = check_multiple_fragments_in_page(urls, urls)
    urls = sorted(list(set(deduplicated)))
    return urls


def get_text_content_of_page(content):
    """
        Read content of url
        Args:
            - sub_url (str): link of sub url
        Return:
            dict of url and text of website
    """
    soup = BeautifulSoup(content, 'html.parser')
    body_raw = soup.get_text()

    # format the text
    body_raw = re.compile(r"\n").sub(" ", body_raw)
    body_raw = re.compile(r"\t").sub(" ", body_raw)
    body_raw = re.compile(r"\r").sub(" ", body_raw)
    body_raw = re.sub(' +', ' ', body_raw) # remove multiple spaces
    return body_raw.strip()


def check_multiple_fragments_in_page(more_links, subpages_links):
    """
        Check if one page has multiple fragments
        Args:
        Return:
            - Deduplicated links (list)
    """
    links = []
    for link in more_links:
        if "#" in link:
            # 'https://www.4.apotheken-website-vorschau.de/ratgeber#Artikel-13136'
            parsed = urlparse(link)
            newurl = parsed.scheme +"://"+ parsed.netloc + parsed.path
            if newurl not in links and newurl not in subpages_links:
                links.append(newurl)
        else:
            links.append(link)
    return links


def run_scraper(pharmacy, params):
    """
        Run Web Scraper
        Args:
            - row (dict): row of pharmacy datas (name, street, zip_code, city)
            - continue_scraper (bool): skip pharmacy that already scraped or start over from the beginning
            - search_qty (int): total suggestions output from google search
            - slug_name (str): name of pharmacy identifier
            - df_index (int): dataframe index
    """
    # Run google search
    search_qty = params.search_qty
    validated_urls = []
    web_button_link, suggestions = get_suggestions_from_google_search(pharmacy, search_qty)
    if web_button_link: # Web button link considered as the desired home page url
        valid_url = {
            "url": web_button_link,
            "score": 100
        }
        validated_urls.append(valid_url)

    # Check suggestion urls
    for suggestion_link in suggestions:
        ratio = fuzz.ratio(pharmacy.name+pharmacy.city, suggestion_link) # run fuzzy wuzzy with name and city
        url_not_duplicated = all(url['url'] != suggestion_link for url in validated_urls) # check if url is not duplicate
        if ratio > 50 and url_not_duplicated:
            is_valid = validate_homepage(suggestion_link, pharmacy)
            if is_valid:
                valid_url = {
                    "url": suggestion_link,
                    "score": ratio
                }
                validated_urls.append(valid_url)

    if continue_scraper and pharmacy.is_json_exists():
        # if continuing scraper and data already exist
        # check if suggestions already exists
        # if not create new data from google search results
        pharmacy_data = pharmacy.read_pharmacy_data()
        if not pharmacy_data.get('suggestions'):
            pharmacy_data = pharmacy.create_pharmacy_data(suggestions=validated_urls)
    else:
        pharmacy_data = pharmacy.create_pharmacy_data(suggestions=validated_urls)
    suggestion_list = pharmacy_data.get('suggestions')

    # Get subpages contents recursively
    for suggestion in suggestion_list:
        home_url = suggestion.get('url')
        pharmacy.prepare_subpage_folder(home_url)
        get_all_subpages(url=home_url, pharmacy=pharmacy, home_url=home_url, max_pages=max_pages, continue_scraper=continue_scraper) # run recursive function


if __name__ == '__main__':
    # initialize argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-qty', required=True, type=int)
    parser.add_argument('--end-index', nargs='?', const=1, type=int, default=0)
    parser.add_argument('--start-index', nargs='?', const=1, type=int, default=0)
    parser.add_argument('--continue-scraper', action='store_true')
    parser.add_argument('--max-pages', type=int)
    args = parser.parse_args()

    # set arguments into variables
    search_qty = args.search_qty
    start_index = args.start_index
    end_index = args.end_index
    continue_scraper = args.continue_scraper
    max_pages = args.max_pages
    print("search_qty", search_qty)
    print('continue_scraper', continue_scraper)
    print("start_index", start_index)
    print("end_index", end_index)
    print("max_pages", max_pages)

    # read data from CSV file
    df = read_data(DATA_PATH)
    df = df.dropna() # there is one NaN data at index 3338

    # handling default ondex filter
    if not start_index:
        start_index = 0
    if not end_index:
        end_index = len(df) 

    errors = []
    for index, row in df.iterrows(): # loop through each row of pharmacy data
        if index >= start_index and index <= end_index: # filter data by index
            print('index', index)
            name = row['name']
            street = row['street']
            zip_code = row['zip']
            city = row['city']
            pharmacy = Pharmacy(name=name, street=street, zip_code=zip_code, city=city, _id=index) # create pharmacy object
            try:
                # run scraper by each pharmacy
                run_scraper(pharmacy=pharmacy, params=args)
            except Exception as e: # catch any errors
                error_string = datetime.now().isoformat()+" "+pharmacy.slug_name+" "+traceback.format_exc() # store error messages
                write_errors(error_string)
                print('traceback', error_string)
                continue
