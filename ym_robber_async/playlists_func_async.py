import requests
import aiohttp
import asyncio 
import os
import re
import pyperclip
import logging

from yandex_music import Client, Album, Playlist, Track
from yandex_music import ClientAsync
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC, TYER, TPOS
from tkinter.filedialog import askdirectory
from tkinter import Tk
from rich.progress import (
    Progress, BarColumn, DownloadColumn,
    TextColumn, TransferSpeedColumn, TimeRemainingColumn,
)

from tracks_func_async import download_track_async
from common_func_async import clean_filename


logger = logging.getLogger(__name__)


# async def get_bitrates_for_all(client, track_list, max_concurrent=4):
#     semaphore = asyncio.Semaphore(max_concurrent)
#     async def get_bitrate(track):
#         async with semaphore:
#             try:
#                 '''     в info храниться информация о доступных вариантах загрузки трека. 
#                         я пока что использую только для просмотра битрейта и выбора максимального для каждого трека  '''
#                 info = await client.tracks_download_info(track.id, get_direct_links=False)  
#                 bitrates = []   # для каждого трека создадим массив, где будем хранить все доступные для скачки битрейты  
#                 print(f"\n Доступные форматы для {track.title}:")
#                 for i in info: 
#                     if i.bitrate_in_kbps: bitrates.append(i.bitrate_in_kbps)
#                 return max(bitrates) if bitrates else 192 # будем брать самый большой
#             except Exception:
#                 return 192
    
#     bitrates = await asyncio.gather(*[get_bitrate(track) for track in track_list])
#     return dict(zip([track.id for track in track_list], bitrates))


# async def get_tracks_from_playlist__async(client, playlist_id):
#     '''
#     в плейлистах иногда возвращаются объекты short_track, которые содержать только id трека, 
#     а иногда объект Track, который содержит все поля трека, нужные для метаданных 
#     '''
#     try:
#         # Получаем плейлист напрямую по ID
#         playlist = await client.playlist(playlist_id)  
        
#         if not playlist:
#             print('Плейлист не найден')
#             return [], None
        
        
#         tracks = playlist.tracks if playlist.tracks else await playlist.fetch_tracks()
    
#         track_list = []
#         for short_track in tracks:
#             # если каждый элемент в tracks уже объект Track то добавляем его track_list
#             if hasattr(short_track, 'track') and short_track.track:
#                     track_list.append(short_track.track)
#             else:
#                 # eсли это только id, получаем полные данные
#                 try:
#                     track_obj = (await client.tracks([short_track.id]))[0]
#                     track_list.append(track_obj)
#                 except Exception as e:
#                     print(f'Не удалось получить трек {short_track.id}: {e}')
#                     continue

#         print(f'\tНазвание плейлиста: {playlist.title}')    
#         print(f'\tВладелец: {playlist.owner.login}')
#         total = len(track_list)
#         print(f"\tНайдено треков: {total}")
#         print("=" * 60)
#         print('Список треков:')
        
#         for track in track_list:
#             artists = ''
#             if track.artists:
#                 artists = ' - ' + ', '.join(artist.name for artist in track.artists)
#             print(f'\t>  {track.title + artists}')
                        
#         return track_list, playlist
#     except Exception as e:
#         print(f"Ошибка при получении плейлиста: {e}")
#         return[], None


async def get_tracks_from_playlist__async(client, playlist_id, max_concurrent=5):
    try:
        playlist = await client.playlist(playlist_id)
        if not playlist:
            return [], None
        
        tracks = playlist.tracks if playlist.tracks else await playlist.fetch_tracks()
        if not tracks:
            return [], playlist
        
        all_ids = []
        track_map = {}  # {id: Track}
        
        for short_track in tracks:
            all_ids.append(short_track.id)
            if hasattr(short_track, 'track') and short_track.track:
                track_map[short_track.id] = short_track.track
        
        # какие нужно дозагрузить
        ids_to_fetch = [tid for tid in all_ids if tid not in track_map]
        
        # параллельно запрашиваем
        if ids_to_fetch:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def fetch_one(track_id):
                async with semaphore:
                    try:
                        result = await client.tracks([track_id])
                        return track_id, result[0] if result else None
                    except Exception as e:
                        logger.warning(f"Трек {track_id}: {e}")
                        return track_id, None
            
            fetched = await asyncio.gather(*[fetch_one(tid) for tid in ids_to_fetch])
            
            for track_id, track_obj in fetched:
                if track_obj:
                    track_map[track_id] = track_obj
        
        # восстанавливаем порядок
        track_list = [track_map[tid] for tid in all_ids if tid in track_map]
        
        logger.info(f"Плейлист '{playlist.title}': {len(track_list)} треков")
        return track_list, playlist
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return [], None


async def download_playlist__async(client, session, playlist, track_list, output_dir="./downloads", max_concurrent = 4):
    if not track_list:
        print("\nСписок треков пуст.")
        return

    playlist_name = clean_filename(playlist.title)
    playlist_output_dir = Path(output_dir) / playlist_name
    playlist_output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []

    semaphore = asyncio.Semaphore(max_concurrent)

    
    with Progress(
        TextColumn("[cyan]{task.description}"),
        BarColumn(bar_width=30),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:

        
        task_ids = {
            track.id: progress.add_task(f" {track.title[:60]}", total=None)
            for track in track_list
        }
        
        
        async def download_one(track, index):
            async with semaphore:
                task_id = task_ids[track.id]
                try:
                    _, metadata, bitrate = await download_track_async(session, track, playlist, str(playlist_output_dir), progress=progress, task_id=task_id)
                    progress.update(task_id, description=f"[green]o {track.title[:50]}")
                    results.append({
                        "track": track,
                        "metadata": metadata,
                        "bitrate": bitrate,
                        "status": "ok",
                        "error": None,
                    })
                    logger.info(f"OK {track.title}")
                except Exception as e:
                    progress.update(task_id, description=f"[red]x {track.title[:50]}")
                    results.append({
                        "track": track,
                        "metadata": None,
                        "bitrate": None,
                        "status": "err",
                        "error": str(e),
                    })
                    logger.error(f"ER {track.title}: {e}")
        
        tasks = [download_one(t, i) for i, t in enumerate(track_list, start=1)]
        await asyncio.gather(*tasks)

    return results, playlist_output_dir