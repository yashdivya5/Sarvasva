from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import requests
import json
import base64
from io import BytesIO
from dotenv import load_dotenv
import logging
from groq import Groq
import re

# Load environment variables
load_dotenv()
lang = "en-IN"  # Default language code

# Flask app setup
app = Flask(__name__, static_folder='static', template_folder="templates")  # Ensure 'templates' folder exists
CORS(app)  # Allow frontend to communicate with backend

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Upload folder for audio files
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the upload folder exists

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max file size

SARVAM_API_KEY = os.getenv('SARVAM_API_KEY')

# Ensure API key is set
if not SARVAM_API_KEY:
    raise ValueError("SARVAM_API_KEY is missing. Please set it in the environment variables.")

# Allowed audio file formats
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a', 'webm'}

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    """ Serve the frontend HTML file """
    return render_template("index.html")



@app.route('/set-language', methods=['POST'])
def set_language():
    """Set the default language for the application."""
    global lang

    data = request.json
    new_lang = data.get("language_code", "").strip()

    if not new_lang:
        return jsonify({"error": "Language code is required"}), 400

    print(f"Language earlier: {lang}")
    lang = new_lang
    print(f"Language set to: {lang}")
    return jsonify({"message": f"Language changed to {lang}"}), 200


# Load API key from environment variables
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Define a session dictionary to track conversation state
conversation_sessions = {}

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chatbot responses using Groq's LLaMA model."""
    try:
        data = request.json
        user_message = data.get("message", "").strip()
        image_url = data.get("image_url", False)
        role = data.get("role", "user").strip()
        session_id = data.get("session_id", "default")
        reset = data.get("reset", False)

        if not user_message and not image_url:
            return jsonify({"error": "Message or image URL cannot be empty"}), 400

        # Initialize or reset session if needed
        if reset or session_id not in conversation_sessions:
            conversation_sessions[session_id] = {
                "messages": [],
                "question_count": 0,
                "asked_questions": set(),
                "prompt_added": False,
                "unknown_answers": set(),
                "assessment_provided": False
            }

        session = conversation_sessions[session_id]

        # Add system prompt only once per conversation
        if not session["prompt_added"]:
            system_prompt = '''You are a friendly, professional, and highly knowledgeable loan assistant. Your goal is to help users understand their loan eligibility in an interactive and engaging manner.

Start by warmly greeting the user and asking for the basic details like name and age etc and then ask required details step by step (e.g., type of loan, loan amount, tenure of loan, age, income, credit score, etc.) instead of requesting everything at once. Ask brief, clear questions to avoid overwhelming the user.

Mandatory Information to Collect:
1. Type of loan (e.g., home loan, personal loan, vehicle loan, etc.)
2. Loan amount the user wants to apply for
3. Loan tenure (how many years/months the loan is required for)

If the user is unsure about a particular detail (e.g., credit score, income), offer alternative methods to assess their eligibility. For example:
- If they don't know their credit score, ask if they have a history of timely bill payments or no defaults.
- If they are unsure about their exact income, ask about their average monthly expenses or job type to estimate their financial standing.

Analyze the following rules carefully:
1. Never ask the same question twice. Check the conversation history before asking a question.
2. If the user says they don't know an answer, note it and move on to a different question.
3. After 10-15 questions, provide a final eligibility assessment based on the information collected.
4. If critical information (e.g., loan type, amount, tenure) is missing, prioritize collecting these before offering an assessment.

For your final assessment:

If the user IS ELIGIBLE for a loan:
1. Congratulate them warmly.
2. Clearly list ALL required documents for loan approval, separated into:
   - Essential documents (must-have)
   - Supporting documents (nice-to-have)
3. Provide a clear step-by-step guide for the loan application process.
4. Offer additional assistance or tips on improving their loan terms if applicable.

If the user IS NOT ELIGIBLE for a loan:
1. Express this sensitively and empathetically.
2. Clearly explain which specific factors affected their eligibility (e.g., low income, insufficient credit score, etc.).
3. Provide actionable, step-by-step guidance to help them meet the eligibility criteria in the future.
4. Suggest a realistic timeframe for when they might consider reapplying.
5. Offer alternative financing options if available.

Throughout the conversation:
- Ask concise follow-up questions to gather missing details if needed.
- Provide helpful tips on improving financial standing, credit score management, or budgeting when relevant.
- Ensure your responses are concise yet informative, and maintain a conversational tone that makes users feel supported throughout the process.
- Don't forget send only plain text no stars or any other special characters in the text.'''

            session["messages"].append({"role": "system", "content": system_prompt})
            session["prompt_added"] = True

        # Process user message for "don't know" responses
        lower_message = user_message.lower()
        contains_dont_know = any(phrase in lower_message for phrase in ["don't know", "dont know", "not sure", "no idea", "unknown"])

        # Add user message to history
        session["messages"].append({"role": role, "content": user_message})

        # Extract question from previous bot message if exists
        if len(session["messages"]) >= 2 and session["messages"][-2]["role"] == "assistant":
            bot_last_msg = session["messages"][-2]["content"]
            if "?" in bot_last_msg:
                question = bot_last_msg.split("?")[0] + "?"
                session["asked_questions"].add(question.lower())
                if contains_dont_know:
                    session["unknown_answers"].add(question.lower())

        # Increment question count if this is a user response
        if role == "user":
            session["question_count"] += 1

        # Add special instruction if approaching question limit
        if 10 <= session["question_count"] < 15 and not session["assessment_provided"]:
            instruction = "You have asked several questions already. Start preparing for a final assessment soon based on the information gathered so far."
            session["messages"].append({"role": "system", "content": instruction})

        # Force prediction after 15 questions or if assessment hasn't been provided yet
        if (session["question_count"] >= 15 or lower_message.find("eligib") >= 0) and not session["assessment_provided"]:
            prediction_instruction = """Based on all information gathered so far, provide a final loan eligibility assessment. Ensure to consider type of loan, amount of loan, and loan tenure as mandatory factors.

If the user IS ELIGIBLE:
1. Congratulate them warmly.
2. Clearly list ALL required documents for loan approval, including primary and secondary documents.
3. Offer a step-by-step guide for the loan application process.
4. Provide assistance in improving loan terms if applicable.

If the user IS NOT ELIGIBLE:
1. Express the outcome empathetically.
2. Identify specific reasons affecting eligibility and suggest improvement steps.
3. Offer practical guidance to meet the eligibility criteria.
4. Provide alternative financing options if suitable.
5. Don't forget send only plain text no stars or any other special characters in the text."""

            session["messages"].append({"role": "system", "content": prediction_instruction})
            session["assessment_provided"] = True

        chat_completion = client.chat.completions.create(
            messages=session["messages"],
            model="llama-3.3-70b-versatile"
        )

        bot_response = chat_completion.choices[0].message.content

        session["messages"].append({"role": "assistant", "content": bot_response})

        return jsonify({
            "response": bot_response,
            "questions_asked": session["question_count"],
            "session_id": session_id,
            "assessment_provided": session["assessment_provided"]
        })

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# Translation API URL for Sarvam AI

