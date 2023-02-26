import os
os.environ["SCRAPERWIKI_DATABASE_NAME"] = "sqlite:///data.sqlite"

import re
import scraperwiki
import logging
from bs4 import BeautifulSoup
from datetime import date
import sqlitedb

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

base_url = 'https://onlineservice.launceston.tas.gov.au/eProperty/P1/PublicNotices/PublicNoticeDetails.aspx'
public_notices_url = base_url + '?r=P1.LCC.WEBGUEST&f=%24P1.ESB.PUBNOTAL.ENQ'
public_notice_details_url = base_url + '?r=P1.LCC.WEBGUEST&f=%24P1.ESB.PUBNOT.VIW&ApplicationId='

def visit_page(conn):
    page = BeautifulSoup(scraperwiki.scrape(public_notices_url), 'html.parser')
    records = get_applications(page)
    get_more_details(records, conn)

def get_applications(page):
    records = []
    for table in page.find_all('table', class_='grid'):
        record = {
            'date_scraped': date.today().isoformat()
        }
        for tr in table.find_all('tr'):
            header = tr.find('td', class_="headerColumn").get_text()
            if not  header:
                continue
            element = tr.find('td', class_="headerColumn").find_next_sibling("td")

            if header == 'Application ID':
                record['council_reference'] = element.find('a').get_text()
                record['info_url'] = public_notice_details_url + record['council_reference']
            elif header == 'Application Description':
                record['description'] = element.get_text()
            elif header == 'Property Address':
                record['address'] = re.sub(r'\sTAS\s+(7\d{3})$', r', TAS, \1', element.get_text())
            elif header == 'Closing Date':
                record['on_notice_to'] = element.get_text()
        records.append(record)
    log.info(f"Found {len(records)} public notices")
    return records

def get_more_details(records, conn):
    for record in records:
        log.info(f"Scraping Public Notice - Application Details for {record['council_reference']}")
        page = BeautifulSoup(scraperwiki.scrape(record['info_url']), 'html.parser')

        for table in page.find_all('table', class_='grid'):
            for tr in table.find_all('tr'):
                try:
                    header_element = tr.find('td', class_="headerColumn")
                    if not header_element:
                        continue
                    header = header_element.get_text()
                    value = tr.find('td', class_="headerColumn").find_next_sibling("td").get_text()
                    if value == '\xa0':
                        # empty cell containing only &nbsp;
                        value = "N/A"
                    if header == "Property Legal Description":
                        record['legal_description'] = value
                    elif header == "Application Received":
                        record['date_received'] = value
                    elif header == "Advertised On":
                        record['on_notice_from'] = value
                except Exception as e:
                    raise e
        store_data(record, conn)

def store_data(record, conn):
    data = (
        record['council_reference'],
        record['address'],
        record['description'],
        record['info_url'],
        record['date_scraped'],
        record['on_notice_from'],
        record['on_notice_to'],
        record['legal_description'],
    )
    sqlitedb.store_data(data, conn)

def main():
    conn = sqlitedb.create_database()
    if conn is not None:
        sqlitedb.create_table(conn)
        visit_page(conn)
    else:
        log.error("Error connecting to database!")
    quit()

if __name__ == '__main__':
    main()
