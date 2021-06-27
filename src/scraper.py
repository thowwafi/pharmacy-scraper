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


def check_suggestion_exists(file_path):
    """
        Check if the current pharmacy already got suggestion links
        Args:
            - file_path (str): path to the json file
        Return:
            - True or False
    """
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return bool(data.get('suggestions'))
    return False


def get_all_links(url, pharmacy, home_url):
    urls = get_links_from_subpages(url)
    write_to_file(urls, pharmacy, home_url)
    for link in urls:
        print('link', link)
        if os.path.exists(slugify(link) + '.json'):
            break
        get_all_links(link, pharmacy, home_url)


def write_to_file(links, pharmacy, home_url):
    domain = urlparse(home_url).netloc
    slug_domain = slugify(domain)
    domain_path = os.path.join(pharmacy.subpages_path, slug_domain)
    makeDirIfNotExists(domain_path)
    url_list_path = os.path.join(domain_path, '0-url-list.json')

    if not os.path.exists(url_list_path):
        initial = {
            "home_url": home_url,
            "sublinks": []
        }
        with open(url_list_path, 'w', encoding='utf-8') as fn:
            json.dump(initial, fn, indent=4, ensure_ascii=False)

    with open(url_list_path, 'r') as f:
        data_urls = json.load(f)
    sublinks = data_urls.get("sublinks")
    count = 0
    import pdb; pdb.set_trace()
    for link in links:
        if link not in sublinks and len(os.listdir(domain_path)) < 6:
            filepath = pharmacy.prepare_file_path_for_subpage(link, count)
            if not os.path.exists(filepath):
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


def write_output_to_json(path, data):
    """
        Write data to json file
        Args:
            - path (str): location of the file
            - data (list/dict): data
    """
    with open(path, 'w', encoding='utf-8') as fn:
        json.dump(data, fn, indent=4, ensure_ascii=False)


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


def create_file_path_for_subpage(sub_url, pharmacy_folder, index):
    """
        Prepare file path for subpages
        Args:
            - suburl (str): address of subpages url
            - pharmacy_folder (str): parent folder of subpages
            - index (int): number of iteration of subpages
        Return:
            - json file path
    """
    parsed = urlparse(sub_url)
    slug_domain = slugify(parsed.netloc)
    subpath = os.path.join(pharmacy_folder, 'subpages', slug_domain)
    makeDirIfNotExists(subpath)
    filename = f"{parsed.path}-{parsed.params}-{parsed.query}-{parsed.fragment}"
    if len(filename) > 100: # handle OS error filename too long
        filename = filename[:100]
    slug_subpage_filename = slugify(filename)
    if parsed.path == "/": # handle root of homepage
        slug_subpage_filename = '1-home'
    return os.path.join(subpath, slug_subpage_filename + ".json")


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


def read_json(path):
    with open(path, 'r', encoding='utf-8') as fn:
        data = json.load(fn)
    return data


