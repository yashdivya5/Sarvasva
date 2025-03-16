import os
import asyncio
import time
import base64
import random
import requests
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


# Replace with your bot & OpenAI API keys
TOKEN = "8125759209:AAEWipIexhQeHmIFykw1J3xpG6ujZPRhIyM"
GEMINI_API_KEY = "AIzaSyC9i96-x18BGKIeV7HOHKn-piu4e5R9IUs"
SARVAM_API_KEY = "d60e2e18-3b3c-492d-8faf-7f9db7c55201"

# Configure Gemini API
try:
    genai.configure(api_key=GEMINI_API_KEY)
    # Verify API key by creating a model
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Failed to initialize Gemini client: {e}")
    model = None


safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]

# Generation configuration
generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 512
}

# Supported Languages
LANGUAGES = {
    "English": "en-IN", "हिंदी": "hi-IN", "বাংলा": "bn-IN", "ગુજરાતી": "gu-IN",
    "ಕನ್ನಡ": "kn-IN", "മലയാളം": "ml-IN", "मराठी": "mr-IN", "ଓଡିଆ": "od-IN",
    "ਪੰਜਾਬੀ": "pa-IN", "தமிழ்": "ta-IN", "తెలుగు": "te-IN"
}

# Store user data
user_data = {}

