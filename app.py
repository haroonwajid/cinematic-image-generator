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
import base64

# Load environment variables
load_dotenv()

# Constants
LEONARDO_API_KEY = os.getenv('LEONARDO_API_KEY')
LEONARDO_API_URL = "https://cloud.leonardo.ai/api/rest/v1"
MAX_IMAGES = 252
MAX_RETRIES = 30
RETRY_DELAY = 2

# Leonardo Model IDs
MODELS = {
    "Alchemy": "ac614f96-1082-45bf-be9d-757f2d31c174",
    "PhotoReal": "291be633-cb24-434f-898f-e662799936ad"
}

def upload_reference_image(api_key, image_file, description):
    """Upload a reference image to Leonardo."""
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    # First, get the upload URL using POST
    upload_url_response = requests.post(
        f"{LEONARDO_API_URL}/init-image",
        headers=headers
    )
    
    if upload_url_response.status_code != 200:
        st.error(f"Error getting upload URL: {upload_url_response.text}")
        return None
    
    upload_data = upload_url_response.json()
    
    # Prepare the file for upload
    files = {
        'file': (image_file.name, image_file, 'image/jpeg')
    }
    
    # Upload the file
    upload_response = requests.post(
        upload_data["uploadInitImage"]["fields"]["url"],
        files=files,
        data=upload_data["uploadInitImage"]["fields"]
    )
    
    if upload_response.status_code != 204:
        st.error(f"Error uploading file: {upload_response.text}")
        return None
    
    # Create the init image
    create_payload = {
        "name": description,
        "uploadId": upload_data["uploadInitImage"]["uploadId"]
    }
    
    create_response = requests.post(
        f"{LEONARDO_API_URL}/init-image",
        headers=headers,
        json=create_payload
    )
    
    if create_response.status_code != 200:
        st.error(f"Error creating init image: {create_response.text}")
        return None
    
    return create_response.json()

def parse_script(script):
    """Parse script into scenes, where each scene consists of a script line and its description."""
    scenes = []
    lines = script.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line:
            description = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].strip() else ""
            scenes.append({
                "script": line,
                "description": description
            })
            i += 2 if description else 1
        else:
            i += 1
    return scenes

def generate_cinematic_prompt(scene, scene_num, reference_images=None):
    """Generate a cinematic prompt from a scene with reference image integration."""
    base_prompt = f"Scene {scene_num}: {scene['script']}"
    if scene['description']:
        base_prompt += f". {scene['description']}"
    
    # Add cinematic enhancements
    base_prompt += ". Professional cinematography, 8k resolution, dramatic composition, cinematic lighting, atmospheric depth, high-end production quality."
    
    if reference_images:
        ref_prompts = []
        for ref in reference_images:
            if ref['tag'] == 'character':
                ref_prompts.append(f"Maintain exact character likeness from reference image '{ref['description']}', including facial features, expression, and style.")
            elif ref['tag'] == 'style':
                ref_prompts.append(f"Match the visual style, lighting, and atmosphere from reference image '{ref['description']}'.")
            elif ref['tag'] == 'location':
                ref_prompts.append(f"Use the environment and setting details from reference image '{ref['description']}'.")
            else:
                ref_prompts.append(f"Incorporate elements from reference image '{ref['description']}' for {ref['tag']} consistency.")
        base_prompt += " " + " ".join(ref_prompts)
    
    return base_prompt

