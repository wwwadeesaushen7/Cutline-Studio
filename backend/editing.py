"""Non-destructive clip edits. All stored word times remain source-relative."""
import re


def apply_edits(clip, settings):
    duration = clip['end'] - clip['start']
    start = settings.get('trim_start', 0)
    end = settings.get('trim_end')
    end = duration if end is None else end
    if start < 0 or end > duration + .001 or end - start < .25:
        raise ValueError('Keep at least 0.25 seconds inside the original clip.')
    end = min(duration, end)
    edits = settings.get('caption_edits', {})
    words = clip.get('words', [])
    if any(not re.fullmatch(r'0|[1-9]\d*', key) or int(key) >= len(words) for key in edits):
        raise ValueError('These caption edits do not match this clip. Reopen the editor and try again.')
    result = dict(clip, start=clip['start'] + start, end=clip['start'] + end)
    result['words'] = []
    for index, word in enumerate(words):
        text = ' '.join(edits.get(str(index), word['text']).split())
        a, b = max(result['start'], word['start']), min(result['end'], word['end'])
        if text and b > a:
            result['words'].append(dict(word, text=text, start=a, end=b))
    result['text'] = ' '.join(word['text'] for word in result['words'])
    return result


def trim_tracking(points, start, end):
    """Rebase a crop path, keeping hard cuts at their exact remaining times."""
    if not points or start <= 0:
        return [dict(point) for point in points if point['time'] < end]
    before = next((p for p in reversed(points) if p['time'] <= start), points[0])
    after = next((p for p in points if p['time'] > start), None)
    center = before['x']
    if after and not after.get('cut') and after['time'] > before['time']:
        fraction = max(0, (start - before['time']) / (after['time'] - before['time']))
        center += (after['x'] - center) * fraction
    return [{'time': 0, 'x': center, 'cut': False}] + [
        dict(point, time=round(point['time'] - start, 6))
        for point in points if start < point['time'] < end
    ]


def subtitle_groups(words, offset, duration):
    """Share timing/group boundaries between burned captions and SRT files."""
    visible = [word for word in words if word['end'] > offset and word['start'] < offset + duration]
    group = []
    for word in visible:
        if group and (len(group) == 5 or word['start'] - group[-1]['end'] > .8):
            yield group
            group = []
        group.append(word)
    if group:
        yield group


def srt_time(seconds):
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole, fraction = divmod(remainder, 1000)
    return f'{hours:02}:{minutes:02}:{whole:02},{fraction:03}'


def write_srt(path, clip):
    cues = []
    offset, duration = clip['start'], clip['end'] - clip['start']
    for group in subtitle_groups(clip['words'], offset, duration):
        start = max(0, group[0]['start'] - offset)
        end = min(duration, group[-1]['end'] - offset + .12)
        # Escape markup so a correction such as '<b>' stays literal in players.
        text = ' '.join(word['text'] for word in group)
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        cues.append(f'{len(cues)+1}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n')
    path.write_text('\n'.join(cues), encoding='utf-8')
