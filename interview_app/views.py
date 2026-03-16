import os
import fitz  # PyMuPDF
import google.generativeai as genai
import markdown
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from dotenv import load_dotenv
import random
import pyttsx3
from django.http import JsonResponse
import json
import time
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

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

@login_required
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

def ai_questions(request):
    if request.method == 'POST':
        # Check if we are submitting the configuration or an answer
        if 'skill' in request.POST:
            # Step 1: Generate the Question
            skill = request.POST.get('skill')
            role = request.POST.get('role')
            difficulty = request.POST.get('difficulty')
            
            prompt = f"Generate one technical interview question for a {role} role focusing on {skill} at a {difficulty} level. Return only the question text."
            response = model.generate_content(prompt)
            
            return render(request, 'interview_app/quiz.html', {
                'question': response.text,
                'skill': skill,
                'role': role,
                'difficulty': difficulty
            })
            
        elif 'user_answer' in request.POST:
            # Step 2: Grade the Answer
            question = request.POST.get('question')
            answer = request.POST.get('user_answer')
            
            grade_prompt = f"""
            Question: {question}
            Candidate Answer: {answer}
            
            Role as a Senior Technical Interviewer. 
            1. Provide a Score out of 10.
            2. Provide a 'Model Answer'.
            3. Give 'Feedback' on how to improve.
            Format the output in clean HTML or Markdown.
            """
            response = model.generate_content(grade_prompt)
            formatted_feedback = markdown.markdown(response.text, extensions=['nl2br', 'extra'])
            
            return render(request, 'interview_app/quiz_result.html', {
                'feedback': formatted_feedback
            })

    # Initial landing state (GET request)
    return render(request, 'interview_app/quiz_setup.html')

def voice_interview_start(request):
    if request.method == 'POST' and request.FILES.get('resume'):
        # 1. Extract Resume Text (Reuse your existing function)
        resume_file = request.FILES['resume']
        fs = FileSystemStorage()
        filename = fs.save(resume_file.name, resume_file)
        path = fs.path(filename)
        resume_content = extract_text_from_pdf(path)
        
        # 2. Store in session so the AI "remembers" it during the call
        request.session['interview_context'] = resume_content
        request.session['total_questions'] = int(request.POST.get('q_count', 7))
        request.session['current_q_index'] = 1
        
        os.remove(path)
        return render(request, 'interview_app/voice_session.html')
    
    return render(request, 'interview_app/voice_setup.html')

def voice_setup(request):
    """Step 1: Upload resume and configure question count."""
    return render(request, 'interview_app/voice_setup.html')

def voice_interview(request):
    """Step 2: The actual voice session."""
    if request.method == 'POST' and request.FILES.get('resume'):
        resume_file = request.FILES['resume']
        q_count = request.POST.get('q_count', 7)
        
        # Extract text using your existing helper
        fs = FileSystemStorage()
        filename = fs.save(resume_file.name, resume_file)
        path = fs.path(filename)
        resume_text = extract_text_from_pdf(path)
        
        # Clean up file after extraction
        if os.path.exists(path):
            os.remove(path)

        # Pass resume context and count to the session template
        return render(request, 'interview_app/voice_session.html', {
            'resume_context': resume_text,
            'total_questions': q_count,
            'role': 'Candidate'
        })
    
    return render(request, 'interview_app/voice_setup.html')

def voice_setup(request):
    return render(request, 'interview_app/voice_setup.html')

def voice_interview(request):
    if request.method == 'POST' and request.FILES.get('resume'):
        resume_file = request.FILES['resume']
        q_count = request.POST.get('q_count', 7)
        
        fs = FileSystemStorage()
        filename = fs.save(resume_file.name, resume_file)
        path = fs.path(filename)
        resume_text = extract_text_from_pdf(path)
        
        if os.path.exists(path):
            os.remove(path)

        return render(request, 'interview_app/voice_session.html', {
            'resume_context': resume_text,
            'total_questions': q_count,
        })
    return render(request, 'interview_app/voice_setup.html')

def voice_chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_speech = data.get('user_speech', "")
            resume_context = data.get('resume_context', "")

            prompt = f"""
            You are a Senior Technical Interviewer. 
            Resume: {resume_context}
            Candidate said: "{user_speech}"
            Action: Ask a short follow-up question (1-2 sentences).
            """
            
            # Generate response
            response = model.generate_content(prompt)
            return JsonResponse({'ai_question': response.text})

        except Exception as e:
            # Check if it's a quota/rate limit error
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg:
                print("Quota exceeded. Waiting 7 seconds...")
                return JsonResponse({
                    'ai_question': "I'm thinking deeply about your last point. Give me just a few seconds to process that."
                })
            
            print(f"Server Error: {e}")
            return JsonResponse({'error': 'Server Busy'}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now login.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'interview_app/register.html', {'form': form})