# Loan questions translated into all languages
LOAN_QUESTIONS = {
    "en-IN": [
        "How many dependents do you have?",
        "For how many months do you need the loan?",
        "Are you a graduate or non-graduate?",
        "What is your annual income?",
        "What is your residential asset value?",
        "What is your commercial asset value?",
        "Are you self-employed?",
        "What is the loan amount you require?",
        "What type of loan are you looking for?",
        "What is the value of your luxury assets?",
        "What is your total bank asset value?"
    ],
    "hi-IN": [
        "आपके कितने आश्रित हैं?",
        "आप कितने महीनों के लिए ऋण चाहते हैं?",
        "क्या आप स्नातक हैं या गैर-स्नातक?",
        "आपकी वार्षिक आय कितनी है?",
        "आपकी आवासीय संपत्ति का मूल्य क्या है?",
        "आपकी व्यावसायिक संपत्ति का मूल्य क्या है?",
        "क्या आप स्वरोजगार करते हैं?",
        "आपको कितनी ऋण राशि चाहिए?",
        "आप किस प्रकार का ऋण चाहते हैं?",
        "आपकी लक्ज़री संपत्ति का मूल्य कितना है?",
        "आपकी कुल बैंक संपत्ति का मूल्य कितना है?"
    ],
    "bn-IN": [
        "আপনার কতজন নির্ভরশীল রয়েছে?",
        "আপনাকে কত মাসের জন্য ঋণের প্রয়োজন?",
        "আপনি স্নাতক না অস্নাতক?",
        "আপনার বার্ষিক আয় কত?",
        "আপনার আবাসিক সম্পত্তির মূল্য কত?",
        "আপনার বাণিজ্যিক সম্পত্তির মূল্য কত?",
        "আপনি কি স্বনিযুক্ত?",
        "আপনার কত ঋণের পরিমাণ প্রয়োজন?",
        "আপনি কী ধরনের ঋণ খুঁজছেন?",
        "আপনার বিলাসবহুল সম্পত্তির মূল্য কত?",
        "আপনার মোট ব্যাংক সম্পদের মূল্য কত?"
    ],
    "gu-IN": [
        "તમારા કેટલા આધારિત સભ્યો છે?",
        "તમારે કેટલા મહિના માટે લોનની જરૂર છે?",
        "શું તમે સ્નાતક છો કે નહીં?",
        "તમારી વાર્ષિક આવક કેટલી છે?",
        "તમારા રહેવાસી સંપત્તિનું મૂલ્ય શું છે?",
        "તમારા વ્યાપારી સંપત્તિનું મૂલ્ય શું છે?",
        "શું તમે સ્વરોજગાર છો?",
        "તમારે કેટલી લોનની રકમની જરૂર છે?",
        "તમે કયા પ્રકારની લોન માટે જોઈ રહ્યા છો?",
        "તમારા વૈભવી સંપત્તિનું મૂલ્ય શું છે?",
        "તમારા કુલ બેંક સંપત્તિનું મૂલ્ય શું છે?"
    ],
    "kn-IN": [
        "ನೀವು ಎಷ್ಟು ಅವಲಂಬಿತರನ್ನು ಹೊಂದಿದ್ದಾರೆ?",
        "ನೀವು ಎಷ್ಟು ತಿಂಗಳು ಸಾಲ ಬೇಕು?",
        "ನೀವು ಪದವೀಧರರಾಗಿದ್ದೀರಾ ಅಥವಾ ಪದವೀಧರರಲ್ಲ?",
        "ನಿಮ್ಮ ವಾರ್ಷಿಕ ಆದಾಯ ಎಷ್ಟು?",
        "ನಿಮ್ಮ ನಿವಾಸ ಆಸ್ತಿಯ ಮೌಲ್ಯ ಎಷ್ಟು?",
        "ನಿಮ್ಮ ವಾಣಿಜ್ಯ ಆಸ್ತಿಯ ಮೌಲ್ಯ ಎಷ್ಟು?",
        "ನೀವು ಸ್ವಾವಲಂಬಿಯಾಗಿ ಉದ್ಯೋಗದಲ್ಲಿದ್ದೀರಾ?",
        "ನೀವು ಎಷ್ಟು ಸಾಲದ ಮೊತ್ತವನ್ನು ಅಗತ್ಯವಿದೆ?",
        "ನೀವು ಯಾವ ರೀತಿಯ ಸಾಲವನ್ನು ಹುಡುಕುತ್ತಿದ್ದೀರಾ?",
        "ನಿಮ್ಮ ಐಶಾರಾಮಿ ಆಸ್ತಿಯ ಮೌಲ್ಯ ಎಷ್ಟು?",
        "ನಿಮ್ಮ ಒಟ್ಟು ಬ್ಯಾಂಕ್ ಆಸ್ತಿಯ ಮೌಲ್ಯ ಎಷ್ಟು?"
    ],
    "ml-IN": [
        "നിങ്ങൾക്ക് എത്ര ആശ്രിതർ ഉണ്ട്?",
        "നിങ്ങൾക്ക് എത്ര മാസത്തേക്ക് ലോൺ വേണം?",
        "നിങ്ങൾ ഒരു ബിരുദധാരിയാണോ അല്ലാത്തതാണോ?",
        "നിങ്ങളുടെ വാർഷിക വരുമാനം എത്ര?",
        "നിങ്ങളുടെ താമസ ആസ്തിയുടെ മൂല്യം എത്ര?",
        "നിങ്ങളുടെ വ്യാപാര ആസ്തിയുടെ മൂല്യം എത്ര?",
        "നിങ്ങൾ സ്വയംതൊഴിലാളിയാണോ?",
        "നിങ്ങൾക്ക് എത്രത്തോളം ലോൺ ആവശ്യമാണ്?",
        "നിങ്ങൾ ഏത് തരത്തിലുള്ള ലോൺ തിരയുകയാണോ?",
        "നിങ്ങളുടെ ആഡംബര ആസ്തിയുടെ മൂല്യം എത്ര?",
        "നിങ്ങളുടെ മൊത്തം ബാങ്ക് ആസ്തിയുടെ മൂല്യം എത്ര?"
    ],
    "mr-IN": [
        "तुमच्याकडे किती अवलंबित आहेत?",
        "तुम्हाला किती महिन्यांसाठी कर्ज पाहिजे?",
        "तुम्ही पदवीधर आहात का?",
        "तुमचे वार्षिक उत्पन्न किती आहे?",
        "तुमच्या निवासी मालमत्तेचे मूल्य किती आहे?",
        "तुमच्या व्यावसायिक मालमत्तेचे मूल्य किती आहे?",
        "तुम्ही स्वयंरोजगार आहात का?",
        "तुम्हाला किती कर्ज रक्कम हवी आहे?",
        "तुम्ही कोणत्या प्रकारचे कर्ज शोधत आहात?",
        "तुमच्या लक्झरी मालमत्तेचे मूल्य किती आहे?",
        "तुमच्या एकूण बँक मालमत्तेचे मूल्य किती आहे?"
    ],
    "od-IN": [
        "ଆପଣଙ୍କ ନିର୍ଭରକ କିଏ?",
        "ଆପଣ କେତେ ମାସ ପାଇଁ ଋଣ ଚାହୁଁଛନ୍ତି?",
        "ଆପଣ ସ୍ନାତକ କି ନୁହଁ?",
        "ଆପଣଙ୍କ ବାର୍ଷିକ ଆୟ କେତେ?",
        "ଆପଣଙ୍କ ନିବାସ ସମ୍ପତ୍ତିର ମୂଲ୍ୟ କେତେ?",
        "ଆପଣଙ୍କ ବାଣିଜ୍ୟିକ ସମ୍ପତ୍ତିର ମୂଲ୍ୟ କେତେ?",
        "ଆପଣ କି ସ୍ୱୟଂରୋଜଗାରୀ?",
        "ଆପଣଙ୍କୁ କେତେ ରିଣ ରାଶି ଦରକାର?",
        "ଆପଣ କେଉଁ ପ୍ରକାରର ଋଣ ଦେଖୁଛନ୍ତି?",
        "ଆପଣଙ୍କ ବିଲାସୀ ସମ୍ପତ୍ତିର ମୂଲ୍ୟ କେତେ?",
        "ଆପଣଙ୍କ ମୋଟ ବ୍ୟାଙ୍କ ସମ୍ପତ୍ତିର ମୂଲ୍ୟ କେତେ?"
    ],
    "pa-IN": [
        "ਤੁਹਾਡੇ ਉੱਤੇ ਕਿੰਨੇ ਨਿਰਭਰ ਕਰਦੇ ਹਨ?",
        "ਤੁਸੀਂ ਕਿੰਨੇ ਮਹੀਨਿਆਂ ਲਈ ਕਰਜ਼ਾ ਚਾਹੁੰਦੇ ਹੋ?",
        "ਕੀ ਤੁਸੀਂ ਗ੍ਰੈਜੁਏਟ ਹੋ ਜਾਂ ਨਾ-ਗ੍ਰੈਜੁਏਟ?",
        "ਤੁਹਾਡੀ ਸਾਲਾਨਾ ਆਮਦਨ ਕਿੰਨੀ ਹੈ?",
        "ਤੁਹਾਡੀ ਰਿਹਾਇਸ਼ੀ ਸੰਪਤੀ ਦੀ ਕੀਮਤ ਕੀ ਹੈ?",
        "ਤੁਹਾਡੀ ਵਪਾਰਕ ਸੰਪਤੀ ਦੀ ਕੀਮਤ ਕੀ ਹੈ?",
        "ਕੀ ਤੁਸੀਂ ਸਵੈ-ਰੋਜ਼ਗਾਰ ਹੋ?",
        "ਤੁਹਾਨੂੰ ਕਿੰਨੀ ਕਰਜ਼ਾ ਰਕਮ ਦੀ ਲੋੜ ਹੈ?",
        "ਤੁਸੀਂ ਕਿਸ ਤਰ੍ਹਾਂ ਦਾ ਕਰਜ਼ਾ ਲੈਣਾ ਚਾਹੁੰਦੇ ਹੋ?",
        "ਤੁਹਾਡੀ ਵਿਲਾਸੀ ਸੰਪਤੀ ਦੀ ਕੀਮਤ ਕੀ ਹੈ?",
        "ਤੁਹਾਡੀ ਕੁੱਲ ਬੈਂਕ ਸੰਪਤੀ ਦੀ ਕੀਮਤ ਕੀ ਹੈ?"
    ],
    "ta-IN": [
        "உங்களிடம் எத்தனை phụவலங்கர்கள் உள்ளனர்?",
        "நீங்கள் எத்தனை மாதத்திற்கு கடன் தேவை?",
        "நீங்கள் ஒரு பட்டதாரியா அல்லது பட்டமில்லாதவரா?",
        "உங்கள் ஆண்டு வருமானம் என்ன?",
        "உங்கள் குடியிருப்பு சொத்தின் மதிப்பு என்ன?",
        "உங்கள் வணிக சொத்தின் மதிப்பு என்ன?",
        "நீங்கள் சுய தொழிலாளியா?",
        "நீங்கள் எவ்வளவு கடன் தேவை?",
        "நீங்கள் எந்த வகையான கடன் தேடுகிறீர்கள்?",
        "உங்கள் ஆடம்பர சொத்தின் மதிப்பு என்ன?",
        "உங்கள் மொத்த வங்கி சொத்தின் மதிப்பு என்ன?"
    ]
}

