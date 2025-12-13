import os
# Robust import for google.genai
genai = None
try:
    # Try new SDK first (google.genai)
    from google import genai
except ImportError:
    try:
        # Try direct module import
        import google.genai as genai
    except ImportError:
        try:
            # Try old SDK
            import google.generativeai as genai
        except ImportError:
            print("CRITICAL: Could not import google.genai or google.generativeai")
            genai = None
import requests
try:
    from azure.identity import ClientSecretCredential
except ImportError:
    ClientSecretCredential = None
    print("WARNING: azure.identity not found. OneDrive features will be disabled.")

# Confidence threshold for retrieval results
# Reads from environment variable, defaults to 0.6
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

def init_gemini_client():
    """Initialize and return Gemini client"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment variables.")
        return None
    return genai.Client(api_key=api_key)

def get_onedrive_token():
    """Get access token for Microsoft Graph API"""
    if ClientSecretCredential is None:
        print("Azure library missing")
        return None

    try:
        tenant_id = os.getenv('MS_TENANT_ID')
        client_id = os.getenv('MS_CLIENT_ID')
        client_secret = os.getenv('MS_CLIENT_SECRET')
        
        if not all([tenant_id, client_id, client_secret]):
            print("Missing OneDrive credentials")
            return None
            
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        token = credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    except Exception as e:
        print(f"Error getting OneDrive token: {e}")
        return None

def get_onedrive_download_link(filename, chatbot_type=None):
    """
    Generate a 1-hour valid download link for a file in OneDrive.
    Returns a temporary Microsoft Graph downloadUrl.
    Iterates through known folders to find the file, prioritized by chatbot_type if provided.
    """

    drive_id = os.getenv('ONEDRIVE_DRIVE_ID')
    
    # Define folder paths
    sop_folder = os.getenv('SOP_FOLDER_PATH')
    general_folder = os.getenv('GENERAL_FOLDER_PATH', os.getenv('OTHERS_FOLDER_PATH', 'AI/Others'))
    insw_folder = os.getenv('INSW_FOLDER_PATH')
    
    # List of folders to check
    folders_to_check = []
    
    # 1. Prioritize based on chatbot_type
    if chatbot_type == 'SOP' and sop_folder:
        folders_to_check.append(sop_folder)
    elif chatbot_type == 'OTHERS' and general_folder:
        folders_to_check.append(general_folder)
    elif chatbot_type == 'INSW' and insw_folder:
        folders_to_check.append(insw_folder)
        
    # 2. Add remaining folders as fallback (in case file is mis-categorized)
    if sop_folder and sop_folder not in folders_to_check:
        folders_to_check.append(sop_folder)
    if general_folder and general_folder not in folders_to_check:
        folders_to_check.append(general_folder)
    if insw_folder and insw_folder not in folders_to_check:
        folders_to_check.append(insw_folder)

    import logging
    logger = logging.getLogger("app_logger")

    if not drive_id or not folders_to_check:
        logger.error("Missing OneDrive drive_id or folder paths configuration")
        return None

    token = get_onedrive_token()
    if not token:
        logger.error("Failed to obtain OneDrive token")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    graph_base_url = "https://graph.microsoft.com/v1.0"
    
    import urllib.parse

    # Iterate through folders and return the first valid link found
    for folder_path in folders_to_check:
        try:
            # logger.info(f"Checking for file '{filename}' in '{folder_path}'...")
            
            # Format: /drives/{drive_id}/root:/{folder}/{filename}?select=id,name,@microsoft.graph.downloadUrl
            encoded_filename = urllib.parse.quote(filename)
            encoded_folder = urllib.parse.quote(folder_path)
            
            direct_url = (
                f"{graph_base_url}/drives/{drive_id}/root:/{encoded_folder}/{encoded_filename}"
                f"?select=id,name,@microsoft.graph.downloadUrl"
            )
            
            response = requests.get(direct_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                download_url = data.get('@microsoft.graph.downloadUrl')
                
                if download_url:
                    logger.info(f"Download URL FOUND for '{filename}' in '{folder_path}'")
                    logger.info(f"Generated Direct URL: {download_url[:100]}...")
                    return download_url
            elif response.status_code == 404:
                # Debug: List files in this folder to see if we missed it due to encoding/casing
                logger.info(f"DEBUG: File not found in '{folder_path}'. Listing contents to find match...")
                try:
                    # Just list names to debug
                    list_url = f"{graph_base_url}/drives/{drive_id}/root:/{encoded_folder}:/children?select=name"
                    list_res = requests.get(list_url, headers=headers)
                    if list_res.status_code == 200:
                        files = [f['name'] for f in list_res.json().get('value', [])]
                        logger.info(f"DEBUG: Contents of '{folder_path}': {files}")
                except Exception as e:
                    logger.error(f"Failed to list folder: {e}")

                continue
            else:
                logger.warning(f"OneDrive error for '{filename}' in '{folder_path}': {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error checking folder '{folder_path}': {e}")
            continue

    logger.error(f"File not found in any configured folders: {filename}")
    return None
    
def create_embedding(client, text: str, model: str = "models/gemini-embedding-001"):
    """Create dense embedding using Gemini"""
    try:
        response = client.models.embed_content(
            model=model,
            contents=text
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return [0.0] * 3072

def create_sparse_vector(text: str):
    """Create sparse BM25-like vector from text"""
    words = text.lower().split()
    word_freq = {}
    for word in words:
        if len(word) > 2:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    indices = []
    values = []
    for word, freq in word_freq.items():
        idx = abs(hash(word)) % (10**6)
        indices.append(idx)
        values.append(freq)
    
    return {"indices": indices, "values": values}


def generate_chat_title(client, user_input, response_text):
    """Generate concise title using Gemini"""
    try:
        model = "gemini-2.5-flash"
        prompt = f"""Generate a very short, concise title (3-5 words) for this chat conversation.
User: {user_input[:200]}
Assistant: {response_text[:200]}

Title:"""
        
        response = client.models.generate_content(
            model=model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        title = response.text.strip().replace('"', '').replace("Title:", "").strip()
        return title if len(title) < 50 else title[:50]
    except Exception as e:
        print(f"Error generating title: {e}")
        return None

