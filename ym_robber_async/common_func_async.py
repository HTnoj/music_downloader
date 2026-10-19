import requests
import aiohttp
import asyncio 
import os
import re
import pyperclip

from yandex_music import Client, Album, Playlist, Track
from yandex_music import ClientAsync
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC, TYER, TPOS
from tkinter.filedialog import askdirectory
from tkinter import Tk


def is_empty(file):
    """
    True если файла cуществует и пустой или не существует
    False иначе
    """
    if (os.path.exists(file) and os.path.getsize(file) == 0):
        return True
    else: return False


def on_code(code):
    print(f'\n Откройте {code.verification_url} и введите код: {code.user_code} (скопирован в буфер обмена)')
    pyperclip.copy(code.user_code) # код в буфер обмена для удобства


def clean_filename(filename):
    # Запрещённые символы: \ / : * ? " < > |
    
    replacements = {
        '/': '   ',     # слэш
        '\\': '   ',    # обратный слэш
        ':': ';',       # двоеточие
        '*': ' ',       # звёздочка
        '?': ' ',       # вопросительный знак
        '"': "'",       # кавычки
        '<': '[',       # меньше
        '>': ']',       # больше
        '|': ' ! ',     # вертикальная черта
    }

    cleaned = filename
    
    for char, replacement in replacements.items():
        cleaned = cleaned.replace(char, replacement)
    
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    
    return cleaned


def select_folder():
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = askdirectory(
        title="Выберите папку для сохранения",
        mustexist=True  
    )
    root.destroy()
    return folder_path if folder_path else None


def extract_collection_id(url):
    '''
    Извлечение id трека, альбома или плейлиста из сслыки, которую отправляет пользователь
    
    Поддерживает:
    - https://music.yandex.ru/album/8602106/track/57273406?utm_source=web&utm_medium=copy_link
    - https://music.yandex.ru/album/12345
    - https://music.yandex.ru/users/username/playlists/12345
    

    Агрументы:
        url(str): ссылкана на плейлист или альбом 

    Возвращает:
        словарь {'type': 'playlist', 'id': match.group(1)} (пример)
    '''

    # для треков
    match = re.search(r'/track/(\d+)', url) # в строке url ищем шаблонную стрроку '/track/(\d+)'
                                            # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                            # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match: return {'type': 'track', 'id': match.group(1)}

    if re.match(r'^\d+$', url): return url # случай, если пользователь сразу прислал id трека вместо ссылки 


    # для альбомов
    match = re.search(r'/album/(\d+)', url)         # в строке url ищем шаблонную стрроку '/album/(\d+)'
                                                    # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                                    # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match: return {'type': 'album', 'id': match.group(1)}
    

    # для плейлистов
    match = re.search(r'/playlists/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url, re.IGNORECASE)
    if match: 
        return {'type': 'playlist', 'id': match.group(1)}
    
    match = re.search(r'/playlists/(\d+)', url)     # в строке url ищем шаблонную стрроку '/playlists/(\d+)'
                                                    # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                                    # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match:
        return {'type': 'playlist', 'id': match.group(1)}

    if re.match(r'^\d+$', url): return url # случай, если пользователь сразу прислал id альбома, плейлиста или трека вместо ссылки 

    return None





