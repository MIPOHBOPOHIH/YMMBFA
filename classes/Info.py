from fastapi import HTTPException
from math import floor
from random import random
from classes.Radio import Radio


class Info:
    def __init__(self, client, lastfm_username=None, lastfm_network=None):
        self.client = client
        self.radio = Radio(client)
        self.first_track = None
        self.lastfm_username = lastfm_username
        self.lastfm_network = lastfm_network

    @staticmethod
    async def get_img_uri(cover_uri: str) -> str:
        return f"https://{cover_uri[:-2]}1000x1000"

    @staticmethod
    async def get_download_link(data) -> str:
        return (await data.get_download_info_async(get_direct_links=True))[0].direct_link

    @staticmethod
    async def get_artists(data) -> str:
        return ', '.join(data.artists_name())

    async def get_track_info(self, track):
        try:
            duration = track.duration_ms // 1000
            return {
                'track_id': int(track.track_id.split(':')[0]),
                'title': track.title,
                'artist': (await self.get_artists(track)),
                'img': (await self.get_img_uri(track.cover_uri)),
                'duration': track.duration_ms // 1000,
                'minutes': duration // 60,
                'seconds': duration % 60,
                'album': track.albums[0].id,
                'download_link': (await self.get_download_link(track))
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to fetch track info") from e

    async def get_track_by_id(self, track_id: int):
        try:
            track = await self.client.tracks([track_id])
            return await self.get_track_info(track[0])
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to fetch track info by ID") from e

    async def get_favourite_songs(self, skip, count):
        playlist = await self.client.users_likes_tracks()
        playlist = await playlist.fetch_tracks_async()
        total = len(playlist)
        playlist = playlist[skip:]
        playlist = playlist[:count]
        data = {
            'skipped': skip,
            'count': count,
            'total': total,
            'tracks': []
        }
        for track in playlist:
            track1 = await self.get_track_info(track)
            data['tracks'].append(track1)
        return data

    async def get_album_info(self, album):
        try:
            tracks = []
            for track in album.volumes[0]:
                track_id = int(track.track_id.split(':')[0])
                tracks.append(track_id)
            return {
                'title': album.title,
                'artists': ', '.join(album.artists_name()),
                'track_count': album.track_count,
                'img': (await self.get_img_uri(album.cover_uri)),
                'tracks': tracks
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to fetch album info") from e

    async def get_albums_with_tracks(self, album_id):
        try:
            album = await self.client.albums_with_tracks(album_id)
            return await self.get_album_info(album)
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to fetch album info") from e

    async def get_track_playlist_of_day(self):
        feed = (await self.client.feed()).generated_playlists
        tracks = []
        for playlists in feed:
            if playlists.type == 'playlistOfTheDay':
                data = playlists.data.tracks
                for track in data:
                    track = await track.fetch_track_async()
                    new_track = await self.get_track_info(track)
                    tracks.append(new_track)
        return tracks

    async def search(self, request):
        try:
            searching_data = await self.client.search(request)
            best = None
            if searching_data['best']['type'] == 'artist':
                best = await self.get_artist_info(searching_data['best']['result']['id'])
            elif searching_data['best']['type'] == 'track':
                best = await self.get_track_info(searching_data['best']['result'])
            elif searching_data['best']['type'] == 'album':
                best = await self.get_album_info(searching_data['best']['result'])
            tracks = []
            track_search = await self.client.search(type_='track', text=request)
            track_tasks = [self.get_track_by_id(track['id']) for track in track_search['tracks']['results']]
            return {
                'type': searching_data['best']['type'],
                'best': best,
                'tracks': tracks
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to search") from e

    async def get_track_from_station(self):  # создание случайного радио и брать трек оттуда
        stations = await self.client.rotor_stations_list()
        station_random_index = floor(len(stations) * random())
        station = stations[station_random_index].station
        station_id = f'{station.id.type}:{station.id.tag}'
        station_from = station.id_for_from
        track = await self.radio.start_radio(station_id, station_from)
        return await self.get_track_info(track)

    async def get_new_releases(self, skip, count):
        new_releases = (await self.client.new_releases()).to_dict()
        new_releases = new_releases['new_releases']
        new_releases = new_releases[skip:]
        new_releases = new_releases[:count]
        releases = []
        for release in new_releases:
            data = await self.get_albums_with_tracks(release)
            releases.append(data)
        return releases

    async def get_current_track(self):
        if self.lastfm_network is not None:
            data = await self.lastfm_network.user_get_recent_tracks(self.lastfm_username, limit=1)
            artist_name = data['recenttracks']['track'][0]['artist']['name']
            track_name = data['recenttracks']['track'][0]['name']
            album_name = data['recenttracks']['track'][0]['album']['#text']
            searching_track = await self.client.search(f'{artist_name} {track_name} {album_name}')
            current_track = searching_track['best']['result']
            await self.lastfm_network._session.close()  # че за хуйня, пукчарм жалуется
            return await self.get_track_info(current_track)
        queues = await self.client.queues_list()
        last_queue = await self.client.queue(queues[0].id)
        last_track_id = last_queue.get_current_track()
        current_track = await last_track_id.fetch_track_async()
        return await self.get_track_info(current_track)

    async def get_artist_info(self, artist_id):
        try:
            artist = (await self.client.artists(artist_id))[0]
            artist_tracks = await self.client.artists_tracks(artist_id)
            artist_albums = await self.client.artists_direct_albums(artist_id)
            return {
                'id': artist['id'],
                'name': artist['name'],
                'cover_url': f"https://{artist['cover']['uri'][:-2]}1000x1000",
                'genres': artist['genres'],
                'albums': [album.id for album in artist_albums.albums],
                'tracks': [int(track.track_id.split(':')[0]) for track in artist_tracks.tracks]
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to fetch artist info") from e

    async def like_track(self, track_id):
        try:
            return {
                "message": await self.client.users_likes_tracks_add(track_id)
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to like track") from e

    async def unlike_track(self, track_id):
        try:
            return {
                "message": await self.client.users_likes_tracks_remove(track_id)
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to unlike track") from e

    async def like_album(self, album_id):
        try:
            return {
                "message": await self.client.users_likes_albums_add(album_id)
            }
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail="Failed to like album") from e

    async def get_like_tracks_by_username(self, username, skip, count):  # TODO: Сделать функцию get_playlist_info
        playlist = await self.client.users_likes_tracks(username)
        playlist = await playlist.fetch_tracks_async()
        total = len(playlist)
        playlist = playlist[skip:]
        playlist = playlist[:count]
        data = {
            'skipped': skip,
            'count': count,
            'total': total,
            'tracks': []
        }
        for track in playlist:
            track1 = await self.get_track_info(track)
            data['tracks'].append(track1)
        return data
