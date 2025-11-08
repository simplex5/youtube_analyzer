#!/usr/bin/env python3
"""
YouTube Video Transcription and Analysis Script

This script downloads a YouTube video, transcribes it using OpenAI's GPT-4o-mini-transcribe,
and then analyzes the transcription using Anthropic's Claude API.

Requirements:
    pip install yt-dlp openai anthropic speechrecognition pydub

Usage:
    python youtube_transcriber.py
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
import anthropic
from openai import OpenAI
import speech_recognition as sr
from pydub import AudioSegment
import yt_dlp
import glob

class YouTubeTranscriber:
    def __init__(self, anthropic_api_key=None, openai_api_key=None):
        """
        Initialize the transcriber with API keys.
        
        Args:
            anthropic_api_key (str): Anthropic API key. If None, will use ANTHROPIC_API_KEY env var.
            openai_api_key (str): OpenAI API key. If None, will use OPENAI_API_KEY env var.
        """
        self.anthropic_api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable or pass anthropic_api_key parameter.")
        
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass openai_api_key parameter.")
        
        self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        # Create sequential output directory
        self.output_dir = self._create_output_directory()
        self.downloads_dir = os.path.join(self.output_dir, "downloads")
        self.transcriptions_dir = os.path.join(self.output_dir, "transcriptions")
        self.extracted_audio_dir = os.path.join(self.output_dir, "extracted_audio")
        
        # Create subdirectories
        for dir_path in [self.downloads_dir, self.transcriptions_dir, self.extracted_audio_dir]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _create_output_directory(self):
        """Create a sequential output directory."""
        base_name = "youtube_analysis"
        counter = 1
        
        while True:
            dir_name = f"{base_name}_{counter:03d}"
            if not os.path.exists(dir_name):
                Path(dir_name).mkdir(parents=True, exist_ok=True)
                print(f"Created output directory: {dir_name}")
                return dir_name
            counter += 1
    
    def download_audio(self, youtube_url):
        """
        Download audio from YouTube video using yt-dlp Python library.
        
        Args:
            youtube_url (str): YouTube video URL
            
        Returns:
            str: Path to downloaded audio file
        """
        output_template = os.path.join(self.downloads_dir, "%(title)s.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            # Options to bypass YouTube throttling
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            'age_limit': None,
            'no_warnings': False,
        }
        
        try:
            print(f"Downloading audio from: {youtube_url}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get title
                info = ydl.extract_info(youtube_url, download=False)
                title = info.get('title', 'audio')
                print(f"Video title: {title}")
                
                # Download the audio
                ydl.download([youtube_url])
                
                # Find the downloaded file
                audio_files = glob.glob(os.path.join(self.downloads_dir, "*.wav"))
                if not audio_files:
                    raise FileNotFoundError("Downloaded audio file not found")
                
                audio_file = audio_files[0]  # Get the first (should be only) wav file
                    
            print(f"Audio downloaded successfully: {audio_file}")
            return audio_file
            
        except Exception as e:
            raise Exception(f"Failed to download audio: {str(e)}")
    
    def chunk_audio(self, audio_file_path, num_chunks=30):
        """
        Split audio file into a specified number of chunks.
        
        Args:
            audio_file_path (str): Path to audio file
            num_chunks (int): Number of chunks to create
            
        Returns:
            list: List of paths to audio chunks
        """
        try:
            print(f"Loading audio file for chunking: {audio_file_path}")
            audio = AudioSegment.from_wav(audio_file_path)
            
            total_duration_ms = len(audio)
            chunk_duration_ms = total_duration_ms // num_chunks
            
            print(f"Audio duration: {total_duration_ms/1000/60:.2f} minutes")
            print(f"Creating {num_chunks} chunks of {chunk_duration_ms/1000/60:.2f} minutes each")
            
            chunk_files = []
            
            for i in range(num_chunks):
                start_time = i * chunk_duration_ms
                end_time = min((i + 1) * chunk_duration_ms, total_duration_ms)
                
                chunk = audio[start_time:end_time]
                chunk_filename = f"chunk_{i+1:03d}.wav"
                chunk_path = os.path.join(self.extracted_audio_dir, chunk_filename)
                
                chunk.export(chunk_path, format="wav")
                chunk_files.append(chunk_path)
                
                print(f"Created chunk {i+1}/{num_chunks}: {chunk_filename} ({(end_time-start_time)/1000/60:.2f} minutes)")
            
            return chunk_files
            
        except Exception as e:
            raise Exception(f"Failed to chunk audio: {str(e)}")
    
    def transcribe_audio_chunk(self, audio_file_path):
        """
        Transcribe a single audio chunk using OpenAI's GPT-4o-mini-transcribe.
        
        Args:
            audio_file_path (str): Path to audio chunk file
            
        Returns:
            str: Transcription text
        """
        max_retries = 2
        retry_count = 0
        transcription = ""
        
        # Common unwanted texts that might appear in transcriptions
        unwanted_texts = [
            '© BF-WATCH TV 2021', 
            '🙏🙏 Thank you for watching! 🙏🙏', 
            'Thank you for watching!', 
            'Thank you for watching.', 
            'ご視聴ありがとうございました', 
            'Thanks for watching!',
            'Subscribe to our channel',
            'Like and subscribe'
        ]
        
        chunk_name = os.path.basename(audio_file_path)
        print(f"Transcribing chunk: {chunk_name}")
        
        while retry_count < max_retries:
            try:
                with open(audio_file_path, "rb") as audio_file:
                    transcript = self.openai_client.audio.transcriptions.create(
                        model="gpt-4o-mini-transcribe",
                        file=audio_file,
                        response_format="text"
                    )
                    transcription = transcript
                    
                    # Check if transcription contains unwanted text
                    if not any(unwanted_text in transcription for unwanted_text in unwanted_texts):
                        print(f"✓ Transcribed {chunk_name}: {len(transcription)} characters")
                        return transcription  # Return successful transcription
                        
            except Exception as e:
                print(f"Error with OpenAI transcription for {chunk_name} (attempt {retry_count + 1}): {e}")
                
            retry_count += 1
            if retry_count < max_retries:
                print(f"Retrying transcription for {chunk_name}...")
        
        # If we get here, OpenAI failed - try Google as fallback
        print(f"Falling back to Google Speech Recognition for {chunk_name}...")
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_file_path) as source:
                audio = r.record(source)
                transcription = r.recognize_google(audio)
                print(f"✓ Google transcribed {chunk_name}: {len(transcription)} characters")
                return transcription
                
        except sr.UnknownValueError:
            print(f"Google Speech Recognition could not understand {chunk_name}")
            return ""
        except Exception as e:
            print(f"Error with Google transcription for {chunk_name}: {e}")
            return transcription if transcription else ""
    
    def transcribe_audio(self, audio_file_path):
        """
        Transcribe audio file by chunking it and transcribing each chunk.
        
        Args:
            audio_file_path (str): Path to audio file
            
        Returns:
            str: Complete transcription text
        """
        # First, chunk the audio
        chunk_files = self.chunk_audio(audio_file_path)
        
        # Transcribe each chunk
        all_transcriptions = []
        for i, chunk_file in enumerate(chunk_files, 1):
            print(f"\nTranscribing chunk {i}/{len(chunk_files)}...")
            transcription = self.transcribe_audio_chunk(chunk_file)
            if transcription.strip():  # Only add non-empty transcriptions
                all_transcriptions.append(f"[Chunk {i}]\n{transcription}\n")
        
        # Combine all transcriptions
        complete_transcription = "\n".join(all_transcriptions)
        print(f"\nTranscription completed! Total length: {len(complete_transcription)} characters")
        
        return complete_transcription
    
    def save_transcription(self, transcription, filename="transcription.txt"):
        """
        Save transcription to a text file in the transcriptions directory.
        
        Args:
            transcription (str): Transcription text
            filename (str): Output filename
        """
        output_path = os.path.join(self.transcriptions_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(transcription)
        print(f"Transcription saved to: {output_path}")
        return output_path
    
    def analyze_transcription(self, transcription, analysis_prompt=None):
        """
        Analyze transcription using Claude API.
        
        Args:
            transcription (str): Transcription text to analyze
            analysis_prompt (str): Custom prompt for analysis
            
        Returns:
            str: Analysis result from Claude
        """
        if analysis_prompt is None:
            analysis_prompt = self.get_default_analysis_prompt()
        
        try:
            print("Analyzing transcription with Claude...")
            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.7,
                system="You are an expert content analyzer. Provide thoughtful, detailed analysis of the given transcription.",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{analysis_prompt}\n\nTranscription to analyze:\n\n{transcription}"
                            }
                        ]
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            raise Exception(f"Failed to analyze transcription: {str(e)}")
    
    def get_default_analysis_prompt(self):
        """
        Get the default analysis prompt. Modify this function to change the analysis behavior.
        
        Returns:
            str: Default analysis prompt
        """
        return """Please analyze this video transcription and provide:

