import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException

from constants import PEP_URL
from exceptions import ParserFindTagException, ParserConnectionError


def get_response(session, url):
    """Возвращает ответ или выбрасывает исключение."""
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        raise ParserConnectionError(f'Ошибка при загрузке страницы {url}')


def find_tag(soup, tag, attrs=None):
    """Ищет тег и выбрасывает исключение, если не найден."""
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        raise ParserFindTagException(f'Не найден тег {tag} {attrs}')
    return searched_tag


def get_pep_table(session):
    """
    Получает список всех PEP через JSON API.
    Возвращает список кортежей (номер, полный URL,
    предварительный статус-буква).
    """
    api_url = 'https://peps.python.org/api/peps.json'
    response = get_response(session, api_url)
    try:
        data = response.json()
    except json.JSONDecodeError:
        raise ParserConnectionError(
            'Не удалось распарсить JSON со списком PEP')

    result = []
    for pep_id, pep_info in data.items():
        if pep_id == '0':
            continue
        number = pep_info.get('number')
        if not number:
            continue
        pep_url = urljoin(PEP_URL, f'pep-{number:0>4}/')
        pep_type = pep_info.get('type', '')
        pep_status = pep_info.get('status', '')
        type_letter = pep_type[0] if pep_type else ''
        if pep_status in ('Active', 'Draft'):
            status_letter = ''
        else:
            status_letter = pep_status[0] if pep_status else ''
        preview_status = type_letter + status_letter
        result.append((number, pep_url, preview_status))
    return result


def get_pep_status_from_page(session, pep_url):
    """Получает актуальный статус со страницы PEP."""
    response = get_response(session, pep_url)
    soup = BeautifulSoup(response.text, 'lxml')

    status_dt = soup.find(
        lambda tag: tag.name == 'dt' and tag.get_text(
            strip=True).startswith('Status')
    )
    if status_dt is None:
        raise ParserFindTagException(
            f'Не найден тег dt со статусом на странице {pep_url}')

    status_dd = status_dt.find_next_sibling('dd')
    if status_dd is None:
        status_dd = status_dt.find_next('dd')
    if status_dd is None:
        raise ParserFindTagException(
            f'Не найден тег dd со статусом на странице {pep_url}')

    return status_dd.get_text(strip=True)
