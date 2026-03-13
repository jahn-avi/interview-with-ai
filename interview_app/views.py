import os
import fitz  # PyMuPDF
import google.generativeai as genai
import markdown
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from dotenv import load_dotenv
import random

# 1. Load Environment Variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 2. SMART MODEL PICKER
def get_best_model():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priorities = [
            'models/gemini-1.5-flash-latest', 
            'models/gemini-1.5-flash', 
            'models/gemini-1.0-pro'
        ]
        for priority in priorities:
            if priority in available_models:
                return priority
        return available_models[0] if available_models else 'models/gemini-1.5-flash'
    except Exception as e:
        print(f"Model lookup failed: {e}")
        return 'models/gemini-1.5-flash'

SELECTED_MODEL = get_best_model()
model = genai.GenerativeModel(SELECTED_MODEL)

# --- VIEW FUNCTIONS ---

def index(request):
    return render(request, 'interview_app/index.html')

def about(request):
    return render(request, 'interview_app/about.html')

def session(request):
    return render(request, 'interview_app/session.html', {'role': 'Data Science Candidate'})

def dashboard(request):
    titles = [
        "Tech Enthusiast",
        "Future CEO",
        "Innovation Leader",
        "Data Wizard",
        "Code Ninja",
        "Problem Solver",
        "Visionary Developer"
    ]
    random_title = random.choice(titles)
    
    return render(request, 'interview_app/dashboard.html', {
        'user_title': random_title
    })

def extract_text_from_pdf(pdf_path):
    """Safely extracts text from the uploaded PDF."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"PDF Extraction Error: {e}")
    return text

def resume_analysis(request):
    """Handles Resume Upload and AI Analysis with clean formatting."""
    if request.method == 'POST' and request.FILES.get('resume'):
        resume_file = request.FILES['resume']
        
        fs = FileSystemStorage()
        filename = fs.save(resume_file.name, resume_file)
        uploaded_file_path = fs.path(filename)

        try:
            # 1. Extract the text
            resume_text = extract_text_from_pdf(uploaded_file_path)

            if not resume_text.strip():
                return render(request, 'interview_app/resume_analysis.html', {
                    'error': 'The PDF seems empty or is an image. Please upload a text-based PDF.'
                })

            # 2. Ask the AI for a structured review with strict formatting rules
            prompt = f"""
            You are a Senior Technical Recruiter. Analyze this resume for a Data Science/CSE role.
            
            CRITICAL FORMATTING RULES:
            - Use ### for section headings.
            - You MUST put a blank line between every paragraph and heading.
            - Use bullet points (*) for lists.
            - Provide a clear 'Resume Score: X/100' at the top.

            Provide:
            ### Resume Score: [Score]/100
            ### Top Skills Detected
            ### Missing Keywords or Sections
            ### 3 Specific Improvements
            
            Resume Text:
            {resume_text}
            """
            
            response = model.generate_content(prompt)
            
            # 3. Convert Markdown to HTML for the frontend
            # 'nl2br' ensures single newlines become breaks, 'extra' handles complex markdown
            formatted_feedback = markdown.markdown(
                response.text, 
                extensions=['nl2br', 'extra', 'sane_lists']
            )
            
            return render(request, 'interview_app/resume_analysis.html', {
                'feedback': formatted_feedback,
                'status': 'Complete'
            })

        except Exception as e:
            return render(request, 'interview_app/resume_analysis.html', {
                'error': f'AI Error: {str(e)}'
            })
        finally:
            if os.path.exists(uploaded_file_path):
                os.remove(uploaded_file_path)

    return render(request, 'interview_app/resume_analysis.html')