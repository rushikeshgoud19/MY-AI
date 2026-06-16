import urllib.request
import urllib.parse
import json
import logging

class Skill:
    def __init__(self):
        self.name = "music_discovery"
        self.description = "Search for music tracks, albums, previews, and artist metadata using public APIs (iTunes and Deezer)."

    def execute(self, query: str, provider: str = "itunes") -> str:
        """
        Executes a music search.
        Arguments:
        - query: The artist, song, or album name to search for (e.g., 'Tycho Awake')
        - provider: 'itunes' (default, fastest) or 'deezer'
        """
        logging.info(f"[MUSIC] Searching {provider} for: {query}")
        
        try:
            if provider.lower() == "itunes":
                return self._search_itunes(query)
            elif provider.lower() == "deezer":
                return self._search_deezer(query)
            else:
                return f"Error: Unknown provider '{provider}'. Use 'itunes' or 'deezer'."
        except Exception as e:
            return f"Music API search failed: {str(e)}"

    def _search_itunes(self, query: str) -> str:
        safe_query = urllib.parse.quote(query)
        url = f"https://itunes.apple.com/search?term={safe_query}&entity=song&limit=5"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
        results = data.get("results", [])
        if not results:
            return f"No music found for '{query}' on iTunes."
            
        output = [f"### Top 5 iTunes Results for '{query}':"]
        for i, track in enumerate(results):
            artist = track.get("artistName", "Unknown Artist")
            name = track.get("trackName", "Unknown Track")
            album = track.get("collectionName", "Unknown Album")
            preview = track.get("previewUrl", "No preview available")
            output.append(f"{i+1}. **{artist} - {name}** (Album: {album})\n   Preview: {preview}")
            
        return "\n".join(output)

    def _search_deezer(self, query: str) -> str:
        safe_query = urllib.parse.quote(query)
        url = f"https://api.deezer.com/search?q={safe_query}&limit=5"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
        results = data.get("data", [])
        if not results:
            return f"No music found for '{query}' on Deezer."
            
        output = [f"### Top 5 Deezer Results for '{query}':"]
        for i, track in enumerate(results):
            artist = track.get("artist", {}).get("name", "Unknown Artist")
            name = track.get("title", "Unknown Track")
            album = track.get("album", {}).get("title", "Unknown Album")
            preview = track.get("preview", "No preview available")
            output.append(f"{i+1}. **{artist} - {name}** (Album: {album})\n   Preview: {preview}")
            
        return "\n".join(output)
