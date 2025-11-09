# YouTube Video Transcription and Analysis

Automatically download, transcribe, and analyze YouTube videos using OpenAI’s speech-to-text API and Claude for high-level analysis.

## Features

- Downloads best-quality audio from YouTube using `yt-dlp`
- Splits audio into chunks for faster, parallel transcription
- Transcribes using **OpenAI audio transcription** (`gpt-4o-mini-transcribe`)
- Falls back to **Google Speech Recognition** if OpenAI transcription fails
- Analyzes the full transcription using **Claude** (`claude-sonnet-4-20250514`)
- Filters out common end-screen / subscribe boilerplate text
- Saves everything into an auto-incremented output directory under `~/Documents`

## Requirements

- Python 3.7+
- [FFmpeg](https://ffmpeg.org/) (required by `yt-dlp` and `pydub`)
- Python packages:
  - `yt-dlp`
  - `openai`
  - `anthropic`
  - `speechrecognition`
  - `pydub`

Install Python dependencies:

```bash
pip install yt-dlp openai anthropic speechrecognition pydub
```

Install FFmpeg:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS (Homebrew)
brew install ffmpeg
```

## Setup

Set your API keys as environment variables:

```bash
export ANTHROPIC_API_KEY='your_anthropic_key'
export OPENAI_API_KEY='your_openai_key'
```

Add those lines to `~/.bashrc` or `~/.zshrc` to persist them.

## Usage

Run the script:

```bash
python youtube_transcriber.py
```

You will be prompted to:

1. Enter the YouTube URL.
2. Review the current analysis prompt (a focused analytical template).
3. Choose:
   - Use the shown custom prompt, **or**
   - Use the built-in default prompt, **or**
   - Enter your own custom analysis prompt.
4. The script will:
   - Download audio
   - Chunk and transcribe it
   - Run analysis with Claude
   - Save transcription and analysis to disk
5. Optionally display a preview of the results in the console.

## Output Structure

All results are stored under `~/Documents` in an auto-numbered directory:

```text
~/Documents/
└── youtube_analysis_001/
    ├── downloads/          # Downloaded original audio (WAV)
    ├── extracted_audio/    # Chunked audio segments
    └── transcriptions/     # Generated text files
        ├── transcription.txt
        └── analysis.txt
```

If the directory already exists, the script creates `youtube_analysis_002`, `youtube_analysis_003`, etc.

## How It Works

1. **Download**  
   Uses `yt-dlp` to fetch best available audio and convert it to WAV.

2. **Chunking**  
   Splits the audio into 30 segments (by default) using `pydub` for parallel processing.

3. **Transcription**  
   - Each chunk is sent to OpenAI:
     - `model="gpt-4o-mini-transcribe"`
   - If OpenAI fails twice for a chunk, it falls back to Google Speech Recognition.
   - Unwanted boilerplate strings (e.g. “Thanks for watching”, “Subscribe to our channel”) are filtered out.

4. **Reconstruction**  
   All chunk transcriptions are reassembled in order into a single `transcription.txt` with chunk markers.

5. **Analysis**  
   The full transcription is sent to Claude (`claude-sonnet-4-20250514`) with:
   - Either the default analysis prompt
   - Or the chosen custom prompt
   Result is saved as `analysis.txt`.

## Configuration

Adjust behavior directly in the script:

- **Chunking**
  - `num_chunks` in `chunk_audio()` (default: `30`)
- **Parallelism**
  - `max_workers` in `transcribe_audio()` (default: `4`)
- **Analysis Prompts**
  - Default analysis: `get_default_analysis_prompt()`
  - Custom example prompt: `custom_analysis_prompt()`
- **Unwanted Text Filtering**
  - Update `UNWANTED_TEXTS` in `YouTubeTranscriber` to strip outro/boilerplate phrases.

## Notes

- Requires valid **Anthropic** and **OpenAI** API keys.
- Uses environment variables only; no keys are hardcoded.
- Designed for local, single-URL, interactive use from the terminal.
