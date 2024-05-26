import streamlit as st
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
import numpy as np

# Define the songScraper class
class songScraper:
    def __init__(self, cid, secret, genius_api_key):
        self.spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))
        self.genius = lyricsgenius.Genius(genius_api_key)

    def get_artists(self, genre="Rock Nacional", artist_n=5, song_n=5, market="AR", artist_popularity=15):
        offset = 1
        size = artist_n
        response = self.spotify.search(q=genre, type='playlist', market=market, limit=None, offset=offset)
        playlists = [playlist['id'] for playlist in response['playlists']['items']]
        artists_data = []
        seen_artist_ids = set()
        while size is None or len(artists_data) < size:
            for playlist_id in playlists:
                results = self.spotify.playlist_tracks(playlist_id)
                tracks = results['items']
                for track in tracks:
                    track_info = track['track']
                    for artist in track_info['artists']:
                        artist_id = artist['id']
                        if artist_id not in seen_artist_ids:
                            seen_artist_ids.add(artist_id)
                            try:
                                artist_data = self.spotify.artist(artist_id)
                            except:
                                artist_data = None
                            if artist_data['popularity'] > artist_popularity:
                                artist_info = {
                                    'Artist': artist['name'],
                                    'Artist_ID': artist_id,
                                    "Artist_genres": artist_data['genres'],
                                    "Artist_popularity": artist_data['popularity']
                                }
                                artists_data.append(artist_info)
                        if size is not None and len(artists_data) >= size:
                            break
                    if size is not None and len(artists_data) >= size:
                        break
                if size is not None and len(artists_data) >= size:
                    break
        df = pd.DataFrame(artists_data)
        songs = []
        song_id = []
        songs_release = []
        songs_popularity = []
        for i in df["Artist"]:
            results = self.spotify.search(q=f"artist:{i}",  type='track', offset=0, limit=song_n)
            songs.append([result["name"] for result in results["tracks"]["items"]])
            song_id.append([result["id"] for result in results["tracks"]["items"]])
            songs_release.append([result["album"]["release_date"] for result in results["tracks"]["items"]])
            songs_popularity.append([result["popularity"] for result in results["tracks"]["items"]])
        df["Track"] = songs
        df["Track_ID"] = song_id
        df["Track_release_date"] = songs_release
        df["Track_popularity"] = songs_popularity
        df = df.explode(["Track","Track_ID","Track_release_date","Track_popularity"])
        return df

    def get_songs(self, n=50, genre="", market="AR", track_popularity_boundary=15):
        offset = 0
        songs_data = []
        while len(songs_data) < n:
            results = self.spotify.search(q=f'genre:"{genre}"', type='track', limit=50, offset=offset, market=market)
            for track in results['tracks']['items']:
                track_name = track['name']
                track_id = track["id"]
                track_release_date = track['album']['release_date']
                track_popularity = track['popularity']
                artist_data = track['artists'][0]
                artist_id = artist_data['id']
                artist_name = artist_data['name']
                artist_popularity = self.get_artist_popularity(artist_id)
                artist_genres = self.get_artist_genres(artist_id)
                album_name = track['album']['name']
                if track_popularity  >= track_popularity_boundary:
                    songs_data.append({'Track': track_name, "Track_ID": track_id, "Track_release_date": track_release_date, "Track_popularity": track_popularity, 'Artist': artist_name, 'Artist_ID': artist_id, 'Artist_Popularity': artist_popularity, 'Artist_Genres': artist_genres, 'Album': album_name})
                    if len(songs_data) >= n:
                        break
            offset += 50
        return pd.DataFrame(songs_data)

    def get_artist_popularity(self, artist_id):
        try:
            artist_data = self.spotify.artist(artist_id)
            return artist_data['popularity']
        except:
            return "nan"

    def get_artist_genres(self, artist_id):
        artist_data = self.spotify.artist(artist_id)
        return artist_data['genres']

    def get_audio_features(self, df):
        features = []
        for i in df["Track_ID"]:
            try:
                feature = self.spotify.audio_features(i)
                if feature:
                    feature = {k: feature[0][k] for k in list(feature[0])[:11]}
                else:
                    feature = "nan"
            except:
                feature = "nan"
            features.append(feature)
        df["features_dict"] = features
        return df

    def get_lyrics(self, df):
        lyrics = []
        total_rows = len(df)
        for idx, row in df.iterrows():
            progress = f"Fetching Lyrics: {idx+1}/{total_rows}"
            print(progress, end="\r")
            try:
                song = self.genius.search_song(row["Track"], row["Artist"])
                if song:
                    lyrics.append(song.lyrics)
                else:
                    lyrics.append("nan")
            except Exception as e:
                print(f"Error occurred: {e}")
                lyrics.append("nan")
        print()
        df["Lyrics"] = lyrics
        return df

    def get_id(self, artist_name):
        try:
            results = self.spotify.search(q=artist_name, type='artist', limit=1)
            if 'artists' in results and 'items' in results['artists'] and len(results['artists']['items']) > 0:
                artist_id = results['artists']['items'][0]['id']
                return artist_id
            else:
                print(f"Artist '{artist_name}' not found.")
                return None
        except spotipy.SpotifyException as e:
            print(f"Spotipy error: {e}")
            return None

# Streamlit App
st.title('Minado de canciones y letras')

cid = st.text_input('Spotify Client ID')
secret = st.text_input('Spotify Client Secret', type='password')
genius_api_key = st.text_input('Genius Token',type='password')

genre = st.text_input('Genero Musical', 'Argentine Rock')
song_n = st.number_input('Cantidad de canciones', 20, 200, 20)

if st.button('Minar canciones'):
    scraper = songScraper(cid, secret, genius_api_key)

    with st.spinner('Cargando...'):
        data = scraper.get_songs(genre=genre, n=song_n)
        data = scraper.get_audio_features(data)
        data = scraper.get_lyrics(data)

    st.success('Datos minados exitosamente!')
    st.dataframe(data)

    csv = data.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar archivo",
        data=csv,
        file_name='songs_data.csv',
        mime='text/csv',
    )
