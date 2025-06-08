import streamlit as st
import requests
import os
from PIL import Image
import io
import json
from datetime import datetime
import zipfile
from dotenv import load_dotenv
import tempfile
import time

# Load environment variables
load_dotenv()

# Constants
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
LEONARDO_API_URL = "https://cloud.leonardo.ai/api/rest/v1"
MAX_IMAGES = 252
MAX_RETRIES = 30  # Maximum number of retries for checking generation status
RETRY_DELAY = 2   # Delay between retries in seconds

# Set page config
st.set_page_config(
    page_title="Cinematic Image Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for dark theme
st.markdown("""
    <style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stTextArea textarea {
        background-color: #262730;
        color: #FAFAFA;
    }
    .stButton button {
        background-color: #4CAF50;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

def parse_script(script):
    """Parse script into lines and remove empty lines."""
    return [line.strip() for line in script.split('\n') if line.strip()]

def generate_cinematic_prompt(script_line, scene_num, reference_images=None):
    """Generate a cinematic prompt from a script line."""
    base_prompt = f"Scene {scene_num}: {script_line}. Cinematic depth, atmospheric lighting, professional cinematography, 8k resolution, dramatic composition."
    
    if reference_images:
        ref_prompts = []
        for ref in reference_images:
            ref_prompts.append(f"Use reference image '{ref['description']}' for {ref['tag']} consistency.")
        base_prompt += " " + " ".join(ref_prompts)
    
    return base_prompt

def create_generation(api_key, prompt, model_id="ac614f96-1082-45bf-be9d-757f2d31c174"):
    """Create a generation using Leonardo API."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "prompt": prompt,
        "modelId": model_id,
        "width": 1024,
        "height": 576,
        "num_images": 1,
        "promptMagic": True,
        "alchemy": True
    }
    
    response = requests.post(
        f"{LEONARDO_API_URL}/generations",
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        st.error(f"Error creating generation: {response.text}")
        return None
        
    return response.json()

def get_generation_images(api_key, generation_id):
    """Get generated images from Leonardo API with retry logic."""
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    for attempt in range(MAX_RETRIES):
        response = requests.get(
            f"{LEONARDO_API_URL}/generations/{generation_id}",
            headers=headers
        )
        
        if response.status_code != 200:
            st.error(f"Error getting generation status: {response.text}")
            return None
            
        data = response.json()
        
        # Check if generation is complete
        if "generations_by_pk" in data:
            generation = data["generations_by_pk"]
            if generation.get("status") == "COMPLETE":
                if generation.get("generated_images") and len(generation["generated_images"]) > 0:
                    return data
            elif generation.get("status") == "FAILED":
                st.error(f"Generation failed: {generation.get('error', 'Unknown error')}")
                return None
        
        # Wait before next retry
        time.sleep(RETRY_DELAY)
    
    st.error("Generation timed out after maximum retries")
    return None

def main():
    st.title("🎬 Cinematic Image Generator")
    
    # Script Input
    st.header("1. Script Input")
    script = st.text_area(
        "Enter your visual script (one line per scene):",
        height=200,
        help="Enter your script with each scene on a new line"
    )
    
    if script:
        script_lines = parse_script(script)
        st.info(f"Total possible scenes: {len(script_lines)}")
        
        # Image Count Selection
        st.header("2. Image Count Selection")
        max_images = min(len(script_lines), MAX_IMAGES)
        num_images = st.slider(
            "Select number of images to generate:",
            min_value=1,
            max_value=max_images,
            value=min(5, max_images)
        )
        
        # Reference Image Upload
        st.header("3. Reference Images (Optional)")
        reference_images = []
        num_refs = st.number_input("Number of reference images (0-5):", 0, 5, 0)
        
        for i in range(num_refs):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                ref_image = st.file_uploader(f"Reference Image {i+1}", type=['png', 'jpg', 'jpeg'], key=f"ref_{i}")
            with col2:
                description = st.text_input(f"Description {i+1}", key=f"desc_{i}")
            with col3:
                tag = st.text_input(f"Tag {i+1}", key=f"tag_{i}")
            
            if ref_image and description and tag:
                reference_images.append({
                    "image": ref_image,
                    "description": description,
                    "tag": tag
                })
        
        # Generate Images
        if st.button("Generate Images"):
            if not LEONARDO_API_KEY:
                st.error("Please set your Leonardo API key in the .env file")
                return
            
            progress_bar = st.progress(0)
            generated_images = []
            
            for i in range(num_images):
                prompt = generate_cinematic_prompt(script_lines[i], i+1, reference_images)
                st.write(f"Generating image {i+1} with prompt: {prompt}")
                
                # Create generation
                generation = create_generation(LEONARDO_API_KEY, prompt)
                if not generation or "sdGenerationJob" not in generation:
                    st.error(f"Failed to create generation for scene {i+1}")
                    continue
                
                generation_id = generation["sdGenerationJob"]["generationId"]
                
                # Wait for generation to complete and get images
                images = get_generation_images(LEONARDO_API_KEY, generation_id)
                if not images:
                    st.error(f"Failed to get images for scene {i+1}")
                    continue
                
                image_url = images["generations_by_pk"]["generated_images"][0]["url"]
                generated_images.append({
                    "url": image_url,
                    "prompt": prompt
                })
                
                progress_bar.progress((i + 1) / num_images)
            
            if generated_images:
                # Display Results
                st.header("Generated Images")
                for i, img_data in enumerate(generated_images):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.image(img_data["url"], caption=f"Scene {i+1}")
                    with col2:
                        st.download_button(
                            f"Download Scene {i+1}",
                            img_data["url"],
                            file_name=f"scene_{i+1}.png"
                        )
                
                # Download All
                if st.button("Download All Images"):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        zip_path = os.path.join(tmpdir, "generated_images.zip")
                        with zipfile.ZipFile(zip_path, 'w') as zipf:
                            for i, img_data in enumerate(generated_images):
                                response = requests.get(img_data["url"])
                                img_path = os.path.join(tmpdir, f"scene_{i+1}.png")
                                with open(img_path, 'wb') as f:
                                    f.write(response.content)
                                zipf.write(img_path, f"scene_{i+1}.png")
                        
                        with open(zip_path, 'rb') as f:
                            st.download_button(
                                "Download ZIP",
                                f,
                                file_name="generated_images.zip",
                                mime="application/zip"
                            )

if __name__ == "__main__":
    main() 