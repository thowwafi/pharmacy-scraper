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
import traceback
import re


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


HOME = os.getcwd()
DATA_PATH = "./source/client_list.csv"


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


def get_links_from_subpages(home_url, content):
    """
        Get sub page links from website content
        Args:
            - homepage_url (string): website url
        Return:
            - list of subpage urls
    """
    extensions = ('.pdf', '.jpg', '.png', '.mp4', '.wmv', '.gif', '.jpeg')
    registrations = ('login', 'register', 'account', 'password')
    external_links = ('mailto:', 'tel:', 'javascript:')
    urls = []
    soup = BeautifulSoup(content, 'html.parser')
    a_tags = soup.find_all('a', href=True)
    links = [i.get('href') for i in a_tags]
    links = sorted(list(set(links)))
    links = [i for i in links if not i.endswith(extensions)]
    links = [i for i in links if not i.endswith(external_links)]
    links = [i for i in links if not i.startswith('#')]
    links = [i for i in links if all(ext not in i for ext in extensions)] # handle url like: https://www.achillesapotheke.de/s/cc_images/cache_2414881223.jpg?t=1302626702
    links = [i for i in links if all(reg not in i for reg in registrations)]
    homepage_domain = urlparse(home_url).netloc
    for link in links:
        a_href = urljoin(home_url, link)
        domain = urlparse(a_href).netloc
        if domain == homepage_domain:
            urls.append(a_href)

    deduplicated = check_duplicate_urls(urls, urls)
    urls = sorted(list(set(deduplicated)))
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


def get_text_content_of_page(content):
    """
        Read content of url
        Args:
            - sub_url (string): link of sub url
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


def check_duplicate_urls(more_links, subpages_links):
    links = []
    for link in more_links:
        if "#" in link:
            parsed = urlparse(link)
            newurl = parsed.scheme +"://"+ parsed.netloc + parsed.path
            if newurl not in links and newurl not in subpages_links:
                links.append(newurl)
        else:
            links.append(link)
    return links


def read_json(path):
    with open(path, 'r', encoding='utf-8') as fn:
        data = json.load(fn)
    return data


def recursive_function(links=[], pharmacy_folder='', home_url='', start_from=1, is_continue=False):
    folder_name = os.path.basename(pharmacy_folder)
    overview_path = os.path.join(pharmacy_folder, 'overview', folder_name + ".json")
    pharmacy_data = read_json(overview_path)
    get_data = [i for i in pharmacy_data.get('suggestions') if i.get('url') == home_url]
    subpages_links = [i.get('url') for i in get_data[0].get('subpages')]
    for index, sub_url in enumerate(links, start=start_from):
        if is_continue and sub_url.get('is_scraped'):
            continue
        sub_link = sub_url.get('url')
        print('sub_link', sub_link)
        response = requests.get(sub_link, verify=False)
        if response.status_code == 200:
            body_text = get_text_content_of_page(response.content)
            filepath = create_file_path_for_subpage(sub_link, pharmacy_folder, index)
            subpage_dict = {
                "url": sub_link,
                "text": body_text
            }
            write_output_to_json(filepath, subpage_dict)

            get_sub_data = [i for i in get_data[0].get('subpages') if i.get('url') == sub_link]
            get_sub_data[0]['is_scraped'] = True
            write_output_to_json(overview_path, pharmacy_data)

            subpage_links = get_links_from_subpages(sub_link, response.content)
            more_links = [i for i in subpage_links if i not in subpages_links]
            new_links = check_duplicate_urls(more_links, subpages_links)
            print('new_links', len(new_links))
            if len(new_links) > 1:
                print('initial', len(get_data[0]['subpages']))
                newlink_list = []
                for newlink in new_links:
                    data_url = {
                        'url': newlink,
                        'is_scraped': False
                    }
                    get_data[0]['subpages'].append(data_url)
                    newlink_list.append(data_url)
                print('updated', len(get_data[0]['subpages']))
                write_output_to_json(overview_path, pharmacy_data)
                start_from = len(subpages_links) + 1
                recursive_function(links=newlink_list, pharmacy_folder=pharmacy_folder, home_url=home_url, start_from=start_from, is_continue=is_continue)


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
    # if continue_scraper and check_suggestion_exists(file_path):
    #     return

    # 4. Run google search
    validated_urls = []
    web_button_link, suggestions = get_suggestions_from_google_search(row, search_qty)
    if web_button_link: # Web button link considered as the desired home page url
        valid_url = {
            "url": web_button_link,
            "score": 100,
            "subpages": []
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
                    "score": ratio,
                    "subpages": []
                }
                validated_urls.append(valid_url)

    # 6. Check for subpages for every suggestions
    for valid_url in validated_urls:
        home_url = valid_url.get('url')
        response = requests.get(home_url, verify=False)
        if response.status_code == 200:
            valid_url['subpages'] = []
            internal_urls = get_links_from_subpages(home_url, response.content)
            for url in internal_urls:
                data_url = {
                    'url': url,
                    'is_scraped': False
                }
                valid_url['subpages'].append(data_url)


    # 7. Prepare dictionary for overview output    

    # 8. Write data to json file output
    if continue_scraper and check_suggestion_exists(file_path):
        pharmacy_data = read_json(file_path)
        suggestion_links = pharmacy_data.get('suggestions')
    else:
        str_row = row.to_json()
        row_json = ast.literal_eval(str_row)
        row_json['suggestions'] = validated_urls
        row_json['_id'] = df_index
        write_output_to_json(file_path, row_json)
        suggestion_links = validated_urls

    # 9. Get subpages contents
    for sub_urls in suggestion_links:
        home_url = sub_urls.get('url')
        links = sub_urls.get('subpages')
        recursive_function(links=links, pharmacy_folder=pharmacy_folder, home_url=home_url, start_from=1, is_continue=continue_scraper)


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
                continue
