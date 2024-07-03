from fastapi import FastAPI, Query
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from yandex_music import ClientAsync as Client
from classes.Info import Info
import lastfm
import random
import json
import aiohttp
import string
from dotenv import dotenv_values

config = dotenv_values(".env")
client_key = config['LASTFM_API_KEY']
client_secret = config['LASTFM_API_SECRET']
app = FastAPI()
title_string = "<title>YMMBFA - Swagger UI</title>"


async def get_info(ya_token: str = None, lastfm_username: str = None) -> Info:
    lastfm_network = None
    client = await Client(ya_token).init()
    if lastfm_username:
        lastfm_network = lastfm.Client(client_key=client_key, client_secret=client_secret)
    return Info(client, lastfm_username, lastfm_network)



@app.get("/song/{track_id}")
async def get_song_by_id(track_id: int,
                         ya_token: str = Query(...,
                                               title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_track_by_id(track_id)


@app.get("/songs")  # ПРИМЕР track_ids: 73131629,73131630
async def get_tracks_by_ids(track_ids: str,
                            ya_token: str = Query(...,
                                                  title="Yandex Music Token")):
    data = track_ids.split(',')
    return [await (await get_info(ya_token)).get_track_by_id(int(track)) for track in data]


@app.get("/favourite_songs")
async def get_favourite_tracks(skip: int = 0, count: int = 25, ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_favourite_songs(skip, count)


@app.get("/album/{album_id}")
async def get_album_by_id(album_id: int, ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_albums_with_tracks(album_id)


@app.get("/playlist_of_the_day")
async def get_tracks_from_playlist_of_the_day(ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_track_playlist_of_day()


@app.get("/search")
async def get_search(request: str, ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).search(request)


@app.get("/get_track_from_station")
async def get_track_from_station(ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_track_from_station()


@app.get("/new_release")
async def get_new_release(skip: int = 0, count: int = 10, ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_new_releases(skip, count)


@app.get("/current_track")
async def get_current_track(ya_token: str = Query(..., title="Yandex Music Token"),
                            lastfm_username: str = Query(None, title="Yandex Music Token")):

    return await (await get_info(ya_token, lastfm_username=lastfm_username)).get_current_track()


@app.get("/artist/{artist_id}")
async def get_album(artist_id: int,
                    ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_artist_info(artist_id)


@app.get("/like_track/{track_id}")
async def like_track(track_id: int,
                     ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).like_track(track_id)


@app.get("/dislike_track/{track_id}")
async def dislike_track(track_id: int,
                        ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).unlike_track(track_id)


@app.get("/get_current_track_beta")
async def get_current_track_very_beta(ya_token: str = Query(..., title="Yandex Music Token")):
    device_info = {
        "app_name": "Chrome",
        "type": 1,
    }

    ws_proto = {
        "Ynison-Device-Id": "".join([random.choice(string.ascii_lowercase) for _ in range(16)]),
        "Ynison-Device-Info": json.dumps(device_info)
    }
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
                url="wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison",
                headers={
                    "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                    "Origin": "http://music.yandex.ru",
                    "Authorization": f"OAuth {ya_token}",
                },
        ) as ws:
            recv = await ws.receive()
            data = json.loads(recv.data)

        new_ws_proto = ws_proto.copy()
        new_ws_proto["Ynison-Redirect-Ticket"] = data["redirect_ticket"]

        to_send = {
            "update_full_state": {
                "player_state": {
                    "player_queue": {
                        "current_playable_index": -1,
                        "entity_id": "",
                        "entity_type": "VARIOUS",
                        "playable_list": [],
                        "options": {
                            "repeat_mode": "NONE"
                        },
                        "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                        "version": {
                            "device_id": ws_proto["Ynison-Device-Id"],
                            "version": 9021243204784341000,
                            "timestamp_ms": 0
                        },
                        "from_optional": ""
                    },
                    "status": {
                        "duration_ms": 0,
                        "paused": True,
                        "playback_speed": 1,
                        "progress_ms": 0,
                        "version": {
                            "device_id": ws_proto["Ynison-Device-Id"],
                            "version": 8321822175199937000,
                            "timestamp_ms": 0
                        }
                    }
                },
                "device": {
                    "capabilities": {
                        "can_be_player": True,
                        "can_be_remote_controller": False,
                        "volume_granularity": 16
                    },
                    "info": {
                        "device_id": ws_proto["Ynison-Device-Id"],
                        "type": "WEB",
                        "title": "Chrome Browser",
                        "app_name": "Chrome"
                    },
                    "volume_info": {
                        "volume": 0
                    },
                    "is_shadow": True
                },
                "is_currently_active": False
            },
            "rid": "ac281c26-a047-4419-ad00-e4fbfda1cba3",
            "player_action_timestamp_ms": 0,
            "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT"
        }

        async with session.ws_connect(
                url=f"wss://{data['host']}/ynison_state.YnisonStateService/PutYnisonState",
                headers={
                    "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(new_ws_proto)}",
                    "Origin": "http://music.yandex.ru",
                    "Authorization": f"OAuth {ya_token}",
                },
                method="GET"
        ) as ws:
            await ws.send_str(json.dumps(to_send))
            recv = await ws.receive()
            ynison = json.loads(recv.data)
            print(ynison)
            track = ynison['player_state']['player_queue']['playable_list'][
                ynison['player_state']['player_queue']['current_playable_index']]
        await session.close()
        return {
            "paused": ynison['player_state']['status']['paused'],
            "duration_ms": ynison['player_state']['status']['duration_ms'],
            "progress_ms": ynison['player_state']['status']['progress_ms'],
            "entity_id": ynison['player_state']['player_queue']['entity_id'],
            "entity_type": ynison['player_state']['player_queue']['entity_type'],
            "track": await (await get_info(ya_token)).get_track_by_id(track['playable_id'])
        }


@app.get("/get_likes_from_username")
async def get_likes_from_username(username: str, skip: int = 0, count: int = 10,
                                  ya_token: str = Query(..., title="Yandex Music Token")):
    return await (await get_info(ya_token)).get_like_tracks_by_username(username, skip, count)


app.mount("/", StaticFiles(directory="./static/", html=True))

if __name__ == '__main__':
    import uvicorn

    try:
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except KeyboardInterrupt:
        exit()
