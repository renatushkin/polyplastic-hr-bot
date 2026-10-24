"""группировка календарных сообщений без изменения сценария excel."""

MAX_TEXT_LIMIT = 3500


def clean_text(step):
    text = (step.get('text') or '').strip()
                                              
    if '# приложить' in text.casefold() or '#приложить' in text.casefold():
        return ''
    return text


def groups(items, max_length=MAX_TEXT_LIMIT):
    """items: (due, employee_id, step). группируем только соседние обычные шаги."""
    result = []
    current = None
    for due, employee_id, step in items:
        body = clean_text(step)
        if not body:
            continue
        interactive = bool([x for x in step.get('buttons', []) if x != 'Далее'])
        key = (due, employee_id)
                                                                
        if (current is None or current['key'] != key or interactive
                or current['interactive'] or len(current['text']) + len(body) + 3 > max_length):
            current = {'key': key, 'steps': [], 'text': '', 'interactive': interactive}
            result.append(current)
        current['steps'].append(step)
        current['text'] += ('\n\n' if current['text'] else '') + body
    return result
