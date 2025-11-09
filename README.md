# YouTube Video Transcription and Analysis

Automatically download, transcribe, and analyze YouTube videos using OpenAI Whisper and Claude AI.

## Features

- Downloads audio from YouTube videos
- Splits long audio into chunks for parallel processing
- Transcribes using OpenAI's Whisper API (with Google Speech Recognition fallback)
- Analyzes transcriptions using Claude AI
- Organizes output into timestamped directories

## Requirements

- Python 3.7+
- FFmpeg (for audio processing)
- API keys:
  - Anthropic API key
  - OpenAI API key

## Installation

```bash
pip install -r requirements.txt
```

Install FFmpeg:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Setup

Set your API keys as environment variables:

```bash
export ANTHROPIC_API_KEY='your_anthropic_key'
export OPENAI_API_KEY='your_openai_key'
```

Add to `~/.bashrc` or `~/.zshrc` to make permanent.

## Usage

```bash
python youtube_transcriber.py
```

Follow the prompts:
1. Enter YouTube URL
2. Choose default or custom analysis prompt
3. Wait for processing
4. View results

## Output Structure

```
youtube_analysis_001/
├── downloads/          # Original audio files
├── extracted_audio/    # Audio chunks
└── transcriptions/     # Transcription and analysis
    ├── transcription.txt
    └── analysis.txt
```

## How It Works

1. Downloads best quality audio from YouTube
2. Splits audio into 30 chunks for parallel processing
3. Transcribes each chunk using OpenAI Whisper
4. Falls back to Google Speech Recognition if needed
5. Analyzes complete transcription with Claude AI
6. Saves all results in organized directory

## Configuration

Modify in code:
- `num_chunks`: Adjust audio splitting (default: 30)
- `max_workers`: Parallel transcription threads (default: 4)
- Analysis prompts: Customize in `custom_analysis_prompt()`

## License

MIT