def get_subpages_recursively(subpages, pharmacy, home_url, start_from, is_continue, max_pages):
    """
        Recursive funtion to get new sub pages in every subpage.

        Args:
            - links (list): list of subpages link in current homepage
            - pharmacy_folder (str): location of output pharmacy folder
            - home_url (str): domain of the current page scraped
            - start_from (int): index of looping to embed in the filename
            - is_continue (bool): additional argument of the scraper to continue or start over from beginning
            - max_pages: additional argument of the scraper to limit maximum subpages
    
    """
    pharmacy_data = pharmacy.read_pharmacy_data()
    get_data = [i for i in pharmacy_data.get('suggestions') if i.get('url') == home_url]
    stored_links = get_data[0].get('subpages')
    print('len(stored_links)', len(stored_links))
    count = start_from
    count_max = 0
    if start_from == 1:
        count_max = len(subpages)

    for subpage_url in subpages:
        print('len(subpages)', len(subpages))
        filepath = pharmacy.prepare_file_path_for_subpage(subpage_url, count)
        count_subpage_files = len(os.listdir(pharmacy.subpath))
        print('count_subpage_files', count_subpage_files)
        if os.path.exists(filepath):
            count += 1
            print('continue', 'continue')
            continue
        print('sub_link', subpage_url)
        response = requests.get(subpage_url, verify=False)
        if response.status_code == 200:
            body_text = get_text_content_of_page(response.content)
            subpage_dict = {
                "url": subpage_url,
                "text": body_text
            }
            pharmacy.save_subpage_content(filepath, subpage_dict)
            # import pdb; pdb.set_trace()

            # update subpage data is_scraped to True
            # get_sub_data = [i for i in get_data[0].get('subpages') if i.get('url') == subpage_url]
            # get_sub_data[0]['is_scraped'] = True
            # count_true = [i for i in get_data[0].get('subpages') if i.get('is_scraped') is True]
            # print('len(count_true)', len(count_true))
            # pharmacy.update_pharmacy_data(pharmacy_data)

            # check new links
            subpage_links = get_links_from_subpages(subpage_url, response.content)
            more_links = [i for i in subpage_links if i not in subpages]
            new_links = check_multiple_fragments_in_page(more_links, subpages)
            print('new_links', len(new_links))
            count += 1
            print('max_pages', max_pages)
            if count_max > max_pages:
                break
            if len(new_links) > 1:
                # for newlink in new_links:
                #     subpages.append(newlink)
                #     get_data[0]['subpages'].append(newlink)
            #         # data_url = {
            #         #     'url': newlink,
            #         #     'is_scraped': False
            #         # }
            #         # get_data[0]['subpages'].append(data_url)
            #         # newlink_list.append(data_url)
            #     print('count', count)
                # pharmacy.update_pharmacy_data(pharmacy_data)

                get_subpages_recursively(subpages=new_links, pharmacy=pharmacy, home_url=home_url,
                                         start_from=count, is_continue=is_continue, max_pages=max_pages)
    return subpages


# def run_scraper(row={}, continue_scraper=False, search_qty=2, slug_name="", df_index=0, max_pages=100):
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
    # Initialize folder for output data
    # pharmacy_folder = os.path.join(HOME, "data", slug_name)
    # overview_path = os.path.join(pharmacy_folder, 'overview')
    # makeDirIfNotExists(overview_path)

    # Initialize file name for output data
    # file_path = os.path.join(overview_path, slug_name+".json")

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

    # Check for subpages for every suggestions
    # for valid_url in validated_urls[1:]:
    #     home_url = valid_url.get('url')
        # internal_urls = get_links_from_subpages(home_url, response.content)
        # response = requests.get(home_url, verify=False)
        # if response.status_code == 200:
        #     valid_url['subpages'] = []
        #     for url in internal_urls:
        #         valid_url['subpages'].append(url)


    if continue_scraper and pharmacy.is_suggestions_exist:
        # if continue_scraper is True and suggestion links already exists
        # read data from existing file
        suggestion_list = pharmacy.get_suggestions()
    else:
        # use data from google search result
        pharmacy.create_pharmacy_data(suggestions=validated_urls)
        suggestion_list = validated_urls

    # Get subpages contents recursively
    for suggestion in suggestion_list:
        home_url = suggestion.get('url')
        get_all_links(url=home_url, pharmacy=pharmacy, home_url=home_url)
        import pdb; pdb.set_trace()
        # subpages = suggestion.get('subpages')
        # subpages_new = get_subpages_recursively(subpages=subpages, pharmacy=pharmacy, home_url=home_url,
        #                          start_from=1, is_continue=continue_scraper, max_pages=max_pages)
        import pdb; pdb.set_trace()
        # get_subpages_recursively(links=links, pharmacy_folder=pharmacy_folder, home_url=home_url,
        #                          start_from=1, is_continue=continue_scraper, max_pages=max_pages)


if __name__ == '__main__':
    # initialize argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-qty', required=True)
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
            pharmacy = Pharmacy(name=name, street=street, zip_code=zip_code, city=city, _id=index)
            # slug_name = f"{slugify(row['name'])}-{slugify(row['city'])}" # create slug for pharmacy identifier
            try:
                # run scraper by each pharmacy
                run_scraper(pharmacy=pharmacy, params=args)
                # run_scraper(row=row, continue_scraper=continue_scraper, search_qty=search_qty, slug_name=slug_name, df_index=index, max_pages=max_pages)
            except Exception as e: # catch any errors
                error_string = datetime.now().isoformat()+" "+pharmacy.slug_name+" "+traceback.format_exc() # store error messages
                write_errors(error_string)
                print('traceback', error_string)
                continue
