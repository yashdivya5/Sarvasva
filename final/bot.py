import os
import random
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


# Replace with your bot & OpenAI API keys
TOKEN = "8125759209:AAEWipIexhQeHmIFykw1J3xpG6ujZPRhIyM"
GEMINI_API_KEY = "AIzaSyC9i96-x18BGKIeV7HOHKn-piu4e5R9IUs"

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
        user_data[user_id] = {
            "language": LANGUAGES[chosen_language], 
            "responses": {},
            "state": "language_selected"
        }
        await update.message.reply_text(f"Language set to {chosen_language}. Let's check your loan eligibility!")
        await ask_loan_questions(update, context)
    else:
        await update.message.reply_text("Invalid selection. Please choose a valid language.")

async def ask_loan_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask loan eligibility questions dynamically."""
    user_id = update.message.from_user.id
    user_language = user_data[user_id]["language"]
    questions = LOAN_QUESTIONS.get(user_language, LOAN_QUESTIONS["en-IN"])
    random.shuffle(questions)  
    user_data[user_id]["questions"] = questions
    user_data[user_id]["current_question"] = 0
    user_data[user_id]["state"] = "asking_questions"

    await update.message.reply_text(questions[0])

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store response and ask the next question."""
    user_id = update.message.from_user.id
    
    # Check if user is in a valid state for responding
    if user_id not in user_data or user_data[user_id].get("state") != "asking_questions":
        await update.message.reply_text("Please start the process by sending /start")
        return

    question_list = user_data[user_id]["questions"]
    responses = user_data[user_id]["responses"]
    current_question_index = user_data[user_id]["current_question"]

    # Store response in English (no language validation)
    responses[question_list[current_question_index]] = update.message.text

    # Ask the next question if available
    if current_question_index + 1 < len(question_list):
        user_data[user_id]["current_question"] += 1
        await update.message.reply_text(question_list[current_question_index + 1])
    else:
        await update.message.reply_text("Thanks! Checking loan eligibility now...")
        await check_loan_eligibility(update, context)

async def check_loan_eligibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Evaluate loan eligibility using Gemini API with structured response."""
    try:
        # Verify model is available
        if model is None:
            await update.message.reply_text("AI model is not initialized. Please contact support.")
            return

        # Get user responses and language
        user_id = update.message.from_user.id
        responses = user_data[user_id]["responses"]
        user_language = user_data[user_id]["language"]

        # Prepare detailed prompt in English
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
        """

        # Generate response
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
        translation_prompt = f"""
        Translate the following text to {get_language_name(user_language)} while maintaining the professional tone and specific details:

        {response.text}
        """

        # Translate the response to user's language
        translated_response = model.generate_content(
            translation_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        # Send the eligibility result
        await update.message.reply_text(translated_response.text)
        
        # Reset user state
        user_data[user_id]["state"] = "completed"

    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

def get_language_name(language_code):
    """Get the full language name for a given language code."""
    language_names = {
        "en-IN": "English",
        "hi-IN": "Hindi",
        "bn-IN": "Bengali",
        "gu-IN": "Gujarati",
        "kn-IN": "Kannada",
        "ml-IN": "Malayalam",
        "mr-IN": "Marathi",
        "od-IN": "Odia",
        "pa-IN": "Punjabi",
        "ta-IN": "Tamil",
        "te-IN": "Telugu"
    }
    return language_names.get(language_code, "English")

def main():
    """Run the bot."""
    try:
        # Validate tokens
        if not TOKEN:
            print("Error: Telegram Bot Token is missing!")
            return
        
        if not GEMINI_API_KEY:
            print("Error: Gemini API Key is missing!")
            return

        # Verify Gemini model is initialized
        if model is None:
            print("Error: Failed to initialize Gemini model!")
            return

        # Create the Application
        app = Application.builder().token(TOKEN).build()
        
        # Add handlers with correct priority
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(
            filters.Regex(f"^({'|'.join(LANGUAGES.keys())})$"), 
            language_selection
        ))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_response
        ))
        
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