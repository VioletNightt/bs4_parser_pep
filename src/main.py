import re
import logging
from urllib.parse import urljoin
from collections import defaultdict

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL
from outputs import control_output
from utils import (
    get_response, find_tag, get_pep_table,
    get_pep_status_from_page
)
from exceptions import ParserConnectionError, ParserFindTagException


WHATS_NEW_URL = 'https://docs.python.org/3/whatsnew/'


def whats_new(session):
    """Парсинг страницы What's New в Python."""
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    soup = BeautifulSoup(response.text, 'lxml')

    sections = soup.select(
        '#what-s-new-in-python div.toctree-wrapper li.toctree-l1')
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    errors = []

    for section in tqdm(sections, desc="Обработка версий Python"):
        version_a_tag = section.find('a')
        if version_a_tag is None:
            errors.append('Не найден тег a в секции')
            continue
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)

        try:
            response = get_response(session, version_link)
        except ParserConnectionError as e:
            errors.append(f'{e} при загрузке {version_link}')
            continue

        version_soup = BeautifulSoup(response.text, 'lxml')
        h1 = version_soup.find('h1')
        dl = version_soup.find('dl')
        dl_text = dl.text.replace('\n', ' ') if dl else ''
        results.append((version_link, h1.text if h1 else '', dl_text))

    for err in errors:
        logging.warning(err)

    return results


def latest_versions(session):
    """Парсинг боковой панели для получения списка версий Python."""
    response = get_response(session, MAIN_DOC_URL)
    soup = BeautifulSoup(response.text, 'lxml')

    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')

    a_tags = None
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise ParserFindTagException('Не найден список c версиями Python')

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
    soup = BeautifulSoup(response.text, 'lxml')

    zip_link = None
    for a_tag in soup.find_all('a', href=True):
        if a_tag['href'].endswith('.zip'):
            zip_link = a_tag['href']
            break

    if zip_link is None:
        raise ParserFindTagException('Не найдена ссылка на ZIP архив')

    archive_url = urljoin(downloads_url, zip_link)
    filename = archive_url.split('/')[-1]
    archive_path = downloads_dir / filename

    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)

    logging.info(f'Архив был загружен и сохранён: {archive_path}')
    print(f"\nАрхив успешно скачан: {archive_path}")


def pep(session):
    """Парсинг документов PEP: подсчёт статусов и логирование несовпадений."""
    pep_list = get_pep_table(session)

    status_count = defaultdict(int)
    errors = []
    mismatches = []

    for pep_number, pep_url, preview_status_char in tqdm(
            pep_list, desc='Обработка PEP'):
        expected_statuses = EXPECTED_STATUS.get(preview_status_char, ())
        try:
            actual_status = get_pep_status_from_page(session, pep_url)
        except (ParserConnectionError, ParserFindTagException) as e:
            errors.append(f'Ошибка при обработке PEP {pep_number}: {e}')
            continue

        if actual_status is None:
            errors.append(f'Не удалось получить статус для PEP {pep_number}')
            continue

        if actual_status not in expected_statuses:
            mismatches.append(
                f'Несовпадающие статусы:\n{pep_url}\n'
                f'Статус в карточке: {actual_status}\n'
                f'Ожидаемые статусы: {expected_statuses}'
            )

        status_count[actual_status] += 1

    for err in errors:
        logging.error(err)
    for mismatch in mismatches:
        logging.info(mismatch)

    # Формируем итоговую таблицу
    return [('Статус', 'Количество'),
            *status_count.items(),
            ('Всего', sum(status_count.values()))]


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    try:
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

    except Exception as e:
        logging.exception(f'Возникла ошибка при выполнении парсера: {e}')
        raise


if __name__ == '__main__':
    main()