TRANSLATE_API_URL = "https://api.sarvam.ai/translate"


@app.route('/translate', methods=['POST'])
def translate_text():
    """API to translate text using Sarvam AI"""
    try:
        # Get request data
        data = request.json

        input_text = data.get("input")
        source_lang = data.get("source_language_code", "").strip()
        target_lang = data.get("target_language_code", "").strip()
        speaker_gender = data.get("speaker_gender", "Female")
        mode = data.get("mode", "formal")
        output_script = data.get("output_script", "fully-native")
        numerals_format = data.get("numerals_format", "international")

        # Validate input
        if not input_text or not input_text.strip():
            return jsonify({"error": "Input text is required"}), 400

        # Split text into chunks if it exceeds the limit
        if len(input_text) > 1000:
            return translate_long_text(
                input_text, 
                source_lang, 
                target_lang, 
                speaker_gender, 
                mode, 
                output_script, 
                numerals_format
            )
        
        # For text within limits, use the regular translation function
        return perform_translation(
            input_text, 
            source_lang, 
            target_lang, 
            speaker_gender, 
            mode, 
            output_script, 
            numerals_format
        )

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


def translate_long_text(input_text, source_lang, target_lang, speaker_gender, mode, output_script, numerals_format):
    """Handle translation of texts longer than 1000 characters by splitting into chunks"""
    
    # Split text into sentences to preserve context better
    # This is a simple split - you might need a more sophisticated approach depending on your languages
    sentences = re.split(r'(?<=[.!?])\s+', input_text)
    
    chunks = []
    current_chunk = ""
    
    # Group sentences into chunks under 1000 characters
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < 950:  # Leave some buffer
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Translate each chunk
    translated_chunks = []
    for chunk in chunks:
        response = perform_translation(
            chunk, 
            source_lang, 
            target_lang, 
            speaker_gender, 
            mode, 
            output_script, 
            numerals_format
        )
        
        # Check if translation was successful
        response_data = response.get_json() if hasattr(response, 'get_json') else response
        if "translated_text" in response_data:
            translated_chunks.append(response_data["translated_text"])
        else:
            # If any chunk fails, return the error
            return response
    
    # Combine all translated chunks
    full_translation = " ".join(translated_chunks)
    
    return jsonify({
        "translated_text": full_translation,
        "chunked_translation": True,
        "chunks_count": len(chunks)
    })


