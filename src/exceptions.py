class ParserFindTagException(Exception):
    """Вызывается, когда парсер не может найти тег."""
    pass


class ParserConnectionError(Exception):
    """Вызывается при ошибке соединения с сайтом."""
    pass


class ParserNotFoundError(Exception):
    """Вызывается, когда не найден ожидаемый элемент."""
    pass