def get_language_code(language_name):
    """
    Convert language name to language code
    """
    language_map = {
        "English": "en-IN", 
        "हिंदी": "hi-IN", 
        "বাংলা": "bn-IN", 
        "ગુજરાતી": "gu-IN",
        "ಕನ್ನಡ": "kn-IN", 
        "മലയാളം": "ml-IN", 
        "मराठी": "mr-IN", 
        "ଓଡିଆ": "od-IN",
        "ਪੰਜਾਬੀ": "pa-IN", 
        "தமிழ்": "ta-IN", 
        "తెలుగు": "te-IN"
    }
    return language_map.get(language_name, "en-IN")

def text_to_speech(text, target_language, speaker=None):
    """
    Convert text to speech using Sarvam AI Text-to-Speech API
    
    :param text: Text to convert to speech
    :param target_language: Language code (e.g., 'hi-IN', 'bn-IN')
    :param speaker: Optional speaker name
    :return: Base64 encoded audio or None if conversion fails
    """
    url = "https://api.sarvam.ai/text-to-speech"
    
    # Default speaker mapping based on language
    default_speakers = {
        "hi-IN": "meera",
        "bn-IN": "pavithra",
        "gu-IN": "maitreyi",
        "kn-IN": "arvind",
        "ml-IN": "amol",
        "mr-IN": "amartya",
        "od-IN": "diya",
        "pa-IN": "neel",
        "ta-IN": "misha",
        "te-IN": "vian",
        "en-IN": "arjun"
    }
    
    # Choose speaker
    chosen_speaker = speaker or default_speakers.get(target_language, "meera")
    
    # Truncate text to 500 characters
    text = text[:500]
    
    payload = {
        "inputs": [text],
        "target_language_code": target_language,
        "speaker": chosen_speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.0,
        "speech_sample_rate": 22050,
        "enable_preprocessing": True,
        "model": "bulbul:v1"
    }
    
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        response_data = response.json()
        
        # Check if audio is available
        if response_data.get("audios"):
            return response_data["audios"][0]
        else:
            print("No audio generated")
            return None
    
    except Exception as e:
        print(f"Text-to-Speech conversion error: {e}")
        return None
    