1. **Summary**: A concise overview of the main topics discussed
2. **Key Points**: The most important points or arguments made
3. **Structure**: How the content is organized and flows
4. **Tone and Style**: The speaking style and tone used
5. **Notable Quotes**: Any particularly interesting or important quotes
6. **Overall Assessment**: Your thoughts on the content's value and quality

Please be thorough but concise in your analysis."""
    
    def process_youtube_video(self, youtube_url, analysis_prompt=None):
        """
        Complete pipeline: download, transcribe, and analyze a YouTube video.
        
        Args:
            youtube_url (str): YouTube video URL
            analysis_prompt (str): Custom analysis prompt
            
        Returns:
            dict: Results containing transcription and analysis
        """
        try:
            # Download audio
            audio_file = self.download_audio(youtube_url)
            
            # Transcribe (this will handle chunking internally)
            transcription = self.transcribe_audio(audio_file)
            
            # Save transcription
            transcription_file = self.save_transcription(transcription)
            
            # Analyze transcription
            analysis = self.analyze_transcription(transcription, analysis_prompt)
            
            # Save analysis
            analysis_file = os.path.join(self.transcriptions_dir, "analysis.txt")
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            print(f"Analysis saved to: {analysis_file}")
            
            return {
                "transcription": transcription,
                "analysis": analysis,
                "transcription_file": transcription_file,
                "analysis_file": analysis_file,
                "output_directory": self.output_dir
            }
            
        except Exception as e:
            print(f"Error processing video: {str(e)}")
            raise

def custom_analysis_prompt():
    """
    Modify this function to customize the analysis prompt.
    
    Returns:
        str: Your custom analysis prompt
    """
    return """Please analyze this video transcription and focus on:

