from yandex_music import Client
import pyperclip
import os
import re
from pathlib import Path
from art import tprint
import sys
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC
import requests
import shutil
from func import is_empty, on_code, extract_track_id, get_track_metadata, add_metadata_to_mp3, download_track, extract_collection_id, get_tracks_from_playlist, get_tracks_from_album, download_collection


width, _ = shutil.get_terminal_size()
width_width = shutil.get_terminal_size().columns
text = ""
full_line_equals = text.ljust(width, "=")
emblem_text1 = text*40 + 'YM_robber'
emblem_text2 = 'YM_robber'


def main():
    print(full_line_equals)
    tprint (emblem_text1)
    print(full_line_equals)

    if not os.path.exists('token.txt'):
        try:
            with open('token.txt', 'x', encoding='utf-8') as f:
                pass
        except FileExistsError:
            print('Файл c токеном уже существует')


    token_file = Path('token.txt')
    

    if is_empty(token_file) == 1:
        print('Для работы нужно получить OAuth-токен')
        client = Client()
        token = client.device_auth(on_code=on_code) # запрашиваю токен
        # печатаю токен в терминал
        print(f'\taccess_token:  {token.access_token}')
        print(f'\trefresh_token: {token.refresh_token}')
        print(f'\texpires_in:    {token.expires_in}')
        # сохраняю в файл
        with open(token_file, 'w', encoding='utf-8') as f:
            f.write(f'{token.access_token}\n')
            f.write(f'{token.refresh_token}\n')
            f.write(f'{token.expires_in}\n')
        print('\tФайл записан')
    else:
        print(f'\tВ файле {token_file} уже имеются данные \n \t Получение OAuth-токена не требуется\n')

    
    lines = token_file.read_text().strip().splitlines()
    access_token = lines[0].strip()    
    refresh_token = lines[1].strip()   
    expires_in = int(lines[2].strip())

    client = Client(access_token)

    print(f'Ваш OAuth-токен: {access_token}\n')
    url = input("Вставьте ссылку на трек, албом или плейлист\n> ").strip()


    track_id = extract_track_id(url)
    if track_id:
        collection_type = 'track'
        print(f"\tID трека: {track_id}\n")
        download_path = input('\nКуда хотите сохранить трек? (вставте путь)\n> ')
        try:
            download_track(track_id, access_token, collection_type, download_path)
            print("=" * 50)
            print("Готово!")
            print("=" * 50)
            sys.exit(1)
        except Exception as e:
            print(f"\nОшибка: {e}")
            sys.exit(1)

    collection_info = extract_collection_id(url)
    if not collection_info:
        print("Не удалось распознать ссылку.")
        print("Поддерживаются ссылки вида:")
        print("\t ~ https://music.yandex.ru/album/12345")
        print("\t ~ https://music.yandex.ru/users/username/playlists/12345")
        print("\t ~ https://music.yandex.ru/track/67890")
        sys.exit(1) 
        
    collection_type = collection_info['type']
    collection_id = collection_info['id']

    if collection_type == 'playlist':
        print(f"\tНайден плейлист. ID: {collection_id}")
        tracks = get_tracks_from_playlist(client, collection_id)
        download_path = input('\nКуда хотите сохранить плейлист? (вставте путь)\n> ')
        download_collection(tracks, access_token, collection_type, download_path)  

    elif collection_type == 'album':
            print(f"\tНайден альбом. Название: ")
            tracks = get_tracks_from_album(client, collection_id)
            download_path = input('\nКуда хотите сохранить альбом? (вставте путь)\n> ')
            download_collection(tracks, access_token, collection_type, download_path)

    


if __name__ == "__main__":
    main()
