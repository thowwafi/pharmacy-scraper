from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import InvalidArgumentException
import json
import ast
import argparse
from fuzzywuzzy import process
import os
from slugify import slugify
from urllib.parse import urlparse


home = os.getcwd()


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


def validate_homepage(driver, link, row):
    try:
        driver.get(link)
    except InvalidArgumentException as e:
        print(e)
        print(link)
        return False
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    datas = [row['name'], row['street'], row['zip'], row['city']]
    got_it = []
    if driver.title == 'Privacy error':
        got_it.append(False)
    for data in datas:
        res = soup(text=lambda t: data in t)
        if res:
            got_it.append(True)
        else:
            got_it.append(False)
    return True in got_it


def google_search(row, total):
    name = row['name']
    street = row['street']
    zip_code = row['zip']
    city = row['city']
    query = name.replace("&", "and").replace(' ', '+')
    URL = f"https://google.com/search?q={query}+{street}+{zip_code}+{city}"
    print("name", f"{name} {city}")
    driver = webdriver.Chrome(executable_path="./chromedriver")
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    homepages = []
    web_button = soup.find('a', class_='ab_button')
    web_button_link = ""
    if web_button:
        web_button_link = web_button.get('href')
        # homepages.append(homepage_link)
    for link in soup.findAll("h3")[:int(total)]:
        homepage_link = link.find_parent('a').get('href')
        # is_valid = validate_homepage(driver, homepage_link, row)
        # links = get_subpages(driver, homepage_link)
        # data = {
        #     "homepage": homepage_link,
        #     "subpages": links
        # }
        domain = urlparse(homepage_link).netloc
        if not domain.startswith("http"):
            domain = f"{urlparse(homepage_link).scheme}://{domain}"

        homepages.append(domain)
    results = process.extract(name+city, homepages, limit=int(total)+1)
    urls = []
    if web_button_link:
        is_valid = validate_homepage(driver, web_button_link, row)
        if is_valid:
            print("valid", web_button_link)
            urls.append(web_button_link)
    for res in results:
        if res[1] > 50:
            is_valid = validate_homepage(driver, res[0], row)
            if is_valid:
                print("valid", res[0])
                urls.append(res[0])
            else:
                print("invalid", res[0])
    driver.quit()
    return urls


def run_scraper(total):
    df = pd.read_csv("./data/client_list.csv", sep=";", encoding='cp1252')
    all_data = []
    for index, row in df.iterrows():
        if index > 29 and index < 100:
            links = google_search(row, total)
            str_row = row.to_json()
            row_json = ast.literal_eval(str_row)
            row_json['suggestions'] = list(set(links))
            row_json['_id'] = index
            slug_name = f"{slugify(row['name'])}-{slugify(row['city'])}"
            folder_path = os.path.join(home, "data", slug_name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            file_path = os.path.join(folder_path, slug_name+".json")
            with open(file_path, 'w', encoding='utf-8') as fn:
                json.dump(row_json, fn, indent=4, ensure_ascii=False)
            # str_row = row.to_json()
            # row_json = ast.literal_eval(str_row)
            # row_json['suggestions'] = links
            # row_json['_id'] = index
            # all_data.append(row_json)
    
    # with open("all_data.json", 'w', encoding='utf-8') as fn:
    #     json.dump(all_data, fn, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', required=True)
    args = parser.parse_args()

    total_suggestion = args.q

    run_scraper(total_suggestion)