# Add this function to your existing code
def speech_to_text_translate(audio_file_path, language=None):
    """
    Convert speech to text using Sarvam AI Speech-to-Text Translation API
    
    :param audio_file_path: Path to the audio file
    :param language: Optional language code (if known)
    :return: Dictionary with transcription details
    """
    url = "https://api.sarvam.ai/speech-to-text-translate"
    
    try:
        # Open the audio file
        with open(audio_file_path, 'rb') as audio_file:
            # Prepare multipart form data
            files = {
                'file': (os.path.basename(audio_file_path), audio_file, 'audio/wav')
            }
            
            # Prepare payload
            payload = {
                'model': 'saaras:v2',
                'with_diarization': 'false'
            }
            
            # Optional: Add language if specified
            if language:
                payload['language_code'] = language
            
            # Headers
            headers = {
                'api-subscription-key': SARVAM_API_KEY
            }
            
            # Make the API request
            response = requests.post(url, files=files, data=payload, headers=headers)
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                return {
                    'transcript': result.get('transcript', ''),
                    'language_code': result.get('language_code', '')
                }
            else:
                print(f"Speech-to-Text API error: {response.text}")
                return None
    
    except Exception as e:
        print(f"Speech-to-Text conversion error: {e}")
        return None
    
async def generate_full_audio(text, user_language, user_id):
    """
    Generate full audio with comprehensive text-to-speech conversion
    
    :param text: Full text to convert to speech
    :param user_language: Language code
    :param user_id: User identifier
    :return: Path to combined audio file
    """
    try:
        # Chunk the text for TTS with a larger chunk size
        text_chunks = chunk_text_for_tts(text, max_chunk_length=800)
        
        # Prepare audio paths
        audio_paths = []
        
        # Generate audio for each chunk with a small delay
        for index, chunk in enumerate(text_chunks):
            try:
                print(f"Processing chunk {index + 1}: {chunk[:100]}...")  # Debug print
                
                # Convert chunk to speech
                audio_base64 = text_to_speech(chunk, user_language)
                
                if audio_base64:
                    # Save audio file
                    audio_path = await save_audio(audio_base64, f"{user_id}_full_eligibility_part{index}.wav")
                    
                    if audio_path:
                        audio_paths.append(audio_path)
                
                # Small delay to prevent potential API rate limiting
                await asyncio.sleep(0.5)
            
            except Exception as chunk_error:
                print(f"Error processing chunk {index}: {chunk_error}")
        
        # Combine audio files
        if len(audio_paths) > 1:
            combined_audio_path = combine_audio_files(
                audio_paths, 
                f"{user_id}_full_eligibility_combined.wav"
            )
            return combined_audio_path
        elif audio_paths:
            # Return single audio file if only one chunk
            return audio_paths[0]
        
        # Fallback: Generate audio for entire text if chunking fails
        fallback_audio_base64 = text_to_speech(text, user_language)
        if fallback_audio_base64:
            fallback_audio_path = await save_audio(fallback_audio_base64, f"{user_id}_full_eligibility_fallback.wav")
            return fallback_audio_path
        
        return None
    
    except Exception as e:
        print(f"Full audio generation error: {e}")
        return None
    
