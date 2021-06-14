from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
import json
import ast


def get_subpages(driver, homepage_link):
    driver.get(homepage_link)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = []
    for link in soup.find_all('a', href=True):
        if 'https' not in link.get('href'):
            a_href = homepage_link + link.get('href')
        else:
            a_href = link.get('href')
        links.append(a_href)
    return links


def google_search(name, street, zip_code, city):
    query = name.replace(' ', '+')
    URL = f"https://google.com/search?q={query}+{street}+{zip_code}+{city}"

    driver = webdriver.Chrome(executable_path="./chromedriver")
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    homepages = []
    for link in soup.findAll("h3")[:2]:
        homepage_link = link.find_parent('a').get('href')
        links = get_subpages(driver, homepage_link)
        data = {
            "homepage": homepage_link,
            "subpages": links
        }
        homepages.append(data)
    driver.quit()
    return homepages


def run_scraper():
    df = pd.read_csv("./data/client_list.csv", sep=";", encoding='cp1252')
    all_data = []
    for index, row in df.iterrows():
        if index < 5:
            links = google_search(row['name'], row['street'], row['zip'], row['city'])
            str_row = row.to_json()
            row_json = ast.literal_eval(str_row)
            row_json['sugestions'] = links
            row_json['_id'] = index
            all_data.append(row_json)
    
    with open("all_data.json", 'w', encoding='utf-8') as fn:
        json.dump(all_data, fn, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    run_scraper()
