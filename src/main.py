import logging
import re
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, PEP_URL
from outputs import control_output
from utils import (build_pep_results, find_tag, get_pep_status_from_page,
                   get_pep_table, get_response, parse_pep_row)

WHATS_NEW_URL = 'https://docs.python.org/3/whatsnew/'


def whats_new(session):
    """Парсинг страницы What's New в Python."""
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        logging.error('Не удалось загрузить страницу What\'s New')
        return

    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all('li',
                                              attrs={'class': 'toctree-l1'})

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python, desc="Обработка версий Python"):
        version_a_tag = section.find('a')
        if version_a_tag is None:
            logging.warning('Не найден тег a в секции')
            continue
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)

        version_response = get_response(session, version_link)
        if version_response is None:
            logging.warning(f'Не удалось загрузить страницу {version_link}')
            continue

        version_soup = BeautifulSoup(version_response.text, features='lxml')
        h1 = find_tag(version_soup, 'h1')
        dl = find_tag(version_soup, 'dl')
        dl_text = dl.text.replace('\n', ' ') if dl else ''

        results.append((version_link, h1.text if h1 else '', dl_text))

    return results


def latest_versions(session):
    """Парсинг боковой панели для получения списка версий Python."""
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')

    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')

    a_tags = None
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Не найден список c версиями Python')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'

    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)

        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''

        results.append((link, version, status))

    return results


def download(session):
    """Скачивание ZIP-архива документации Python."""
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)

    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        logging.error('Не удалось загрузить страницу download.html')
        return

    soup = BeautifulSoup(response.text, 'lxml')

    zip_link = None
    for a_tag in soup.find_all('a', href=True):
        if a_tag['href'].endswith('.zip'):
            zip_link = a_tag['href']
            break

    if zip_link is None:
        logging.error('Не найдена ссылка на ZIP архив')
        return

    archive_url = urljoin(downloads_url, zip_link)
    filename = archive_url.split('/')[-1]
    archive_path = downloads_dir / filename

    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)

    logging.info(f'Архив был загружен и сохранён: {archive_path}')
    print(f"\nАрхив успешно скачан: {archive_path}")


def pep(session):
    response = get_response(session, PEP_URL)
    if response is None:
        logging.error('Не удалось загрузить страницу PEP')
        return

    soup = BeautifulSoup(response.text, features='lxml')
    table = get_pep_table(soup)
    if table is None:
        logging.error('Не найдена таблица со списком PEP')
        return

    pep_data = []
    rows = table.find_all('tr')
    for row in tqdm(rows[1:], desc="Сбор данных о PEP"):
        parsed = parse_pep_row(row)
        if parsed is None:
            continue

        pep_num, full_link, status_key = parsed
        status_from_page = get_pep_status_from_page(
            session, full_link, pep_num)
        if status_from_page is None:
            continue

        expected_statuses = EXPECTED_STATUS.get(status_key, ())
        if expected_statuses and status_from_page not in expected_statuses:
            logging.info(
                f'Несовпадающие статусы:\n'
                f'{full_link}\n'
                f'Статус в карточке: {status_from_page}\n'
                f'Ожидаемые статусы: {list(expected_statuses)}\n'
            )

        pep_data.append({
            'number': pep_num,
            'link': full_link,
            'status': status_from_page,
        })

    return build_pep_results(pep_data)


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()

    if args.clear_cache:
        session.cache.clear()
        print("Кеш очищен")

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)


if __name__ == '__main__':
    main()
