#!/usr/bin/env python3
"""
YouTube Video Transcription and Analysis Script

Requirements:
    pip install yt-dlp openai anthropic speechrecognition pydub
"""

import os
import sys
import glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import anthropic
from openai import OpenAI
import speech_recognition as sr
from pydub import AudioSegment
import yt_dlp

class YouTubeTranscriber:
    UNWANTED_TEXTS = [
        '© BF-WATCH TV 2021', '🙏🙏 Thank you for watching! 🙏🙏',
        'Thank you for watching!', 'Thank you for watching.',
        'ご視聴ありがとうございました', 'Thanks for watching!',
        'Subscribe to our channel', 'Like and subscribe'
    ]
    
    def __init__(self, anthropic_api_key=None, openai_api_key=None):
        self.anthropic_api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.anthropic_api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")
        
        self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        self.output_dir = self._create_output_directory()
        self.downloads_dir = Path(self.output_dir) / "downloads"
        self.transcriptions_dir = Path(self.output_dir) / "transcriptions"
        self.extracted_audio_dir = Path(self.output_dir) / "extracted_audio"
        
        for dir_path in [self.downloads_dir, self.transcriptions_dir, self.extracted_audio_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _create_output_directory(self):
        documents_dir = Path.home() / "Documents"
        counter = 1
        while True:
            dir_name = documents_dir / f"youtube_analysis_{counter:03d}"
            if not dir_name.exists():
                dir_name.mkdir(parents=True, exist_ok=True)
                print(f"Created output directory: {dir_name}")
                return str(dir_name)
            counter += 1
    
    def download_audio(self, youtube_url):
        output_template = str(self.downloads_dir / "%(title)s.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            'no_warnings': False,
        }
        
        print(f"Downloading audio from: {youtube_url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            print(f"Video title: {info.get('title', 'Unknown')}")
            ydl.download([youtube_url])
            
            audio_files = list(self.downloads_dir.glob("*.wav"))
            if not audio_files:
                raise FileNotFoundError("Downloaded audio file not found")
            
            audio_file = str(audio_files[0])
            print(f"Audio downloaded: {audio_file}")
            return audio_file
    
    def chunk_audio(self, audio_file_path, num_chunks=30):
        print(f"Loading audio file: {audio_file_path}")
        audio = AudioSegment.from_wav(audio_file_path)
        
        total_duration_ms = len(audio)
        chunk_duration_ms = total_duration_ms // num_chunks
        
        print(f"Audio duration: {total_duration_ms/1000/60:.2f} min | "
              f"Creating {num_chunks} chunks of {chunk_duration_ms/1000/60:.2f} min each")
        
        chunk_files = []
        for i in range(num_chunks):
            start_time = i * chunk_duration_ms
            end_time = min((i + 1) * chunk_duration_ms, total_duration_ms)
            
            chunk = audio[start_time:end_time]
            chunk_path = self.extracted_audio_dir / f"chunk_{i+1:03d}.wav"
            chunk.export(str(chunk_path), format="wav")
            chunk_files.append(str(chunk_path))
            
            print(f"Chunk {i+1}/{num_chunks}: {(end_time-start_time)/1000/60:.2f} min")
        
        return chunk_files
    
    def _transcribe_with_openai(self, audio_file_path):
        with open(audio_file_path, "rb") as audio_file:
            transcript = self.openai_client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                response_format="text"
            )
            return transcript
    
    def _transcribe_with_google(self, audio_file_path):
        r = sr.Recognizer()
        with sr.AudioFile(audio_file_path) as source:
            audio = r.record(source)
            return r.recognize_google(audio)
    
    def transcribe_audio_chunk(self, audio_file_path):
        chunk_name = os.path.basename(audio_file_path)
        print(f"Transcribing: {chunk_name}")
        
        # Try OpenAI twice
        for attempt in range(2):
            try:
                transcription = self._transcribe_with_openai(audio_file_path)
                if not any(text in transcription for text in self.UNWANTED_TEXTS):
                    print(f"✓ OpenAI transcribed {chunk_name}: {len(transcription)} chars")
                    return transcription
            except Exception as e:
                print(f"OpenAI attempt {attempt + 1} failed for {chunk_name}: {e}")
        
        # Fallback to Google
        print(f"Using Google fallback for {chunk_name}")
        try:
            transcription = self._transcribe_with_google(audio_file_path)
            print(f"✓ Google transcribed {chunk_name}: {len(transcription)} chars")
            return transcription
        except sr.UnknownValueError:
            print(f"Google couldn't understand {chunk_name}")
            return ""
        except Exception as e:
            print(f"Google failed for {chunk_name}: {e}")
            return ""
    
    def transcribe_audio(self, audio_file_path, max_workers=4):
        chunk_files = self.chunk_audio(audio_file_path)
        
        all_transcriptions = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(self.transcribe_audio_chunk, chunk): (i, chunk)
                for i, chunk in enumerate(chunk_files, 1)
            }
            
            results = {}
            for future in as_completed(future_to_chunk):
                chunk_num, chunk_file = future_to_chunk[future]
                try:
                    transcription = future.result()
                    if transcription.strip():
                        results[chunk_num] = transcription
                except Exception as e:
                    print(f"Error transcribing chunk {chunk_num}: {e}")
        
        # Reconstruct in order
        for i in sorted(results.keys()):
            all_transcriptions.append(f"[Chunk {i}]\n{results[i]}\n")
        
        complete_transcription = "\n".join(all_transcriptions)
        print(f"\nTranscription complete: {len(complete_transcription)} chars")
        return complete_transcription
    
    def save_transcription(self, transcription, filename="transcription.txt"):
        output_path = self.transcriptions_dir / filename
        output_path.write_text(transcription, encoding='utf-8')
        print(f"Transcription saved: {output_path}")
        return str(output_path)
    
    def analyze_transcription(self, transcription, analysis_prompt=None):
        if analysis_prompt is None:
            analysis_prompt = self.get_default_analysis_prompt()
        
        print("Analyzing with Claude...")
        message = self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0.7,
            system="You are an expert content analyzer. Provide thoughtful, detailed analysis.",
            messages=[{
                "role": "user",
                "content": f"{analysis_prompt}\n\nTranscription:\n\n{transcription}"
            }]
        )
        return message.content[0].text
    
    def get_default_analysis_prompt(self):
        return """Analyze this transcription:

1. **Summary**: Main topics overview
2. **Key Points**: Important arguments
3. **Structure**: Content organization
4. **Tone and Style**: Speaking style
5. **Notable Quotes**: Important quotes
6. **Assessment**: Value and quality

Be thorough but concise."""
    
    def process_youtube_video(self, youtube_url, analysis_prompt=None):
        audio_file = self.download_audio(youtube_url)
        transcription = self.transcribe_audio(audio_file)
        transcription_file = self.save_transcription(transcription)
        
        analysis = self.analyze_transcription(transcription, analysis_prompt)
        analysis_file = self.transcriptions_dir / "analysis.txt"
        analysis_file.write_text(analysis, encoding='utf-8')
        print(f"Analysis saved: {analysis_file}")
        
        return {
            "transcription": transcription,
            "analysis": analysis,
            "transcription_file": transcription_file,
            "analysis_file": str(analysis_file),
            "output_directory": self.output_dir
        }

