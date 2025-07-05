from fastapi import FastAPI, HTTPException, Query
from youtube_transcript_api import YouTubeTranscriptApi
import re
import requests

app = FastAPI(title="YouTube Transcript API", version="1.0.0")


@app.get("/")
def read_root():
    return {
        "message": "YouTube Transcript API",
        "endpoints": {
            "get_transcript": "/api/transcript/{video_id}",
            "get_transcript_with_lang": "/api/transcript-{language_code}/{video_id}",
            "get_available_languages": "/api/transcript_languages/{video_id}"
        },
        "examples": {
            "basic_transcript": "/api/transcript/dQw4w9WgXcQ",
            "spanish_transcript": "/api/transcript-es/dQw4w9WgXcQ",
            "english_transcript": "/api/transcript-en/dQw4w9WgXcQ",
            "available_languages": "/api/transcript_languages/dQw4w9WgXcQ"
        }
    }

@app.get("/api/transcript/{video_id}")
def get_transcript(video_id: str, proxy: str = Query(None, description="Proxy URL (optional)")):
    """Get transcript for a YouTube video (defaults to English)"""
    try:
        # Extract video ID if URL is provided
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube video ID or URL")
        
        # Set up proxy if provided
        proxies = None
        if proxy:
            proxies = {"http": proxy, "https": proxy}
        
        # Get transcript with retry mechanism
        transcript = None
        try:
            if proxies:
                # Custom session with proxy
                session = requests.Session()
                session.proxies = proxies
                transcript = YouTubeTranscriptApi.get_transcript(video_id, proxies=proxies)
            else:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as first_error:
            # If first attempt fails, try with different languages
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
            except Exception as second_error:
                # If still fails, try to get any available transcript
                try:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    transcript = transcript_list.find_transcript(['en', 'en-US']).fetch()
                except Exception:
                    # If all fails, return the original error with helpful message
                    raise HTTPException(
                        status_code=503, 
                        detail=f"YouTube is blocking requests. Try: 1) Different video ID, 2) Add ?proxy=YOUR_PROXY_URL, 3) Try again later. Original error: {str(first_error)}"
                    )
        
        # Format response
        formatted_transcript = []
        full_text = ""
        
        for entry in transcript:
            formatted_entry = {
                "text": entry['text'],
                "start": entry['start'],
                "duration": entry['duration']
            }
            formatted_transcript.append(formatted_entry)
            full_text += entry['text'] + " "
        
        return {
            "video_id": video_id,
            "transcript": formatted_transcript,
            "full_text": full_text.strip(),
            "total_entries": len(formatted_transcript),
            "proxy_used": proxy is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "No transcripts were found" in error_msg:
            raise HTTPException(status_code=404, detail="No transcripts found for this video")
        elif "Video unavailable" in error_msg:
            raise HTTPException(status_code=404, detail="Video not found or unavailable")
        else:
            raise HTTPException(status_code=500, detail=f"Error retrieving transcript: {error_msg}")

@app.get("/api/transcript-{language_code}/{video_id}")
def get_transcript_with_language(language_code: str, video_id: str, proxy: str = Query(None, description="Proxy URL (optional)")):
    """Get transcript for a YouTube video in specific language"""
    try:
        # Extract video ID if URL is provided
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube video ID or URL")
        
        # Set up proxy if provided
        proxies = None
        if proxy:
            proxies = {"http": proxy, "https": proxy}
        
        # Get transcript in specific language
        try:
            if proxies:
                # Custom session with proxy
                session = requests.Session()
                session.proxies = proxies
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language_code], proxies=proxies)
            else:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language_code])
        except Exception as e:
            # If the specific language fails, try to get available transcripts and suggest alternatives
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                available_langs = [t.language_code for t in transcript_list]
                raise HTTPException(
                    status_code=404, 
                    detail=f"No transcript found for language '{language_code}'. Available languages: {', '.join(available_langs)}"
                )
            except Exception:
                raise HTTPException(status_code=404, detail=f"No transcripts found for this video in language: {language_code}")
        
        # Format response
        formatted_transcript = []
        full_text = ""
        
        for entry in transcript:
            formatted_entry = {
                "text": entry['text'],
                "start": entry['start'],
                "duration": entry['duration']
            }
            formatted_transcript.append(formatted_entry)
            full_text += entry['text'] + " "
        
        return {
            "video_id": video_id,
            "language": language_code,
            "transcript": formatted_transcript,
            "full_text": full_text.strip(),
            "total_entries": len(formatted_transcript),
            "proxy_used": proxy is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "No transcripts were found" in error_msg:
            raise HTTPException(status_code=404, detail=f"No transcripts found for this video in language: {language_code}")
        elif "Video unavailable" in error_msg:
            raise HTTPException(status_code=404, detail="Video not found or unavailable")
        else:
            raise HTTPException(status_code=500, detail=f"Error retrieving transcript: {error_msg}")

@app.get("/api/transcript_languages/{video_id}")
def get_available_languages(video_id: str, proxy: str = Query(None, description="Proxy URL (optional)")):
    """Get available transcript languages for a video"""
    try:
        # Extract video ID if URL is provided
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube video ID or URL")
        
        # Set up proxy if provided
        proxies = None
        if proxy:
            proxies = {"http": proxy, "https": proxy}
        
        # Get available transcripts
        try:
            if proxies:
                # Note: YouTubeTranscriptApi.list_transcripts doesn't directly support proxies
                # but we can try to use the session approach
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            else:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        except Exception as e:
            if "Video unavailable" in str(e):
                raise HTTPException(status_code=404, detail="Video not found or unavailable")
            else:
                raise HTTPException(status_code=500, detail=f"Error retrieving languages: {str(e)}")
        
        available_languages = []
        for transcript in transcript_list:
            available_languages.append({
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable
            })
        
        return {
            "video_id": video_id,
            "available_languages": available_languages,
            "total_languages": len(available_languages),
            "proxy_used": proxy is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "Video unavailable" in error_msg:
            raise HTTPException(status_code=404, detail="Video not found or unavailable")
        else:
            raise HTTPException(status_code=500, detail=f"Error retrieving languages: {error_msg}")

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "YouTube Transcript API"}

# Required for Vercel
handler = app