1. **Main Arguments**: What are the core arguments or thesis statements?
2. **Evidence Presented**: What evidence or examples are used to support claims?
3. **Logical Structure**: How well-structured and logical is the presentation?
4. **Potential Biases**: Are there any apparent biases or one-sided perspectives?
5. **Actionable Insights**: What practical takeaways can viewers implement?
6. **Questions Raised**: What questions does this content raise for further exploration?

Provide specific examples from the transcription to support your analysis."""

def main():
    """Main function to run the script interactively."""
    
    # Check for required dependencies
    try:
        import yt_dlp
        from openai import OpenAI
        import anthropic
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install required packages:")
        print("pip install yt-dlp openai anthropic speechrecognition pydub")
        sys.exit(1)
    
    # Get YouTube URL from user
    youtube_url = input("Enter YouTube URL: ").strip()
    if not youtube_url:
        print("No URL provided. Exiting.")
        sys.exit(1)
    
    # Initialize transcriber
    try:
        transcriber = YouTubeTranscriber()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set your API keys in your ~/.bashrc file:")
        print("export ANTHROPIC_API_KEY='your_anthropic_key'")
        print("export OPENAI_API_KEY='your_openai_key'")
        print("Then run: source ~/.bashrc")
        sys.exit(1)
    
    # Ask about custom analysis prompt
    use_custom_prompt = input("Use custom analysis prompt? (y/n): ").strip().lower() == 'y'
    analysis_prompt = custom_analysis_prompt() if use_custom_prompt else None
    
    # Process the video
    try:
        print("\n" + "="*50)
        print("Processing YouTube video...")
        print("="*50)
        
        results = transcriber.process_youtube_video(
            youtube_url=youtube_url,
            analysis_prompt=analysis_prompt
        )
        
        print("\n" + "="*50)
        print("Processing completed successfully!")
        print("="*50)
        print(f"Output directory: {results['output_directory']}")
        print(f"Transcription saved to: {results['transcription_file']}")
        print(f"Analysis saved to: {results['analysis_file']}")
        
        # Optionally display results
        show_results = input("\nDisplay results in terminal? (y/n): ").strip().lower() == 'y'
        if show_results:
            print("\n" + "-"*30 + " TRANSCRIPTION " + "-"*30)
            print(results['transcription'][:500] + "..." if len(results['transcription']) > 500 else results['transcription'])
            
            print("\n" + "-"*30 + " ANALYSIS " + "-"*30)
            print(results['analysis'])
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()