from django.contrib import admin
from django.urls import path
from interview_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='home'),
    path('session/', views.session, name='session'),
    path('about/', views.about, name='about'), # New path
    path('dashboard/', views.dashboard, name='dashboard'),
    path('resume-analysis/', views.resume_analysis, name='resume_analysis'),
    path('ai-questions/', views.ai_questions, name='ai_questions'),
]