async def save_audio(audio_base64, filename):
    """
    Save base64 encoded audio to a file
    
    :param audio_base64: Base64 encoded audio
    :param filename: Output filename
    """
    try:
        # Ensure audio directory exists
        os.makedirs("audio", exist_ok=True)
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Save audio file
        full_path = os.path.join("audio", filename)
        with open(full_path, "wb") as audio_file:
            audio_file.write(audio_bytes)
        
        return full_path
    except Exception as e:
        print(f"Error saving audio: {e}")
        return None

def chunk_text(text, max_length=1000):
    """
    Split text into chunks of at most max_length characters 
    while preserving word boundaries.
    """
    chunks = []
    
    while len(text) > max_length:
        # Find the last space within the max length
        split_index = text.rfind(" ", 0, max_length)
        
        # If no space found, force split at max_length
        if split_index == -1:
            split_index = max_length
        
        # Add chunk and remove leading/trailing spaces
        chunks.append(text[:split_index].strip())
        text = text[split_index:].lstrip()
    
    # Add the last chunk if any text remains
    if text:
        chunks.append(text.strip())
    
    return chunks


def translate_text(input_text, source_language, target_language):
    """
    Translate text using Sarvam Translation API with comprehensive chunk handling
    """
    url = "https://api.sarvam.ai/translate"

    # Validate input parameters
    valid_languages = ["en-IN", "hi-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN"]
    if source_language not in valid_languages or target_language not in valid_languages:
        print(f"Invalid language code. Source: {source_language}, Target: {target_language}")
        return input_text

    # Chunk the text
    text_chunks = chunk_text(input_text)
    translated_chunks = []

    for chunk in text_chunks:
        payload = {
            "input": chunk,
            "source_language_code": source_language,
            "target_language_code": target_language,
            "speaker_gender": "Female",
            "mode": "formal",
            "enable_preprocessing": False,
            "output_script": None,
            "numerals_format": "international"
        }

        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            response_data = response.json()
            
            # Validate response
            if "translated_text" in response_data:
                translated_chunks.append(response_data["translated_text"])
            else:
                print(f"Unexpected translation response: {response_data}")
                translated_chunks.append(chunk)
        
        except requests.exceptions.RequestException as req_err:
            print(f"Request error during translation: {req_err}")
            translated_chunks.append(chunk)
        except ValueError as val_err:
            print(f"JSON parsing error: {val_err}")
            translated_chunks.append(chunk)
        except Exception as e:
            print(f"Unexpected error during translation: {e}")
            translated_chunks.append(chunk)

    # Combine translated chunks
    final_translation = " ".join(translated_chunks)
    
    return final_translation
    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to select a language."""
    keyboard = [[lang] for lang in LANGUAGES.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Please select your preferred language:", reply_markup=reply_markup)

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the selected language and start loan questions."""
    chosen_language = update.message.text
    if chosen_language in LANGUAGES:
        user_id = update.message.from_user.id
        # Get the language code directly
        language_code = LANGUAGES[chosen_language]
        user_data[user_id] = {
            "language": language_code,  # Store language code
            "original_language_name": chosen_language,  # Store original language name
            "responses": {},
            "state": "language_selected"
        }
        
        # Translate welcome message
        welcome_message = f"Language set to {chosen_language}. Let's check your loan eligibility!"
        if language_code != "en-IN":
            try:
                # Translate welcome message
                localized_welcome = translate_text(
                    welcome_message, 
                    source_language="en-IN", 
                    target_language=language_code
                )
                
                # Convert welcome message to speech
                welcome_audio_base64 = text_to_speech(localized_welcome, language_code)
                
                # Save and send audio
                if welcome_audio_base64:
                    welcome_audio_path = await save_audio(welcome_audio_base64, f"{user_id}_welcome.wav")
                    if welcome_audio_path:
                        with open(welcome_audio_path, 'rb') as audio_file:
                            await update.message.reply_voice(audio_file)
                
                # Send text message
                await update.message.reply_text(localized_welcome)
            
            except Exception as translation_error:
                print(f"Translation error for welcome message: {translation_error}")
                await update.message.reply_text(welcome_message)
        else:
            await update.message.reply_text(welcome_message)
        
        await ask_loan_questions(update, context)
    else:
        await update.message.reply_text("Invalid selection. Please choose a valid language.")

