from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
import json
import ast
import argparse
from fuzzywuzzy import process


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
    driver.get(link)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    datas = [row['name'], row['street'], row['zip'], row['city']]
    got_it = []
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
    query = name.replace(' ', '+')
    URL = f"https://google.com/search?q={query}+{street}+{zip_code}+{city}"
    print("name", name)
    driver = webdriver.Chrome(executable_path="./chromedriver")
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    homepages = []
    web_button = soup.find('a', class_='ab_button')
    if web_button:
        homepage_link = web_button.get('href')
        homepages.append(homepage_link)
    for link in soup.findAll("h3")[:int(total)]:
        homepage_link = link.find_parent('a').get('href')
        print("homepage_link", homepage_link)
        # is_valid = validate_homepage(driver, homepage_link, row)
        # links = get_subpages(driver, homepage_link)
        # data = {
        #     "homepage": homepage_link,
        #     "subpages": links
        # }
        homepages.append(homepage_link)
    results = process.extract(name+city, homepages, limit=int(total)+1)
    urls = []
    for res in results:
        if res[1] > 50:
            is_valid = validate_homepage(driver, res[0], row)
            if is_valid:
                urls.append(res[0])
    driver.quit()
    import pdb; pdb.set_trace()
    return urls


def run_scraper(total):
    df = pd.read_csv("./data/client_list.csv", sep=";", encoding='cp1252')
    all_data = []
    for index, row in df.iterrows():
        if index < 5:
            links = google_search(row, total)
            str_row = row.to_json()
            row_json = ast.literal_eval(str_row)
            row_json['suggestions'] = links
            row_json['_id'] = index
            with open(f"{row['name']}.json", 'w', encoding='utf-8') as fn:
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
