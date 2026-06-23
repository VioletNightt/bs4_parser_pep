# utils.py
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException

from exceptions import ParserFindTagException
from constants import PEP_URL


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
    """Возвращает таблицу со списком PEP (старый сайт)."""
    table = soup.find('table', class_='pep-zero-table')
    if table is None:
        tables = soup.find_all('table')
        for t in tables:
            if t.find('a', href=re.compile(r'/peps/pep-\d+')):
                return t
    return table


def parse_pep_row(row):
    """
    Извлекает из строки таблицы:
    - номер PEP (int)
    - ссылку (str)
    - ключ статуса (str) – буквенный код из первой колонки или ''.
    Возвращает кортеж (pep_num, link, status_key) или None.
    """
    cols = row.find_all('td')
    if len(cols) < 2:
        return None

    first_col_text = cols[0].get_text(strip=True)
    if re.match(r'^[A-Z]+$', first_col_text):
        status_key = first_col_text
    else:
        status_key = ''

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
    """Извлекает статус PEP со страницы документа."""
    response = get_response(session, pep_url)
    if response is None:
        logging.warning(f'Не удалось загрузить страницу PEP {pep_num}')
        return None

    soup = BeautifulSoup(response.text, 'lxml')

    status = (
        _extract_from_dl_field_list(soup) or
        _extract_from_dt_status(soup) or
        _extract_from_status_label_in_tags(soup) or
        _extract_from_full_text(soup)
    )

    if status is None:
        logging.warning(f'Не удалось извлечь статус для PEP {pep_num}')
    return status


def _extract_from_dl_field_list(soup):
    """Стратегия 1: поиск <dl> с классом 'field-list' или 'rfc2822'."""
    dl = soup.find('dl', class_=re.compile(r'field-list|rfc2822'))
    if dl:
        dt = dl.find('dt', string=re.compile(r'Status', re.I))
        if dt:
            dd = dt.find_next_sibling('dd')
            if dd:
                return dd.get_text(strip=True) or None
    return None


def _extract_from_dt_status(soup):
    """Стратегия 2: любой <dt> со словом 'Status' прямо в soup."""
    dt = soup.find('dt', string=re.compile(r'Status', re.I))
    if dt:
        dd = dt.find_next_sibling('dd')
        if dd:
            return dd.get_text(strip=True) or None
    return None


def _extract_from_status_label_in_tags(soup):
    """Стратегия 3: ищем 'Status: ...' в тегах <p>, <span>, <div>."""
    status_pattern = re.compile(r'Status:\s*(.+)', re.I)
    for tag in soup.find_all(['p', 'span', 'div']):
        if tag.string and 'Status:' in tag.string:
            match = status_pattern.search(tag.string)
            if match:
                return match.group(1).strip()
    return None


def _extract_from_full_text(soup):
    """Стратегия 4: поиск по всему тексту страницы."""
    text = soup.get_text()
    status_pattern = re.compile(r'Status:\s*(.+)', re.I)
    match = status_pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


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