def custom_analysis_prompt():
    return """Analyze focusing on:

1. **Main Arguments**: Core thesis statements
2. **Evidence**: Supporting claims and examples
3. **Logical Structure**: Presentation quality
4. **Potential Biases**: One-sided perspectives
5. **Actionable Insights**: Practical takeaways
6. **Questions Raised**: Further exploration topics

Provide specific examples."""

def main():
    try:
        import yt_dlp
        from openai import OpenAI
        import anthropic
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install yt-dlp openai anthropic speechrecognition pydub")
        sys.exit(1)
    
    youtube_url = input("Enter YouTube URL: ").strip()
    if not youtube_url:
        print("No URL provided. Exiting.")
        sys.exit(1)
    
    try:
        transcriber = YouTubeTranscriber()
    except ValueError as e:
        print(f"Error: {e}")
        print("Set API keys in ~/.bashrc:")
        print("export ANTHROPIC_API_KEY='your_key'")
        print("export OPENAI_API_KEY='your_key'")
        sys.exit(1)
    
    use_custom = input("Use custom analysis prompt? (y/n): ").strip().lower() == 'y'
    analysis_prompt = custom_analysis_prompt() if use_custom else None
    
    print("\n" + "="*50)
    print("Processing YouTube video...")
    print("="*50)
    
    results = transcriber.process_youtube_video(youtube_url, analysis_prompt)
    
    print("\n" + "="*50)
    print("Completed!")
    print("="*50)
    print(f"Directory: {results['output_directory']}")
    print(f"Transcription: {results['transcription_file']}")
    print(f"Analysis: {results['analysis_file']}")
    
    if input("\nDisplay results? (y/n): ").strip().lower() == 'y':
        print("\n" + "-"*30 + " TRANSCRIPTION " + "-"*30)
        print(results['transcription'][:500] + "..." if len(results['transcription']) > 500 else results['transcription'])
        print("\n" + "-"*30 + " ANALYSIS " + "-"*30)
        print(results['analysis'])

if __name__ == "__main__":
    main()