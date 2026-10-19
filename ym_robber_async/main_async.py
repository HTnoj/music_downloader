import asyncio
import aiohttp
import sys
import os
import re
import requests
import shutil
import pyperclip
import logging
import argparse

from platformdirs import user_data_dir
from yandex_music import ClientAsync
from yandex_music import Client
from pathlib import Path
from art import tprint
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC
from rich.logging import RichHandler
from logging.handlers import RotatingFileHandler
from rich.progress import (
    Progress, BarColumn, DownloadColumn,
    TextColumn, TransferSpeedColumn, TimeRemainingColumn,
)

from ym_robber_async.tracks_func_async import download_track_async
from ym_robber_async.playlists_func_async import get_tracks_from_playlist__async, download_playlist__async
from ym_robber_async.common_func_async import on_code, is_empty, extract_collection_id, select_folder
from ym_robber_async.album_func_async import get_tracks_from_album__async, download_album__async


width, _ = shutil.get_terminal_size()
width_width = shutil.get_terminal_size().columns
text = ""
full_line_equals = text.ljust(width, "=")
emblem_text1 = text*40 + 'YM_robber'
emblem_text2 = 'YM_robber'

logger = logging.getLogger(__name__)


def setup_logging(show_console = True):
    handlers = []
    log_file = Path(__file__).parent / 'ym_robber_async.log'
        
    file_handler = RotatingFileHandler(
                log_file,
                maxBytes = 5_000_000,  
                backupCount = 2,        
                encoding = 'utf-8',
            )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(module)s.%(funcName)s: %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
    ))
    handlers.append(file_handler)
    if show_console:
        console_handler = RichHandler(
                rich_tracebacks = True,   
                show_path = False,        
                show_time = True,         
                show_level = True,        
                markup = True,
            )
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(console_handler)

    logging.basicConfig(
            level = logging.INFO,
            handlers = handlers,
            force = True,  # на случай, если какая нибудь библиотека вызовет свой logging.basicConfig()
        )
        
    logging.getLogger(__name__).info(f"Логи: {log_file}")


def parse_args():
    parser = argparse.ArgumentParser(
        prog='ym-robber',
        description='Скачивание музыки из Яндекс Музыки',
    )
    parser.add_argument(
        '-q', '--quiet',
        action = 'store_false',
        help = 'Не показывать логи в консоли (в файл пишутся всегда)',
    )
    return parser.parse_args()


def show_report(results, playlist_output_dir):
    success = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "err"]
    
    print()
    print("=" * 60)
    print(f"Успешно скачано: {len(success)}")
    print(f"С ошибками:      {len(errors)}")
    
    if errors:
        print("\nНе удалось скачать:")
        for r in errors:
            print(f"\t{r['track'].title}")
            print(f"\t\t{r['error']}")
    
    print(f"\nПапка: {playlist_output_dir}")
    print("=" * 60)