def create_generation(api_key, prompt, model_id, reference_image_ids=None):
    """Create a generation using Leonardo API with advanced features."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    # Start with basic payload
    payload = {
        "prompt": prompt,
        "modelId": model_id,
        "width": 1024,
        "height": 576,
        "num_images": 1
    }
    
    # Add reference images if provided
    if reference_image_ids:
        payload["init_image_ids"] = reference_image_ids
    
    # Add model-specific features
    if model_id == MODELS["PhotoReal"]:
        payload["photoReal"] = True
    else:
        payload["alchemy"] = True
        payload["promptMagic"] = True
    
    # Add negative prompt
    payload["negative_prompt"] = "blurry, low quality, distorted, deformed, ugly, bad anatomy, disfigured, poorly drawn face, mutation, mutated, extra limb, missing limb, floating limbs, disconnected limbs, malformed hands, blur, out of focus, long neck, long body, distorted proportions, bad proportions, gross proportions, text, error, missing fingers, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
    
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
        
        if "generations_by_pk" in data:
            generation = data["generations_by_pk"]
            if generation.get("status") == "COMPLETE":
                if generation.get("generated_images") and len(generation["generated_images"]) > 0:
                    return data
            elif generation.get("status") == "FAILED":
                st.error(f"Generation failed: {generation.get('error', 'Unknown error')}")
                return None
        
        time.sleep(RETRY_DELAY)
    
    st.error("Generation timed out after maximum retries")
    return None

def main():
    st.title("🎬 Cinematic Image Generator")
    
    # Script Input
    st.header("1. Script Input")
    script = st.text_area(
        "Enter your visual script (one line per scene, followed by its description):",
        height=300,
        help="Enter your script with each scene on a new line, followed by its description on the next line"
    )
    
    if script:
        scenes = parse_script(script)
        st.info(f"Total possible scenes: {len(scenes)}")
        
        # Image Count Selection
        st.header("2. Image Count Selection")
        max_images = min(len(scenes), MAX_IMAGES)
        num_images = st.slider(
            "Select number of images to generate:",
            min_value=1,
            max_value=max_images,
            value=min(5, max_images)
        )
        
        # Model Selection
        st.header("3. Model Selection")
        selected_model = st.selectbox(
            "Choose the model:",
            list(MODELS.keys()),
            help="Alchemy: Best for cinematic scenes, PhotoReal: Best for realistic images"
        )
        
        # Reference Image Upload
        st.header("4. Reference Images (Optional)")
        reference_images = []
        num_refs = st.number_input("Number of reference images (0-5):", 0, 5, 0)
        
        uploaded_refs = []
        for i in range(num_refs):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                ref_image = st.file_uploader(f"Reference Image {i+1}", type=['png', 'jpg', 'jpeg'], key=f"ref_{i}")
            with col2:
                description = st.text_input(f"Description {i+1}", key=f"desc_{i}")
            with col3:
                tag = st.selectbox(
                    f"Tag {i+1}",
                    ["character", "style", "location", "other"],
                    key=f"tag_{i}"
                )
            
            if ref_image and description:
                if ref_image not in [r["image"] for r in uploaded_refs]:
                    # Reset file pointer to beginning
                    ref_image.seek(0)
                    # Upload reference image to Leonardo
                    ref_data = upload_reference_image(LEONARDO_API_KEY, ref_image, description)
                    if ref_data and "uploadInitImage" in ref_data:
                        uploaded_refs.append({
                            "image": ref_image,
                            "description": description,
                            "tag": tag,
                            "id": ref_data["uploadInitImage"]["id"]
                        })
                        reference_images.append({
                            "image": ref_image,
                            "description": description,
                            "tag": tag
                        })
                        st.success(f"Successfully uploaded reference image: {description}")
                    else:
                        st.error(f"Failed to upload reference image: {description}")
        
        # Generate Images
        if st.button("Generate Images"):
            if not LEONARDO_API_KEY:
                st.error("Please set your Leonardo API key in the .env file")
                return
            
            progress_bar = st.progress(0)
            generated_images = []
            
            # Get reference image IDs
            ref_ids = [ref["id"] for ref in uploaded_refs] if uploaded_refs else None
            
            for i in range(num_images):
                prompt = generate_cinematic_prompt(scenes[i], i+1, reference_images)
                st.write(f"Generating image {i+1} with prompt: {prompt}")
                
                # Create generation
                generation = create_generation(
                    LEONARDO_API_KEY,
                    prompt,
                    MODELS[selected_model],
                    ref_ids
                )
                
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
                        st.image(img_data["url"], caption=f"Scene {i+1}: {scenes[i]['script']}")
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