from django.urls import path
from django.contrib.auth import views as auth
from onboarding import views
urlpatterns = [path('', views.home), path('login/', auth.LoginView.as_view(template_name='login.html')), path('logout/', auth.LogoutView.as_view()), path('api/projects/', views.projects), path('api/projects/<int:pk>/', views.project), path('api/projects/<int:pk>/chat/', views.chat), path('api/projects/<int:pk>/review/', views.review), path('api/projects/<int:pk>/approve/', views.approve)]
urlpatterns += [path('api/documents/', views.documents), path('api/ai-status/', views.ai_status)]