def perform_translation(input_text, source_lang, target_lang, speaker_gender, mode, output_script, numerals_format):
    """Perform translation request to Sarvam AI API"""
    try:
        # Prepare request payload
        payload = {
            "input": input_text,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "speaker_gender": speaker_gender,
            "mode": mode,
            "model": "mayura:v1",
            "enable_preprocessing": False,
            "output_script": output_script,
            "numerals_format": numerals_format
        }

        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY
        }

        # Send request to Sarvam AI API
        response = requests.post(TRANSLATE_API_URL, json=payload, headers=headers)
        response_data = response.json()
        
        print(f"Sarvam API Response for chunk of {len(input_text)} chars:", response_data)

        # Handle translation response
        if "translated_text" in response_data:
            return jsonify({
                "translated_text": response_data["translated_text"],
                "request_id": response_data.get("request_id", "unknown"),
                "source_language_code": response_data.get("source_language_code", "unknown")
            })

        # If translation failed, return actual error message
        return jsonify({
            "error": response_data.get("error", {}).get("message", "Translation failed"),
            "request_id": response_data.get("error", {}).get("request_id", "unknown"),
            "details": response_data
        }), 500

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "API request failed", "details": str(e)}), 500



# Speech-to-Text API URL

UPLOAD_FOLDER = "uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/speech-to-text', methods=['POST'])
def speech_to_text():
    """ Convert Speech to Text """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(audio_file.filename):
        return jsonify({'error': 'Invalid file format'}), 400

    # Secure the filename and save temporarily
    filename = secure_filename(audio_file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        # Save the file
        audio_file.save(file_path)

        # Ensure file is not empty
        if os.stat(file_path).st_size == 0:
            os.remove(file_path)
            return jsonify({'error': 'Uploaded file is empty'}), 400

        # Fetch the current language setting
        global lang
        current_lang = lang
        logging.info(f"Using language for STT: {current_lang}")

        print("current lang:", current_lang)  # Debugging

        # Call Speech-to-Text API
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'audio/wav')}
            data = {
                'model': 'saarika:v2',
                'language_code': current_lang,
                'with_timestamps': 'false',
                'with_diarization': 'false',
                'num_speakers': '1'
            }
            headers = {'api-subscription-key': SARVAM_API_KEY}
            response = requests.post('https://api.sarvam.ai/speech-to-text', headers=headers, data=data, files=files)
            response.raise_for_status()  # Raise error if request fails

            result = response.json()
            logging.info(f"Speech-to-text response: {result}")

        if 'transcript' not in result:
            return jsonify({'error': 'No transcript found in response'}), 500

        transcription_text = result['transcript']
        detected_language = result.get('language_code', current_lang)

        # **Optional: Translate to English if detected language is not English**
        # translated_text = None
        # if detected_language != "en-IN":
        #     payload = {
        #         "input": transcription_text,
        #         "source_language_code": detected_language,
        #         "target_language_code": "en-IN",
        #         "speaker_gender": "Female",
        #         "mode": "formal",
        #         "model": "mayura:v1"
        #     }
        #     headers = {
        #         "Content-Type": "application/json",
        #         "api-subscription-key": SARVAM_API_KEY
        #     }
            
        #     trans_response = requests.post(TRANSLATE_API_URL, json=payload, headers=headers)
        #     trans_data = trans_response.json()
            
        #     if "translated_text" in trans_data:
        #         translated_text = trans_data["translated_text"]
        #         logging.info(f"Translated response to English: {translated_text}")

        # Response data
        response_data = {
            'transcription': transcription_text,
            'language_code': detected_language
        }

        # Include translation if applicable
        # if translated_text:
        #     response_data['translated_text'] = translated_text

        return jsonify(response_data)

    except requests.exceptions.RequestException as e:
        logging.error(f"Speech-to-text API request failed: {str(e)}")
        return jsonify({'error': f'API request failed: {str(e)}'}), 500

    except Exception as e:
        logging.error(f"Unexpected error in STT: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)  # Clean up uploaded file after processing




TRANSLATE_API_URL = "https://api.sarvam.ai/translate"
# SARVAM_API_KEY should be loaded from your environment or config

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    """Convert Text to Speech using Sarvam AI."""
    try:
        data = request.json
        text_list = data.get("inputs", [])
        if not text_list or not isinstance(text_list, list) or not text_list[0].strip():
            return jsonify({"error": "Text is required"}), 400

        text = text_list[0]  # Extract first item from list
        
        # Debug prints
        print("data:", data)
        print("lang:", lang)
        
        # Get target language from request and set source_lang accordingly
        currLang = data.get("target_language_code")
        source_lang = data.get("source_language_code", lang)  # Default to lang if not specified

        LANGUAGE_CONFIG = {
            'en-IN': {"model": "bulbul:v1", "chunk_size": 500, "silence_bytes": 2000, "speaker": "meera"},
            'hi-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'ta-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'te-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'kn-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'ml-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'mr-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'bn-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'gu-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'pa-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"}
        }

        config = LANGUAGE_CONFIG.get(currLang, LANGUAGE_CONFIG['en-IN'])
        model = config["model"]
        chunk_size = config["chunk_size"]
        silence_bytes = config["silence_bytes"]
        speaker = config["speaker"]

        # Translate text if source and target languages differ
        if source_lang != currLang:
            translate_payload = {
                "input": text,
                "source_language_code": source_lang,
                "target_language_code": currLang,
                "speaker_gender": "Female",
                "mode": "formal",
                "model": "bulbul:v1"
            }
            translate_headers = {
                "Content-Type": "application/json",
                "api-subscription-key": SARVAM_API_KEY
            }
            try:
                translate_response = requests.post(TRANSLATE_API_URL, json=translate_payload, headers=translate_headers)
                if translate_response.status_code == 200:
                    translate_result = translate_response.json()
                    text = translate_result.get("translated_text", text)
                    print(f"Successfully translated to {currLang}")
                else:
                    print(f"Translation failed with status {translate_response.status_code}")
            except Exception as e:
                print(f"Translation error: {str(e)}")
                # Continue with original text if translation fails

        # Process text in chunks for TTS
        audio_data_combined = BytesIO()
        silence_chunk = b"\x00" * silence_bytes  # Buffer for smooth playback

        text_chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        for chunk in text_chunks:
            if not chunk.strip():
                continue

            request_body = {
                "inputs": [chunk],
                "target_language_code": currLang,
                "speaker": speaker,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.0,
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
                "model": model
            }
            if currLang == "en-IN":
                request_body["eng_interpolation_wt"] = 123

            headers = {
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json"
            }

            response = requests.post("https://api.sarvam.ai/text-to-speech", headers=headers, json=request_body)
            if response.status_code != 200:
                print(f"TTS API error: {response.text}")
                continue  # Proceed with next chunk

            result = response.json()
            if "audios" in result and result["audios"]:
                audio_data_combined.write(base64.b64decode(result["audios"][0]))
                audio_data_combined.write(silence_chunk)

        if audio_data_combined.getbuffer().nbytes <= silence_bytes:
            return jsonify({"error": "Failed to generate audio"}), 500

        audio_data_combined.seek(0)
        return send_file(audio_data_combined, mimetype="audio/mpeg")

    except requests.exceptions.RequestException as e:
        logging.error(f"TTS API request failed: {str(e)}")
        return jsonify({"error": "API request failed", "details": str(e)}), 500

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import requests
import json
import base64
from io import BytesIO
from dotenv import load_dotenv
import logging
from groq import Groq
import re

# Load environment variables
load_dotenv()
lang = "en-IN"  # Default language code

# Flask app setup
app = Flask(__name__, static_folder='static', template_folder="templates")  # Ensure 'templates' folder exists
CORS(app)  # Allow frontend to communicate with backend

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Upload folder for audio files
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the upload folder exists

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max file size

SARVAM_API_KEY = os.getenv('SARVAM_API_KEY')

# Ensure API key is set
if not SARVAM_API_KEY:
    raise ValueError("SARVAM_API_KEY is missing. Please set it in the environment variables.")

# Allowed audio file formats
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a', 'webm'}

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    """ Serve the frontend HTML file """
    return render_template("index.html")



@app.route('/set-language', methods=['POST'])
def set_language():
    """Set the default language for the application."""
    global lang

    data = request.json
    new_lang = data.get("language_code", "").strip()

    if not new_lang:
        return jsonify({"error": "Language code is required"}), 400

    print(f"Language earlier: {lang}")
    lang = new_lang
    print(f"Language set to: {lang}")
    return jsonify({"message": f"Language changed to {lang}"}), 200


# Load API key from environment variables
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Define a session dictionary to track conversation state
conversation_sessions = {}

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chatbot responses using Groq's LLaMA model."""
    try:
        data = request.json
        user_message = data.get("message", "").strip()
        image_url = data.get("image_url", False)
        role = data.get("role", "user").strip()
        session_id = data.get("session_id", "default")
        reset = data.get("reset", False)

        if not user_message and not image_url:
            return jsonify({"error": "Message or image URL cannot be empty"}), 400

        # Initialize or reset session if needed
        if reset or session_id not in conversation_sessions:
            conversation_sessions[session_id] = {
                "messages": [],
                "question_count": 0,
                "asked_questions": set(),
                "prompt_added": False,
                "unknown_answers": set(),
                "assessment_provided": False
            }

        session = conversation_sessions[session_id]

        # Add system prompt only once per conversation
        if not session["prompt_added"]:
            system_prompt = '''You are a friendly, professional, and highly knowledgeable loan assistant. Your goal is to help users understand their loan eligibility in an interactive and engaging manner.

Start by warmly greeting the user and asking for the basic details like name and age etc and then ask required details step by step (e.g., type of loan, loan amount, tenure of loan, age, income, credit score, etc.) instead of requesting everything at once. Ask brief, clear questions to avoid overwhelming the user.

Mandatory Information to Collect:
1. Type of loan (e.g., home loan, personal loan, vehicle loan, etc.)
2. Loan amount the user wants to apply for
3. Loan tenure (how many years/months the loan is required for)

If the user is unsure about a particular detail (e.g., credit score, income), offer alternative methods to assess their eligibility. For example:
- If they don't know their credit score, ask if they have a history of timely bill payments or no defaults.
- If they are unsure about their exact income, ask about their average monthly expenses or job type to estimate their financial standing.

Analyze the following rules carefully:
1. Never ask the same question twice. Check the conversation history before asking a question.
2. If the user says they don't know an answer, note it and move on to a different question.
3. After 10-15 questions, provide a final eligibility assessment based on the information collected.
4. If critical information (e.g., loan type, amount, tenure) is missing, prioritize collecting these before offering an assessment.

For your final assessment:

If the user IS ELIGIBLE for a loan:
1. Congratulate them warmly.
2. Clearly list ALL required documents for loan approval, separated into:
   - Essential documents (must-have)
   - Supporting documents (nice-to-have)
3. Provide a clear step-by-step guide for the loan application process.
4. Offer additional assistance or tips on improving their loan terms if applicable.

If the user IS NOT ELIGIBLE for a loan:
1. Express this sensitively and empathetically.
2. Clearly explain which specific factors affected their eligibility (e.g., low income, insufficient credit score, etc.).
3. Provide actionable, step-by-step guidance to help them meet the eligibility criteria in the future.
4. Suggest a realistic timeframe for when they might consider reapplying.
5. Offer alternative financing options if available.

Throughout the conversation:
- Ask concise follow-up questions to gather missing details if needed.
- Provide helpful tips on improving financial standing, credit score management, or budgeting when relevant.
- Ensure your responses are concise yet informative, and maintain a conversational tone that makes users feel supported throughout the process.
- Don't forget send only plain text no stars or any other special characters in the text.'''

            session["messages"].append({"role": "system", "content": system_prompt})
            session["prompt_added"] = True

        # Process user message for "don't know" responses
        lower_message = user_message.lower()
        contains_dont_know = any(phrase in lower_message for phrase in ["don't know", "dont know", "not sure", "no idea", "unknown"])

        # Add user message to history
        session["messages"].append({"role": role, "content": user_message})

        # Extract question from previous bot message if exists
        if len(session["messages"]) >= 2 and session["messages"][-2]["role"] == "assistant":
            bot_last_msg = session["messages"][-2]["content"]
            if "?" in bot_last_msg:
                question = bot_last_msg.split("?")[0] + "?"
                session["asked_questions"].add(question.lower())
                if contains_dont_know:
                    session["unknown_answers"].add(question.lower())

        # Increment question count if this is a user response
        if role == "user":
            session["question_count"] += 1

        # Add special instruction if approaching question limit
        if 10 <= session["question_count"] < 15 and not session["assessment_provided"]:
            instruction = "You have asked several questions already. Start preparing for a final assessment soon based on the information gathered so far."
            session["messages"].append({"role": "system", "content": instruction})

        # Force prediction after 15 questions or if assessment hasn't been provided yet
        if (session["question_count"] >= 15 or lower_message.find("eligib") >= 0) and not session["assessment_provided"]:
            prediction_instruction = """Based on all information gathered so far, provide a final loan eligibility assessment. Ensure to consider type of loan, amount of loan, and loan tenure as mandatory factors.

If the user IS ELIGIBLE:
1. Congratulate them warmly.
2. Clearly list ALL required documents for loan approval, including primary and secondary documents.
3. Offer a step-by-step guide for the loan application process.
4. Provide assistance in improving loan terms if applicable.

If the user IS NOT ELIGIBLE:
1. Express the outcome empathetically.
2. Identify specific reasons affecting eligibility and suggest improvement steps.
3. Offer practical guidance to meet the eligibility criteria.
4. Provide alternative financing options if suitable.
5. Don't forget send only plain text no stars or any other special characters in the text."""

            session["messages"].append({"role": "system", "content": prediction_instruction})
            session["assessment_provided"] = True

        chat_completion = client.chat.completions.create(
            messages=session["messages"],
            model="llama-3.3-70b-versatile"
        )

        bot_response = chat_completion.choices[0].message.content

        session["messages"].append({"role": "assistant", "content": bot_response})

        return jsonify({
            "response": bot_response,
            "questions_asked": session["question_count"],
            "session_id": session_id,
            "assessment_provided": session["assessment_provided"]
        })

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# Translation API URL for Sarvam AI

TRANSLATE_API_URL = "https://api.sarvam.ai/translate"


@app.route('/translate', methods=['POST'])
def translate_text():
    """API to translate text using Sarvam AI"""
    try:
        # Get request data
        data = request.json

        input_text = data.get("input")
        source_lang = data.get("source_language_code", "").strip()
        target_lang = data.get("target_language_code", "").strip()
        speaker_gender = data.get("speaker_gender", "Female")
        mode = data.get("mode", "formal")
        output_script = data.get("output_script", "fully-native")
        numerals_format = data.get("numerals_format", "international")

        # Validate input
        if not input_text or not input_text.strip():
            return jsonify({"error": "Input text is required"}), 400

        # Split text into chunks if it exceeds the limit
        if len(input_text) > 1000:
            return translate_long_text(
                input_text, 
                source_lang, 
                target_lang, 
                speaker_gender, 
                mode, 
                output_script, 
                numerals_format
            )
        
        # For text within limits, use the regular translation function
        return perform_translation(
            input_text, 
            source_lang, 
            target_lang, 
            speaker_gender, 
            mode, 
            output_script, 
            numerals_format
        )

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


def translate_long_text(input_text, source_lang, target_lang, speaker_gender, mode, output_script, numerals_format):
    """Handle translation of texts longer than 1000 characters by splitting into chunks"""
    
    # Split text into sentences to preserve context better
    # This is a simple split - you might need a more sophisticated approach depending on your languages
    sentences = re.split(r'(?<=[.!?])\s+', input_text)
    
    chunks = []
    current_chunk = ""
    
    # Group sentences into chunks under 1000 characters
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < 950:  # Leave some buffer
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Translate each chunk
    translated_chunks = []
    for chunk in chunks:
        response = perform_translation(
            chunk, 
            source_lang, 
            target_lang, 
            speaker_gender, 
            mode, 
            output_script, 
            numerals_format
        )
        
        # Check if translation was successful
        response_data = response.get_json() if hasattr(response, 'get_json') else response
        if "translated_text" in response_data:
            translated_chunks.append(response_data["translated_text"])
        else:
            # If any chunk fails, return the error
            return response
    
    # Combine all translated chunks
    full_translation = " ".join(translated_chunks)
    
    return jsonify({
        "translated_text": full_translation,
        "chunked_translation": True,
        "chunks_count": len(chunks)
    })


def perform_translation(input_text, source_lang, target_lang, speaker_gender, mode, output_script, numerals_format):
    """Perform translation request to Sarvam AI API"""
    try:
        # Prepare request payload
        payload = {
            "input": input_text,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "speaker_gender": speaker_gender,
            "mode": mode,
            "model": "mayura:v1",
            "enable_preprocessing": False,
            "output_script": output_script,
            "numerals_format": numerals_format
        }

        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY
        }

        # Send request to Sarvam AI API
        response = requests.post(TRANSLATE_API_URL, json=payload, headers=headers)
        response_data = response.json()
        
        print(f"Sarvam API Response for chunk of {len(input_text)} chars:", response_data)

        # Handle translation response
        if "translated_text" in response_data:
            return jsonify({
                "translated_text": response_data["translated_text"],
                "request_id": response_data.get("request_id", "unknown"),
                "source_language_code": response_data.get("source_language_code", "unknown")
            })

        # If translation failed, return actual error message
        return jsonify({
            "error": response_data.get("error", {}).get("message", "Translation failed"),
            "request_id": response_data.get("error", {}).get("request_id", "unknown"),
            "details": response_data
        }), 500

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "API request failed", "details": str(e)}), 500



