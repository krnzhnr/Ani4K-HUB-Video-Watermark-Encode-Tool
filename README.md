# Ani4K HUB Video Watermark & Encode Tool

This script automates the process of applying watermarks to videos and encoding them with compression. It dynamically adjusts the video bitrate to ensure the output file meets the specified maximum size.

## Features
- **Add watermark**: Automatically adds a watermark image to the video.
- **Dynamic bitrate adjustment**: Adjusts the video bitrate dynamically to meet the target file size if the video length exceeds a specified threshold.
- **Compression**: Compresses videos to optimize file size without compromising quality.
- **Easy to use**: Just configure the settings in `config.yaml` and run the script.

## Installation

### Prerequisites
- Python 3.x
- FFmpeg (ensure it's installed and accessible from the command line)
- Dependencies listed in `requirements.txt`

### Steps to install

1. Clone this repository:

   ```bash
   git clone https://github.com/krnzhnr/Ani4K-HUB-Video-Watermark-Encode-Tool.git
   cd Ani4K-HUB-Video-Watermark-Encode-Tool
   ```
2. Create a virtual environment and install the required dependencies:

   - Windows:
 
     ```bash
     run_script.bat
     ```
   - Linux/macOS:

     ```bash
     python -m venv venv
     source venv/bin/activate  # On Windows use 'venv\Scripts\activate'
     pip install -r requirements.txt
     ```
3. Ensure FFmpeg is installed and accessible from the command line.

   - For installation instructions, visit FFmpeg.org.
## Configuration
The settings for the script are located in the config.yaml file. You can adjust the following parameters:

- **input_dir**: Directory where the input video files are located. By default, this will be the directory next to the script folder.
- **output_dir**: Directory to store watermarked videos. This will be created next to the script folder if it doesn't exist.
- **no_wm_output_dir**: Directory to store videos without watermark. This will also be created next to the script folder.
- **static_watermark**: Path to the watermark image.
- **description**: Description text for video metadata.
- **threshold_minutes**: Video length threshold (in minutes) above which bitrate adjustment is applied.
- **max_file_size_gb**: Maximum file size for the output video (in GB).
- **default_video_bitrate**: Default video bitrate (in Mbps), which will be automatically converted to bps.
- **target_audio_bitrate**: Target audio bitrate (in kbps).

## Usage
- Place your videos in the input_dir (by default, it will be next to the script folder).

- Configure the config.yaml file with your desired settings.

- Run the script:

   ```bash
   python watermark_script_updated.py
   ```
The script will process all video files in the input directory, apply the watermark, and encode them. If the video length exceeds the threshold, the script will adjust the bitrate to ensure the file size does not exceed the maximum size defined in the config.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
