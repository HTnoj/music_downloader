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

from common_func_async import clean_filename, is_empty

logger = logging.getLogger(__name__)

def get_track_metadata(track, context = None):
    artist_names = [artist.name for artist in track.artists]
    artists_str = " & ".join(artist_names)  # "Artist1 & Artist2"
    
    album_stupid = track.albums[0] if track.albums else None
    album_title = None
    album_year = album_stupid.year if album_stupid else None

    track_number = None
    disc = None
    cover_url = None
    
    if isinstance(context, Album):
        album_title = context.title
        album_year = context.year

        try:
            cover_url = context.get_cover_url('1000x1000')
        except Exception:
            if hasattr(context, 'cover_uri') and context.cover_uri:
                cover_url = context.cover_uri.replace('%%', '1000x1000')

        '''
        идем по дискам в альбоме, переданном в функию, и проверяем: если id трека из альбома совпадает с id трека, 
        переданного в функцию, то записываем в переменную track_number номер трека из альбома (т.е. track_index)
        Это поможет избежать путаницы в нумерации треков (тк у любого трека в поле "альбом" стоит только какой то один
        альбом, не всегда тот, который ты скачиваешь)
        '''
        if context.volumes:
            for volume_index, volume in enumerate(context.volumes, start=1):
                for track_index, trk in enumerate(volume, start=1):
                    if trk.id == track.id:
                        track_number = track_index          # бля, токо бы это сработало
                        if len(context.volumes) > 1:
                            disc = volume_index
                        break
                if track_number is not None: break    


        # track_number = track.albums[0].track_position.index

    elif isinstance(context, Playlist):
        if album_stupid:
            album_title = album_stupid.title
            album_year = album_stupid.year
            try:
                cover_url = album_stupid.get_cover_url('1000x1000')
            except Exception:
                if hasattr(album_stupid, 'cover_uri') and album_stupid.cover_uri:
                    cover_url = album_stupid.cover_uri.replace('%%', '1000x1000')


    elif isinstance(context, Track):
        if album_stupid:
            album_title = album_stupid.title
            album_year = album_stupid.year
            try:
                cover_url = album_stupid.get_cover_url('1000x1000')
            except Exception:
                if hasattr(album_stupid, 'cover_uri') and album_stupid.cover_uri:
                    cover_url = album_stupid.cover_uri.replace('%%', '1000x1000')

    # if collection_type == 'playlist' and hasattr(track, 'track_position'):
    #     track_number = track.track_position.index

    #if hasattr(track, 'track_position') and track.track_position:
    #    track_number = album.track_position.index
    #elif hasattr(track, 'meta_data') and hasattr(track.meta_data, 'number'):
    #    track_number = track.meta_data.number

    
    # cover_url = None
    # if album:
    #     try:
    #         cover_url = album.get_cover_url('400x400')
    #     except Exception:
    #         if hasattr(album, 'cover_uri') and album.cover_uri:
    #             cover_url = album.cover_uri.replace('%%', '400x400')


    # допольнительная информация о треке. в ЯМ обычно указывается в названии трека серым цветом  
    # example: Digeridoo Live in Cornwall, 1990

    else:
        album_stupid = track.albums[0] if track.albums else None
        if album_stupid:
            album_title = album_stupid.title
            album_year = album_stupid.year
            try:
                cover_url = album_stupid.get_cover_url('1000x1000')
            except Exception:
                if hasattr(album_stupid, 'cover_uri') and album_stupid.cover_uri:
                    cover_url = album_stupid.cover_uri.replace('%%', '1000x1000')

    
    
    metadata = {
        "title": track.title,
        "version": track.version,
        "disc": disc,
        "artist": artists_str,
        "album": album_title,
        "year": album_year,
        "track_number": track_number,
        "cover_url": cover_url
    }

    return metadata