# Speech-to-Text API URL

UPLOAD_FOLDER = "uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/speech-to-text', methods=['POST'])
def speech_to_text():
    """ Convert Speech to Text """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(audio_file.filename):
        return jsonify({'error': 'Invalid file format'}), 400

    # Secure the filename and save temporarily
    filename = secure_filename(audio_file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        # Save the file
        audio_file.save(file_path)

        # Ensure file is not empty
        if os.stat(file_path).st_size == 0:
            os.remove(file_path)
            return jsonify({'error': 'Uploaded file is empty'}), 400

        # Fetch the current language setting
        global lang
        current_lang = lang
        logging.info(f"Using language for STT: {current_lang}")

        print("current lang:", current_lang)  # Debugging

        # Call Speech-to-Text API
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'audio/wav')}
            data = {
                'model': 'saarika:v2',
                'language_code': current_lang,
                'with_timestamps': 'false',
                'with_diarization': 'false',
                'num_speakers': '1'
            }
            headers = {'api-subscription-key': SARVAM_API_KEY}
            response = requests.post('https://api.sarvam.ai/speech-to-text', headers=headers, data=data, files=files)
            response.raise_for_status()  # Raise error if request fails

            result = response.json()
            logging.info(f"Speech-to-text response: {result}")

        if 'transcript' not in result:
            return jsonify({'error': 'No transcript found in response'}), 500

        transcription_text = result['transcript']
        detected_language = result.get('language_code', current_lang)

        # **Optional: Translate to English if detected language is not English**
        # translated_text = None
        # if detected_language != "en-IN":
        #     payload = {
        #         "input": transcription_text,
        #         "source_language_code": detected_language,
        #         "target_language_code": "en-IN",
        #         "speaker_gender": "Female",
        #         "mode": "formal",
        #         "model": "mayura:v1"
        #     }
        #     headers = {
        #         "Content-Type": "application/json",
        #         "api-subscription-key": SARVAM_API_KEY
        #     }
            
        #     trans_response = requests.post(TRANSLATE_API_URL, json=payload, headers=headers)
        #     trans_data = trans_response.json()
            
        #     if "translated_text" in trans_data:
        #         translated_text = trans_data["translated_text"]
        #         logging.info(f"Translated response to English: {translated_text}")

        # Response data
        response_data = {
            'transcription': transcription_text,
            'language_code': detected_language
        }

        # Include translation if applicable
        # if translated_text:
        #     response_data['translated_text'] = translated_text

        return jsonify(response_data)

    except requests.exceptions.RequestException as e:
        logging.error(f"Speech-to-text API request failed: {str(e)}")
        return jsonify({'error': f'API request failed: {str(e)}'}), 500

    except Exception as e:
        logging.error(f"Unexpected error in STT: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)  # Clean up uploaded file after processing




TRANSLATE_API_URL = "https://api.sarvam.ai/translate"
# SARVAM_API_KEY should be loaded from your environment or config

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    """Convert Text to Speech using Sarvam AI."""
    try:
        data = request.json
        text_list = data.get("inputs", [])
        if not text_list or not isinstance(text_list, list) or not text_list[0].strip():
            return jsonify({"error": "Text is required"}), 400

        text = text_list[0]  # Extract first item from list
        
        # Debug prints
        print("data:", data)
        print("lang:", lang)
        
        # Get target language from request and set source_lang accordingly
        currLang = data.get("target_language_code")
        source_lang = data.get("source_language_code", lang)  # Default to lang if not specified

        LANGUAGE_CONFIG = {
            'en-IN': {"model": "bulbul:v1", "chunk_size": 500, "silence_bytes": 2000, "speaker": "meera"},
            'hi-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'ta-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'te-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'kn-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'ml-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'mr-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'bn-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'gu-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"},
            'pa-IN': {"model": "bulbul:v1", "chunk_size": 300, "silence_bytes": 3000, "speaker": "meera"}
        }

        config = LANGUAGE_CONFIG.get(currLang, LANGUAGE_CONFIG['en-IN'])
        model = config["model"]
        chunk_size = config["chunk_size"]
        silence_bytes = config["silence_bytes"]
        speaker = config["speaker"]

        # Translate text if source and target languages differ
        if source_lang != currLang:
            translate_payload = {
                "input": text,
                "source_language_code": source_lang,
                "target_language_code": currLang,
                "speaker_gender": "Female",
                "mode": "formal",
                "model": "bulbul:v1"
            }
            translate_headers = {
                "Content-Type": "application/json",
                "api-subscription-key": SARVAM_API_KEY
            }
            try:
                translate_response = requests.post(TRANSLATE_API_URL, json=translate_payload, headers=translate_headers)
                if translate_response.status_code == 200:
                    translate_result = translate_response.json()
                    text = translate_result.get("translated_text", text)
                    print(f"Successfully translated to {currLang}")
                else:
                    print(f"Translation failed with status {translate_response.status_code}")
            except Exception as e:
                print(f"Translation error: {str(e)}")
                # Continue with original text if translation fails

        # Process text in chunks for TTS
        audio_data_combined = BytesIO()
        silence_chunk = b"\x00" * silence_bytes  # Buffer for smooth playback

        text_chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        for chunk in text_chunks:
            if not chunk.strip():
                continue

            request_body = {
                "inputs": [chunk],
                "target_language_code": currLang,
                "speaker": speaker,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.0,
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
                "model": model
            }
            if currLang == "en-IN":
                request_body["eng_interpolation_wt"] = 123

            headers = {
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json"
            }

            response = requests.post("https://api.sarvam.ai/text-to-speech", headers=headers, json=request_body)
            if response.status_code != 200:
                print(f"TTS API error: {response.text}")
                continue  # Proceed with next chunk

            result = response.json()
            if "audios" in result and result["audios"]:
                audio_data_combined.write(base64.b64decode(result["audios"][0]))
                audio_data_combined.write(silence_chunk)

        if audio_data_combined.getbuffer().nbytes <= silence_bytes:
            return jsonify({"error": "Failed to generate audio"}), 500

        audio_data_combined.seek(0)
        return send_file(audio_data_combined, mimetype="audio/mpeg")

    except requests.exceptions.RequestException as e:
        logging.error(f"TTS API request failed: {str(e)}")
        return jsonify({"error": "API request failed", "details": str(e)}), 500

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(port=3000, debug=True)