async def ask_loan_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask loan eligibility questions dynamically with speech support."""
    user_id = update.message.from_user.id
    user_language = user_data[user_id]["language"]
    questions = LOAN_QUESTIONS.get(user_language, LOAN_QUESTIONS["en-IN"])
    random.shuffle(questions)  
    user_data[user_id]["questions"] = questions
    user_data[user_id]["current_question"] = 0
    user_data[user_id]["state"] = "asking_questions"
    
    # Prepare to store audio paths
    user_data[user_id]["question_audio_paths"] = []

    # Convert all questions to audio
    for index, question in enumerate(questions):
        try:
            # Convert question to speech
            audio_base64 = text_to_speech(question, user_language)
            
            if audio_base64:
                # Save audio file
                audio_path = await save_audio(audio_base64, f"{user_id}_question_{index}.wav")
                
                if audio_path:
                    # Store audio path
                    user_data[user_id]["question_audio_paths"].append(audio_path)
        
        except Exception as e:
            print(f"Error in question speech conversion for question {index}: {e}")

    # Get the first question
    first_question = questions[0]
    
    # Send first question's audio if available
    if user_data[user_id]["question_audio_paths"]:
        first_audio_path = user_data[user_id]["question_audio_paths"][0]
        try:
            with open(first_audio_path, 'rb') as audio_file:
                await update.message.reply_voice(audio_file)
        except Exception as e:
            print(f"Error sending first question audio: {e}")
    
    # Send text question and instructions for audio response
    await update.message.reply_text(f"{first_question}\n\nPlease respond with an audio message.")

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle both text and audio responses."""
    user_id = update.message.from_user.id
    
    # Check if user is in a valid state for responding
    if user_id not in user_data or user_data[user_id].get("state") != "asking_questions":
        await update.message.reply_text("Please start the process by sending /start")
        return

    question_list = user_data[user_id]["questions"]
    responses = user_data[user_id]["responses"]
    current_question_index = user_data[user_id]["current_question"]
    current_question = question_list[current_question_index]

    # Handle audio response
    if update.message.voice:
        try:
            # Download the voice file
            voice_file = await update.message.voice.get_file()
            voice_path = f"audio/{user_id}_response_{current_question_index}.wav"
            
            # Ensure audio directory exists
            os.makedirs("audio", exist_ok=True)
            
            # Download the file
            await voice_file.download_to_drive(voice_path)
            
            # Convert speech to text
            stt_result = speech_to_text_translate(voice_path)
            
            if stt_result and stt_result['transcript']:
                # Store the transcribed response
                responses[current_question] = stt_result['transcript']
                
                # Optionally, log the detected language
                detected_language = stt_result.get('language_code', 'Unknown')
                print(f"Detected language: {detected_language}")
            else:
                await update.message.reply_text("Sorry, I couldn't understand your audio response. Please try again.")
                return
        
        except Exception as e:
            print(f"Error processing audio response: {e}")
            await update.message.reply_text("An error occurred while processing your audio response.")
            return
    
    # Handle text response (fallback)
    elif update.message.text:
        responses[current_question] = update.message.text
    
    # Ask the next question if available
    if current_question_index + 1 < len(question_list):
        # Move to next question
        user_data[user_id]["current_question"] += 1
        next_question_index = user_data[user_id]["current_question"]
        next_question = question_list[next_question_index]

        # Send next question's audio if available
        question_audio_paths = user_data[user_id].get("question_audio_paths", [])
        if question_audio_paths and next_question_index < len(question_audio_paths):
            try:
                with open(question_audio_paths[next_question_index], 'rb') as audio_file:
                    await update.message.reply_voice(audio_file)
            except Exception as e:
                print(f"Error sending next question audio: {e}")
        
        # Send text of next question
        await update.message.reply_text(f"{next_question}\n\nPlease respond with an audio message.")
    else:
        # Proceed to loan eligibility check
        await update.message.reply_text("Thanks! Checking loan eligibility now...")
        await check_loan_eligibility(update, context)