async def add_metadata_to_mp3__async(session, file_path, metadata, cover_cache = None):
    '''Добавляет метаданные в MP3-файл
    Агрументы:
            file_path(any): путь к файлу
            metadata(dict): метаданные файла
    '''
    
    audio = MP3(str(file_path), ID3=ID3)
    
    # если тегов нет — создаём новый контейнер ID3
    if audio.tags is None:
        audio.add_tags()

    # если есть приписка -- добавляем ее в метаданные
    if metadata['version'] is not None:
        audio.tags.add(TIT2(encoding=3,
                            text=metadata['title'] # + ' (' + metadata['version'] + ')'
                            ))
    else: audio.tags.add(TIT2(encoding=3, text=metadata['title']))

    audio.tags.add(TPE1(encoding=3, text=metadata['artist']))
    audio.tags.add(TALB(encoding=3, text=metadata['album']))
    
    if metadata.get('year'):
        audio.tags.add(TDRC(encoding=3, text=str(metadata['year']))) 
        audio.tags.add(TYER(encoding=3, text=str(metadata['year']))) 
    
    if metadata.get('track_number'):
        audio.tags.add(TRCK(encoding=3, text=str(metadata['track_number'])))

    if metadata.get('disc'):
        audio.tags.add(TPOS(encoding=3, text=str(metadata['disc']))) 
    
    # добавляем обложку
    if metadata.get('cover_url'):
        cover_url=metadata['cover_url']
        cover_data=None
        if cover_cache is not None and cover_url in cover_cache:
            cover_data = cover_cache[cover_url]
        else:
            try:
                async with session.get(metadata['cover_url'], timeout=10) as response:
                    if response.status == 200:
                        cover_data = await response.read()
                        mime = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
                        if cover_cache is not None:
                            cover_cache[cover_url] = cover_data
            except Exception as e:
                logger.warning(f'Олбложка не добавлена для {file_path.name}: {e}')
        if cover_data:
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,                        
                    type=3,
                    desc='Cover',
                    data=cover_data
                )
            ) 
    # сохр изменения
    audio.save()


# async def download_track__async(track, context, output_dir="./downloads"):
#     '''
#     Cкачивание трека по его id из Яндекс Музыки.
    
#     Аргументы:
#         track_id (str): ID трека
#         token (str): OAuth-токен
#         collection_type (str): тип коллекции (албом, плейлист или просто трек)
#         output_dir (str): Папка для сохранения
#     '''

#     print('\nПолучение информации о треке...')

#     metadata = get_track_metadata(track, context) # получаем метаданные трека в словарь

#     if metadata['version'] is not None:
#         filename = f'{metadata["title"]} ({metadata["version"]}).mp3' 
#         filename = clean_filename(filename)
#     else:
#         filename = f'{metadata["title"]}.mp3'
#         filename = clean_filename(filename)                            
    
#     output_path = Path(output_dir) 
#     output_path.mkdir(parents=True, exist_ok=True)
    
#     file_path = output_path / filename
    
#     await track.download_async(str(file_path), codec='mp3', bitrate_in_kbps=192, timeout=20) 
#     if file_path.exists():
#         print(f'Трек скачан: {file_path}')
#         print('\n')
#     else:
#         raise RuntimeError(f'Ошибка скачивания трека: {file_path}')

#     print("Добавление метаданных в файл...")
#     try:
#         await add_metadata_to_mp3__async(file_path, metadata)
#     except Exception as e:
#         print(f"Ошибка при добавлении метаданных: {e}")
#         print("\tФайл скачан, но без метаданных")
    
#     print(f'Трек сохранён: {file_path}')
#     print('_'*100)


async def download_track_async(session, track, context, output_dir="./downloads", progress=None, task_id=None):
    '''
    Cкачивание трека по его id из Яндекс Музыки.
    
    Аргументы:
        track_id (str): ID трека
        token (str): OAuth-токен
        collection_type (str): тип коллекции (албом, плейлист или просто трек)
        output_dir (str): Папка для сохранения
    '''

    metadata = get_track_metadata(track, context) # получаем метаданные трека в словарь

    # формируем название трека (файла), не забывая почистить его
    if metadata['version'] is not None:
        filename = f'{metadata["title"]} ({metadata["version"]}).mp3' 
    else:
        filename = f'{metadata["title"]}.mp3'
    filename = clean_filename(filename)  

    output_path = Path(output_dir) 
    output_path.mkdir(parents=True, exist_ok=True)

    file_path = output_path / filename

    # полулаем битрейт и формат(mp3, aac)
    info = await track.get_download_info_async(get_direct_links=True)
    if not info: raise RuntimeError(f'Трек {metadata['title']} недоступен для скачки (не полученo info трека)')

    best = sorted(info, key=lambda x: -x.bitrate_in_kbps)[0] # берем лучший битрейт
    bitrate = best.bitrate_in_kbps
    
    # скачиваем
    try:
        timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=60)

        async with session.get(best.direct_link, timeout=timeout) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('Content-Length', 0))
            if progress and task_id is not None:
                progress.update(task_id, total=total_size)

            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    if progress and task_id is not None: progress.advance(task_id, len(chunk))
    except Exception as e:
                raise RuntimeError(f'Ошибка скачивания трека {metadata['title']}: {e}')

    if not file_path.exists() or is_empty(file_path) == 1:
        raise RuntimeError(f"Файл пустой: {file_path}")
           
    try:
        await add_metadata_to_mp3__async(session, file_path, metadata)
    except Exception as e:
        raise RuntimeError(f'Ошибка добавлния метаданных в трек {metadata['title']}: {e}')

    return track, metadata, bitrate