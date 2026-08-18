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


width, _ = shutil.get_terminal_size()
text = " "
full_line_equals = text.ljust(width, "=")




def is_empty(file):
    if (os.path.exists(file) and os.path.getsize(file) == 0):
        return True
    else: return False


def on_code(code):
    print(f'\n Откройте {code.verification_url} и введите код: {code.user_code} (скопирован в буфер обмена)')
    pyperclip.copy(code.user_code) # код в буфер обмена для удобства


def extract_track_id(url):
    '''
    Извлечение id трека из сслыку, которую отправляет пользователь

    Агрументы:
        url(str): ссылкана трек
    '''
    match = re.search(r'/track/(\d+)', url) # в строке url ищем шаблонную стрроку '/track/(\d+)'
                                            # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                            # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match:
        return match.group(1)

    if re.match(r'^\d+$', url): return url # случай, если пользователь сразу прислал id трека вместо ссылки 

    return None


def get_track_metadata(track):
        artist_names = [artist.name for artist in track.artists]
        artists_str = " & ".join(artist_names)  # "Artist1 & Artist2"
    
        album = track.albums[0] if track.albums else None
        album_title = album.title if album else "Unknown Album"
        album_year = album.year if album else None
    
        track_number = None
        if hasattr(album, 'track_number'):
            track_number = album.track_number
        elif hasattr(track, 'meta_data') and hasattr(track.meta_data, 'number'):
            track_number = track.meta_data.number
    
        cover_url = None
        if album:
            try:
                cover_url = album.get_cover_url('400x400')
            except Exception:
                if hasattr(album, 'cover_uri') and album.cover_uri:
                    cover_url = album.cover_uri.replace('%%', '400x400')
    
        metadata = {
            "title": track.title,
            "artist": artists_str,
            "album": album_title,
            "year": album_year,
            "track_number": track_number,
            "cover_url": cover_url
        }
        print(f'\tНазвение трека: {metadata["title"]}')
        print(f'\tАртист: {metadata["artist"]}')
        print(f'\tАльбом: {metadata["album"]}')
        print(f'\tГод: {metadata["year"]}')
        print(f'\tНомер трека: {metadata["track_number"]}')
        print(f'\tОбложка: {metadata["cover_url"]}')
        print('\t')

        return metadata

def download_cover(cover_url, save_path):
    response = requests.get(cover_url, timeout=10)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    return False

def add_metadata_to_mp3(file_path, metadata):
    '''Добавляет метаданные в MP3-файл
    Агрументы:
            file_path(any): путь к файлу
            metadata(dict): метаданные файла
    '''
    
    # Открываем файл
    audio = MP3(str(file_path), ID3=ID3)
    
    # Если тегов нет — создаём новый контейнер ID3
    if audio.tags is None:
        print("Создаём контейнер для тегов...")
        audio.add_tags()
    
    # Теперь audio.tags точно существует
    audio.tags.add(TIT2(encoding=3, text=metadata['title']))
    audio.tags.add(TPE1(encoding=3, text=metadata['artist']))
    audio.tags.add(TALB(encoding=3, text=metadata['album']))
    
    if metadata.get('year'):
        audio.tags.add(TDRC(encoding=3, text=str(metadata['year'])))
    
    if metadata.get('track_number'):
        audio.tags.add(TRCK(encoding=3, text=str(metadata['track_number'])))
    
    # Добавляем обложку
    if metadata.get('cover_url'):
        try:
            response = requests.get(metadata['cover_url'], timeout=10)
            response.raise_for_status()
            # with open('img.png', 'wb') as f:
            #             f.write(response.content)
            if response.status_code == 200:
                mime = response.headers.get("Content-Type","image/jpeg").split(";")[0]
                print(f"Content-Type обложки: {mime}")
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime=mime,
                        type=3,
                        desc='Cover',
                        data=response.content
                    )
                )
                print('\tОбложка добавлена')
        except Exception as e:
            print(f"\tНе удалось добавить обложку: {e}")
    
    # Сохраняем изменения
    audio.save()
    print("\tМетаданные добавлены")



def download_track(track_id, token, output_dir="./downloads"):
    '''
    Скачивание трека по его ID из Яндекс Музыки.
    
    Аргументы:
        track_id (str): ID трека
        token (str): OAuth-токен
        output_dir (str): Папка для сохранения
    '''

    client = Client(token).init()
    
    print('\nПолучение информации о треке...')
    track = client.tracks([track_id])[0]
    metadata = get_track_metadata(track) # получаем метаданные трека в словарь
    filename = f'{metadata['artist']} - {metadata['title']}.mp3'

    output_path = Path(output_dir) 
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / filename
    

    track.download(str(file_path))
    if file_path.exists:
        print(f'Трек скачан: {file_path}')
        print('\n')
    else: print(f'Ошибка скачивания трека: {file_path}')

    print("Добавление метаданных в файл...")
    try:
        add_metadata_to_mp3(file_path, metadata)
    except Exception as e:
        print(f"Ошибка при добавлении метаданных: {e}")
        print("\tФайл скачан, но без метаданных")
    
    print(f'✅ Трек сохранён: {file_path}')




    




def main():
    print(full_line_equals)
    tprint ('YM_robber')
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
        print('\t Файл записан')
    else: print(f'\t В файле {token_file} уже имеются данные \n \t Получение OAuth-токена не требуется\n')

    lines = token_file.read_text().strip().splitlines()
    access_token = lines[0].strip()    
    refresh_token = lines[1].strip()   
    expires_in = int(lines[2].strip()) 

    print(f'Ваш OAuth-токен: {access_token}\n')
    url = input("Вставьте ссылку на трек\n> ").strip()
    track_id = extract_track_id(url)
    if not track_id:
        print("Не удалось извлечь ID трека из ссылки")
        print("\t Поддерживаются ссылки вида:")
        print("\t\t ~ https://music.yandex.ru/album/12345/track/67890")
        print("\t\t ~ https://music.yandex.ru/track/67890")
        print("\t\t ~ или просто ID (например: 67890)")
        sys.exit(1)
    print(f"\t ID трека: {track_id}\n")

    dowload_path = input('\n Куда хотите сохранить трек? (вставте путь)\n> ')

    


    # Скачиваем
    try:
        download_track(track_id, access_token, dowload_path)
        print("=" * 50)
        print("Готово!")
        print("=" * 50)
    except Exception as e:
        print(f"\nОшибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
