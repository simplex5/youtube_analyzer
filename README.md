# YouTube Video Transcription and Analysis

Download, transcribe, and analyze YouTube videos using OpenAI’s speech-to-text API and Claude for structured content analysis.  
Designed to **reuse previous work**: it skips re-downloading and re-transcribing when outputs already exist for a given video.

---

## Features

- Uses `yt-dlp` to download best-quality audio from YouTube.
- Organizes outputs **per video title** in a dedicated directory under `~/Documents` (or `C:\Users\<YourName>\Documents` on Windows).
- Splits audio into chunks for faster, parallel transcription.
- Primary transcription via **OpenAI audio transcription** (`gpt-4o-mini-transcribe`).
- Automatic fallback to **Google Speech Recognition** if OpenAI fails.
- Filters out common boilerplate phrases (e.g. “Thanks for watching”, “Subscribe to our channel”).
- Skips:
  - Downloading if audio already exists.
  - Transcription if a base transcription already exists.
- Always generates a **new Claude analysis** per run and stores each as a separate answer file.

---

## Requirements

- Python 3.7+
- [FFmpeg](https://ffmpeg.org/) (required for `yt-dlp` and `pydub`)
- Python packages:
  - `yt-dlp`
  - `openai`
  - `anthropic`
  - `speechrecognition`
  - `pydub`

Install dependencies:

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

---

## 🪟 Windows Setup

### 1. Install FFmpeg on Windows

#### Option A — via Chocolatey (recommended)
If you use [Chocolatey](https://chocolatey.org/install):

```powershell
choco install ffmpeg -y
```

#### Option B — manual install
1. Download FFmpeg from: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract it (e.g. to `C:\ffmpeg`).
3. Add it to your system PATH:
   - Open **Control Panel → System → Advanced system settings → Environment Variables**.
   - Under **System Variables**, find `Path`, click **Edit**, and add:
     ```
     C:\ffmpeg\bin
     ```

You can verify installation with:
```powershell
ffmpeg -version
```

### 2. Set Environment Variables for API Keys

Open PowerShell (as Administrator or for your user) and run:

```powershell
setx ANTHROPIC_API_KEY "your_anthropic_key"
setx OPENAI_API_KEY "your_openai_key"
```

Then **close and reopen** PowerShell to apply the new environment variables.

To confirm they’re set:
```powershell
echo $Env:ANTHROPIC_API_KEY
echo $Env:OPENAI_API_KEY
```

---

## Setup (macOS / Linux)

Set your API keys as environment variables:

```bash
export ANTHROPIC_API_KEY='your_anthropic_key'
export OPENAI_API_KEY='your_openai_key'
```

Add these to `~/.bashrc`, `~/.bash_profile`, or `~/.zshrc` to make them persistent.

The script **does not** read keys from the code; missing keys will cause a clear error and exit.

---

## Usage

From the project directory:

```bash
python youtube_analyzer.py
```

You’ll be prompted to:

1. Enter a YouTube URL.
2. Review the current custom analysis prompt (shown in the terminal).
3. Choose:
   - Use the shown custom prompt,
   - Use the default built-in analysis prompt, or
   - Enter your own custom prompt.
4. The script will:
   - Initialize directories for that specific video title.
   - Reuse existing audio or transcription if available.
   - Otherwise download, chunk, and transcribe.
   - Run analysis with Claude.
   - Save results to disk.
5. Optionally display a preview of the transcription and analysis.

---

## Output Structure

For each video, outputs are stored under:

```text
~/Documents/<SanitizedVideoTitle>_analysis/
├── base_transcription/
│   └── transcription.txt        # Full combined transcription (with chunk markers)
├── base_youtube_audio/
│   └── <original>.wav           # Downloaded source audio
├── extracted_audio/
│   ├── chunk_001.wav
│   ├── chunk_002.wav
│   └── ...                      # Generated chunks for transcription
└── responses/
    ├── answer_1.txt             # First Claude analysis for this video
    ├── answer_2.txt             # Second analysis (e.g. different prompt)
    └── ...
```

Behavior details:

- If `base_youtube_audio/*.wav` exists → reuse audio (no new download).
- If `base_transcription/transcription.txt` exists → reuse transcription (no re-transcribe).
- Each new run always writes a new `answer_N.txt` in `responses/`.

Directory names are derived from the **sanitized video title** (invalid path characters removed, length capped).

---

## How It Works

1. **Video Metadata & Directories**
   - Fetches basic info (title) via `yt-dlp`.
   - Creates `<SanitizedTitle>_analysis` with the standard subdirectories if not present.

2. **Audio Handling**
   - Checks for existing WAV in `base_youtube_audio/`.
   - If missing, downloads best audio via `yt-dlp` and converts to WAV.

3. **Chunking**
   - If not already chunked, splits audio into 30 chunks by default using `pydub`.
   - Stores chunks in `extracted_audio/`.

4. **Transcription**
   - If `base_transcription/transcription.txt` exists, it’s reused.
   - Otherwise:
     - Each chunk is sent to OpenAI:
       - `model="gpt-4o-mini-transcribe"`, `response_format="text"`.
     - On repeated failure for a chunk, falls back to Google Speech Recognition.
     - Filters out configured `UNWANTED_TEXTS`.
     - Reassembles results in order with `[Chunk N]` headers.
     - Saves to `base_transcription/transcription.txt`.

5. **Analysis (Claude)**
   - Uses either:
     - Default analysis prompt (`get_default_analysis_prompt()`), or
     - The interactive/custom prompt chosen at runtime.
   - Sends the full transcription + prompt to:
     - `model="claude-sonnet-4-20250514"`.
   - Saves each response as `responses/answer_<N>.txt`, incrementing `N`.

---

## Configuration

Adjust directly in `youtube_analyzer.py`:

- **Chunking count**: `num_chunks` in `chunk_audio()` (default: `30`).
- **Parallel workers**: `max_workers` in `transcribe_audio()` (default: `4`).
- **Boilerplate filters**: edit `UNWANTED_TEXTS` in `YouTubeTranscriber`.
- **Default analysis prompt**:
  - `get_default_analysis_prompt()`.
- **Custom template prompt**:
  - `custom_analysis_prompt()`.

---

## Notes

- No API keys are stored in the repository.
- The script is built for local, interactive CLI use.
- Safe to use in public repos as long as your environment variables (keys) are kept outside the codebase.
