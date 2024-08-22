#!/usr/bin/env python3
"""
bundesAPI/handelsregister is the command-line interface for the shared register of companies portal for the German federal states.
You can query, download, automate and much more, without using a web browser.
"""

import argparse
import pathlib
import sys
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Dictionaries to map arguments to values
schlagwortOptionen = {
    "all": 1,
    "min": 2,
    "exact": 3
}


class HandelsRegister:
    def __init__(self, args):
        self.args = args

        chrome_options = Options()
        chrome_options.add_argument("--disable-search-engine-choice-screen")
        self.browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

        self.cachedir = pathlib.Path("cache")
        self.cachedir.mkdir(parents=True, exist_ok=True)

    def open_startpage(self):
        self.browser.get("https://www.handelsregister.de")

    def companyname2cachename(self, companyname):
        # map a companyname to a filename, that caches the downloaded HTML, so re-running this script touches the
        # webserver less often.
        return self.cachedir / companyname

    def search_company(self):
        cachename = self.companyname2cachename(self.args.schlagwoerter)
        if self.args.force == False and cachename.exists():
            with open(cachename, "r") as f:
                html = f.read()
                print("return cached content for %s" % self.args.schlagwoerter)
        else:
            # TODO implement token bucket to abide by rate limit
            # Use an atomic counter: https://gist.github.com/benhoyt/8c8a8d62debe8e5aa5340373f9c509c7
            advanced_search_link = self.browser.find_element(By.ID, "naviForm:erweiterteSucheLink")
            advanced_search_link.click()

            if self.args.debug == True:
                print(self.browser.title())

            # wait for the page to load
            self.browser.implicitly_wait(5)

            try:
                form = self.browser.find_element(By.NAME, "form")
            except Exception as e:
                print("Form not found:", e)
                return None

            text_field = form.find_element(By.ID, "form:schlagwoerter")
            text_field.send_keys(self.args.schlagwoerter)

            time.sleep(2)

            self.browser.find_element(By.ID, "form:erweiterteSucheLabel").click()

            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            submit_button = self.browser.find_element(By.ID, "form:btnSuche")
            submit_button.click()

            time.sleep(15)

            html = self.browser.page_source
            with open(cachename, "w") as f:
                f.write(html)

            # TODO catch the situation if there's more than one company?
            # TODO get all documents attached to the exact company
            # TODO parse useful information out of the PDFs
        return get_companies_in_searchresults(html)


def parse_result(result):
    cells = []
    for cellnum, cell in enumerate(result.find_all('td')):
        # assert cells[7] == 'History'
        cells.append(cell.text.strip())
    # assert cells[7] == 'History'
    d = {}
    d['court'] = cells[1]
    d['name'] = cells[2]
    d['state'] = cells[3]
    d['status'] = cells[4]
    d['documents'] = cells[5]  # todo: get the document links
    d['history'] = []
    hist_start = 8
    hist_cnt = (len(cells) - hist_start) / 3
    for i in range(hist_start, len(cells), 3):
        d['history'].append((cells[i], cells[i + 1]))  # (name, location)
    # print('d:',d)
    return d


def pr_company_info(c):
    for tag in ('name', 'court', 'state', 'status'):
        print('%s: %s' % (tag, c.get(tag, '-')))
    print('history:')
    for name, loc in c.get('history'):
        print(name, loc)


def get_companies_in_searchresults(html):
    soup = BeautifulSoup(html, 'html.parser')
    grid = soup.find('table', role='grid')
    # print('grid: %s', grid)
    results = []
    for result in grid.find_all('tr'):
        a = result.get('data-ri')
        if a is not None:
            index = int(a)
            # print('r[%d] %s' % (index, result))
            d = parse_result(result)
            results.append(d)
    return results


def parse_args():
    # Parse arguments
    parser = argparse.ArgumentParser(description='A handelsregister CLI')
    parser.add_argument(
        "-d",
        "--debug",
        help="Enable debug mode and activate logging",
        action="store_true"
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Force a fresh pull and skip the cache",
        action="store_true"
    )
    parser.add_argument(
        "-s",
        "--schlagwoerter",
        help="Search for the provided keywords",
        required=True,
        default="Gasag AG"  # TODO replace default with a generic search term
    )
    parser.add_argument(
        "-so",
        "--schlagwortOptionen",
        help="Keyword options: all=contain all keywords; min=contain at least one keyword; exact=contain the exact company name.",
        choices=["all", "min", "exact"],
        default="all"
    )
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()
    h = HandelsRegister(args)
    h.open_startpage()
    companies = h.search_company()
    if companies is not None:
        for c in companies:
            pr_company_info(c)