def combine_audio_files(audio_paths, output_path):
    """
    Combine multiple audio files into a single file using advanced method
    
    :param audio_paths: List of paths to audio files
    :param output_path: Path to save combined audio file
    :return: Path to combined audio file or None if combination fails
    """
    try:
        # Ensure we have multiple audio files to combine
        if len(audio_paths) <= 1:
            return audio_paths[0] if audio_paths else None

        try:
            # Try using pydub if available
            from pydub import AudioSegment
            
            # Combine audio files
            combined = AudioSegment.empty()
            for path in audio_paths:
                audio = AudioSegment.from_wav(path)
                # Add a small silence between chunks if needed
                combined += audio + AudioSegment.silent(duration=500)  # 500ms silence
            
            # Export combined audio
            combined.export(output_path, format="wav")
            return output_path
        
        except ImportError:
            # Fallback to simple file concatenation
            with open(output_path, 'wb') as outfile:
                for audio_path in audio_paths:
                    with open(audio_path, 'rb') as infile:
                        outfile.write(infile.read())
            return output_path
    
    except Exception as e:
        print(f"Audio combination error: {e}")
        return None
    
async def check_loan_eligibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Evaluate loan eligibility with multi-chunk speech support and combined audio."""
    try:
        # Verify model is available
        if model is None:
            await update.message.reply_text("AI model is not initialized. Please contact support.")
            return

        # Get user responses and language
        user_id = update.message.from_user.id
        responses = user_data[user_id]["responses"]
        user_language = user_data[user_id]["language"]

        # Prepare detailed prompt
        prompt = f"""
        Act as a professional Indian bank loan advisor. Analyze the following financial details 
        and provide a comprehensive loan eligibility assessment with specific, structured advice:

        Financial Profile:
        {chr(10).join(f"- {key}: {value}" for key, value in responses.items())}

        Provide a response with the following structure:
        A. Loan Eligibility Assessment
        - Clearly state if the loan is approved or not
        - Provide specific reasons for the decision

        B. If Loan is Eligible:
        1. Detailed Bank Loan Acquisition Steps (Indian Banking Context)
        - Step-by-step process to apply for the loan
        - Recommended bank procedures
        - Expected timeline

        2. Required Documentation
        - Comprehensive list of documents needed
        - Specific Indian banking document requirements
        - Tips for document preparation

        3. Professional Recommendations
        - Tailored financial advice
        - Suggestions for loan optimization
        - Long-term financial planning insights

        C. If Loan is Not Eligible:
        1. Specific Reasons for Rejection
        - Detailed explanation of why the loan was not approved

        2. Actionable Improvement Strategies
        - Concrete steps to improve loan eligibility
        - Financial health improvement suggestions
        - Specific recommendations for increasing creditworthiness

        3. Alternative Financial Guidance
        - Alternative financing options
        - Steps to strengthen financial profile
        - Professional advice for future loan applications

        Ensure the advice is:
        - Practical and actionable
        - Specific to Indian banking context
        - Professionally and empathetically worded
        - Use plain text format without any special formatting
        """

        # Generate response using Gemini
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 1024
        }

        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]

        # Generate response in English
        response = model.generate_content(
            prompt, 
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        # Translate to user's language
        if user_language != "en-IN":
            try:
                translated_text = translate_text(
                    response.text, 
                    source_language="en-IN",  
                    target_language=user_language
                )
            except Exception as translation_error:
                print(f"Translation error: {translation_error}")
                translated_text = response.text
        else:
            translated_text = response.text

        # Generate full audio with improved method
        try:
            # Generate full audio file
            full_audio_path = await generate_full_audio(
                translated_text, 
                user_language, 
                user_id
            )
            
            # Send audio if generated successfully
            if full_audio_path:
                with open(full_audio_path, 'rb') as audio_file:
                    await update.message.reply_voice(audio_file)
            
            # Send text response
            await update.message.reply_text(translated_text)
        
        except Exception as audio_error:
            print(f"Audio generation error: {audio_error}")
            await update.message.reply_text(translated_text)
        
        # Store last response and reset state
        user_data[user_id]['last_response'] = translated_text
        user_data[user_id]["state"] = "completed"

    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

def chunk_text_for_tts(text, max_chunk_length=500):
    """
    Split text into chunks suitable for Text-to-Speech API
    
    :param text: Full text to be chunked
    :param max_chunk_length: Maximum length of each chunk
    :return: List of text chunks
    """
    # If text is short enough, return as single chunk
    if len(text) <= max_chunk_length:
        return [text]
    
    chunks = []
    current_chunk = []
    current_chunk_length = 0
    
    # Split text into sentences
    sentences = text.split('. ')
    
    for sentence in sentences:
        # Calculate potential chunk length
        sentence_length = len(sentence) + 2  # +2 for '. '
        
        # If adding this sentence would exceed max length, start a new chunk
        if current_chunk_length + sentence_length > max_chunk_length:
            # Join and add current chunk
            chunks.append('. '.join(current_chunk) + '.')
            current_chunk = []
            current_chunk_length = 0
        
        current_chunk.append(sentence)
        current_chunk_length += sentence_length
    
    # Add any remaining sentences
    if current_chunk:
        chunks.append('. '.join(current_chunk) + '.')
    
    # Debugging: Print chunk information
    print(f"Total chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i + 1} (Length: {len(chunk)})")
    
    return chunks

async def text_to_speech_multiple(text, target_language):
    """
    Convert long text to speech by breaking it into chunks
    
    :param text: Full text to convert
    :param target_language: Language code for speech
    :return: List of audio base64 encodings
    """
    # Chunk the text for TTS
    text_chunks = chunk_text_for_tts(text)
    
    # Prepare audio chunks
    audio_chunks = []
    
    for chunk in text_chunks:
        try:
            # Convert each chunk to speech
            audio_base64 = text_to_speech(chunk, target_language)
            
            if audio_base64:
                audio_chunks.append(audio_base64)
        except Exception as e:
            print(f"Error converting chunk to speech: {e}")
    
    return audio_chunks

async def regenerate_speech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Regenerate speech for the last response"""
    user_id = update.message.from_user.id
    
    # Check if we have a previous response
    if user_id in user_data and 'last_response' in user_data[user_id]:
        last_response = user_data[user_id]['last_response']
        user_language = user_data[user_id]['language']
        
        try:
            audio_base64 = text_to_speech(last_response, user_language)
            
            if audio_base64:
                # Save audio file
                audio_path = await save_audio(audio_base64, f"{user_id}_regenerated.wav")
                
                if audio_path:
                    # Send audio file
                    with open(audio_path, 'rb') as audio_file:
                        await update.message.reply_voice(audio_file)
            
            await update.message.reply_text("Speech regenerated!")
        
        except Exception as e:
            await update.message.reply_text(f"Could not regenerate speech: {str(e)}")
    else:
        await update.message.reply_text("No previous response found.")

def main():
    """Run the bot."""
    try:
        # ... (existing validation code)

        # Create the Application
        app = Application.builder().token(TOKEN).build()
        
        # Add handlers with correct priority
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(
            filters.Regex(f"^({'|'.join(LANGUAGES.keys())})$"), 
            language_selection
        ))
        app.add_handler(MessageHandler(
            filters.VOICE | filters.TEXT, 
            handle_response
        ))
        app.add_handler(CommandHandler("speak", regenerate_speech))
        
        print("Bot is running...")
        app.run_polling(
            drop_pending_updates=True
        )
    
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()