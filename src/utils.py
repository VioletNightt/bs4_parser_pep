# utils.py
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException

from exceptions import ParserFindTagException
from src.constants import PEP_URL


def get_response(session, url):
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}',
            stack_info=True
        )


def find_tag(soup, tag, attrs=None):
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag


def get_pep_table(soup):
    """Возвращает таблицу со списком PEP."""
    table = soup.find('table', class_='pep-zero-table')
    if table is None:
        table = soup.find('table', {'class': 'rfc2822'})
    return table


def parse_pep_row(row):
    """
    Извлекает из строки таблицы:
    - номер PEP (int)
    - ссылку (str)
    - ключ статуса (str)
    Возвращает кортеж (pep_num, link, status_key) или None.
    """
    cols = row.find_all('td')
    if len(cols) < 3:
        return None

    first_col_text = cols[0].get_text(strip=True)
    status_key = first_col_text[1:] if len(first_col_text) > 1 else ''

    link_tag = cols[1].find('a')
    if link_tag is None:
        return None

    href = link_tag.get('href')
    pep_number = link_tag.get_text(strip=True)
    number_match = re.search(r'(\d+)', pep_number)
    if not number_match:
        return None

    pep_num = int(number_match.group(1))
    if pep_num == 0:
        return None

    full_link = urljoin(PEP_URL, href)
    return pep_num, full_link, status_key


def get_pep_status_from_page(session, pep_url, pep_num):
    """Загружает страницу PEP, извлекает статус, сравнивает с ожидаемым."""
    response = get_response(session, pep_url)
    if response is None:
        logging.warning(f'Не удалось загрузить страницу PEP {pep_num}')
        return None

    pep_soup = BeautifulSoup(response.text, features='lxml')
    dl = pep_soup.find('dl', class_='rfc2822 field-list simple')
    if dl is None:
        dl = pep_soup.find('dl')
        if dl is None:
            logging.warning(f'Не найден блок dl для PEP {pep_num}')
            return None

    status_dt = dl.find('dt', string='Status')
    if status_dt is None:
        status_dt = dl.find('dt', string=lambda s: s and 'Status' in s)
        if status_dt is None:
            logging.warning(f'Не найден тег dt со статусом для PEP {pep_num}')
            return None

    status_dd = status_dt.find_next_sibling('dd')
    if status_dd is None:
        logging.warning(f'Не найден тег dd со статусом для PEP {pep_num}')
        return None

    status_from_page = status_dd.get_text(strip=True)
    return status_from_page


def build_pep_results(pep_data):
    """Подсчитывает статусы и формирует итоговую таблицу."""
    from collections import Counter
    status_counter = Counter(item['status'] for item in pep_data)
    total_pep = len(pep_data)

    results = [('Статус', 'Количество')]
    for status, count in sorted(status_counter.items()):
        results.append((status, count))
    results.append(('Total', total_pep))
    return results
