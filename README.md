# Cinematic Image Generator

A Streamlit application that generates cinematic images from script lines using the Leonardo AI API.

## Features

- Script input with automatic line parsing
- Image count selection (up to 252 images)
- Optional reference image upload (1-5 images)
- Cinematic prompt generation
- Leonardo AI API integration
- Dark theme UI
- Progress tracking
- Individual and batch image downloads

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory and add your Leonardo API key:
   ```
   LEONARDO_API_KEY=your_api_key_here
   ```
4. Run the application:
   ```bash
   streamlit run app.py
   ```

## Usage

1. Enter your visual script in the text area (one scene per line)
2. Select the number of images to generate
3. (Optional) Upload reference images with descriptions and tags
4. Click "Generate Images" to start the generation process
5. View and download the generated images

## Requirements

- Python 3.7+
- Streamlit
- Requests
- Pillow
- python-dotenv
- zipfile36

## Note

Make sure you have a valid Leonardo AI API key. You can get one by signing up at [Leonardo AI](https://leonardo.ai/). 