async def main():
    args = parse_args()
    setup_logging(show_console = args.quiet)
    async with aiohttp.ClientSession() as session:
        print(full_line_equals)
        tprint (emblem_text1)
        print(full_line_equals)
        

        app_data_dir = Path(user_data_dir("ym_robber", "HTnoj"))
        app_data_dir.mkdir(parents=True, exist_ok=True)
        token_file = app_data_dir / 'token.txt'


        if is_empty(token_file) == 1:
            print('Для работы нужно получить OAuth-токен')
            client = ClientAsync()
            token = await client.device_auth(on_code=on_code) # запрашиваю токен
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
            print(f'\tВ файле {token_file} уже имеются данные \n \tПолучение OAuth-токена не требуется\n')


        lines = token_file.read_text().strip().splitlines()
        access_token = lines[0].strip()    
        refresh_token = lines[1].strip()   
        expires_in = int(lines[2].strip())


        client = ClientAsync(access_token)
        await client.init()




        user_id = client.me.account.uid
        print(f"Ваш user_id: {user_id}")

        print(f'Ваш OAuth-токен: {access_token}\n')

        while True:
            url = input("Вставьте ссылку на трек, альбом или плейлист\n> ").strip()
            collection_info = extract_collection_id(url)
            if not collection_info:
                print("Не удалось распознать ссылку.")
                print("Поддерживаются ссылки вида:")
                print("\t ~ https://music.yandex.ru/album/12345")
                print("\t ~ https://music.yandex.ru/users/username/playlists/12345")
                print("\t ~ https://music.yandex.ru/track/67890\n")
                continue

            collection_type = collection_info['type']
            collection_id = collection_info['id']

            if collection_type == 'track':
                track_id = collection_id
                track = (await client.tracks([track_id]))[0] # получаем объект трека по его id
                print(f"\tID трека: {track_id}")
                print(f"\tНазвание трека: {track.title}")
                artist_names = [artist.name for artist in track.artists]
                artists_str = " & ".join(artist_names)  # "Artist1 & Artist2"
                print(f"\tИсполнитель: {artists_str}\n")
                while True:
                    print('Выберите папку')
                    download_path = select_folder()
                    if download_path is None:
                        print('Папка не выбрана.')
                        continue
                    print(f'Выбранная папка: {download_path}')
                    break

                try:
                    with Progress(
                            TextColumn("[cyan]{task.description}"),
                            BarColumn(bar_width=30),
                            DownloadColumn(),
                            TransferSpeedColumn(),
                            TimeRemainingColumn(),
                        ) as progress:
                            task_id = progress.add_task(f" {track.title[:60]}", total=None)                                       
                            _, metadata, bitrate = await download_track_async(session, track, track, str(download_path), progress=progress, task_id=task_id)
                            progress.update(task_id, description=f"[green]o {track.title[:50]}")
                            success = True
                except Exception as e:
                    progress.update(task_id, description=f"[red]x {track.title[:50]}")
                    print(f"\nОшибка: {e}\n")
                    continue

                if success and metadata:
                    print(f"\tСкачан: {metadata['title']}")
                    print(f"\tАртист: {metadata['artist']}")
                    print(f"\tБитрейт: {bitrate} kbps")
                    print(f"\tФайл: {download_path}")

                ans = input('\nНажмите Enter, чтобы продолжить...\nИли \'exit\' для выхода\n> ')
                if ans.lower().strip() == 'exit':
                    print('\nДо свидания!')
                    sys.exit()
                continue

            elif collection_type == 'playlist':
                print(f'\tНайден плейлист. ID: {collection_id}')
                tracks, playlist = await get_tracks_from_playlist__async(client, collection_id, 5)
                if not tracks or not playlist:
                    print('Не удалось получить треки плейлиста')
                    continue

                print(f'\tНазвание плейлиста: {playlist.title}')    
                print(f'\tВладелец: {playlist.owner.login}')
                total = len(tracks)
                print(f"\tНайдено треков: {total}")

                # можно поменять на табличку из rich
                print("=" * 60)
                print('Список треков:')
                for track in tracks:
                    artists = ''
                    if track.artists:
                        artists = ' - ' + ', '.join(artist.name for artist in track.artists)
                    print(f'\t>  {track.title + artists}')
                print("=" * 60)

                while True:
                    print('Выберите папку')
                    download_path = select_folder()
                    if download_path is None:
                        logger.warning(f'Пользователь не выбрал папку для загрузки')
                        continue
                    print(f'Выбранная папка: {download_path}')
                    break

                results, output_path = await download_playlist__async(client, session, playlist, tracks, download_path, 4)
                show_report(results, output_path)

            elif collection_type == 'album':
                tracks, album = await get_tracks_from_album__async(client, collection_id, 4)
                if not tracks or not album:
                    print('Не удалось получить треки плейлиста')
                    continue

                print(f'\nНазвание альбома: {album.title}')
                print(f"Исполнитель: {', '.join([artist.name for artist in album.artists])}")
                print(f'Год: {album.year}')
                total = len(tracks)
                print(f"Найдено треков: {total}")
                print("=" * 60)
                print('Список треков:')
        
                for track in tracks:
                        artists = ''
                        if track.artists:
                            artists = ' - ' + ', '.join(artist.name for artist in track.artists)
                        print(f'\t>  {track.title + artists}')
                while True:
                    print('Выберите папку')
                    download_path = select_folder()
                    if download_path is None:
                        logger.warning(f'Пользователь не выбрал папку для загрузки')
                        continue
                    logger.info(f'Пользователь выбрал папку для загрузки: {download_path}')
                    break
                results, output_path = await download_album__async(session, album, tracks, download_path, 4)
                show_report(results, output_path)


            ans = input('\nНажмите Enter, чтобы продолжить скачивать...'
                                '\nИли введите \'exit\' чтобы завершить работу программы...\n')
            if ans.lower().strip() == 'exit':
                print('\n\nДо свидания!')
                sys.exit()
            elif ans.lower() == "":
                continue
            else: continue
        
        
def Main():
    # Запускаем event loop и передаем ему асинхронную функцию
    asyncio.run(main())

    

if __name__ == "__main__":
    Main()